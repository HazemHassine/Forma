import json
from fastapi import APIRouter, HTTPException
from models import (
    ResumeData,
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
from factual_integrity import build_resume_evidence, validate_resume_edits
import context_engine

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


def _validate_tailored_data(conn, parent_version_id: int, candidate_data: dict, audit: dict | None) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM resume_versions WHERE id = ?", (parent_version_id,))
    parent = cursor.fetchone()
    if not parent:
        raise HTTPException(status_code=400, detail="Tailored versions require a valid source parent")
    # The API serializes ResumeData with defaults included, while older source
    # records may omit those default-valued fields. Normalize the parent with
    # the same schema before comparing so serialization defaults are never
    # mistaken for uncited factual edits.
    parent_data = ResumeData.model_validate(json.loads(parent["data"])).model_dump(mode="json")
    claim_evidence = {
        item.get("field_path"): item.get("evidence_ids", [])
        for item in (audit or {}).get("claim_audit", [])
        if isinstance(item, dict) and item.get("status") == "accepted" and item.get("field_path")
    }
    vault_evidence = (audit or {}).get("evidence_catalog") or context_engine.assemble_evidence(conn, max_items=1000)
    vault_evidence = [item for item in vault_evidence if str(item.get("id", "")).startswith("vault:")]
    validated, _, blocked = validate_resume_edits(
        parent_data, candidate_data, claim_evidence, vault_evidence
    )
    if blocked or validated != candidate_data:
        reasons = sorted({item.get("reason", "unsupported_edit") for item in blocked})
        raise HTTPException(
            status_code=409,
            detail="Tailored resume contains unsupported changes: " + ", ".join(reasons or ["unverified_change"]),
        )


def _serialize_version(row) -> ResumeVersion:
    return ResumeVersion(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        data=json.loads(row["data"]),
        created_at=row["created_at"],
        is_current=bool(row["is_current"]),
        template_id=row["template_id"] or "modern",
        version_kind=row["version_kind"] or "manual_source",
        parent_version_id=row["parent_version_id"],
        root_version_id=row["root_version_id"],
        tailoring_audit=json.loads(row["tailoring_audit"]) if row["tailoring_audit"] else None,
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
        "SELECT id, name, description, created_at, is_current, template_id, "
        "version_kind, parent_version_id, root_version_id "
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
            version_kind=row["version_kind"] or "manual_source",
            parent_version_id=row["parent_version_id"],
            root_version_id=row["root_version_id"],
        )
        for row in rows
    ]


@router.post("", response_model=ResumeVersion, status_code=201)
async def create_resume_version(version: ResumeVersionCreate):
    """Create a new resume version."""
    conn = get_db()
    cursor = conn.cursor()
    root_version_id = version.root_version_id
    if version.parent_version_id:
        cursor.execute(
            "SELECT id, root_version_id, version_kind FROM resume_versions WHERE id = ?",
            (version.parent_version_id,),
        )
        parent = cursor.fetchone()
        if not parent:
            conn.close()
            raise HTTPException(status_code=400, detail="Parent resume version not found")
        if (
            version.version_kind in {"tailored_draft", "tailored_final"}
            and parent["version_kind"] not in {"authoritative_source", "manual_source"}
        ):
            conn.close()
            raise HTTPException(
                status_code=409,
                detail="Tailored versions must be derived from an approved source resume",
            )
        root_version_id = parent["root_version_id"] or parent["id"]
    if version.version_kind in {"tailored_draft", "tailored_final"}:
        if not version.parent_version_id:
            conn.close()
            raise HTTPException(status_code=400, detail="Tailored versions require a source parent")
        parent_cursor = conn.cursor()
        parent_cursor.execute("SELECT data FROM resume_versions WHERE id = ?", (version.parent_version_id,))
        parent_data = ResumeData.model_validate(
            json.loads(parent_cursor.fetchone()["data"])
        ).model_dump(mode="json")
        canonical_audit = dict(version.tailoring_audit or {})
        canonical_audit["evidence_catalog"] = (
            build_resume_evidence(parent_data) + context_engine.assemble_evidence(conn, max_items=1000)
        )
        version.tailoring_audit = canonical_audit
        _validate_tailored_data(
            conn,
            version.parent_version_id,
            version.data.model_dump(mode="json"),
            canonical_audit,
        )
    cursor.execute(
        """
        INSERT INTO resume_versions (
            name, description, data, template_id, version_kind,
            parent_version_id, root_version_id, tailoring_audit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version.name, version.description, version.data.model_dump_json(),
            version.template_id.value, version.version_kind, version.parent_version_id,
            root_version_id, json.dumps(version.tailoring_audit) if version.tailoring_audit else None,
        ),
    )
    conn.commit()
    version_id = cursor.lastrowid
    if root_version_id is None:
        cursor.execute(
            "UPDATE resume_versions SET root_version_id = ? WHERE id = ?",
            (version_id, version_id),
        )
        conn.commit()
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
    existing_audit = json.loads(row["tailoring_audit"]) if row["tailoring_audit"] else {}
    audit_payload = existing_audit
    if update.tailoring_audit is not None:
        audit_payload = {
            **existing_audit,
            "claim_audit": update.tailoring_audit.get("claim_audit", existing_audit.get("claim_audit", [])),
            "blocked_edits": update.tailoring_audit.get("blocked_edits", existing_audit.get("blocked_edits", [])),
        }
    new_tailoring_audit = json.dumps(audit_payload) if audit_payload else None
    new_version_kind = update.version_kind or row["version_kind"]
    if update.version_kind is not None:
        allowed_transition = (
            update.version_kind == row["version_kind"]
            or (row["version_kind"] == "tailored_draft" and update.version_kind == "tailored_final")
        )
        if not allowed_transition:
            conn.close()
            raise HTTPException(status_code=409, detail="Resume version provenance cannot be rewritten")
    if update.data is not None and row["version_kind"] in {"tailored_draft", "tailored_final"}:
        _validate_tailored_data(
            conn,
            row["parent_version_id"],
            update.data.model_dump(mode="json"),
            audit_payload,
        )

    cursor.execute(
        "UPDATE resume_versions SET name = ?, description = ?, data = ?, template_id = ?, tailoring_audit = ?, version_kind = ? WHERE id = ?",
        (new_name, new_description, new_data, new_template_id, new_tailoring_audit, new_version_kind, version_id),
    )
    conn.commit()

    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    conn.close()
    return _serialize_version(row)


@router.post("/{version_id}/mark-authoritative", response_model=ResumeVersion)
async def mark_resume_authoritative(version_id: int):
    """Explicitly approve a legacy or manual resume as factual source material."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Resume version not found")
    if row["version_kind"] in {"tailored_draft", "tailored_final"}:
        conn.close()
        raise HTTPException(status_code=409, detail="Generated versions cannot become authoritative evidence")
    cursor.execute(
        """
        UPDATE resume_versions
        SET version_kind = 'authoritative_source', parent_version_id = NULL,
            root_version_id = id, tailoring_audit = NULL
        WHERE id = ?
        """,
        (version_id,),
    )
    conn.commit()
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
    updated = cursor.fetchone()
    conn.close()
    return _serialize_version(updated)


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
        """
        INSERT INTO resume_versions (
            name, description, data, template_id, version_kind,
            parent_version_id, root_version_id, tailoring_audit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_name, row["description"], row["data"], row["template_id"],
            row["version_kind"], row["parent_version_id"], row["root_version_id"],
            row["tailoring_audit"],
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.execute("SELECT * FROM resume_versions WHERE id = ?", (new_id,))
    new_row = cursor.fetchone()
    conn.close()
    return _serialize_version(new_row)


@router.get("/{version_id}/pdf")
def download_resume_pdf(version_id: int):
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
def preview_resume_pdf(version_id: int):
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
