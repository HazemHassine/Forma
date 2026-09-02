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
from models import ResumeData


class DatabaseBootstrapTests(unittest.TestCase):
    def test_external_schema_and_neutral_seed_bootstrap_a_fresh_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "resume.db"
            with mock.patch.object(database, "DB_PATH", str(db_path)):
                database.init_db()
                database.init_db()
                database.seed_initial_resume()
                database.seed_initial_resume()

            conn = sqlite3.connect(db_path)
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            row = conn.execute(
                "SELECT name, description, data, template_id FROM resume_versions"
            ).fetchone()
            count = conn.execute(
                "SELECT COUNT(*) FROM resume_versions"
            ).fetchone()[0]
            conn.close()

        self.assertTrue(database.SCHEMA_PATH.is_file())
        self.assertTrue(database.GENERATION_CONTEXT_MIGRATION_PATH.is_file())
        self.assertTrue(database.RESUME_TEMPLATE_MIGRATION_PATH.is_file())
        self.assertIn("job_applications", tables)
        self.assertIn("cover_letters", tables)
        self.assertIn("company_research_reports", tables)
        self.assertIn("profile_assets", tables)
        self.assertNotIn("job_captures", tables)
        self.assertEqual(count, 1)
        self.assertEqual(row[0], "Starter Resume")
        self.assertIn("Privacy-safe example", row[1])
        self.assertEqual(row[3], "modern")

        resume = ResumeData.model_validate(json.loads(row[2]))
        self.assertEqual(resume.personal_info.name, "Your Name")
        self.assertEqual(resume.personal_info.email, "")

    def test_legacy_database_is_copied_only_when_destination_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "legacy.db"
            destination = Path(temp_dir) / "private" / "resume.db"
            conn = sqlite3.connect(source)
            conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
            conn.execute("INSERT INTO marker (value) VALUES ('preserved')")
            conn.commit()
            conn.close()

            with (
                mock.patch.object(database, "DB_PATH", str(destination)),
                mock.patch.object(database, "LEGACY_DB_PATH", source),
                mock.patch.object(database, "ensure_data_layout"),
            ):
                self.assertTrue(database.migrate_legacy_database())
                self.assertFalse(database.migrate_legacy_database())

            conn = sqlite3.connect(destination)
            value = conn.execute("SELECT value FROM marker").fetchone()[0]
            conn.close()

        self.assertEqual(value, "preserved")


if __name__ == "__main__":
    unittest.main()
