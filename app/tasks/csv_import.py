from app.tasks.celery_app import celery_app
from app.utils.csv_parser import parse_csv_file_streaming, validate_product_row, normalize_sku
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.database import DATABASE_URL_SYNC, SessionLocal
from app.models.product import Product
import redis
import os
import json
import csv
import io
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Redis connection for progress tracking
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Convert to TLS for Upstash
if redis_url and "upstash.io" in redis_url:
    redis_url = redis_url.rstrip('/').rstrip('/0').rstrip('/1').rstrip('/2')
    if redis_url.startswith("redis://"):
        redis_url = redis_url.replace("redis://", "rediss://", 1)
redis_client = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)

# Batch size for database operations
BATCH_SIZE = 50  # Larger batches = fewer commits = better performance


def update_progress(task_id: str, **kwargs):
    """Update task progress in Redis."""
    progress_key = f"task_progress:{task_id}"
    
    # Get existing progress or create new
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
    if progress.get("total_rows", 0) > 0:
        progress["progress"] = (progress["processed_rows"] / progress["total_rows"]) * 100.0
    
    # Save to Redis
    redis_client.setex(progress_key, 3600, json.dumps(progress))  # Expire after 1 hour


def count_csv_rows(file_content: bytes, stop_after: int | None = None) -> int:
    """
    Count CSV data rows (excluding header). If stop_after is provided, stop counting
    once the number of data rows exceeds the threshold (useful for inline processing checks).
    """
    text_content = file_content.decode('utf-8', errors='ignore')
    text_content = text_content.replace('\r\n', '\n').replace('\r', '\n')
    
    first_line = text_content.split('\n')[0] if '\n' in text_content else text_content
    delimiter = ',' if ',' in first_line else ('\t' if '\t' in first_line else ',')
    
    reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
    row_count = 0
    for _ in reader:
        row_count += 1
        if stop_after is not None and (row_count - 1) >= stop_after:
            break
    data_rows = max(row_count - 1, 0)
    return data_rows


def _process_csv_import_core(task_id: str, file_content: bytes, filename: str, celery_task_id: str | None = None):
    """
    Core CSV import logic shared by both Celery task and inline processing.
    """
    try:
        update_progress(
            task_id,
            status="processing",
            message="Parsing CSV file...",
            celery_task_id=celery_task_id
        )
        
        estimated_total = max(count_csv_rows(file_content), 1)
        update_progress(
            task_id,
            total_rows=estimated_total,
            message=f"Processing approximately {estimated_total} rows..."
        )
        
        db = SessionLocal()
        try:
            update_progress(task_id, message="Loading existing products...")
            existing_products = db.query(Product).all()
            existing_by_sku = {normalize_sku(p.sku): p for p in existing_products}
            update_progress(task_id, message=f"Found {len(existing_by_sku)} existing products. Processing CSV...")
            
            processed_rows = 0
            successful_rows = 0
            failed_rows = 0
            errors = []
            to_create = []
            to_update = []
            actual_total = 0
            
            for row_data in parse_csv_file_streaming(file_content):
                actual_total += 1
                
                if actual_total > estimated_total:
                    estimated_total = actual_total
                    update_progress(task_id, total_rows=estimated_total)
                
                try:
                    is_valid, error_msg = validate_product_row(row_data)
                    if not is_valid:
                        failed_rows += 1
                        errors.append(f"Row {row_data['row_number']}: {error_msg}")
                        processed_rows += 1
                        if processed_rows % 5 == 0 or processed_rows == estimated_total:
                            update_progress(
                                task_id,
                                processed_rows=processed_rows,
                                successful_rows=successful_rows,
                                failed_rows=failed_rows,
                                total_rows=estimated_total,
                                message=f"Processed {processed_rows}/{estimated_total} rows..."
                            )
                        continue
                    
                    normalized_sku = normalize_sku(row_data['sku'])
                    existing = existing_by_sku.get(normalized_sku)
                    
                    if existing:
                        existing.name = row_data['name']
                        existing.sku = row_data['sku']
                        existing.description = row_data.get('description')
                        existing.active = True
                        to_update.append(existing)
                    else:
                        new_product = Product(
                            name=row_data['name'],
                            sku=row_data['sku'],
                            description=row_data.get('description'),
                            active=True
                        )
                        to_create.append(new_product)
                        existing_by_sku[normalized_sku] = new_product
                    
                    successful_rows += 1
                    processed_rows += 1
                    
                    if len(to_create) >= BATCH_SIZE:
                        db.add_all(to_create)
                        db.commit()
                        to_create = []
                    
                    if len(to_update) >= BATCH_SIZE:
                        db.commit()
                        to_update = []
                    
                    update_interval = 5 if estimated_total < 100 else 10
                    if processed_rows % update_interval == 0 or processed_rows == actual_total:
                        update_progress(
                            task_id,
                            processed_rows=processed_rows,
                            successful_rows=successful_rows,
                            failed_rows=failed_rows,
                            total_rows=estimated_total,
                            errors=errors[-10:] if errors else [],
                            message=f"Processed {processed_rows}/{estimated_total} rows..."
                        )
                
                except Exception as e:
                    failed_rows += 1
                    error_msg = f"Row {row_data.get('row_number', 'unknown')}: {str(e)}"
                    errors.append(error_msg)
                    processed_rows += 1
                    if processed_rows % 5 == 0 or processed_rows == estimated_total:
                        update_progress(
                            task_id,
                            processed_rows=processed_rows,
                            successful_rows=successful_rows,
                            failed_rows=failed_rows,
                            total_rows=estimated_total,
                            message=f"Processed {processed_rows}/{estimated_total} rows..."
                        )
                    continue
            
            if actual_total != estimated_total:
                update_progress(task_id, total_rows=actual_total)
            
            if to_create:
                db.add_all(to_create)
            if to_create or to_update:
                db.commit()
            
            update_progress(
                task_id,
                status="completed",
                processed_rows=processed_rows,
                successful_rows=successful_rows,
                failed_rows=failed_rows,
                total_rows=actual_total,
                errors=errors[-20:] if errors else [],
                message=f"Import completed. {successful_rows} successful, {failed_rows} failed.",
                progress=100.0,
                completed_at=datetime.utcnow().isoformat()
            )
            
            return {
                "success": True,
                "total_rows": actual_total,
                "successful_rows": successful_rows,
                "failed_rows": failed_rows,
                "errors": errors[-20:] if errors else []
            }
        
        finally:
            db.close()
    
    except Exception as e:
        update_progress(
            task_id,
            status="failed",
            message=f"Import failed: {str(e)}",
            progress=100.0,
            completed_at=datetime.utcnow().isoformat(),
            errors=[str(e)]
        )
        raise


@celery_app.task(bind=True, ignore_result=True)
def process_csv_import(self, task_id: str, file_content: bytes, filename: str):
    """Celery task entrypoint."""
    return _process_csv_import_core(task_id, file_content, filename, celery_task_id=self.request.id)


def process_csv_import_inline(task_id: str, file_content: bytes, filename: str):
    """Inline processing entrypoint (bypasses Celery)."""
    return _process_csv_import_core(task_id, file_content, filename, celery_task_id=None)
