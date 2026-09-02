import os
import shutil
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _resolve_data_dir() -> Path:
    configured = os.getenv("CV_PERSONALIZER_DATA_DIR")
    if not configured:
        return PROJECT_DIR / "local-data"

    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path.resolve()


DATA_DIR = _resolve_data_dir()
STATIC_DIR = DATA_DIR / "static"
DOCUMENTS_DIR = STATIC_DIR / "documents"
DB_PATH = DATA_DIR / "resume.db"


def ensure_data_layout() -> None:
    """Create private runtime directories and copy legacy assets once."""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    legacy_assets = (
        (BACKEND_DIR / "static" / "profile.jpg", STATIC_DIR / "profile.jpg"),
        (
            BACKEND_DIR / "static" / "documents" / "signature.png",
            DOCUMENTS_DIR / "signature.png",
        ),
    )
    for source, destination in legacy_assets:
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
