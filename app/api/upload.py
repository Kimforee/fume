from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas import UploadResponse
from app.tasks.csv_chunk_processor import process_csv_file
import os
import uuid
import redis
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Maximum file size: 500MB
MAX_FILE_SIZE = 500 * 1024 * 1024


@router.post("", response_model=UploadResponse, status_code=202)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to upload")
):
    """
    Upload a CSV file for processing.
    
    This endpoint returns immediately (202 Accepted) to avoid timeout issues.
    All processing happens asynchronously in Celery workers.
    
    Accepts any CSV format with columns containing: name/product name, sku/product code, description.
    Auto-detects column mapping and delimiter (comma or tab).
    Returns a task ID for progress tracking.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    # Read file content (this is fast for most files, but for very large files
    # we could stream directly to a temp file and pass the path)
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
    
    # Store initial progress in Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Convert to TLS for Upstash
    if redis_url and "upstash.io" in redis_url:
        redis_url = redis_url.rstrip('/').rstrip('/0').rstrip('/1').rstrip('/2')
        if redis_url.startswith("redis://"):
            redis_url = redis_url.replace("redis://", "rediss://", 1)
    redis_client = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)
    progress_key = f"task_progress:{task_id}"
    initial_progress = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0.0,
        "total_rows": 0,
        "processed_rows": 0,
        "successful_rows": 0,
        "failed_rows": 0,
        "errors": [],
        "created_at": datetime.utcnow().isoformat(),
        "message": "File uploaded. Starting processing..."
    }
    redis_client.setex(progress_key, 3600, json.dumps(initial_progress))
    
    # Enqueue processing task (all heavy work happens in Celery worker)
    # This returns immediately, avoiding timeout issues
    from app.tasks.celery_app import celery_app
    import logging
    
    try:
        # Use send_task - it should use the broker_transport_options from celery_app.conf
        # The SSL options are configured in celery_app, so connections should use them
        result = celery_app.send_task(
            'app.tasks.csv_import.process_csv_import',
            args=(task_id, content, file.filename),
            ignore_result=True  # We use Redis for progress tracking, not Celery results
        )
        logging.info(f"Task enqueued successfully: {result.id}")
    except Exception as e:
        # If send_task fails, try the regular delay method as fallback
        logging.warning(f"send_task failed, trying delay: {str(e)}")
        try:
            result = process_csv_file.delay(task_id, content, file.filename)
            logging.info(f"Task enqueued via delay: {result.id}")
        except Exception as e2:
            # If both fail, update progress to show error
            logging.error(f"Failed to enqueue task: {str(e2)}")
            error_progress = initial_progress.copy()
            error_progress["status"] = "failed"
            error_progress["message"] = f"Failed to enqueue task: {str(e2)}"
            redis_client.setex(progress_key, 3600, json.dumps(error_progress))
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start processing. Please try again."
            )
    
    return UploadResponse(
        task_id=task_id,
        message="File uploaded successfully. Processing started in background...",
        filename=file.filename
    )
