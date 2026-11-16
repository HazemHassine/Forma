import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

backend_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=backend_env_path, override=False)

from config import STATIC_DIR, ensure_data_layout
from database import (
    DatabaseUnavailable,
    database_backend,
    database_error,
    ensure_schema,
    get_db,
    migrate_legacy_database,
)
from routers import resumes, jobs, photos
from routers.ai import router as ai_router
from routers.company_research import router as company_research_router
from routers.cover_letters import router as cover_letters_router
from routers.cv_critique import router as cv_critique_router
from routers.context import router as context_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and seed data on startup."""
    ensure_data_layout()
    migrate_legacy_database()
    # A database that is down (for example a paused Supabase project) must not
    # stop the server: the UI needs to come up to explain what is wrong.
    ensure_schema()
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

@app.middleware("http")
async def finish_startup_when_database_returns(request: Request, call_next):
    """Complete skipped startup migrations once the database is reachable."""
    if request.url.path.startswith("/api/"):
        await run_in_threadpool(ensure_schema)
    return await call_next(request)


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable_handler(request: Request, exc: DatabaseUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def _database_state() -> dict:
    """Probe the database without raising, for health and status endpoints."""
    try:
        conn = get_db()
        try:
            conn.execute("SELECT 1 AS ok").fetchone()
        finally:
            conn.close()
    except DatabaseUnavailable as exc:
        return {"database_status": "unavailable", "database_error": str(exc)}
    if not ensure_schema():
        return {
            "database_status": "unavailable",
            "database_error": database_error() or "The database is not ready yet.",
        }
    return {"database_status": "connected", "database_error": None}


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
app.include_router(cv_critique_router)
app.include_router(context_router)


@app.get("/")
async def root():
    return {
        "message": "CV Personalizer API",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    # Always 200 while the process is up: Docker starts the frontend only when
    # this passes, and the frontend is what explains a database problem.
    state = _database_state()
    return {
        "status": "healthy" if state["database_status"] == "connected" else "degraded",
        "database": database_backend(),
        **state,
    }


@app.get("/api/system/status")
def system_status():
    state = _database_state()
    return {
        "status": "ready" if state["database_status"] == "connected" else "degraded",
        "database": database_backend(),
        **state,
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
