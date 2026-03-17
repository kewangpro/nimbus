from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.api import deps
from app.crud import crud_audit
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.storage import client
from app.core.config import settings
import uuid

router = APIRouter()

@router.post("/", response_model=dict)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Upload a file to MinIO.
    """
    file_extension = file.filename.split(".")[-1]
    file_name = f"{uuid.uuid4()}.{file_extension}"
    
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Upload to MinIO
        from io import BytesIO
        client.put_object(
            settings.MINIO_BUCKET,
            file_name,
            BytesIO(content),
            file_size,
            content_type=file.content_type,
        )
        
        url = f"http://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}/{file_name}"
        
        await crud_audit.log_action(
            db, 
            "file.upload", 
            current_user.id, 
            "file", 
            None, 
            details={"filename": file.filename, "size": file_size}
        )
        
        return {
            "url": url,
            "filename": file.filename,
            "storage_name": file_name
        }
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="Could not upload file")
