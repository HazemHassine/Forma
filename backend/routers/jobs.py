import json
from fastapi import APIRouter, HTTPException
from models import JobApplication, JobApplicationCreate, JobApplicationUpdate
from database import get_db
from datetime import datetime

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/stats")
async def get_job_stats():
    """Get job application statistics by status."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, COUNT(*) as count FROM job_applications GROUP BY status"
    )
    rows = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as total FROM job_applications")
    total = cursor.fetchone()["total"]
    conn.close()

    stats = {row["status"]: row["count"] for row in rows}
    stats["total"] = total
    return stats


@router.get("", response_model=list[JobApplication])
async def list_job_applications():
    """List all job applications with resume version names."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT j.*, rv.name as resume_version_name
        FROM job_applications j
        LEFT JOIN resume_versions rv ON j.resume_version_id = rv.id
        ORDER BY j.applied_at DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        JobApplication(
            id=row["id"],
            company=row["company"],
            position=row["position"],
            url=row["url"],
            status=row["status"],
            resume_version_id=row["resume_version_id"],
            resume_version_name=row["resume_version_name"],
            applied_at=row["applied_at"],
            notes=row["notes"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.post("", response_model=JobApplication, status_code=201)
async def create_job_application(job: JobApplicationCreate):
    """Create a new job application."""
    conn = get_db()
    cursor = conn.cursor()

    # Validate resume_version_id if provided
    if job.resume_version_id is not None:
        cursor.execute(
            "SELECT id FROM resume_versions WHERE id = ?", (job.resume_version_id,)
        )
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Resume version not found")

    cursor.execute(
        """
        INSERT INTO job_applications (
            company, position, url, status, resume_version_id, applied_at, notes
        )
        VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
        """,
        (
            job.company,
            job.position,
            job.url,
            job.status,
            job.resume_version_id,
            job.applied_at.isoformat() if job.applied_at is not None else None,
            job.notes,
        ),
    )
    conn.commit()
    job_id = cursor.lastrowid

    cursor.execute(
        """
        SELECT j.*, rv.name as resume_version_name
        FROM job_applications j
        LEFT JOIN resume_versions rv ON j.resume_version_id = rv.id
        WHERE j.id = ?
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return JobApplication(
        id=row["id"],
        company=row["company"],
        position=row["position"],
        url=row["url"],
        status=row["status"],
        resume_version_id=row["resume_version_id"],
        resume_version_name=row["resume_version_name"],
        applied_at=row["applied_at"],
        notes=row["notes"],
        updated_at=row["updated_at"],
    )


@router.get("/{job_id}", response_model=JobApplication)
async def get_job_application(job_id: int):
    """Get a single job application."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT j.*, rv.name as resume_version_name
        FROM job_applications j
        LEFT JOIN resume_versions rv ON j.resume_version_id = rv.id
        WHERE j.id = ?
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job application not found")
    return JobApplication(
        id=row["id"],
        company=row["company"],
        position=row["position"],
        url=row["url"],
        status=row["status"],
        resume_version_id=row["resume_version_id"],
        resume_version_name=row["resume_version_name"],
        applied_at=row["applied_at"],
        notes=row["notes"],
        updated_at=row["updated_at"],
    )


@router.put("/{job_id}", response_model=JobApplication)
async def update_job_application(job_id: int, update: JobApplicationUpdate):
    """Update a job application."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_applications WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Job application not found")

    fields_set = update.model_fields_set

    # An explicit null removes the resume association. An omitted field keeps it.
    if (
        "resume_version_id" in fields_set
        and update.resume_version_id is not None
    ):
        cursor.execute(
            "SELECT id FROM resume_versions WHERE id = ?", (update.resume_version_id,)
        )
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Resume version not found")

    new_company = update.company if update.company is not None else row["company"]
    new_position = update.position if update.position is not None else row["position"]
    new_url = update.url if "url" in fields_set else row["url"]
    new_status = update.status if update.status is not None else row["status"]
    new_resume_id = (
        update.resume_version_id
        if "resume_version_id" in fields_set
        else row["resume_version_id"]
    )
    new_applied_at = (
        update.applied_at.isoformat()
        if "applied_at" in fields_set and update.applied_at is not None
        else row["applied_at"]
    )
    new_notes = update.notes if "notes" in fields_set else row["notes"]

    cursor.execute(
        """
        UPDATE job_applications
        SET company = ?, position = ?, url = ?, status = ?,
            resume_version_id = ?, applied_at = ?, notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            new_company,
            new_position,
            new_url,
            new_status,
            new_resume_id,
            new_applied_at,
            new_notes,
            datetime.now().isoformat(),
            job_id,
        ),
    )
    conn.commit()

    cursor.execute(
        """
        SELECT j.*, rv.name as resume_version_name
        FROM job_applications j
        LEFT JOIN resume_versions rv ON j.resume_version_id = rv.id
        WHERE j.id = ?
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return JobApplication(
        id=row["id"],
        company=row["company"],
        position=row["position"],
        url=row["url"],
        status=row["status"],
        resume_version_id=row["resume_version_id"],
        resume_version_name=row["resume_version_name"],
        applied_at=row["applied_at"],
        notes=row["notes"],
        updated_at=row["updated_at"],
    )


@router.delete("/{job_id}")
async def delete_job_application(job_id: int):
    """Delete a job application."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_applications WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Job application not found")
    cursor.execute("DELETE FROM job_applications WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return {"message": "Job application deleted"}
