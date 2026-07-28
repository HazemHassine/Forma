from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import (
    CompanyResearchReport,
    CompanyResearchReportContent,
    CompanyResearchReportRequest,
    CompanyResearchReportSummary,
)
from openai_helper import research_company_report

router = APIRouter(
    prefix="/api/company-research",
    tags=["company research"],
)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _serialize_report(row) -> CompanyResearchReport:
    return CompanyResearchReport(
        id=row["id"],
        company=row["company"],
        website_url=row["website_url"],
        role=row["role"],
        job_context=row["job_context"],
        focus=row["focus"],
        report=CompanyResearchReportContent.model_validate_json(row["report"]),
        created_at=row["created_at"],
    )


def _serialize_summary(row) -> CompanyResearchReportSummary:
    report = CompanyResearchReportContent.model_validate_json(row["report"])
    return CompanyResearchReportSummary(
        id=row["id"],
        company=row["company"],
        legal_name=report.identity.legal_name,
        website=report.identity.website,
        role=row["role"],
        confidence=report.confidence,
        researched_at=report.researched_at,
        created_at=row["created_at"],
    )


@router.get("", response_model=list[CompanyResearchReportSummary])
def list_company_research_reports(
    company: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    clauses = []
    parameters = []
    company_filter = _optional_text(company)
    if company_filter:
        clauses.append("company LIKE ? COLLATE NOCASE")
        parameters.append(f"%{company_filter}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.extend([limit, offset])

    conn = get_db()
    try:
        rows = conn.execute(
            f"""
            SELECT *
            FROM company_research_reports
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            parameters,
        ).fetchall()
    finally:
        conn.close()
    return [_serialize_summary(row) for row in rows]


@router.post(
    "/research",
    response_model=CompanyResearchReport,
    status_code=201,
)
def create_company_research_report(payload: CompanyResearchReportRequest):
    company = payload.company.strip()
    if not company:
        raise HTTPException(status_code=400, detail="Company is required")

    website_url = _optional_text(payload.website_url)
    role = _optional_text(payload.role)
    job_context = _optional_text(payload.job_context)
    focus = _optional_text(payload.focus)

    try:
        result = research_company_report(
            company=company,
            website_url=website_url,
            role=role,
            job_context=job_context,
            focus=focus,
        )
        report = CompanyResearchReportContent(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Company research failed: {exc}",
        ) from exc

    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO company_research_reports
                (
                    company, website_url, role, job_context, focus, report,
                    researched_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company,
                website_url,
                role,
                job_context,
                focus,
                report.model_dump_json(),
                report.researched_at,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM company_research_reports WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    finally:
        conn.close()
    return _serialize_report(row)


@router.get("/{report_id}", response_model=CompanyResearchReport)
def get_company_research_report(report_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM company_research_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Company research report not found",
        )
    return _serialize_report(row)


@router.delete("/{report_id}")
def delete_company_research_report(report_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM company_research_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Company research report not found",
            )
        conn.execute(
            "DELETE FROM company_research_reports WHERE id = ?",
            (report_id,),
        )
        conn.commit()
    finally:
        conn.close()
    return {"message": "Company research report deleted"}
