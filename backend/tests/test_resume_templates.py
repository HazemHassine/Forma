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
from models import ResumeVersionUpdate
from pdf_generator import RESUME_TEMPLATE_IDS, render_resume_document
from routers import resumes


LONG_TOKEN = "github.com/" + "unbroken-layout-regression-token-" * 7
FINAL_SENTINEL = "FINAL-REFERENCE-SENTINEL"


def overflow_resume():
    long_bullet = (
        "Built a deliberately detailed system description to exercise natural "
        "pagination and verify that every line remains visible in the generated document."
    )
    return {
        "personal_info": {
            "name": "A Very Long Candidate Name That Must Wrap Safely",
            "title": "Principal Engineer for Distributed Systems, Applied Research, and Product Architecture",
            "address": "A long address value that should wrap instead of leaving the printable page",
            "phone": "+00 123 456 789",
            "email": "candidate.with.a.long.address@example.com",
            "github": LONG_TOKEN,
            "linkedin": "linkedin.com/in/long-candidate-profile-for-layout-testing",
        },
        "about_me": " ".join([long_bullet] * 3),
        "education": [
            {
                "institution": "International University with an Intentionally Long Institutional Name",
                "location": "A Very Long City and Country Name",
                "degree": "Master of Science in a Long Interdisciplinary Academic Programme",
                "dates": "September 2020 – August 2026",
                "details": long_bullet,
            }
        ],
        "work_experience": [
            {
                "company": f"Long Organisation Name {index}",
                "location": "A Location That Must Wrap Correctly",
                "role": "Senior Technical Role with Broad Cross-functional Responsibilities",
                "dates": "January 2020 – December 2026",
                "bullets": [long_bullet] * 8,
            }
            for index in range(4)
        ],
        "projects": [
            {
                "name": "Project with an Intentionally Descriptive and Long Name",
                "type": "Independent Research Project",
                "description": long_bullet,
                "stack": "Python, PostgreSQL, FastAPI, Distributed Systems, Observability",
                "extra_info": LONG_TOKEN,
                "bullets": [long_bullet] * 4,
            }
        ],
        "research": [
            {
                "title": "A Long Research Title Designed to Exercise Multi-line Heading Pagination",
                "institution": "Research Institute",
                "location": "International",
                "date": "2026",
                "description": long_bullet,
                "focus": "Distributed systems, evaluation, reliability, and human-computer interaction",
            }
        ],
        "skills": [
            {"category": "A Long Skill Category", "items": [LONG_TOKEN, "Architecture", "Testing"]},
            {"category": "Engineering", "items": ["Python", "PostgreSQL", "Docker"]},
        ],
        "certificates": [{"name": "Long Certificate Name for Layout Testing", "issuer": "Test Institute"}],
        "languages": [{"language": "English", "level": "Professional proficiency"}],
        "references": FINAL_SENTINEL,
    }


class ResumeTemplateTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_template_is_listed_and_switching_preserves_resume_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "resume.db")
            with mock.patch.object(database, "DB_PATH", db_path):
                database.init_db()
                database.seed_initial_resume()

                connection = sqlite3.connect(db_path)
                connection.row_factory = sqlite3.Row
                before = connection.execute(
                    "SELECT id, data FROM resume_versions"
                ).fetchone()
                connection.close()

                with mock.patch.object(resumes, "get_db", side_effect=database.get_db):
                    updated = await resumes.update_resume_version(
                        before["id"],
                        ResumeVersionUpdate(template_id="technical"),
                    )

                connection = sqlite3.connect(db_path)
                connection.row_factory = sqlite3.Row
                after = connection.execute(
                    "SELECT data, template_id FROM resume_versions WHERE id = ?",
                    (before["id"],),
                ).fetchone()
                connection.close()

        template_ids = {item["id"] for item in resumes.RESUME_TEMPLATES}
        self.assertEqual(
            template_ids,
            {
                "modern", "classic", "minimal", "executive", "creative",
                "technical", "latex", "ats", "timeline",
            },
        )
        self.assertEqual(updated.template_id.value, "technical")
        self.assertEqual(after["template_id"], "technical")
        self.assertEqual(json.loads(after["data"]), json.loads(before["data"]))

    def test_every_template_paginates_long_content_without_clipping_text(self):
        resume = overflow_resume()

        for template_id in sorted(RESUME_TEMPLATE_IDS):
            with self.subTest(template_id=template_id):
                document = render_resume_document(resume, template_id=template_id)
                pdf = document.write_pdf()
                self.assertGreater(len(pdf), 1000)

                rendered_text = "".join(
                    box.text
                    for page in document.pages
                    for box in page._page_box.descendants()
                    if getattr(box, "text", None)
                )
                compact_text = (
                    "".join(rendered_text.split())
                    .replace("\u2010", "")
                    .replace("\u00ad", "")
                )
                self.assertIn(FINAL_SENTINEL, rendered_text)
                self.assertIn("".join(LONG_TOKEN.split()), compact_text)

                for page in document.pages:
                    page_box = page._page_box
                    left = page_box.position_x + page_box.margin_left
                    right = left + page_box.width
                    top = page_box.position_y + page_box.margin_top
                    bottom = top + page_box.height
                    for box in page_box.descendants():
                        if not getattr(box, "text", None):
                            continue
                        self.assertGreaterEqual(box.position_x, left - 0.75)
                        self.assertLessEqual(box.position_x + box.width, right + 0.75)
                        self.assertGreaterEqual(box.position_y, top - 0.75)
                        self.assertLessEqual(box.position_y + box.height, bottom + 0.75)

    def test_section_reordering_and_removal_in_pdf(self):
        resume = {
            "personal_info": {
                "name": "Alex Tester",
                "title": "Engineer",
                "address": "Berlin, Germany",
                "phone": "+49 000 0000",
                "email": "alex@example.com",
                "github": "github.com/alex",
                "linkedin": "linkedin.com/in/alex",
            },
            "about_me": "SECTION_ABOUT_MARKER",
            "education": [
                {
                    "institution": "SECTION_EDUCATION_MARKER",
                    "location": "Berlin",
                    "degree": "B.Sc.",
                    "dates": "2020-2024",
                }
            ],
            "work_experience": [
                {
                    "company": "SECTION_EXPERIENCE_MARKER",
                    "location": "Berlin",
                    "role": "Developer",
                    "dates": "2024-Present",
                    "bullets": ["Did work"],
                }
            ],
            "projects": [
                {
                    "name": "SECTION_PROJECTS_MARKER",
                    "type": "Project",
                    "description": "App",
                    "stack": "Python",
                    "bullets": ["Feature"],
                }
            ],
            "research": [],
            "skills": [{"category": "Languages", "items": ["Python"]}],
            "certificates": [],
            "languages": [],
            "references": "",
        }

        for template_id in ["latex", "ats", "timeline", "modern"]:
            with self.subTest(template_id=template_id):
                # 1. Custom order: work_experience before education
                resume_reordered = dict(resume, section_order=["work_experience", "education", "about_me"])
                doc = render_resume_document(resume_reordered, template_id=template_id)
                text = "".join(b.text for p in doc.pages for b in p._page_box.descendants() if getattr(b, "text", None))
                exp_pos = text.find("SECTION_EXPERIENCE_MARKER")
                edu_pos = text.find("SECTION_EDUCATION_MARKER")
                self.assertNotEqual(exp_pos, -1)
                self.assertNotEqual(edu_pos, -1)
                self.assertLess(exp_pos, edu_pos, f"Work experience should precede education in {template_id}")

                # 2. Section removal: education removed from section_order
                resume_removed = dict(resume, section_order=["work_experience", "about_me"])
                doc_removed = render_resume_document(resume_removed, template_id=template_id)
                text_removed = "".join(b.text for p in doc_removed.pages for b in p._page_box.descendants() if getattr(b, "text", None))
                self.assertNotIn("SECTION_EDUCATION_MARKER", text_removed)
                self.assertIn("SECTION_EXPERIENCE_MARKER", text_removed)

    def test_personal_info_website_and_custom_fields_in_pdf(self):
        resume = {
            "personal_info": {
                "name": "Jane Developer",
                "title": "Senior Engineer",
                "email": "jane@example.com",
                "website": "janedev.com",
                # address, phone, github, linkedin omitted/deleted
                "custom_fields": [
                    {"label": "Portfolio", "value": "portfolio.janedev.com", "url": "https://portfolio.janedev.com"}
                ],
            },
            "about_me": "Bio text",
            "education": [],
            "work_experience": [],
            "projects": [],
            "research": [],
            "skills": [],
            "certificates": [],
            "languages": [],
            "references": "",
        }

        for template_id in ["latex", "ats", "timeline", "modern"]:
            with self.subTest(template_id=template_id):
                doc = render_resume_document(resume, template_id=template_id)
                text = "".join(b.text for p in doc.pages for b in p._page_box.descendants() if getattr(b, "text", None))
                self.assertIn("Jane Developer", text)
                self.assertIn("janedev.com", text)
                self.assertIn("portfolio.janedev.com", text)


if __name__ == "__main__":
    unittest.main()

