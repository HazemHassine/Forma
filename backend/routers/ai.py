import json
from fastapi import APIRouter, HTTPException
from models import AISuggestRequest, AISuggestResponse, OptimizeRequest, OptimizeResponse, ResumeData
from ai_helper import suggest_improvement, optimize_resume
from database import get_db

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/suggest", response_model=AISuggestResponse)
def suggest(request: AISuggestRequest):
    """Get AI-powered improvement suggestions for a resume section."""
    try:
        suggestion = suggest_improvement(
            section_type=request.section_type,
            current_content=request.current_content,
            job_description=request.job_description,
            feedback=request.feedback,
        )
        return AISuggestResponse(suggestion=suggestion)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI suggestion failed: {str(e)}",
        )


@router.post("/optimize", response_model=OptimizeResponse)
def optimize(request: OptimizeRequest):
    """Optimize an entire resume for a specific job description."""
    try:
        # Load the resume from the database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT data FROM resume_versions WHERE id = ?",
            (request.resume_version_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Resume version {request.resume_version_id} not found",
            )

        original_data = json.loads(row["data"])

        # Validate with Pydantic
        original_resume = ResumeData(**original_data)

        # Optimize
        optimized_data = optimize_resume(
            resume_data=original_data,
            job_description=request.job_description,
            target_role=request.target_role,
            company=request.company,
            instructions=request.instructions,
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
