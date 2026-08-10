import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from cover_letter_pdf import cover_letter_page_count, generate_cover_letter_pdf
from database import get_db
from models import (
    AIProvider,
    CompanyResearch,
    CoverLetter,
    CoverLetterAnalysis,
    CoverLetterAnalyzeRequest,
    CoverLetterContent,
    CoverLetterGenerateRequest,
    CoverLetterGenerationContext,
    CoverLetterResearchRequest,
    CoverLetterUpdate,
)
from openai_helper import (
    analyze_cover_letter as run_cover_letter_analysis,
    generate_cover_letter,
    research_company,
    resolve_cover_letter_angle_id,
    sanitize_company_research,
)


router = APIRouter(prefix="/api/cover-letters", tags=["cover letters"])


def _ordinal_date() -> str:
    now = datetime.now()
    day = now.day
    suffix = "th" if 10 < day % 100 < 14 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{now.strftime('%b')} {day}{suffix} {now.year}"


def _serialize(row) -> CoverLetter:
    generation_context = None
    if "generation_context" in row.keys() and row["generation_context"]:
        generation_context = json.loads(row["generation_context"])
    return CoverLetter(
        id=row["id"],
        resume_version_id=row["resume_version_id"],
        resume_version_name=row["resume_version_name"],
        company=row["company"],
        position=row["position"],
        source_url=row["source_url"],
        job_post=row["job_post"],
        content=json.loads(row["content"]),
        generation_context=generation_context,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=list[CoverLetter])
def list_cover_letters():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT cl.*, rv.name AS resume_version_name
        FROM cover_letters cl
        LEFT JOIN resume_versions rv ON rv.id = cl.resume_version_id
        ORDER BY cl.created_at DESC
        """
    ).fetchall()
    conn.close()
    return [_serialize(row) for row in rows]


@router.post("/{provider}/analyze", response_model=CoverLetterAnalysis)
def analyze_cover_letter(
    payload: CoverLetterAnalyzeRequest,
    provider: AIProvider = AIProvider.chatgpt,
):
    conn = get_db()
    try:
        resume = conn.execute(
            "SELECT data FROM resume_versions WHERE id = ?",
            (payload.resume_version_id,),
        ).fetchone()
    finally:
        conn.close()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume version not found")

    try:
        result = run_cover_letter_analysis(
            resume_data=json.loads(resume["data"]),
            job_post=payload.job_post,
            company=payload.company,
            position=payload.position,
            source_url=payload.source_url,
            instructions=payload.instructions,
            provider=provider.value,
        )
        return CoverLetterAnalysis(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Cover letter analysis failed: {exc}",
        ) from exc


@router.post("/{provider}/research", response_model=CompanyResearch)
def research_cover_letter_company(
    payload: CoverLetterResearchRequest,
    provider: AIProvider = AIProvider.chatgpt,
):
    try:
        result = research_company(
            company=payload.company,
            position=payload.position,
            role_summary=payload.role_summary,
            source_url=payload.source_url,
            provider=provider.value,
        )
        return CompanyResearch(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Company research failed: {exc}",
        ) from exc


@router.post("/{provider}/generate", response_model=CoverLetter, status_code=201)
def create_cover_letter(
    payload: CoverLetterGenerateRequest,
    provider: AIProvider = AIProvider.chatgpt,
):
    conn = get_db()
    try:
        resume = conn.execute(
            "SELECT id, name, data FROM resume_versions WHERE id = ?",
            (payload.resume_version_id,),
        ).fetchone()
    finally:
        conn.close()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume version not found")

    resume_data = json.loads(resume["data"])
    analysis_data = (
        payload.analysis.model_dump(mode="json") if payload.analysis else None
    )
    research_data = sanitize_company_research(
        payload.research.model_dump(mode="json") if payload.research else None
    )
    answers_data = [answer.model_dump(mode="json") for answer in payload.answers]
    effective_angle_id = resolve_cover_letter_angle_id(
        analysis_data,
        payload.selected_angle_id,
    )
    generation_context = CoverLetterGenerationContext(
        provider=provider,
        source_url=payload.source_url,
        instructions=payload.instructions,
        analysis=analysis_data,
        research=research_data,
        answers=answers_data,
        selected_angle_id=effective_angle_id,
    )

    try:
        generated = generate_cover_letter(
            resume_data=resume_data,
            job_post=payload.job_post,
            current_date=_ordinal_date(),
            company=payload.company,
            position=payload.position,
            instructions=payload.instructions,
            source_url=payload.source_url,
            analysis=analysis_data,
            research=research_data,
            answers=answers_data,
            selected_angle_id=effective_angle_id,
            provider=provider.value,
        )
        content = CoverLetterContent(**generated)
        if cover_letter_page_count(content.model_dump(), resume_data) > 1:
            raise ValueError(
                "The generated letter exceeded one A4 page, so it was rejected and not saved. "
                "Please generate it again."
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {exc}") from exc

    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO cover_letters
                (
                    resume_version_id, company, position, source_url, job_post,
                    content, generation_context
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.resume_version_id,
                content.company,
                content.position,
                payload.source_url,
                payload.job_post,
                content.model_dump_json(),
                generation_context.model_dump_json(),
            ),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT cl.*, rv.name AS resume_version_name
            FROM cover_letters cl
            LEFT JOIN resume_versions rv ON rv.id = cl.resume_version_id
            WHERE cl.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
    finally:
        conn.close()
    return _serialize(row)


@router.get("/{letter_id}", response_model=CoverLetter)
def get_cover_letter(letter_id: int):
    conn = get_db()
    row = conn.execute(
        """
        SELECT cl.*, rv.name AS resume_version_name
        FROM cover_letters cl
        LEFT JOIN resume_versions rv ON rv.id = cl.resume_version_id
        WHERE cl.id = ?
        """,
        (letter_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return _serialize(row)


@router.put("/{letter_id}", response_model=CoverLetter)
def update_cover_letter(letter_id: int, update: CoverLetterUpdate):
    conn = get_db()
    row = conn.execute("SELECT * FROM cover_letters WHERE id = ?", (letter_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Cover letter not found")
    content = json.loads(row["content"])
    for key, value in update.model_dump(exclude_none=True).items():
        content[key] = value
    validated = CoverLetterContent(**content)
    conn.execute(
        """
        UPDATE cover_letters
        SET company = ?, position = ?, content = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            validated.company,
            validated.position,
            validated.model_dump_json(),
            datetime.now().isoformat(),
            letter_id,
        ),
    )
    conn.commit()
    updated = conn.execute(
        """
        SELECT cl.*, rv.name AS resume_version_name
        FROM cover_letters cl
        LEFT JOIN resume_versions rv ON rv.id = cl.resume_version_id
        WHERE cl.id = ?
        """,
        (letter_id,),
    ).fetchone()
    conn.close()
    return _serialize(updated)


@router.get("/{letter_id}/pdf")
def cover_letter_pdf(letter_id: int, download: bool = Query(default=False)):
    conn = get_db()
    row = conn.execute(
        """
        SELECT cl.*, rv.data AS resume_data
        FROM cover_letters cl
        JOIN resume_versions rv ON rv.id = cl.resume_version_id
        WHERE cl.id = ?
        """,
        (letter_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    pdf = generate_cover_letter_pdf(json.loads(row["content"]), json.loads(row["resume_data"]))
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="cover-letter-{letter_id}.pdf"'},
    )


@router.delete("/{letter_id}")
def delete_cover_letter(letter_id: int):
    conn = get_db()
    row = conn.execute("SELECT id FROM cover_letters WHERE id = ?", (letter_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Cover letter not found")
    conn.execute("DELETE FROM cover_letters WHERE id = ?", (letter_id,))
    conn.commit()
    conn.close()
    return {"message": "Cover letter deleted"}
