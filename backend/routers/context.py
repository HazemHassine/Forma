import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import (
    AIProvider,
    ContextItem,
    ContextItemCreate,
    ContextItemUpdate,
    ContextPreviewResponse,
    ContextProfile,
    ContextSource,
    ContextSourceCreate,
    ContextSourceUpdate,
    ContextStats,
    ContextSynthesizeRequest,
    ContextSynthesizeResponse,
)
import context_engine

router = APIRouter(prefix="/api/context", tags=["context vault"])


# ============================================================================
# Context Sources (Intake Layer)
# ============================================================================

@router.get("/sources", response_model=list[ContextSource])
def get_sources(active_only: bool = Query(False)):
    """List all raw candidate context sources (dumps, links, notes)."""
    conn = get_db()
    try:
        return context_engine.list_sources(conn, active_only=active_only)
    finally:
        conn.close()


@router.post("/sources", response_model=ContextSource, status_code=201)
def add_source(data: ContextSourceCreate):
    """Add a new raw context source (AI information dump, link, portfolio doc)."""
    conn = get_db()
    try:
        source_id = context_engine.create_source(conn, data)
        created = context_engine.get_source(conn, source_id)
        if not created:
            raise HTTPException(status_code=500, detail="Failed to retrieve created source")
        return created
    finally:
        conn.close()


@router.get("/sources/{source_id}", response_model=ContextSource)
def get_source_by_id(source_id: int):
    """Fetch details of a single context source."""
    conn = get_db()
    try:
        source = context_engine.get_source(conn, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        return source
    finally:
        conn.close()


@router.put("/sources/{source_id}", response_model=ContextSource)
def update_source_by_id(source_id: int, data: ContextSourceUpdate):
    """Update title, content, url or active state of a context source."""
    conn = get_db()
    try:
        updated = context_engine.update_source(conn, source_id, data)
        if not updated:
            raise HTTPException(status_code=404, detail="Source not found")
        return updated
    finally:
        conn.close()


@router.delete("/sources/{source_id}")
def delete_source_by_id(source_id: int):
    """Delete a context source."""
    conn = get_db()
    try:
        deleted = context_engine.delete_source(conn, source_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Source not found")
        return {"message": "Context source deleted successfully"}
    finally:
        conn.close()


# ============================================================================
# Context Items (Knowledge Cards Layer)
# ============================================================================

@router.get("/items", response_model=list[ContextItem])
def get_items(
    category: Optional[str] = Query(None),
    active_only: bool = Query(False),
    query: Optional[str] = Query(None),
):
    """List structured context knowledge cards with optional category and search filters."""
    conn = get_db()
    try:
        return context_engine.list_items(
            conn,
            category=category,
            active_only=active_only,
            query=query,
        )
    finally:
        conn.close()


@router.post("/items", response_model=ContextItem, status_code=201)
def add_item(data: ContextItemCreate):
    """Manually add an individual context fact or project card to the vault."""
    conn = get_db()
    try:
        item_id = context_engine.create_item(conn, data)
        created = context_engine.get_item(conn, item_id)
        if not created:
            raise HTTPException(status_code=500, detail="Failed to retrieve created item")
        return created
    finally:
        conn.close()


@router.get("/items/{item_id}", response_model=ContextItem)
def get_item_by_id(item_id: int):
    """Fetch an individual context item."""
    conn = get_db()
    try:
        item = context_engine.get_item(conn, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    finally:
        conn.close()


@router.put("/items/{item_id}", response_model=ContextItem)
def update_item_by_id(item_id: int, data: ContextItemUpdate):
    """Update content, title, tags or active state of a context item."""
    conn = get_db()
    try:
        updated = context_engine.update_item(conn, item_id, data)
        if not updated:
            raise HTTPException(status_code=404, detail="Item not found")
        return updated
    finally:
        conn.close()


@router.post("/items/{item_id}/toggle", response_model=ContextItem)
def toggle_item_active(item_id: int):
    """Toggle whether a context item is active/used in AI generations."""
    conn = get_db()
    try:
        toggled = context_engine.toggle_item(conn, item_id)
        if not toggled:
            raise HTTPException(status_code=404, detail="Item not found")
        return toggled
    finally:
        conn.close()


@router.delete("/items/{item_id}")
def delete_item_by_id(item_id: int):
    """Delete an individual context knowledge item."""
    conn = get_db()
    try:
        deleted = context_engine.delete_item(conn, item_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"message": "Context item deleted successfully"}
    finally:
        conn.close()


# ============================================================================
# Profile, Synthesis & Assembly Layer
# ============================================================================

@router.get("/profile", response_model=Optional[ContextProfile])
def get_executive_profile():
    """Fetch the synthesized executive persona and differentiators."""
    conn = get_db()
    try:
        return context_engine.get_profile(conn)
    finally:
        conn.close()


@router.get("/stats", response_model=ContextStats)
def get_context_stats():
    """Get metrics on total sources, items, category breakdown and token estimates."""
    conn = get_db()
    try:
        return context_engine.get_stats(conn)
    finally:
        conn.close()


@router.post("/{provider}/synthesize", response_model=ContextSynthesizeResponse)
def synthesize_sources(
    provider: AIProvider,
    request: ContextSynthesizeRequest = ContextSynthesizeRequest(),
):
    """Run AI knowledge distillation across all active sources to produce structured context cards."""
    conn = get_db()
    try:
        result = context_engine.synthesize_context(
            conn=conn,
            provider=provider.value,
            additional_notes=request.additional_notes,
            replace_existing=request.replace_existing,
        )
        return ContextSynthesizeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context synthesis failed: {str(e)}")
    finally:
        conn.close()


@router.get("/preview", response_model=ContextPreviewResponse)
def preview_assembled_context(
    target_role: Optional[str] = Query(None),
    job_description: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    max_items: int = Query(15),
):
    """Preview the exact bounded context block injected into AI prompts."""
    conn = get_db()
    try:
        prompt = context_engine.assemble_context(
            conn,
            target_role=target_role,
            job_description=job_description,
            company=company,
            max_items=max_items,
        )
        tokens = max(1, len(prompt) // 4) if prompt else 0
        active_items = context_engine.list_items(conn, active_only=True)
        return ContextPreviewResponse(
            assembled_prompt=prompt,
            item_count=len(active_items),
            estimated_tokens=tokens,
        )
    finally:
        conn.close()


@router.post("/import-resume/{resume_version_id}", response_model=ContextSource, status_code=201)
def import_from_resume(resume_version_id: int):
    """Bootstrap context vault by importing an existing resume version as a source."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, data FROM resume_versions WHERE id = ?", (resume_version_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Resume version not found")

        resume_json = row["data"]
        try:
            resume_data = json.loads(resume_json)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON in resume version")

        # Convert resume JSON into a clean, comprehensive text dump
        sections = []
        info = resume_data.get("personal_info", {})
        if info.get("name"):
            sections.append(f"Name: {info.get('name')}")
        if info.get("title"):
            sections.append(f"Title: {info.get('title')}")
        if resume_data.get("about_me"):
            sections.append(f"Summary:\n{resume_data.get('about_me')}")

        works = resume_data.get("work_experience", [])
        if works:
            sections.append("Work Experience:")
            for w in works:
                bullets = "\n".join(f"  - {b}" for b in w.get("bullets", []))
                sections.append(f"- {w.get('role')} at {w.get('company')} ({w.get('dates')}):\n{bullets}")

        projects = resume_data.get("projects", [])
        if projects:
            sections.append("Projects:")
            for p in projects:
                bullets = "\n".join(f"  - {b}" for b in p.get("bullets", []))
                sections.append(f"- {p.get('name')} ({p.get('type')}, Stack: {p.get('stack')}):\n  {p.get('description')}\n{bullets}")

        skills = resume_data.get("skills", [])
        if skills:
            sections.append("Skills:")
            for s in skills:
                sections.append(f"- {s.get('category')}: {', '.join(s.get('items', []))}")

        research = resume_data.get("research", [])
        if research:
            sections.append("Research:")
            for r in research:
                sections.append(f"- {r.get('title')} ({r.get('institution')}): {r.get('description')}")

        content = "\n\n".join(sections)
        source_data = ContextSourceCreate(
            title=f"Imported from Resume: {row['name']}",
            source_type="resume",
            content=content,
            is_active=True,
        )
        source_id = context_engine.create_source(conn, source_data)
        created = context_engine.get_source(conn, source_id)
        if not created:
            raise HTTPException(status_code=500, detail="Failed to retrieve imported source")
        return created
    finally:
        conn.close()
