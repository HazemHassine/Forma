import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

backend_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=backend_env_path, override=False)

from config import STATIC_DIR, ensure_data_layout
from database import (
    database_backend,
    get_db,
    init_db,
    migrate_legacy_database,
    seed_initial_resume,
)
from routers import resumes, jobs, photos
from routers.ai import router as ai_router
from routers.company_research import router as company_research_router
from routers.cover_letters import router as cover_letters_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and seed data on startup."""
    ensure_data_layout()
    migrate_legacy_database()
    init_db()
    seed_initial_resume()
    yield


app = FastAPI(
    title="CV Personalizer API",
    description="API for managing resume versions and job applications",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_origin_regex=r"^http://127\.0\.0\.1:\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount private, persistent user assets.
ensure_data_layout()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(photos.router)
app.include_router(ai_router)
app.include_router(cover_letters_router)
app.include_router(company_research_router)


@app.get("/")
async def root():
    return {
        "message": "CV Personalizer API",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    conn = get_db()
    try:
        conn.execute("SELECT 1 AS ok").fetchone()
    finally:
        conn.close()
    return {"status": "healthy", "database": database_backend()}


@app.get("/api/system/status")
async def system_status():
    conn = get_db()
    try:
        conn.execute("SELECT 1 AS ok").fetchone()
    finally:
        conn.close()
    return {
        "status": "ready",
        "database": database_backend(),
        "ai": {
            "gemini": {
                "configured": bool(os.getenv("GEMINI_API_KEY")),
                "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            },
            "chatgpt": {
                "configured": bool(os.getenv("OPENAI_API_KEY")),
                "model": os.getenv("OPENAI_RESUME_MODEL", "gpt-5.6-sol"),
            },
        },
    }
