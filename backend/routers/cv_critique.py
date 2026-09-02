import json
from typing import Optional
from fastapi import APIRouter, HTTPException

from cv_critic import critique_cv
from database import get_db
from models import (
    AIProvider,
    CVCritiqueRequest,
    CVCritiqueResponse,
    CVCritiqueSummary,
    CritiqueReport,
)

router = APIRouter(prefix="/api/cv-critique", tags=["cv critique"])


def _serialize_critique_row(row) -> CVCritiqueResponse:
    critique_data = row["critique_data"]
    if isinstance(critique_data, str):
        report_dict = json.loads(critique_data)
    else:
        report_dict = critique_data

    return CVCritiqueResponse(
        id=row["id"],
        resume_version_id=row["resume_version_id"],
        target_role=row["target_role"],
        job_description=row["job_description"],
        provider=row["provider"],
        overall_score=row["overall_score"],
        summary=row["summary"],
        report=CritiqueReport.model_validate(report_dict),
        created_at=str(row["created_at"]),
    )


def _serialize_critique_summary(row) -> CVCritiqueSummary:
    critique_data = row["critique_data"]
    if isinstance(critique_data, str):
        report_dict = json.loads(critique_data)
    else:
        report_dict = critique_data

    return CVCritiqueSummary(
        id=row["id"],
        resume_version_id=row["resume_version_id"],
        target_role=row["target_role"],
        provider=row["provider"],
        overall_score=row["overall_score"],
        verdict=report_dict.get("verdict", ""),
        critical_count=report_dict.get("critical_count", 0),
        warning_count=report_dict.get("warning_count", 0),
        created_at=str(row["created_at"]),
    )


@router.post("/{provider}", response_model=CVCritiqueResponse)
def create_cv_critique(provider: AIProvider, request: CVCritiqueRequest):
    """Run an in-depth critique on a resume version and save the report."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, data FROM resume_versions WHERE id = ?",
        (request.resume_version_id,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail=f"Resume version {request.resume_version_id} not found",
        )

    resume_data = json.loads(row["data"])

    try:
        report = critique_cv(
            resume_data=resume_data,
            target_role=request.target_role,
            job_description=request.job_description,
            instructions=request.instructions,
            provider=provider.value,
        )
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Critique failed: {str(e)}")

    overall_score = report.get("overall_score", 0)
    summary = report.get("summary", "")

    cursor.execute(
        """
        INSERT INTO cv_critiques
            (resume_version_id, target_role, job_description, provider, overall_score, summary, critique_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.resume_version_id,
            request.target_role,
            request.job_description,
            provider.value,
            overall_score,
            summary,
            json.dumps(report),
        ),
    )
    critique_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM cv_critiques WHERE id = ?", (critique_id,))
    created_row = cursor.fetchone()
    conn.close()

    return _serialize_critique_row(created_row)


@router.get("/version/{version_id}", response_model=list[CVCritiqueSummary])
def list_critiques_for_version(version_id: int):
    """List historical critiques generated for a specific resume version."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM cv_critiques
        WHERE resume_version_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (version_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [_serialize_critique_summary(r) for r in rows]


@router.get("/{critique_id}", response_model=CVCritiqueResponse)
def get_critique(critique_id: int):
    """Fetch complete details of a specific critique report."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cv_critiques WHERE id = ?", (critique_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Critique report not found")
    return _serialize_critique_row(row)


@router.delete("/{critique_id}")
def delete_critique(critique_id: int):
    """Delete a critique report."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM cv_critiques WHERE id = ?", (critique_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Critique report not found")

    cursor.execute("DELETE FROM cv_critiques WHERE id = ?", (critique_id,))
    conn.commit()
    conn.close()
    return {"message": "Critique deleted successfully"}
