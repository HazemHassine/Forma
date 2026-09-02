import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from fastapi.responses import FileResponse

from config import STATIC_DIR
from database import get_db

router = APIRouter(prefix="/api/photos", tags=["photos"])

PHOTO_FILENAME = "profile.jpg"
PHOTO_ASSET_ID = "current"
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def get_current_photo_data():
    conn = get_db()
    try:
        return conn.execute(
            "SELECT content_type, data FROM profile_assets WHERE id = ?",
            (PHOTO_ASSET_ID,),
        ).fetchone()
    finally:
        conn.close()


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

    content = await file.read(MAX_PHOTO_BYTES + 1)
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Photo must be 5 MB or smaller")
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded photo is empty")

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO profile_assets (id, content_type, data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                content_type = excluded.content_type,
                data = excluded.data,
                updated_at = CURRENT_TIMESTAMP
            """,
            (PHOTO_ASSET_ID, file.content_type, content),
        )
        conn.commit()
    finally:
        conn.close()

    return {"path": "/api/photos/current", "message": "Photo uploaded successfully"}


@router.get("/current")
async def get_current_photo():
    """Get the current profile photo URL."""
    asset = get_current_photo_data()
    if asset:
        return Response(content=bytes(asset["data"]), media_type=asset["content_type"])

    # One-time compatibility fallback for data created before Supabase support.
    photo_path = os.path.join(STATIC_DIR, PHOTO_FILENAME)
    if os.path.exists(photo_path):
        return FileResponse(photo_path)
    raise HTTPException(status_code=404, detail="No profile photo has been uploaded")
