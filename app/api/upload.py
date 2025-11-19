from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas import UploadResponse
from app.tasks.csv_import import process_csv_import
import os
import uuid

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Maximum file size: 500MB
MAX_FILE_SIZE = 500 * 1024 * 1024


@router.post("", response_model=UploadResponse, status_code=202)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to upload (tab-separated)")
):
    """
    Upload a CSV file for processing.
    
    Expected format: name, sku, description (tab-separated)
    Returns a task ID for progress tracking.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size (500MB)"
        )
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Save file temporarily (or pass content directly to task)
    # For large files, we'll pass content directly to avoid disk I/O
    # In production, you might want to save to S3 or similar
    
    # Create async task
    task = process_csv_import.delay(task_id, content, file.filename)
    
    return UploadResponse(
        task_id=task_id,
        message="File uploaded successfully. Processing started.",
        filename=file.filename
    )

