import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models import JobApplicationCreate, JobApplicationUpdate
from routers import jobs as job_routes


class JobApplicationRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "jobs.db"

        conn = self.get_db()
        conn.executescript(
            """
            CREATE TABLE resume_versions (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE job_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                position TEXT NOT NULL,
                url TEXT,
                status TEXT DEFAULT 'applied',
                resume_version_id INTEGER,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                updated_at TIMESTAMP,
                FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id)
            );

            INSERT INTO resume_versions (id, name)
            VALUES (11, 'Agentic AI');

            INSERT INTO job_applications (
                id, company, position, status, resume_version_id, applied_at
            )
            VALUES
                (1, 'Linked GmbH', 'AI Student', 'applied', 11, '2026-07-01'),
                (2, 'Unlinked GmbH', 'Data Student', 'applied', NULL, '2026-07-02');
            """
        )
        conn.commit()
        conn.close()

        patcher = mock.patch.object(job_routes, "get_db", side_effect=self.get_db)
        patcher.start()
        self.addCleanup(patcher.stop)

    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def fetch_job(self, job_id):
        conn = self.get_db()
        row = conn.execute(
            "SELECT * FROM job_applications WHERE id = ?",
            (job_id,),
        ).fetchone()
        conn.close()
        return row

    async def test_editing_an_unlinked_application_accepts_null_resume(self):
        result = await job_routes.update_job_application(
            2,
            JobApplicationUpdate(
                company="Unlinked GmbH",
                position="Data Student",
                resume_version_id=None,
                applied_at="2026-07-20",
            ),
        )

        self.assertIsNone(result.resume_version_id)
        self.assertEqual(result.applied_at, "2026-07-20")
        stored = self.fetch_job(2)
        self.assertIsNone(stored["resume_version_id"])
        self.assertEqual(stored["applied_at"], "2026-07-20")

    async def test_explicit_null_clears_resume_while_omission_preserves_it(self):
        preserved = await job_routes.update_job_application(
            1,
            JobApplicationUpdate(notes="Still linked"),
        )
        self.assertEqual(preserved.resume_version_id, 11)

        cleared = await job_routes.update_job_application(
            1,
            JobApplicationUpdate(resume_version_id=None),
        )
        self.assertIsNone(cleared.resume_version_id)
        self.assertIsNone(self.fetch_job(1)["resume_version_id"])

    async def test_create_persists_selected_applied_date(self):
        created = await job_routes.create_job_application(
            JobApplicationCreate(
                company="New Company",
                position="Working Student",
                resume_version_id=None,
                applied_at="2026-07-15",
            )
        )

        self.assertIsNone(created.resume_version_id)
        self.assertEqual(created.applied_at, "2026-07-15")
        self.assertEqual(self.fetch_job(created.id)["applied_at"], "2026-07-15")


if __name__ == "__main__":
    unittest.main()
