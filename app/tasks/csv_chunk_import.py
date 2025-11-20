from app.tasks.celery_app import celery_app
from app.utils.csv_parser import normalize_sku
from app.database import DATABASE_URL_SYNC
import psycopg2
from psycopg2.extras import execute_values
import redis
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

# Redis connection for progress tracking
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Convert to TLS for Upstash
if redis_url and "upstash.io" in redis_url:
    redis_url = redis_url.rstrip('/').rstrip('/0').rstrip('/1').rstrip('/2')
    if redis_url.startswith("redis://"):
        redis_url = redis_url.replace("redis://", "rediss://", 1)
redis_client = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)

# Chunk size for processing (smaller = more frequent progress updates)
CHUNK_ROWS = 100


def update_progress(task_id: str, **kwargs):
    """Update task progress in Redis."""
    progress_key = f"task_progress:{task_id}"
    
    existing = redis_client.get(progress_key)
    if existing:
        progress = json.loads(existing)
    else:
        progress = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0.0,
            "total_rows": 0,
            "processed_rows": 0,
            "successful_rows": 0,
            "failed_rows": 0,
            "errors": [],
            "created_at": datetime.utcnow().isoformat(),
        }
    
    # Update with new values
    progress.update(kwargs)
    
    # Calculate progress percentage
    total_rows = progress.get("total_rows", 0)
    processed_rows = progress.get("processed_rows", 0)
    if total_rows > 0:
        progress["progress"] = min(100.0, (processed_rows / total_rows) * 100.0)
    else:
        progress["progress"] = 0.0
    
    redis_client.setex(progress_key, 3600, json.dumps(progress))


def check_cancelled(task_id: str) -> bool:
    """Check if task has been cancelled."""
    progress_key = f"task_progress:{task_id}"
    existing = redis_client.get(progress_key)
    if existing:
        progress = json.loads(existing)
        return progress.get("status") == "cancelled"
    return False


@celery_app.task(bind=True, max_retries=3, ignore_result=True)
def process_chunk_task(self, task_id: str, chunk_data: List[Dict], column_mapping: Dict[str, str], chunk_number: int):
    """
    Process a single chunk of CSV data using fast bulk insert.
    
    Args:
        task_id: Task identifier for progress tracking
        chunk_data: List of dictionaries with row data
        column_mapping: Mapping of CSV columns to our fields
        chunk_number: Chunk number for logging
    """
    # Check if cancelled
    if check_cancelled(task_id):
        return {"success": False, "message": "Task cancelled", "chunk": chunk_number}
    
    try:
        # Get database connection string (convert asyncpg URL to psycopg2 format)
        db_url = DATABASE_URL_SYNC
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        successful = 0
        failed = 0
        errors = []
        
        # Prepare data for bulk insert
        insert_values = []
        update_values = []
        
        for row_data in chunk_data:
            try:
                name = row_data.get('name', '').strip()
                sku = row_data.get('sku', '').strip()
                description = row_data.get('description', '').strip() or None
                
                if not name or not sku:
                    failed += 1
                    continue
                
                # Normalize SKU for lookup
                normalized_sku = normalize_sku(sku)
                
                # Check if exists (we'll handle upsert)
                cur.execute(
                    "SELECT id FROM products WHERE LOWER(sku) = %s",
                    (normalized_sku,)
                )
                existing = cur.fetchone()
                
                if existing:
                    # Update existing
                    update_values.append((name, sku, description, True, existing[0]))
                else:
                    # Insert new (timestamps will be set by database)
                    insert_values.append((name, sku, description, True))
                
                successful += 1
                
            except Exception as e:
                failed += 1
                errors.append(f"Row {row_data.get('row_number', 'unknown')}: {str(e)}")
        
        # Bulk insert new products using execute_values (very fast)
        if insert_values:
            # Use execute_values for fast bulk insert
            # The database will set created_at and updated_at via DEFAULT
            insert_sql = """
                INSERT INTO products (name, sku, description, active)
                VALUES %s
            """
            execute_values(
                cur,
                insert_sql,
                insert_values,
                template=None,  # Auto-generate template from column count
                page_size=1000
            )
        
        # Bulk update existing products
        if update_values:
            for name, sku, description, active, product_id in update_values:
                cur.execute(
                    """
                    UPDATE products 
                    SET name = %s, sku = %s, description = %s, active = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (name, sku, description, active, product_id)
                )
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Update progress after each chunk completes
        chunk_start = chunk_data[0].get('chunk_start_row', 0) if chunk_data else 0
        processed_count = chunk_start + len(chunk_data)
        
        # Get current progress to accumulate totals
        progress_key = f"task_progress:{task_id}"
        existing = redis_client.get(progress_key)
        if existing:
            current_progress = json.loads(existing)
            total_successful = current_progress.get("successful_rows", 0) + successful
            total_failed = current_progress.get("failed_rows", 0) + failed
            total_chunks = current_progress.get("total_chunks", "?")
        else:
            total_successful = successful
            total_failed = failed
            total_chunks = "?"
        
        update_progress(
            task_id,
            processed_rows=processed_count,
            successful_rows=total_successful,
            failed_rows=total_failed,
            errors=errors[-5:] if errors else [],  # Keep last 5 errors per chunk
            message=f"Processed chunk {chunk_number}/{total_chunks} ({processed_count} rows processed)"
        )
        
        return {
            "success": True,
            "chunk": chunk_number,
            "successful": successful,
            "failed": failed
        }
        
    except Exception as exc:
        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10)
        else:
            update_progress(
                task_id,
                errors=[f"Chunk {chunk_number} failed: {str(exc)}"]
            )
            raise

