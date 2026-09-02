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
from routers import resumes


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
            {"modern", "classic", "minimal", "executive", "creative", "technical"},
        )
        self.assertEqual(updated.template_id.value, "technical")
        self.assertEqual(after["template_id"], "technical")
        self.assertEqual(json.loads(after["data"]), json.loads(before["data"]))


if __name__ == "__main__":
    unittest.main()
