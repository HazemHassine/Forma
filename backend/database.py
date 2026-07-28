import json
import sqlite3
from pathlib import Path

from config import BACKEND_DIR, DB_PATH as CONFIGURED_DB_PATH, ensure_data_layout


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
DEFAULT_RESUME_PATH = BACKEND_DIR / "sample_data" / "default_resume.json"
LEGACY_DB_PATH = BACKEND_DIR / "resume.db"


def get_db() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate_legacy_database() -> bool:
    """Copy the former source-tree database into private storage once."""
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

    conn.commit()
    conn.close()


def seed_initial_resume() -> None:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM resume_versions")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    resume_data = json.loads(DEFAULT_RESUME_PATH.read_text(encoding="utf-8"))
    cursor.execute(
        """
        INSERT INTO resume_versions (name, description, data, is_current)
        VALUES (?, ?, ?, ?)
        """,
        (
            "Starter Resume",
            "Privacy-safe example. Replace it with your own information.",
            json.dumps(resume_data),
            1,
        ),
    )
    conn.commit()
    conn.close()
