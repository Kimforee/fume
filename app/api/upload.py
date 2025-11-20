from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas import UploadResponse
from app.tasks.csv_chunk_import import process_chunk_task
from app.utils.csv_parser import parse_csv_file_streaming, detect_column_mapping
from celery import group
import os
import uuid
import redis
import json
import csv
import io
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Maximum file size: 500MB
MAX_FILE_SIZE = 500 * 1024 * 1024
CHUNK_ROWS = 100  # Process 100 rows per chunk (smaller chunks = faster progress updates)


@router.post("", response_model=UploadResponse, status_code=202)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to upload")
):
    """
    Upload a CSV file for processing.
    
    Accepts any CSV format with columns containing: name/product name, sku/product code, description.
    Auto-detects column mapping and delimiter (comma or tab).
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
    
    # Parse CSV to get header and detect column mapping
    text_content = content.decode('utf-8')
    text_content = text_content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Auto-detect delimiter
    first_line = text_content.split('\n')[0] if '\n' in text_content else text_content
    delimiter = ','
    if '\t' in first_line:
        delimiter = '\t'
    
    # Read header
    reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV file has no header row")
    
    # Detect column mapping
    column_mapping = detect_column_mapping(reader.fieldnames)
    
    # Count total rows (approximate)
    total_rows = text_content.count('\n') - 1  # Subtract header
    total_chunks = (total_rows + CHUNK_ROWS - 1) // CHUNK_ROWS
    
    # Stream CSV and create chunks
    chunks = []
    chunk = []
    chunk_start_row = 1  # Start after header
    
    for row_data in parse_csv_file_streaming(content):
        row_data['chunk_start_row'] = chunk_start_row
        chunk.append(row_data)
        
        if len(chunk) >= CHUNK_ROWS:
            chunks.append(chunk)
            chunk = []
            chunk_start_row += CHUNK_ROWS
    
    # Add remaining chunk
    if chunk:
        chunks.append(chunk)
    
    # Create Celery tasks for each chunk
    tasks = []
    for i, chunk_data in enumerate(chunks, start=1):
        tasks.append(process_chunk_task.s(task_id, chunk_data, column_mapping, i))
    
    # Execute all chunks as a group
    job = group(tasks).apply_async()
    
    # Store task info in Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    progress_key = f"task_progress:{task_id}"
    initial_progress = {
        "task_id": task_id,
        "status": "processing",
        "progress": 0.0,
        "total_rows": total_rows,
        "processed_rows": 0,
        "successful_rows": 0,
        "failed_rows": 0,
        "errors": [],
        "created_at": datetime.utcnow().isoformat(),
        "celery_group_id": str(job.id),
        "total_chunks": len(chunks),
        "completed_chunks": 0,
        "message": f"Starting import of {total_rows} rows in {len(chunks)} chunks..."
    }
    redis_client.setex(progress_key, 3600, json.dumps(initial_progress))
    
    return UploadResponse(
        task_id=task_id,
        message=f"File uploaded successfully. Processing {len(chunks)} chunks...",
        filename=file.filename
    )
