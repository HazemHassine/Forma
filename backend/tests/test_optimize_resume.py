import unittest
from unittest import mock
import copy

from models import ResumeData
from ai_helper import optimize_resume


SAMPLE_RESUME_DATA = {
    "personal_info": {
        "name": "Alex Doe",
        "title": "Software Engineer",
        "email": "alex@example.com",
        "phone": "+1234567890",
        "address": "San Francisco, CA",
        "website": "https://alex.dev",
        "github": "https://github.com/alex",
        "linkedin": "https://linkedin.com/in/alex",
        "custom_fields": [],
    },
    "about_me": "Original about me summary describing engineering skills.",
    "education": [
        {
            "institution": "Tech University",
            "location": "Boston, MA",
            "degree": "B.S. in Computer Science",
            "dates": "2018 - 2022",
            "details": "Graduated with honors",
        }
    ],
    "work_experience": [
        {
            "company": "Acme Corp",
            "location": "San Francisco, CA",
            "role": "Full Stack Engineer",
            "dates": "2022 - Present",
            "bullets": [
                "Built customer dashboards using React and Python.",
                "Improved query latency by 30% through indexing.",
            ],
        }
    ],
    "projects": [
        {
            "name": "DataPipeline",
            "type": "Open Source",
            "description": "Original pipeline description.",
            "stack": "Python, Docker, Redis",
            "extra_info": None,
            "bullets": [
                "Processed 1M records daily.",
            ],
        }
    ],
    "research": [
        {
            "title": "Federated Optimization",
            "institution": "Research Lab",
            "location": "Boston, MA",
            "date": "2021",
            "description": "Original research description.",
            "focus": "Distributed Systems",
        }
    ],
    "skills": [
        {
            "category": "Languages",
            "items": ["Python", "TypeScript", "SQL"],
        }
    ],
    "certificates": [
        {
            "name": "AWS Certified Solutions Architect",
            "issuer": "Amazon Web Services",
        }
    ],
    "languages": [
        {
            "language": "English",
            "level": "Native",
        }
    ],
    "references": "Available upon request",
    "section_order": [
        "about_me",
        "work_experience",
        "education",
        "skills",
        "projects",
        "research",
    ],
}


class TestOptimizeResume(unittest.TestCase):
    def setUp(self):
        self.resume = copy.deepcopy(SAMPLE_RESUME_DATA)

    def test_optimize_resume_preserves_all_sections_and_merges_tailored_content(self):
        mock_ai_result = {
            "resume": {
                "about_me": "Tailored about me emphasizing backend and data pipelines.",
                "work_experience": [
                    {
                        "bullets": [
                            "Built high-throughput dashboards using React and Python.",
                            "Engineered indexed database queries reducing p95 latency by 30%.",
                        ]
                    }
                ],
                "projects": [
                    {
                        "description": "High-throughput streaming ETL pipeline.",
                        "bullets": [
                            "Handled 1M+ transactions daily with Redis and Python.",
                        ],
                    }
                ],
                "research": [
                    {
                        "description": "Analyzed distributed gradient synchronization in privacy-preserving networks.",
                    }
                ],
            },
            "match_summary": "Tailored candidate profile to emphasize Python pipelines and latency optimization.",
            "strengths": ["Strong backend experience in Python", "Demonstrated database optimization"],
            "gaps": ["No direct Kubernetes production management mentioned"],
            "keywords_used": ["Python", "ETL", "Latency", "Redis"],
        }

        with mock.patch("ai_helper.AI_GRAPH.invoke", return_value={"result": mock_ai_result}):
            optimized = optimize_resume(
                resume_data=self.resume,
                job_description="Looking for a Python Backend Engineer.",
                target_role="Backend Engineer",
                company="Acme Corp",
                provider="gemini",
            )

        # Validate that the merged resume conforms strictly to ResumeData
        resume_model = ResumeData(**optimized["resume"])
        self.assertIsNotNone(resume_model)

        # Verify tailored fields were updated
        self.assertEqual(
            optimized["resume"]["about_me"],
            "Tailored about me emphasizing backend and data pipelines.",
        )
        self.assertEqual(
            optimized["resume"]["work_experience"][0]["bullets"],
            [
                "Built high-throughput dashboards using React and Python.",
                "Engineered indexed database queries reducing p95 latency by 30%.",
            ],
        )
        self.assertEqual(
            optimized["resume"]["projects"][0]["description"],
            "High-throughput streaming ETL pipeline.",
        )
        self.assertEqual(
            optimized["resume"]["projects"][0]["bullets"],
            ["Handled 1M+ transactions daily with Redis and Python."],
        )
        self.assertEqual(
            optimized["resume"]["research"][0]["description"],
            "Analyzed distributed gradient synchronization in privacy-preserving networks.",
        )

        # Verify immutable fields remain untouched
        self.assertEqual(
            optimized["resume"]["personal_info"]["name"],
            self.resume["personal_info"]["name"],
        )
        self.assertEqual(
            optimized["resume"]["work_experience"][0]["company"],
            self.resume["work_experience"][0]["company"],
        )
        self.assertEqual(
            optimized["resume"]["work_experience"][0]["role"],
            self.resume["work_experience"][0]["role"],
        )
        self.assertEqual(
            optimized["resume"]["education"],
            self.resume["education"],
        )
        self.assertEqual(
            optimized["resume"]["skills"],
            self.resume["skills"],
        )
        self.assertEqual(
            optimized["resume"]["certificates"],
            self.resume["certificates"],
        )
        self.assertEqual(
            optimized["resume"]["languages"],
            self.resume["languages"],
        )

        # Verify metadata
        self.assertEqual(len(optimized["strengths"]), 2)
        self.assertEqual(len(optimized["gaps"]), 1)
        self.assertEqual(len(optimized["keywords_used"]), 4)

    def test_optimize_resume_handles_partial_model_response_gracefully(self):
        # Model returns only about_me, omitting work_experience and projects
        mock_ai_result = {
            "resume": {
                "about_me": "Tailored about me only.",
            },
            "match_summary": "High-level summary tailoring.",
            "strengths": ["Quick learner"],
            "gaps": [],
            "keywords_used": ["Python"],
        }

        with mock.patch("ai_helper.AI_GRAPH.invoke", return_value={"result": mock_ai_result}):
            optimized = optimize_resume(
                resume_data=self.resume,
                job_description="Looking for Python developer.",
                provider="gemini",
            )

        # ResumeData validation must still succeed
        resume_model = ResumeData(**optimized["resume"])
        self.assertEqual(optimized["resume"]["about_me"], "Tailored about me only.")
        # Original work experience and projects must be safely preserved
        self.assertEqual(
            optimized["resume"]["work_experience"],
            self.resume["work_experience"],
        )
        self.assertEqual(
            optimized["resume"]["projects"],
            self.resume["projects"],
        )

    def test_optimize_resume_handles_bullet_length_mismatch_safely(self):
        # Model returns 3 bullets when original has 2 bullets
        mock_ai_result = {
            "resume": {
                "about_me": "Tailored about me.",
                "work_experience": [
                    {
                        "bullets": [
                            "Extra bullet 1",
                            "Extra bullet 2",
                            "Extra bullet 3",
                        ]
                    }
                ],
            },
            "match_summary": "Tailored.",
            "strengths": [],
            "gaps": [],
            "keywords_used": [],
        }

        with mock.patch("ai_helper.AI_GRAPH.invoke", return_value={"result": mock_ai_result}):
            optimized = optimize_resume(
                resume_data=self.resume,
                job_description="Looking for Python developer.",
                provider="gemini",
            )

        # When bullet counts mismatch, original bullets should be preserved to avoid corruption
        self.assertEqual(
            optimized["resume"]["work_experience"][0]["bullets"],
            self.resume["work_experience"][0]["bullets"],
        )


if __name__ == "__main__":
    unittest.main()
