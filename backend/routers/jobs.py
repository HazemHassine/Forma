from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from database import get_db
from models import (
    JobApplication,
    JobApplicationCreate,
    JobApplicationUpdate,
    JobBulkStatusRequest,
    JobEvent,
    JobEventCreate,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Statuses that still need attention from the candidate.
ACTIVE_STATUSES = {"saved", "applied", "interviewing", "offer"}
# An application with no reply and no planned follow-up goes stale after this.
STALE_AFTER_DAYS = 14
WEEKS_OF_ACTIVITY = 8

# Optional free-text columns that an explicit null clears.
CLEARABLE_FIELDS = (
    "url",
    "notes",
    "job_description",
    "location",
    "salary",
    "contact",
    "next_step",
)

JOB_SELECT = """
    SELECT j.*, rv.name AS resume_version_name
    FROM job_applications j
    LEFT JOIN resume_versions rv ON j.resume_version_id = rv.id
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_date(value) -> date | None:
    """Read the calendar date from any stored date or timestamp string."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _company_key(value: str | None) -> str:
    return (value or "").strip().lower()


def _prepared_companies(cursor) -> tuple[set[str], set[str]]:
    """Companies that already have a saved cover letter or research report."""
    cursor.execute("SELECT DISTINCT company FROM cover_letters")
    letters = {_company_key(row["company"]) for row in cursor.fetchall()}
    cursor.execute("SELECT DISTINCT company FROM company_research_reports")
    research = {_company_key(row["company"]) for row in cursor.fetchall()}
    return letters, research


def _row_to_job(row, letters: set[str] = frozenset(), research: set[str] = frozenset()) -> JobApplication:
    row = dict(row)
    company_key = _company_key(row["company"])
    return JobApplication(
        id=row["id"],
        company=row["company"],
        position=row["position"],
        url=row["url"],
        status=row["status"] or "applied",
        resume_version_id=row["resume_version_id"],
        resume_version_name=row.get("resume_version_name"),
        applied_at=str(row["applied_at"]),
        notes=row["notes"],
        updated_at=row["updated_at"],
        job_description=row.get("job_description"),
        location=row.get("location"),
        salary=row.get("salary"),
        contact=row.get("contact"),
        next_step=row.get("next_step"),
        follow_up_at=str(row["follow_up_at"])[:10] if row.get("follow_up_at") else None,
        status_changed_at=row.get("status_changed_at"),
        has_cover_letter=bool(company_key) and company_key in letters,
        has_research=bool(company_key) and company_key in research,
    )


def _load_job(cursor, job_id: int) -> JobApplication | None:
    cursor.execute(f"{JOB_SELECT} WHERE j.id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        return None
    letters, research = _prepared_companies(cursor)
    return _row_to_job(row, letters, research)


def _load_all(cursor) -> list[JobApplication]:
    cursor.execute(f"{JOB_SELECT} ORDER BY j.applied_at DESC, j.id DESC")
    rows = cursor.fetchall()
    letters, research = _prepared_companies(cursor)
    return [_row_to_job(row, letters, research) for row in rows]


def _log_event(cursor, job_id: int, kind: str, detail: str | None) -> None:
    cursor.execute(
        "INSERT INTO job_events (job_id, kind, detail, created_at) VALUES (?, ?, ?, ?)",
        (job_id, kind, detail, _now()),
    )


def _require_resume_version(cursor, conn, resume_version_id: int) -> None:
    cursor.execute("SELECT id FROM resume_versions WHERE id = ?", (resume_version_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Resume version not found")


def _last_activity(job: JobApplication) -> date | None:
    dates = [d for d in (_as_date(job.applied_at), _as_date(job.status_changed_at)) if d]
    return max(dates) if dates else None


def build_overview(jobs: list[JobApplication], interviewed_ids: set[int], today: date) -> dict:
    """Summarise the pipeline into what needs doing and how the search is going."""
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.status] = counts.get(job.status, 0) + 1

    due, upcoming, stale, saved = [], [], [], []
    for job in jobs:
        if job.status not in ACTIVE_STATUSES:
            continue
        follow_up = _as_date(job.follow_up_at)
        if job.status == "saved":
            saved.append(job)
        if follow_up:
            if follow_up <= today:
                due.append(job)
            elif follow_up <= today + timedelta(days=7):
                upcoming.append(job)
            continue
        if job.status == "applied":
            last = _last_activity(job)
            if last and (today - last).days >= STALE_AFTER_DAYS:
                stale.append(job)

    due.sort(key=lambda job: job.follow_up_at or "")
    upcoming.sort(key=lambda job: job.follow_up_at or "")
    stale.sort(key=lambda job: _last_activity(job) or today)

    week_start = today - timedelta(days=today.weekday())
    weekly = []
    for offset in range(WEEKS_OF_ACTIVITY - 1, -1, -1):
        start = week_start - timedelta(weeks=offset)
        end = start + timedelta(days=7)
        count = sum(
            1
            for job in jobs
            if job.status != "saved"
            and (applied := _as_date(job.applied_at)) is not None
            and start <= applied < end
        )
        weekly.append({"week_start": start.isoformat(), "count": count})

    submitted = [job for job in jobs if job.status != "saved"]
    responded = [job for job in submitted if job.status in {"interviewing", "offer", "rejected"}]
    interviewed = [
        job for job in submitted
        if job.status in {"interviewing", "offer"} or job.id in interviewed_ids
    ]

    def rate(part: list, whole: list) -> int | None:
        return round(100 * len(part) / len(whole)) if whole else None

    return {
        "today": today.isoformat(),
        "counts": counts,
        "total": len(jobs),
        "active": sum(1 for job in jobs if job.status in ACTIVE_STATUSES),
        "submitted": len(submitted),
        "applied_this_week": weekly[-1]["count"],
        "response_rate": rate(responded, submitted),
        "interview_rate": rate(interviewed, submitted),
        "stale_after_days": STALE_AFTER_DAYS,
        "due": due,
        "upcoming": upcoming,
        "stale": stale,
        "saved": saved,
        "weekly": weekly,
    }


@router.get("/stats")
def get_job_stats():
    """Get job application statistics by status."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, COUNT(*) as count FROM job_applications GROUP BY status"
    )
    rows = cursor.fetchall()
    conn.close()

    stats = {row["status"]: row["count"] for row in rows}
    stats["total"] = sum(stats.values())
    return stats


@router.get("/overview")
def get_job_overview():
    """What needs attention today, plus pipeline and activity numbers."""
    conn = get_db()
    cursor = conn.cursor()
    jobs = _load_all(cursor)
    cursor.execute(
        "SELECT DISTINCT job_id FROM job_events WHERE kind = 'status' AND detail LIKE ?",
        ("%→ interviewing",),
    )
    interviewed_ids = {row["job_id"] for row in cursor.fetchall()}
    conn.close()
    return build_overview(jobs, interviewed_ids, date.today())


@router.get("", response_model=list[JobApplication])
def list_job_applications():
    """List all job applications with resume version names."""
    conn = get_db()
    cursor = conn.cursor()
    jobs = _load_all(cursor)
    conn.close()
    return jobs


@router.post("", response_model=JobApplication, status_code=201)
def create_job_application(job: JobApplicationCreate):
    """Create a new job application."""
    company = _clean(job.company)
    position = _clean(job.position)
    if not company or not position:
        raise HTTPException(status_code=422, detail="Company and position are required")

    conn = get_db()
    cursor = conn.cursor()
    if job.resume_version_id is not None:
        _require_resume_version(cursor, conn, job.resume_version_id)

    # status_changed_at stays empty until the status really changes, so an
    # application logged late is aged from the day it was sent, not from today.
    cursor.execute(
        """
        INSERT INTO job_applications (
            company, position, url, status, resume_version_id, applied_at, notes,
            job_description, location, salary, contact, next_step, follow_up_at
        )
        VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company,
            position,
            _clean(job.url),
            job.status.value,
            job.resume_version_id,
            job.applied_at.isoformat() if job.applied_at is not None else None,
            _clean(job.notes),
            _clean(job.job_description),
            _clean(job.location),
            _clean(job.salary),
            _clean(job.contact),
            _clean(job.next_step),
            job.follow_up_at.isoformat() if job.follow_up_at is not None else None,
        ),
    )
    job_id = cursor.lastrowid
    _log_event(cursor, job_id, "created", job.status.value)
    conn.commit()

    created = _load_job(cursor, job_id)
    conn.close()
    return created


@router.post("/bulk-status")
def bulk_update_status(request: JobBulkStatusRequest):
    """Move several applications to one status, e.g. closing out old ones."""
    conn = get_db()
    cursor = conn.cursor()
    now = _now()
    updated = 0
    for job_id in dict.fromkeys(request.ids):
        cursor.execute("SELECT status FROM job_applications WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if not row or row["status"] == request.status.value:
            continue
        clear_follow_up = request.status.value not in ACTIVE_STATUSES
        cursor.execute(
            f"""
            UPDATE job_applications
            SET status = ?, status_changed_at = ?, updated_at = ?
                {", follow_up_at = NULL" if clear_follow_up else ""}
            WHERE id = ?
            """,
            (request.status.value, now, now, job_id),
        )
        _log_event(cursor, job_id, "status", f"{row['status']} → {request.status.value}")
        updated += 1
    conn.commit()
    conn.close()
    return {"updated": updated}


@router.get("/{job_id}", response_model=JobApplication)
def get_job_application(job_id: int):
    """Get a single job application."""
    conn = get_db()
    cursor = conn.cursor()
    job = _load_job(cursor, job_id)
    conn.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job application not found")
    return job


@router.put("/{job_id}", response_model=JobApplication)
def update_job_application(job_id: int, update: JobApplicationUpdate):
    """Update a job application. Omitted fields are kept as they are."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_applications WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Job application not found")
    row = dict(row)

    fields_set = update.model_fields_set

    # An explicit null removes the resume association. An omitted field keeps it.
    if "resume_version_id" in fields_set and update.resume_version_id is not None:
        _require_resume_version(cursor, conn, update.resume_version_id)

    old_status = row["status"] or "applied"
    new_status = update.status.value if update.status is not None else old_status
    status_changed = new_status != old_status

    values = {
        "company": _clean(update.company) or row["company"],
        "position": _clean(update.position) or row["position"],
        "status": new_status,
        "resume_version_id": (
            update.resume_version_id
            if "resume_version_id" in fields_set
            else row["resume_version_id"]
        ),
        "applied_at": row["applied_at"],
        "follow_up_at": row.get("follow_up_at"),
        "status_changed_at": row.get("status_changed_at"),
    }
    for field in CLEARABLE_FIELDS:
        values[field] = (
            _clean(getattr(update, field)) if field in fields_set else row.get(field)
        )

    if "applied_at" in fields_set and update.applied_at is not None:
        values["applied_at"] = update.applied_at.isoformat()
    elif status_changed and old_status == "saved" and new_status == "applied":
        # A saved job becomes a real application today.
        values["applied_at"] = date.today().isoformat()

    if "follow_up_at" in fields_set:
        values["follow_up_at"] = (
            update.follow_up_at.isoformat() if update.follow_up_at is not None else None
        )
    elif status_changed and new_status not in ACTIVE_STATUSES:
        # Nothing left to chase once an application is closed.
        values["follow_up_at"] = None

    now = _now()
    if status_changed:
        values["status_changed_at"] = now
    values["updated_at"] = now

    columns = list(values)
    cursor.execute(
        f"UPDATE job_applications SET {', '.join(f'{column} = ?' for column in columns)} WHERE id = ?",
        (*(values[column] for column in columns), job_id),
    )
    if status_changed:
        _log_event(cursor, job_id, "status", f"{old_status} → {new_status}")
    conn.commit()

    updated = _load_job(cursor, job_id)
    conn.close()
    return updated


@router.delete("/{job_id}")
def delete_job_application(job_id: int):
    """Delete a job application and its activity log."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM job_applications WHERE id = ?", (job_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Job application not found")
    cursor.execute("DELETE FROM job_events WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM job_applications WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return {"message": "Job application deleted"}


@router.get("/{job_id}/events", response_model=list[JobEvent])
def list_job_events(job_id: int):
    """Activity log for one application, newest first."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM job_events WHERE job_id = ? ORDER BY id DESC", (job_id,)
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return [
        JobEvent(
            id=row["id"],
            job_id=row["job_id"],
            kind=row["kind"],
            detail=row["detail"],
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


@router.post("/{job_id}/events", response_model=JobEvent, status_code=201)
def add_job_event(job_id: int, event: JobEventCreate):
    """Log a note against an application: a call, an email, an interview."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM job_applications WHERE id = ?", (job_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Job application not found")
    now = _now()
    cursor.execute(
        "INSERT INTO job_events (job_id, kind, detail, created_at) VALUES (?, ?, ?, ?)",
        (job_id, "note", event.detail.strip(), now),
    )
    event_id = cursor.lastrowid
    cursor.execute(
        "UPDATE job_applications SET updated_at = ? WHERE id = ?", (now, job_id)
    )
    conn.commit()
    conn.close()
    return JobEvent(
        id=event_id, job_id=job_id, kind="note", detail=event.detail.strip(), created_at=now
    )
