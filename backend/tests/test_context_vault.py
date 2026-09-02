import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
from main import app
import context_engine
from models import (
    ContextSourceCreate,
    ContextSourceUpdate,
    ContextItemCreate,
    ContextItemUpdate,
)


class _IsolatedDBMixin:
    """Provide an isolated temporary SQLite database for each test."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._tmpdir, "test_context.db")
        self._orig_db_path = database.DB_PATH
        self._orig_db_url = database.DATABASE_URL

        os.environ["DATABASE_URL"] = ""
        database.DB_PATH = self._db_path
        database.DATABASE_URL = ""
        database.init_db()
        database.seed_initial_resume()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        database.DATABASE_URL = self._orig_db_url
        os.environ.pop("DATABASE_URL", None)
        try:
            os.remove(self._db_path)
            os.rmdir(self._tmpdir)
        except OSError:
            pass


class SourcesCRUDTests(_IsolatedDBMixin, unittest.TestCase):
    def test_sources_crud(self):
        conn = database.get_db()
        try:
            # Create
            source_id = context_engine.create_source(
                conn,
                ContextSourceCreate(
                    title="Master Career Log",
                    source_type="dump",
                    content="Experienced staff engineer with 10 years scaling distributed systems in Go and Python.",
                    url="https://github.com/example",
                ),
            )
            self.assertGreater(source_id, 0)

            # Read
            source = context_engine.get_source(conn, source_id)
            self.assertIsNotNone(source)
            self.assertEqual(source.title, "Master Career Log")
            self.assertEqual(source.url, "https://github.com/example")
            self.assertTrue(source.is_active)

            # List
            sources = context_engine.list_sources(conn)
            self.assertEqual(len(sources), 1)

            # Update
            updated = context_engine.update_source(
                conn,
                source_id,
                ContextSourceUpdate(title="Updated Master Career Log", is_active=False),
            )
            self.assertEqual(updated.title, "Updated Master Career Log")
            self.assertFalse(updated.is_active)

            active_sources = context_engine.list_sources(conn, active_only=True)
            self.assertEqual(len(active_sources), 0)

            # Delete
            self.assertTrue(context_engine.delete_source(conn, source_id))
            self.assertIsNone(context_engine.get_source(conn, source_id))
        finally:
            conn.close()


class ItemsCRUDAndToggleTests(_IsolatedDBMixin, unittest.TestCase):
    def test_items_crud_and_toggle(self):
        conn = database.get_db()
        try:
            item_id = context_engine.create_item(
                conn,
                ContextItemCreate(
                    category="achievement_metric",
                    title="Latency Reduction by 60%",
                    content="Optimized PostgreSQL read replica caching with Redis, reducing p99 latency from 120ms to 48ms.",
                    tags=["postgresql", "redis", "latency", "performance"],
                ),
            )
            self.assertGreater(item_id, 0)

            item = context_engine.get_item(conn, item_id)
            self.assertIsNotNone(item)
            self.assertEqual(item.category, "achievement_metric")
            self.assertIn("redis", item.tags)
            self.assertTrue(item.is_active)

            # Toggle active
            toggled = context_engine.toggle_item(conn, item_id)
            self.assertFalse(toggled.is_active)

            active_items = context_engine.list_items(conn, active_only=True)
            self.assertEqual(len(active_items), 0)

            # Toggle back
            toggled_back = context_engine.toggle_item(conn, item_id)
            self.assertTrue(toggled_back.is_active)

            # Query filter
            filtered = context_engine.list_items(conn, query="PostgreSQL")
            self.assertEqual(len(filtered), 1)
            filtered_empty = context_engine.list_items(conn, query="NonExistentTerm")
            self.assertEqual(len(filtered_empty), 0)

            # Update
            updated = context_engine.update_item(
                conn,
                item_id,
                ContextItemUpdate(title="Latency Reduction by 65%"),
            )
            self.assertEqual(updated.title, "Latency Reduction by 65%")

            # Delete
            self.assertTrue(context_engine.delete_item(conn, item_id))
            self.assertIsNone(context_engine.get_item(conn, item_id))
        finally:
            conn.close()


class ProfileAndStatsTests(_IsolatedDBMixin, unittest.TestCase):
    def test_profile_and_stats(self):
        conn = database.get_db()
        try:
            # Initial stats
            stats = context_engine.get_stats(conn)
            self.assertEqual(stats.total_sources, 0)
            self.assertEqual(stats.total_items, 0)
            self.assertEqual(stats.estimated_tokens, 0)

            # Create source and items
            s_id = context_engine.create_source(
                conn,
                ContextSourceCreate(
                    title="Bio",
                    content="Bio text here",
                ),
            )
            context_engine.create_item(
                conn,
                ContextItemCreate(
                    source_id=s_id,
                    category="profile_persona",
                    title="Engineering Philosophy",
                    content="Believes in pragmatic architecture and high test coverage.",
                    tags=["architecture"],
                ),
            )

            profile = context_engine.save_profile(
                conn,
                summary="Staff Engineer with deep backend experience.",
                key_differentiators=["10x scale experience", "Open source maintainer"],
                target_roles=["Staff Software Engineer", "Principal Engineer"],
                stats={"notes": "test"},
            )
            self.assertIsNotNone(profile)
            self.assertTrue(profile.summary.startswith("Staff"))
            self.assertEqual(len(profile.key_differentiators), 2)

            stats_after = context_engine.get_stats(conn)
            self.assertEqual(stats_after.total_sources, 1)
            self.assertEqual(stats_after.total_items, 1)
            self.assertEqual(stats_after.categories_breakdown.get("profile_persona"), 1)
        finally:
            conn.close()


class AssembleContextRelevanceTests(_IsolatedDBMixin, unittest.TestCase):
    def test_assemble_context_relevance(self):
        conn = database.get_db()
        try:
            context_engine.save_profile(
                conn,
                summary="Principal distributed systems engineer.",
                key_differentiators=["Low-latency specialist"],
                target_roles=["Staff Engineer"],
                stats={},
            )
            # Create distinct items
            context_engine.create_item(
                conn,
                ContextItemCreate(
                    category="achievement_metric",
                    title="Kafka Streaming Throughput",
                    content="Scaled Kafka cluster to 500,000 events/sec.",
                    tags=["kafka", "streaming", "throughput", "event-driven"],
                ),
            )
            context_engine.create_item(
                conn,
                ContextItemCreate(
                    category="experience_project",
                    title="React Frontend Redesign",
                    content="Migrated legacy jQuery UI to React and Vite with Tailwind.",
                    tags=["react", "frontend", "javascript"],
                ),
            )

            # Assemble with Kafka query
            kafka_context = context_engine.assemble_context(
                conn,
                target_role="Streaming Systems Engineer",
                job_description="Looking for an engineer experienced with Kafka, event pipelines, and high throughput.",
                max_items=10,
            )
            self.assertIn("Kafka Streaming Throughput", kafka_context)
            self.assertIn("500,000 events/sec", kafka_context)
            self.assertIn("EXECUTIVE SUMMARY & POSITIONING", kafka_context)

            # Assemble with general query
            general_context = context_engine.assemble_context(conn, max_items=5)
            self.assertIn("CANDIDATE VERIFIED CONTEXT VAULT", general_context)
        finally:
            conn.close()


class APIContextEndpointsTests(_IsolatedDBMixin, unittest.TestCase):
    def test_api_context_endpoints(self):
        from fastapi.testclient import TestClient
        client = TestClient(app)

        # 1. Create source via API
        resp = client.post(
            "/api/context/sources",
            json={
                "title": "GitHub Profile and Notes",
                "source_type": "link",
                "content": "Full stack open source contributor. Created popular ASGI middleware.",
                "url": "https://github.com/my-user",
            },
        )
        self.assertEqual(resp.status_code, 201)
        source_data = resp.json()
        source_id = source_data["id"]
        self.assertEqual(source_data["title"], "GitHub Profile and Notes")

        # 2. List sources
        resp = client.get("/api/context/sources")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

        # 3. Create context item via API
        resp = client.post(
            "/api/context/items",
            json={
                "source_id": source_id,
                "category": "skills_arsenal",
                "title": "Python AsyncIO Mastery",
                "content": "Deep internals of uvloop, async event loops, and concurrency patterns.",
                "tags": ["python", "asyncio", "concurrency"],
            },
        )
        self.assertEqual(resp.status_code, 201)
        item_id = resp.json()["id"]

        # 4. Toggle item
        resp = client.post(f"/api/context/items/{item_id}/toggle")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["is_active"])

        resp = client.post(f"/api/context/items/{item_id}/toggle")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_active"])

        # 5. Get stats
        resp = client.get("/api/context/stats")
        self.assertEqual(resp.status_code, 200)
        stats = resp.json()
        self.assertEqual(stats["total_sources"], 1)
        self.assertEqual(stats["total_items"], 1)
        self.assertEqual(stats["active_items"], 1)

        # 6. Preview assembled context
        resp = client.get("/api/context/preview?target_role=Python+Architect")
        self.assertEqual(resp.status_code, 200)
        preview = resp.json()
        self.assertEqual(preview["item_count"], 1)
        self.assertIn("Python AsyncIO Mastery", preview["assembled_prompt"])

        # 7. Import from resume
        # The starter resume was seeded by database.seed_initial_resume()
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM resume_versions LIMIT 1")
        resume_row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(resume_row)
        resume_id = resume_row["id"]

        resp = client.post(f"/api/context/import-resume/{resume_id}")
        self.assertEqual(resp.status_code, 201)
        imported_source = resp.json()
        self.assertIn("Imported from Resume", imported_source["title"])
        self.assertEqual(imported_source["source_type"], "resume")

        # Verify total sources now 2
        resp = client.get("/api/context/sources")
        self.assertEqual(len(resp.json()), 2)
