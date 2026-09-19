import copy
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
from models import ResumeVersionCreate, ResumeVersionKind
from routers.resumes import _validate_tailored_data, create_resume_version, mark_resume_authoritative


class TailoredVersionValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        self.original_db_url = database.DATABASE_URL
        database.DB_PATH = str(Path(self.temp_dir.name) / "resume.db")
        database.DATABASE_URL = ""
        os.environ["DATABASE_URL"] = ""
        database.init_db()
        database.seed_initial_resume()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        database.DATABASE_URL = self.original_db_url
        os.environ.pop("DATABASE_URL", None)
        self.temp_dir.cleanup()

    def test_direct_save_cannot_bypass_metric_validation(self):
        conn = database.get_db()
        try:
            row = conn.execute("SELECT id, data FROM resume_versions LIMIT 1").fetchone()
            resume = json.loads(row["data"])
            candidate = copy.deepcopy(resume)
            original = resume["about_me"]
            candidate["about_me"] = original + " Served 500+ users."
            audit = {
                "claim_audit": [{
                    "field_path": "about_me",
                    "status": "accepted",
                    "evidence_ids": ["resume:about_me"],
                }]
            }
            with self.assertRaises(HTTPException) as raised:
                _validate_tailored_data(conn, row["id"], candidate, audit)
            self.assertEqual(raised.exception.status_code, 409)
            self.assertIn("unsupported_metric", raised.exception.detail)
        finally:
            conn.close()

    def test_legacy_resume_requires_explicit_authoritative_promotion(self):
        conn = database.get_db()
        try:
            row = conn.execute("SELECT id FROM resume_versions LIMIT 1").fetchone()
            conn.execute(
                "UPDATE resume_versions SET version_kind = 'legacy_unreviewed' WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            version_id = row["id"]
        finally:
            conn.close()

        promoted = asyncio.run(mark_resume_authoritative(version_id))
        self.assertEqual(promoted.version_kind.value, "authoritative_source")
        self.assertEqual(promoted.root_version_id, version_id)

    def test_schema_defaults_do_not_block_an_unchanged_tailored_save(self):
        conn = database.get_db()
        try:
            row = conn.execute("SELECT id, data FROM resume_versions LIMIT 1").fetchone()
            source_id = row["id"]
            source_data = json.loads(row["data"])
        finally:
            conn.close()

        created = asyncio.run(create_resume_version(ResumeVersionCreate(
            name="Unchanged tailored draft",
            data=source_data,
            version_kind=ResumeVersionKind.tailored_draft,
            parent_version_id=source_id,
            tailoring_audit={"claim_audit": [], "blocked_edits": []},
        )))
        self.assertEqual(created.version_kind.value, "tailored_draft")

    def test_tailored_version_cannot_use_a_tailored_parent(self):
        conn = database.get_db()
        try:
            row = conn.execute("SELECT id, data FROM resume_versions LIMIT 1").fetchone()
            source_id = row["id"]
            source_data = json.loads(row["data"])
            cursor = conn.execute(
                """
                INSERT INTO resume_versions (
                    name, data, version_kind, parent_version_id, root_version_id
                ) VALUES (?, ?, 'tailored_draft', ?, ?)
                """,
                ("Existing tailored draft", row["data"], source_id, source_id),
            )
            tailored_parent_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(create_resume_version(ResumeVersionCreate(
                name="Second tailored draft",
                data=source_data,
                version_kind=ResumeVersionKind.tailored_draft,
                parent_version_id=tailored_parent_id,
                tailoring_audit={"claim_audit": [], "blocked_edits": []},
            )))
        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
