import os
from fastapi import APIRouter, UploadFile, File, HTTPException

from config import STATIC_DIR

router = APIRouter(prefix="/api/photos", tags=["photos"])

PHOTO_FILENAME = "profile.jpg"


@router.post("/upload")
async def upload_photo(file: UploadFile = File(...)):
    """Upload a new profile photo."""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Allowed: {', '.join(allowed_types)}",
        )

    # Ensure static directory exists
    os.makedirs(STATIC_DIR, exist_ok=True)

    # Save the file
    photo_path = os.path.join(STATIC_DIR, PHOTO_FILENAME)
    with open(photo_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    return {"path": f"/static/{PHOTO_FILENAME}", "message": "Photo uploaded successfully"}


@router.get("/current")
async def get_current_photo():
    """Get the current profile photo URL."""
    photo_path = os.path.join(STATIC_DIR, PHOTO_FILENAME)
    if os.path.exists(photo_path):
        return {"path": f"/static/{PHOTO_FILENAME}", "exists": True}
    return {"path": None, "exists": False}
