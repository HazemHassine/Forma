import copy
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from factual_integrity import build_resume_evidence, validate_resume_edits


RESUME = {
    "about_me": "Engineer building agentic, human-in-the-loop systems.",
    "work_experience": [{
        "company": "Acme",
        "role": "Trainer",
        "dates": "2020-2024",
        "bullets": ["Trained 100+ staff and maintained nightly backups."],
    }],
    "projects": [
        {
            "name": "Forma",
            "type": "Personal",
            "description": "Planned an architectural fix for the ingestion service.",
            "stack": "Python",
            "bullets": ["Built a human-in-the-loop agentic workflow."],
        },
        {
            "name": "Atlas",
            "type": "Personal",
            "description": "Published documentation at https://example.com/atlas.",
            "stack": "Go",
            "bullets": ["Operated a rollback mechanism."],
        },
    ],
    "research": [],
}


class FactualIntegrityTests(unittest.TestCase):
    def validate(self, path, proposed, evidence_ids):
        model = copy.deepcopy(RESUME)
        if path == "about_me":
            model["about_me"] = proposed
        elif path.startswith("work_experience"):
            model["work_experience"][0]["bullets"][0] = proposed
        elif path == "projects.0.description":
            model["projects"][0]["description"] = proposed
        else:
            model["projects"][0]["bullets"][0] = proposed
        _, _, blocked = validate_resume_edits(
            RESUME,
            model,
            {path: evidence_ids},
        )
        return blocked

    def test_blocks_metric_inflation(self):
        blocked = self.validate(
            "work_experience.0.bullets.0",
            "Trained 500+ staff and maintained nightly backups.",
            ["resume:work_experience:0"],
        )
        self.assertEqual(blocked[0]["reason"], "unsupported_metric:500+")

    def test_blocks_agentic_to_multi_agent(self):
        blocked = self.validate(
            "about_me",
            "Engineer building multi-agent, human-in-the-loop systems.",
            ["resume:about_me"],
        )
        self.assertIn("unsupported_capability", blocked[0]["reason"])

    def test_blocks_human_supervised_to_autonomous(self):
        blocked = self.validate(
            "projects.0.bullets.0",
            "Built an autonomous agentic workflow.",
            ["resume:projects:0"],
        )
        self.assertEqual(blocked[0]["reason"], "unsupported_capability:autonomous")

    def test_blocks_backup_to_rollback(self):
        blocked = self.validate(
            "work_experience.0.bullets.0",
            "Trained 100+ staff and maintained a rollback mechanism.",
            ["resume:work_experience:0"],
        )
        self.assertEqual(blocked[0]["reason"], "unsupported_capability:rollback")

    def test_blocks_planned_work_as_implemented(self):
        blocked = self.validate(
            "projects.0.description",
            "Implemented an architectural fix for the ingestion service.",
            ["resume:projects:0"],
        )
        self.assertEqual(blocked[0]["reason"], "planned_work_presented_as_delivered")

    def test_blocks_evidence_from_wrong_project(self):
        blocked = self.validate(
            "projects.0.bullets.0",
            "Built an agentic workflow with a rollback mechanism.",
            ["resume:projects:1"],
        )
        self.assertTrue(blocked[0]["reason"].startswith("wrong_subject"))

    def test_blocks_link_from_wrong_project(self):
        blocked = self.validate(
            "projects.0.description",
            "Planned an architectural fix documented at https://example.com/atlas.",
            ["resume:projects:0"],
        )
        self.assertEqual(blocked[0]["reason"], "unsupported_link")

    def test_blocks_new_named_technology(self):
        blocked = self.validate(
            "projects.0.bullets.0",
            "Built a human-in-the-loop agentic workflow with Kubernetes.",
            ["resume:projects:0"],
        )
        self.assertEqual(blocked[0]["reason"], "unsupported_named_term:Kubernetes")

    def test_blocks_unsupported_scale_language(self):
        blocked = self.validate(
            "projects.0.bullets.0",
            "Built a large-scale human-in-the-loop agentic workflow.",
            ["resume:projects:0"],
        )
        self.assertEqual(blocked[0]["reason"], "unsupported_sensitive_term:large-scale")

    def test_allows_normal_title_cased_sentence_openers(self):
        blocked = self.validate(
            "work_experience.0.bullets.0",
            "Mapped staff workflows and maintained nightly backups.",
            ["resume:work_experience:0"],
        )
        self.assertEqual(blocked, [])


if __name__ == "__main__":
    unittest.main()
