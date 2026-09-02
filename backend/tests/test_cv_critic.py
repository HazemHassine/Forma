import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
from cv_critic import critique_cv
from models import (
    AIProvider,
    CVCritiqueRequest,
    CritiqueCategory,
    CritiqueReport,
    CritiqueSeverity,
)
from routers import cv_critique


SAMPLE_REPORT = {
    "overall_score": 74,
    "verdict": "Clear technical background, but lacks measurable outcomes in key projects.",
    "summary": "The resume communicates experience well, but uses passive verbs and lacks business metrics.",
    "category_scores": [
        {"category": "impact", "label": "Impact & Metrics", "score": 60, "summary": "Too many bullets describe tasks rather than results."},
        {"category": "brevity", "label": "Brevity", "score": 85, "summary": "Good line lengths across sections."},
        {"category": "style", "label": "Tone & Style", "score": 75, "summary": "Minor buzzwords detected."},
        {"category": "structure", "label": "Structure", "score": 80, "summary": "Clean section hierarchy."},
        {"category": "ats", "label": "ATS Readiness", "score": 70, "summary": "Core technical skills present."},
    ],
    "strengths": [
        "Consistent chronology across engineering roles.",
        "Demonstrated technical depth in distributed systems.",
    ],
    "critical_count": 1,
    "warning_count": 1,
    "suggestion_count": 1,
    "issues": [
        {
            "id": "crit-1",
            "section": "work_experience",
            "location_label": "Senior Engineer — Bullet 1",
            "severity": "critical",
            "category": "impact",
            "problem": "Starts with passive duty phrasing instead of measurable outcome.",
            "why_it_hurts": "Hiring managers cannot assess the scale or business impact of your work.",
            "original_text": "Responsible for maintaining backend microservices.",
            "suggested_fix": "Maintained 14 Go microservices, sustaining 99.98% uptime across 2M daily requests.",
        },
        {
            "id": "warn-1",
            "section": "about_me",
            "location_label": "About Me",
            "severity": "warning",
            "category": "style",
            "problem": "Uses generic corporate cliche.",
            "why_it_hurts": "Dilutes technical credibility with filler language.",
            "original_text": "A passionate and results-driven software engineer.",
            "suggested_fix": "Software engineer with 6 years building distributed backend services and data pipelines.",
        },
        {
            "id": "sug-1",
            "section": "skills",
            "location_label": "Skills — Languages",
            "severity": "suggestion",
            "category": "ats",
            "problem": "Skills are unranked and lack depth indicator.",
            "why_it_hurts": "Recruiters cannot tell primary stack from incidental tools.",
            "original_text": "Python, Go, C++, Bash, HTML, CSS",
            "suggested_fix": "Core: Python, Go. Familiar: C++, Bash.",
        },
    ],
}


class CVCriticTests(unittest.TestCase):
    def test_critique_cv_reconciles_counts_and_clamps_score(self):
        with mock.patch("cv_critic.AI_GRAPH.invoke") as mock_invoke:
            mock_invoke.return_value = {"result": dict(SAMPLE_REPORT, overall_score=120)}
            result = critique_cv(
                resume_data={"personal_info": {"name": "Test"}},
                provider="gemini",
            )
            self.assertEqual(result["overall_score"], 100)
            self.assertEqual(result["critical_count"], 1)
            self.assertEqual(result["warning_count"], 1)
            self.assertEqual(result["suggestion_count"], 1)

    def test_router_crud_flow_with_sqlite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "test_resume.db")
            with mock.patch.object(database, "DB_PATH", db_path):
                database.init_db()
                database.seed_initial_resume()

                # Find seeded resume version
                conn = database.get_db()
                row = conn.execute("SELECT id FROM resume_versions LIMIT 1").fetchone()
                version_id = row["id"]
                conn.close()

                # Mock AI graph invoke
                with mock.patch("cv_critic.AI_GRAPH.invoke") as mock_invoke:
                    mock_invoke.return_value = {"result": SAMPLE_REPORT}

                    with mock.patch.object(cv_critique, "get_db", side_effect=database.get_db):
                        # 1. Create critique
                        response = cv_critique.create_cv_critique(
                            provider=AIProvider.gemini,
                            request=CVCritiqueRequest(
                                resume_version_id=version_id,
                                target_role="Senior Platform Engineer",
                            ),
                        )
                        self.assertEqual(response.overall_score, 74)
                        self.assertEqual(len(response.report.issues), 3)
                        critique_id = response.id

                        # 2. List critiques for version
                        summaries = cv_critique.list_critiques_for_version(version_id)
                        self.assertEqual(len(summaries), 1)
                        self.assertEqual(summaries[0].id, critique_id)
                        self.assertEqual(summaries[0].overall_score, 74)

                        # 3. Get single critique
                        single = cv_critique.get_critique(critique_id)
                        self.assertEqual(single.id, critique_id)
                        self.assertEqual(single.report.issues[0].severity, CritiqueSeverity.critical)

                        # 4. Delete critique
                        del_res = cv_critique.delete_critique(critique_id)
                        self.assertIn("deleted", del_res["message"].lower())

                        # 5. Verify deleted
                        summaries_after = cv_critique.list_critiques_for_version(version_id)
                        self.assertEqual(len(summaries_after), 0)


if __name__ == "__main__":
    unittest.main()
