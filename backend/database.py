import json
import hashlib
import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from config import BACKEND_DIR, DATABASE_URL, DB_PATH as CONFIGURED_DB_PATH, ensure_data_layout


# Kept as a module variable so tests and one-off tooling can safely point the
# database layer at a temporary SQLite file.
DB_PATH = str(CONFIGURED_DB_PATH)
SCHEMA_PATH = BACKEND_DIR / "sql" / "schema.sql"
GENERATION_CONTEXT_MIGRATION_PATH = (
    BACKEND_DIR
    / "sql"
    / "migrations"
    / "001_add_cover_letter_generation_context.sql"
)
RESUME_TEMPLATE_MIGRATION_PATH = (
    BACKEND_DIR / "sql" / "migrations" / "002_add_resume_template.sql"
)
DEFAULT_RESUME_PATH = BACKEND_DIR / "sample_data" / "default_resume.json"
LEGACY_DB_PATH = BACKEND_DIR / "resume.db"
REQUIRED_POSTGRES_TABLES = {
    "resume_versions",
    "job_applications",
    "cover_letters",
    "company_research_reports",
    "profile_assets",
}


def _database_url() -> str:
    """Read the URL lazily so tests and process-level overrides remain reliable."""
    if DB_PATH != str(CONFIGURED_DB_PATH):
        return ""
    return os.getenv("DATABASE_URL", DATABASE_URL).strip()


def database_backend() -> str:
    return "supabase" if _database_url() else "sqlite"


def _psycopg_url(url: str) -> str:
    # Supabase snippets sometimes use SQLAlchemy's dialect-qualified scheme.
    return re.sub(r"^postgresql\+psycopg://", "postgresql://", url, count=1)


def _serialize_postgres_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


class PostgresCursor:
    """Small DB-API compatibility layer for the app's existing SQLite queries."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None

    def execute(self, query: str, parameters=()):
        statement = query.replace("?", "%s")
        is_insert = statement.lstrip().upper().startswith("INSERT INTO")
        if is_insert and " RETURNING " not in statement.upper():
            statement = statement.rstrip().rstrip(";") + " RETURNING id"
        self._cursor.execute(statement, tuple(parameters or ()))
        if is_insert:
            inserted = self._cursor.fetchone()
            if inserted:
                self.lastrowid = inserted["id"]
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._normalize(row)

    def fetchall(self):
        return [self._normalize(row) for row in self._cursor.fetchall()]

    @staticmethod
    def _normalize(row):
        if row is None:
            return None
        return {key: _serialize_postgres_value(value) for key, value in row.items()}


class PostgresConnection:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return PostgresCursor(self._connection.cursor())

    def execute(self, query: str, parameters=()):
        return self.cursor().execute(query, parameters)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def get_db():
    url = _database_url()
    if url:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL is configured, but psycopg is not installed. "
                "Run pip install -r backend/requirements.txt."
            ) from exc
        connection = psycopg.connect(
            _psycopg_url(url),
            row_factory=dict_row,
            connect_timeout=10,
        )
        return PostgresConnection(connection)

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate_legacy_database() -> bool:
    """Copy the former source-tree database into private storage once."""
    if database_backend() != "sqlite":
        return False
    ensure_data_layout()
    destination = Path(DB_PATH)
    source = LEGACY_DB_PATH

    if destination.exists() or not source.is_file():
        return False
    if destination.resolve() == source.resolve():
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_conn:
        with sqlite3.connect(destination) as destination_conn:
            source_conn.backup(destination_conn)
    return True


def init_db() -> None:
    if database_backend() == "supabase":
        conn = get_db()
        try:
            rows = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (?, ?, ?, ?, ?)
                """,
                tuple(sorted(REQUIRED_POSTGRES_TABLES)),
            ).fetchall()
            found = {row["table_name"] for row in rows}
            missing = sorted(REQUIRED_POSTGRES_TABLES - found)
            if missing:
                raise RuntimeError(
                    "Supabase is connected, but Forma's schema is missing: "
                    f"{', '.join(missing)}. Paste supabase/schema.sql into the "
                    "Supabase SQL Editor and run it, then restart Forma."
                )
            columns = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'resume_versions'
                """
            ).fetchall()
            if "template_id" not in {row["column_name"] for row in columns}:
                raise RuntimeError(
                    "The Supabase schema is out of date. Run supabase/schema.sql "
                    "again in the SQL Editor, then restart Forma."
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cv_critiques (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    resume_version_id BIGINT NOT NULL REFERENCES resume_versions(id) ON DELETE CASCADE,
                    target_role TEXT,
                    job_description TEXT,
                    provider TEXT NOT NULL DEFAULT 'gemini',
                    overall_score INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    critique_data TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cv_critiques_version
                    ON cv_critiques (resume_version_id, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_sources (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'dump',
                    content TEXT NOT NULL,
                    url TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_context_sources_active
                    ON context_sources (is_active, id DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_items (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    source_id BIGINT REFERENCES context_sources(id) ON DELETE SET NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_context_items_category
                    ON context_items (category)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_context_items_active
                    ON context_items (is_active, id DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_context_items_source
                    ON context_items (source_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_profiles (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    summary TEXT NOT NULL,
                    key_differentiators TEXT NOT NULL DEFAULT '[]',
                    target_roles TEXT NOT NULL DEFAULT '[]',
                    stats TEXT NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            for statement in (
                "ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS version_kind TEXT NOT NULL DEFAULT 'legacy_unreviewed'",
                "ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS parent_version_id BIGINT REFERENCES resume_versions(id) ON DELETE SET NULL",
                "ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS root_version_id BIGINT REFERENCES resume_versions(id) ON DELETE SET NULL",
                "ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS tailoring_audit TEXT",
                "ALTER TABLE context_items ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'pending'",
                "ALTER TABLE context_items ADD COLUMN IF NOT EXISTS origin TEXT NOT NULL DEFAULT 'manual'",
                "ALTER TABLE context_items ADD COLUMN IF NOT EXISTS subject_type TEXT",
                "ALTER TABLE context_items ADD COLUMN IF NOT EXISTS subject_key TEXT",
            ):
                conn.execute(statement)
            conn.execute(
                "UPDATE resume_versions SET root_version_id = id WHERE root_version_id IS NULL"
            )
            conn.execute(
                """
                UPDATE resume_versions SET version_kind = 'tailored_draft'
                WHERE version_kind IN ('legacy_unreviewed', 'manual_source')
                  AND (name LIKE ? OR description LIKE ?)
                """,
                ("Draft · %", "Recoverable tailoring draft%"),
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resume_versions_parent ON resume_versions (parent_version_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resume_versions_root ON resume_versions (root_version_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_source_revisions (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    source_id BIGINT NOT NULL REFERENCES context_sources(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_item_citations (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    item_id BIGINT NOT NULL REFERENCES context_items(id) ON DELETE CASCADE,
                    source_revision_id BIGINT NOT NULL REFERENCES context_source_revisions(id) ON DELETE CASCADE,
                    source_quote TEXT NOT NULL,
                    start_offset INTEGER,
                    end_offset INTEGER
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_source_revisions_source ON context_source_revisions (source_id, id DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_item_citations_item ON context_item_citations (item_id)"
            )
            conn.execute(
                """
                INSERT INTO context_source_revisions (source_id, content, content_hash)
                SELECT s.id, s.content, md5(s.content)
                FROM context_sources s
                WHERE NOT EXISTS (
                    SELECT 1 FROM context_source_revisions r WHERE r.source_id = s.id
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # Older local databases predate the generation context column. The
    # idempotency guard stays in Python because SQLite cannot conditionally add
    # a column across all supported versions.
    cover_letter_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(cover_letters)").fetchall()
    }
    if "generation_context" not in cover_letter_columns:
        cursor.executescript(
            GENERATION_CONTEXT_MIGRATION_PATH.read_text(encoding="utf-8")
        )

    resume_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(resume_versions)").fetchall()
    }
    if "template_id" not in resume_columns:
        cursor.executescript(
            RESUME_TEMPLATE_MIGRATION_PATH.read_text(encoding="utf-8")
        )

    sqlite_resume_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(resume_versions)").fetchall()
    }
    for column_name, definition in (
        ("version_kind", "TEXT NOT NULL DEFAULT 'legacy_unreviewed'"),
        ("parent_version_id", "INTEGER"),
        ("root_version_id", "INTEGER"),
        ("tailoring_audit", "TEXT"),
    ):
        if column_name not in sqlite_resume_columns:
            cursor.execute(f"ALTER TABLE resume_versions ADD COLUMN {column_name} {definition}")
    cursor.execute("UPDATE resume_versions SET root_version_id = id WHERE root_version_id IS NULL")
    cursor.execute(
        """
        UPDATE resume_versions SET version_kind = 'tailored_draft'
        WHERE version_kind IN ('legacy_unreviewed', 'manual_source')
          AND (name LIKE ? OR description LIKE ?)
        """,
        ("Draft · %", "Recoverable tailoring draft%"),
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_resume_versions_parent ON resume_versions (parent_version_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_resume_versions_root ON resume_versions (root_version_id)"
    )

    sqlite_context_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(context_items)").fetchall()
    }
    for column_name, definition in (
        ("verification_status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("origin", "TEXT NOT NULL DEFAULT 'manual'"),
        ("subject_type", "TEXT"),
        ("subject_key", "TEXT"),
    ):
        if column_name not in sqlite_context_columns:
            cursor.execute(f"ALTER TABLE context_items ADD COLUMN {column_name} {definition}")

    existing_revision_sources = {
        row["source_id"]
        for row in cursor.execute("SELECT DISTINCT source_id FROM context_source_revisions").fetchall()
    }
    for source in cursor.execute("SELECT id, content FROM context_sources").fetchall():
        if source["id"] not in existing_revision_sources:
            cursor.execute(
                """
                INSERT INTO context_source_revisions (source_id, content, content_hash)
                VALUES (?, ?, ?)
                """,
                (
                    source["id"], source["content"],
                    hashlib.sha256(source["content"].encode("utf-8")).hexdigest(),
                ),
            )

    conn.commit()
    conn.close()


def seed_initial_resume() -> None:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS count FROM resume_versions")
    if cursor.fetchone()["count"] > 0:
        conn.close()
        return

    resume_data = json.loads(DEFAULT_RESUME_PATH.read_text(encoding="utf-8"))
    cursor.execute(
        """
        INSERT INTO resume_versions (
            name, description, data, template_id, is_current, version_kind
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "Starter Resume",
            "Privacy-safe example. Replace it with your own information.",
            json.dumps(resume_data),
            "modern",
            True,
            "authoritative_source",
        ),
    )
    seeded_id = cursor.lastrowid
    cursor.execute(
        "UPDATE resume_versions SET root_version_id = ? WHERE id = ?",
        (seeded_id, seeded_id),
    )
    conn.commit()
    conn.close()
