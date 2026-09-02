import json
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
        INSERT INTO resume_versions (name, description, data, template_id, is_current)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "Starter Resume",
            "Privacy-safe example. Replace it with your own information.",
            json.dumps(resume_data),
            "modern",
            True,
        ),
    )
    conn.commit()
    conn.close()
