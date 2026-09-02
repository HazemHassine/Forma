import json
from fastapi import APIRouter, HTTPException
from models import (
    ResumeVersionCreate,
    ResumeVersionUpdate,
    ResumeVersion,
    ResumeVersionSummary,
    ResumeDuplicateRequest,
    ResumeTemplateOption,
)
from database import get_db
from fastapi.responses import Response
from pdf_generator import generate_pdf
from routers.photos import get_current_photo_data

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

RESUME_TEMPLATES = [
    {"id": "modern", "name": "Modern", "description": "Balanced two-column layout", "accent": "#1f4e79"},
    {"id": "classic", "name": "Classic", "description": "Traditional serif styling", "accent": "#5b4636"},
    {"id": "minimal", "name": "Minimal", "description": "Clean and understated", "accent": "#222222"},
    {"id": "executive", "name": "Executive", "description": "Confident navy and gold", "accent": "#13233f"},
    {"id": "creative", "name": "Creative", "description": "Warm editorial character", "accent": "#bb4d3e"},
    {"id": "technical", "name": "Technical", "description": "Compact and precise", "accent": "#146b52"},
    {"id": "latex", "name": "LaTeX", "description": "Academic single-column typesetting", "accent": "#111111"},
    {"id": "ats", "name": "ATS Simple", "description": "Plain parsing-first document flow", "accent": "#2f3b46"},
    {"id": "timeline", "name": "Timeline", "description": "Dates lead a chronological rail", "accent": "#315b7d"},
]


def _serialize_version(row) -> ResumeVersion:
    return ResumeVersion(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        data=json.loads(row["data"]),
        created_at=row["created_at"],
        is_current=bool(row["is_current"]),
        template_id=row["template_id"] or "modern",
    )


@router.get("/templates", response_model=list[ResumeTemplateOption])
async def list_resume_templates():
    return RESUME_TEMPLATES


@router.get("", response_model=list[ResumeVersionSummary])
async def list_resume_versions():
    """List all resume versions (without full data)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, description, created_at, is_current, template_id "
        "FROM resume_versions ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        ResumeVersionSummary(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            is_current=bool(row["is_current"]),
            template_id=row["template_id"] or "modern",
        )
        for row in rows
    ]


@router.post("", response_model=ResumeVersion, status_code=201)
async def create_resume_version(version: ResumeVersionCreate):
    """Create a new resume version."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO resume_versions (name, description, data, template_id) VALUES (?, ?, ?, ?)",
        (version.name, version.description, version.data.model_dump_json(), version.template_id.value),
    )
    conn.commit()
    version_id = cursor.lastrowid
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    conn.close()
    return _serialize_version(row)


@router.get("/{version_id}", response_model=ResumeVersion)
async def get_resume_version(version_id: int):
    """Get a full resume version with data."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return _serialize_version(row)


@router.put("/{version_id}", response_model=ResumeVersion)
async def update_resume_version(version_id: int, update: ResumeVersionUpdate):
    """Update a resume version."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume version not found")

    new_name = update.name if update.name is not None else row["name"]
    new_description = (
        update.description if update.description is not None else row["description"]
    )
    new_data = (
        update.data.model_dump_json() if update.data is not None else row["data"]
    )
    new_template_id = (
        update.template_id.value
        if update.template_id is not None
        else row["template_id"]
    )

    cursor.execute(
        "UPDATE resume_versions SET name = ?, description = ?, data = ?, template_id = ? WHERE id = ?",
        (new_name, new_description, new_data, new_template_id, version_id),
    )
    conn.commit()

    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    conn.close()
    return _serialize_version(row)


@router.delete("/{version_id}")
async def delete_resume_version(version_id: int):
    """Delete a resume version (cannot delete current version)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume version not found")
    if row["is_current"]:
        conn.close()
        raise HTTPException(
            status_code=400, detail="Cannot delete the current resume version"
        )
    cursor.execute("DELETE FROM resume_versions WHERE id = ?", (version_id,))
    conn.commit()
    conn.close()
    return {"message": "Resume version deleted"}


@router.post("/{version_id}/duplicate", response_model=ResumeVersion, status_code=201)
async def duplicate_resume_version(
    version_id: int, request: ResumeDuplicateRequest = ResumeDuplicateRequest()
):
    """Duplicate an existing resume version."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume version not found")

    new_name = request.name or f"{row['name']} (Copy)"
    cursor.execute(
        "INSERT INTO resume_versions (name, description, data, template_id) VALUES (?, ?, ?, ?)",
        (new_name, row["description"], row["data"], row["template_id"]),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (new_id,))
    new_row = cursor.fetchone()
    conn.close()
    return _serialize_version(new_row)


@router.get("/{version_id}/pdf")
async def download_resume_pdf(version_id: int):
    """Generate and download resume as PDF."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Resume version not found")

    resume_data = json.loads(row["data"])
    photo = get_current_photo_data()
    pdf_bytes = generate_pdf(
        resume_data,
        template_id=row["template_id"],
        photo_data=bytes(photo["data"]) if photo else None,
        photo_content_type=photo["content_type"] if photo else None,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="resume_{version_id}.pdf"'
        },
    )


@router.get("/{version_id}/preview")
async def preview_resume_pdf(version_id: int):
    """Generate and return resume PDF for inline preview."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Resume version not found")

    resume_data = json.loads(row["data"])
    photo = get_current_photo_data()
    pdf_bytes = generate_pdf(
        resume_data,
        template_id=row["template_id"],
        photo_data=bytes(photo["data"]) if photo else None,
        photo_content_type=photo["content_type"] if photo else None,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="resume_{version_id}.pdf"'
        },
    )


@router.post("/{version_id}/set-current")
async def set_current_version(version_id: int):
    """Set a resume version as the current one."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume version not found")

    # Unset all current flags
    cursor.execute("UPDATE resume_versions SET is_current = FALSE")
    # Set the selected one as current
    cursor.execute(
        "UPDATE resume_versions SET is_current = TRUE WHERE id = ?", (version_id,)
    )
    conn.commit()
    conn.close()
    return {"message": f"Resume version {version_id} is now the current version"}
