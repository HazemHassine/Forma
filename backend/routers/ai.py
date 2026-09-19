import json
from fastapi import APIRouter, HTTPException
from models import (
    AIProvider,
    AISuggestRequest,
    AISuggestResponse,
    OptimizeRequest,
    OptimizeResponse,
    ResumeData,
)
from ai_helper import suggest_improvement, optimize_resume
from factual_integrity import build_resume_evidence, field_subject, validate_suggestion
from database import get_db

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/{provider}/suggest", response_model=AISuggestResponse)
def suggest(provider: AIProvider, request: AISuggestRequest):
    """Get AI-powered improvement suggestions for a resume section."""
    context_str = None
    vault_evidence = []
    resume_data = None
    if request.include_context:
        try:
            conn = get_db()
            try:
                import context_engine
                context_str = context_engine.assemble_context(
                    conn,
                    job_description=request.job_description,
                    max_items=10,
                )
                vault_evidence = context_engine.assemble_evidence(
                    conn,
                    job_description=request.job_description,
                    max_items=10,
                )
            finally:
                conn.close()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Verified context could not be loaded: {exc}",
            )

    if request.resume_version_id:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT data, version_kind FROM resume_versions WHERE id = ?",
                (request.resume_version_id,),
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Resume version not found")
            if row["version_kind"] in {"tailored_draft", "tailored_final", "legacy_unreviewed"}:
                raise HTTPException(
                    status_code=409,
                    detail="Regenerate from the authoritative source version, not a generated draft.",
                )
            resume_data = json.loads(row["data"])
        finally:
            conn.close()

    try:
        suggestion = suggest_improvement(
            section_type=request.section_type,
            current_content=request.current_content,
            job_description=request.job_description,
            feedback=request.feedback,
            context_data=context_str,
            provider=provider.value,
        )
        evidence = build_resume_evidence(resume_data or {}) + vault_evidence
        subject = (
            field_subject(resume_data, request.field_path)
            if resume_data and request.field_path
            else ("profile", "candidate")
        )
        compatible = evidence if subject[0] == "profile" else [
            item for item in evidence
            if item.get("subject_type") in {None, "profile", subject[0]}
            and (
                item.get("subject_type") != subject[0]
                or not item.get("subject_key")
                or item.get("subject_key") == subject[1]
            )
        ]
        if not compatible:
            compatible = [{
                "id": "current:field",
                "text": request.current_content,
                "subject_type": subject[0],
                "subject_key": subject[1],
            }]
        guarded, audit = validate_suggestion(
            request.current_content,
            suggestion,
            request.field_path or request.section_type,
            [item["id"] for item in compatible],
            compatible,
            subject,
        )
        if request.field_path and request.field_path.endswith(".bullets") and audit:
            lines = [
                line.strip().removeprefix("- ").strip()
                for line in guarded.splitlines()
                if line.strip()
            ]
            audit = [
                {
                    **audit[0],
                    "field_path": f"{request.field_path}.{index}",
                    "proposed_text": line,
                }
                for index, line in enumerate(lines)
            ]
        return AISuggestResponse(suggestion=guarded, claim_audit=audit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI suggestion failed: {str(e)}",
        )


@router.post("/{provider}/optimize", response_model=OptimizeResponse)
def optimize(provider: AIProvider, request: OptimizeRequest):
    """Optimize an entire resume for a specific job description."""
    try:
        # Load the resume from the database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT data, version_kind FROM resume_versions WHERE id = ?",
            (request.resume_version_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(
                status_code=404,
                detail=f"Resume version {request.resume_version_id} not found",
            )

        original_data = json.loads(row["data"])
        if row["version_kind"] in {"tailored_draft", "tailored_final", "legacy_unreviewed"}:
            conn.close()
            raise HTTPException(
                status_code=409,
                detail=(
                    "This resume is generated or has not been reviewed as an authoritative source. "
                    "Choose or approve an authoritative source version first."
                ),
            )

        context_str = None
        context_evidence = []
        if request.include_context:
            try:
                import context_engine
                context_str = context_engine.assemble_context(
                    conn,
                    target_role=request.target_role,
                    job_description=request.job_description,
                    company=request.company,
                    max_items=15,
                )
                context_evidence = context_engine.assemble_evidence(
                    conn,
                    target_role=request.target_role,
                    job_description=request.job_description,
                    company=request.company,
                    max_items=15,
                )
            except Exception as exc:
                conn.close()
                raise HTTPException(
                    status_code=503,
                    detail=f"Verified context could not be loaded: {exc}",
                )

        conn.close()

        # Validate with Pydantic
        original_resume = ResumeData(**original_data)

        # Optimize
        optimized_data = optimize_resume(
            resume_data=original_data,
            job_description=request.job_description,
            target_role=request.target_role,
            company=request.company,
            instructions=request.instructions,
            context_data=context_str,
            context_evidence=context_evidence,
            provider=provider.value,
        )

        # Validate optimized data with Pydantic
        optimized_resume = ResumeData(**optimized_data["resume"])

        return OptimizeResponse(
            original=original_resume,
            optimized=optimized_resume,
            match_summary=optimized_data.get("match_summary"),
            strengths=optimized_data.get("strengths", []),
            gaps=optimized_data.get("gaps", []),
            keywords_used=optimized_data.get("keywords_used", []),
            context_evidence_used=optimized_data.get("context_evidence_used", []),
            claim_audit=optimized_data.get("claim_audit", []),
            blocked_edits=optimized_data.get("blocked_edits", []),
            evidence_catalog=build_resume_evidence(original_data) + context_evidence,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Resume optimization failed: {str(e)}",
        )
