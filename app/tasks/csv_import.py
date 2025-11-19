from app.tasks.celery_app import celery_app
from app.utils.csv_parser import parse_csv_file, validate_product_row, normalize_sku
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.database import DATABASE_URL_SYNC, SessionLocal
from app.models.product import Product
import redis
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Redis connection for progress tracking
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(redis_url, decode_responses=True)

# Batch size for database operations
BATCH_SIZE = 1000


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


@celery_app.task(bind=True, name="csv_import.process_csv_import")
def process_csv_import(self, task_id: str, file_content: bytes, filename: str):
    """
    Process CSV file import asynchronously.
    
    Args:
        task_id: Unique task identifier
        file_content: CSV file content as bytes
        filename: Original filename
    """
    try:
        # Initialize progress
        update_progress(
            task_id,
            status="processing",
            message="Parsing CSV file...",
            celery_task_id=self.request.id
        )
        
        # Parse CSV file
        rows = parse_csv_file(file_content)
        
        if not rows:
            update_progress(
                task_id,
                status="failed",
                message="No valid rows found in CSV file",
                total_rows=0,
                progress=100.0,
                completed_at=datetime.utcnow().isoformat()
            )
            return {"success": False, "message": "No valid rows found"}
        
        total_rows = len(rows)
        update_progress(
            task_id,
            total_rows=total_rows,
            message=f"Processing {total_rows} rows..."
        )
        
        # Create database session (sync for Celery)
        db = SessionLocal()
        
        try:
            processed_rows = 0
            successful_rows = 0
            failed_rows = 0
            errors = []
            batch = []
            
            # Process rows in batches
            for row_data in rows:
                try:
                    # Validate row
                    is_valid, error_msg = validate_product_row(row_data)
                    if not is_valid:
                        failed_rows += 1
                        errors.append(f"Row {row_data['row_number']}: {error_msg}")
                        processed_rows += 1
                        continue
                    
                    # Normalize SKU for case-insensitive lookup
                    normalized_sku = normalize_sku(row_data['sku'])
                    
                    # Check if product exists (case-insensitive)
                    existing = db.query(Product).filter(
                        func.lower(Product.sku) == normalized_sku
                    ).first()
                    
                    if existing:
                        # Update existing product
                        existing.name = row_data['name']
                        existing.sku = row_data['sku']  # Keep original case
                        existing.description = row_data.get('description')
                        existing.active = True  # Reactivate if it was inactive
                        batch.append(existing)
                    else:
                        # Create new product
                        new_product = Product(
                            name=row_data['name'],
                            sku=row_data['sku'],
                            description=row_data.get('description'),
                            active=True
                        )
                        batch.append(new_product)
                    
                    successful_rows += 1
                    
                    # Commit batch when it reaches BATCH_SIZE
                    if len(batch) >= BATCH_SIZE:
                        db.add_all(batch)
                        db.commit()
                        batch = []
                    
                    processed_rows += 1
                    
                    # Update progress every 100 rows
                    if processed_rows % 100 == 0:
                        update_progress(
                            task_id,
                            processed_rows=processed_rows,
                            successful_rows=successful_rows,
                            failed_rows=failed_rows,
                            errors=errors[-10:] if errors else [],  # Keep last 10 errors
                            message=f"Processed {processed_rows}/{total_rows} rows..."
                        )
                
                except Exception as e:
                    failed_rows += 1
                    error_msg = f"Row {row_data.get('row_number', 'unknown')}: {str(e)}"
                    errors.append(error_msg)
                    processed_rows += 1
                    continue
            
            # Commit remaining batch
            if batch:
                db.add_all(batch)
                db.commit()
            
            # Final progress update
            update_progress(
                task_id,
                status="completed",
                processed_rows=processed_rows,
                successful_rows=successful_rows,
                failed_rows=failed_rows,
                errors=errors[-20:] if errors else [],  # Keep last 20 errors
                message=f"Import completed. {successful_rows} successful, {failed_rows} failed.",
                progress=100.0,
                completed_at=datetime.utcnow().isoformat()
            )
            
            return {
                "success": True,
                "total_rows": total_rows,
                "successful_rows": successful_rows,
                "failed_rows": failed_rows,
                "errors": errors[-20:] if errors else []
            }
        
        finally:
            db.close()
    
    except Exception as e:
        # Update progress with error
        update_progress(
            task_id,
            status="failed",
            message=f"Import failed: {str(e)}",
            progress=100.0,
            completed_at=datetime.utcnow().isoformat(),
            errors=[str(e)]
        )
        raise

