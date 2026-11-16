import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
from models import (
    JobApplicationCreate,
    JobApplicationUpdate,
    JobBulkStatusRequest,
    JobEventCreate,
)
from routers import jobs as job_routes


LEGACY_SCHEMA = """
CREATE TABLE resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    data TEXT NOT NULL,
    template_id TEXT NOT NULL DEFAULT 'modern',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT 0
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
INSERT INTO resume_versions (id, name, data) VALUES (11, 'Agentic AI', '{}');
INSERT INTO job_applications (id, company, position, status, resume_version_id, applied_at)
VALUES
    (1, 'Linked GmbH', 'AI Student', 'applied', 11, '2026-07-01'),
    (2, 'Unlinked GmbH', 'Data Student', 'applied', NULL, '2026-07-02');
"""


class JobApplicationRouteTests(unittest.TestCase):
    """Runs against a database created by the first release and then upgraded."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "jobs.db"

        conn = sqlite3.connect(self.db_path)
        conn.executescript(LEGACY_SCHEMA)
        conn.commit()
        conn.close()

        patcher = mock.patch.object(database, "DB_PATH", str(self.db_path))
        patcher.start()
        self.addCleanup(patcher.stop)
        database.init_db()

    def fetch_job(self, job_id):
        conn = database.get_db()
        row = conn.execute(
            "SELECT * FROM job_applications WHERE id = ?", (job_id,)
        ).fetchone()
        conn.close()
        return row

    def create(self, **overrides):
        payload = {"company": "Acme", "position": "Engineer", **overrides}
        return job_routes.create_job_application(JobApplicationCreate(**payload))

    def test_upgrade_keeps_existing_applications_and_adds_new_fields(self):
        database.init_db()  # A second run must be a no-op.
        jobs = job_routes.list_job_applications()
        self.assertEqual({job.company for job in jobs}, {"Linked GmbH", "Unlinked GmbH"})
        linked = next(job for job in jobs if job.id == 1)
        self.assertEqual(linked.resume_version_name, "Agentic AI")
        self.assertIsNone(linked.follow_up_at)
        self.assertIsNone(linked.job_description)

    def test_editing_an_unlinked_application_accepts_null_resume(self):
        result = job_routes.update_job_application(
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

    def test_explicit_null_clears_resume_while_omission_preserves_it(self):
        preserved = job_routes.update_job_application(
            1, JobApplicationUpdate(notes="Still linked")
        )
        self.assertEqual(preserved.resume_version_id, 11)

        cleared = job_routes.update_job_application(
            1, JobApplicationUpdate(resume_version_id=None)
        )
        self.assertIsNone(cleared.resume_version_id)
        self.assertIsNone(self.fetch_job(1)["resume_version_id"])

    def test_create_persists_selected_applied_date(self):
        created = self.create(
            company="New Company",
            position="Working Student",
            resume_version_id=None,
            applied_at="2026-07-15",
        )

        self.assertIsNone(created.resume_version_id)
        self.assertEqual(created.applied_at, "2026-07-15")
        self.assertEqual(self.fetch_job(created.id)["applied_at"], "2026-07-15")

    def test_create_stores_job_post_and_follow_up(self):
        created = self.create(
            status="saved",
            job_description="  Build agents.  ",
            location="Berlin",
            salary="70k",
            contact="Sam, recruiter",
            next_step="Tailor resume",
            follow_up_at="2026-08-01",
        )
        self.assertEqual(created.status, "saved")
        self.assertEqual(created.job_description, "Build agents.")
        self.assertEqual(created.follow_up_at, "2026-08-01")
        self.assertEqual(job_routes.get_job_application(created.id).location, "Berlin")

    def test_a_backdated_application_counts_as_silent_since_it_was_sent(self):
        old_date = (date.today() - timedelta(days=40)).isoformat()
        created = self.create(company="Late Entry", applied_at=old_date)
        self.assertIsNone(created.status_changed_at)

        overview = job_routes.get_job_overview()
        self.assertIn(created.id, [job.id for job in overview["stale"]])
        # The two legacy rows from July are silent too.
        self.assertEqual(len(overview["stale"]), 3)

    def test_unknown_status_and_blank_company_are_rejected(self):
        with self.assertRaises(ValidationError):
            JobApplicationCreate(company="Acme", position="Engineer", status="maybe")
        with self.assertRaises(HTTPException) as raised:
            self.create(company="   ")
        self.assertEqual(raised.exception.status_code, 422)

    def test_omitted_fields_survive_and_explicit_null_clears_text(self):
        created = self.create(job_description="Post", follow_up_at="2026-08-01")
        kept = job_routes.update_job_application(
            created.id, JobApplicationUpdate(notes="Called them")
        )
        self.assertEqual(kept.job_description, "Post")
        self.assertEqual(kept.follow_up_at, "2026-08-01")

        cleared = job_routes.update_job_application(
            created.id, JobApplicationUpdate(job_description=None, follow_up_at=None)
        )
        self.assertIsNone(cleared.job_description)
        self.assertIsNone(cleared.follow_up_at)
        self.assertEqual(cleared.notes, "Called them")

    def test_applying_to_a_saved_job_dates_it_today_and_logs_the_change(self):
        created = self.create(status="saved", applied_at="2026-01-01")
        applied = job_routes.update_job_application(
            created.id, JobApplicationUpdate(status="applied")
        )
        self.assertEqual(applied.applied_at[:10], date.today().isoformat())
        self.assertIsNotNone(applied.status_changed_at)

        events = job_routes.list_job_events(created.id)
        self.assertEqual([event.kind for event in events], ["status", "created"])
        self.assertEqual(events[0].detail, "saved → applied")

    def test_closing_an_application_clears_its_follow_up(self):
        created = self.create(follow_up_at="2026-08-01")
        closed = job_routes.update_job_application(
            created.id, JobApplicationUpdate(status="rejected")
        )
        self.assertIsNone(closed.follow_up_at)

    def test_bulk_status_closes_only_the_listed_applications(self):
        result = job_routes.bulk_update_status(
            JobBulkStatusRequest(ids=[1, 1, 999], status="ghosted")
        )
        self.assertEqual(result, {"updated": 1})
        self.assertEqual(self.fetch_job(1)["status"], "ghosted")
        self.assertEqual(self.fetch_job(2)["status"], "applied")
        self.assertEqual(job_routes.get_job_stats(), {"ghosted": 1, "applied": 1, "total": 2})

    def test_notes_are_logged_and_deleted_with_the_application(self):
        note = job_routes.add_job_event(1, JobEventCreate(detail=" Phone screen booked "))
        self.assertEqual(note.detail, "Phone screen booked")
        self.assertEqual(len(job_routes.list_job_events(1)), 1)

        job_routes.delete_job_application(1)
        self.assertEqual(job_routes.list_job_events(1), [])
        with self.assertRaises(HTTPException):
            job_routes.get_job_application(1)

    def test_saved_material_for_the_same_company_is_flagged(self):
        conn = database.get_db()
        conn.execute(
            "INSERT INTO cover_letters (resume_version_id, company, position, job_post, content) "
            "VALUES (11, ' linked gmbh ', 'AI Student', 'post', '{}')"
        )
        conn.execute(
            "INSERT INTO company_research_reports (company, report, researched_at) "
            "VALUES ('Unlinked GmbH', '{}', '2026-07-01')"
        )
        conn.commit()
        conn.close()

        jobs = {job.id: job for job in job_routes.list_job_applications()}
        self.assertTrue(jobs[1].has_cover_letter)
        self.assertFalse(jobs[1].has_research)
        self.assertTrue(jobs[2].has_research)


class JobOverviewTests(unittest.TestCase):
    TODAY = date(2026, 11, 16)  # A Monday.

    def job(self, job_id, status="applied", days_ago=0, follow_up_in=None, changed_days_ago=None):
        from models import JobApplication

        return JobApplication(
            id=job_id,
            company=f"Company {job_id}",
            position="Engineer",
            status=status,
            applied_at=(self.TODAY - timedelta(days=days_ago)).isoformat(),
            follow_up_at=(
                (self.TODAY + timedelta(days=follow_up_in)).isoformat()
                if follow_up_in is not None
                else None
            ),
            status_changed_at=(
                f"{(self.TODAY - timedelta(days=changed_days_ago)).isoformat()}T10:00:00+00:00"
                if changed_days_ago is not None
                else None
            ),
        )

    def test_sorts_applications_into_what_needs_attention(self):
        jobs = [
            self.job(1, days_ago=30),                      # stale: silent for a month
            self.job(2, days_ago=30, follow_up_in=-2),     # follow-up overdue
            self.job(3, days_ago=30, follow_up_in=3),      # follow-up this week
            self.job(4, days_ago=30, follow_up_in=20),     # planned, not yet relevant
            self.job(5, days_ago=5),                       # too recent to chase
            self.job(6, status="saved", days_ago=40),      # not applied yet
            self.job(7, status="rejected", days_ago=40),   # closed
            self.job(8, status="interviewing", days_ago=40, changed_days_ago=1),
        ]
        overview = job_routes.build_overview(jobs, set(), self.TODAY)

        self.assertEqual([job.id for job in overview["due"]], [2])
        self.assertEqual([job.id for job in overview["upcoming"]], [3])
        self.assertEqual([job.id for job in overview["stale"]], [1])
        self.assertEqual([job.id for job in overview["saved"]], [6])
        self.assertEqual(overview["active"], 7)
        self.assertEqual(overview["counts"]["applied"], 5)

    def test_weekly_activity_and_rates(self):
        jobs = [
            self.job(1, days_ago=0),
            self.job(2, days_ago=7),
            self.job(3, days_ago=8, status="rejected"),
            self.job(4, days_ago=3, status="interviewing"),
            self.job(5, days_ago=0, status="saved"),
        ]
        overview = job_routes.build_overview(jobs, {3}, self.TODAY)

        self.assertEqual(len(overview["weekly"]), 8)
        self.assertEqual(overview["weekly"][-1], {"week_start": "2026-11-16", "count": 1})
        self.assertEqual(overview["weekly"][-2]["count"], 2)  # jobs 2 and 4
        self.assertEqual(overview["weekly"][-3]["count"], 1)  # job 3, the Sunday before
        self.assertEqual(overview["applied_this_week"], 1)
        self.assertEqual(overview["submitted"], 4)
        self.assertEqual(overview["response_rate"], 50)
        # Job 3 was interviewed before being rejected, per its activity log.
        self.assertEqual(overview["interview_rate"], 50)

    def test_empty_pipeline_has_no_rates(self):
        overview = job_routes.build_overview([], set(), self.TODAY)
        self.assertIsNone(overview["response_rate"])
        self.assertEqual(overview["total"], 0)


class DatabaseAvailabilityTests(unittest.TestCase):
    def test_paused_supabase_project_is_explained(self):
        message = database.describe_connection_error(
            Exception("FATAL: (EAUTHQUERY) authentication query failed: connection to database not available")
        )
        self.assertIn("pause", message)
        self.assertIn("restore", message)

    def test_wrong_password_is_explained(self):
        message = database.describe_connection_error(
            Exception('FATAL: password authentication failed for user "postgres"')
        )
        self.assertIn("password", message)


if __name__ == "__main__":
    unittest.main()
