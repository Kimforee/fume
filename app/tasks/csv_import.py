from app.tasks.celery_app import celery_app
from app.utils.csv_parser import parse_csv_file_streaming, validate_product_row, normalize_sku
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
# Convert to TLS for Upstash
if redis_url and "upstash.io" in redis_url:
    redis_url = redis_url.rstrip('/').rstrip('/0').rstrip('/1').rstrip('/2')
    if redis_url.startswith("redis://"):
        redis_url = redis_url.replace("redis://", "rediss://", 1)
redis_client = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)

# Batch size for database operations
BATCH_SIZE = 20  # Smaller batches = more frequent commits and progress updates


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


@celery_app.task(bind=True, ignore_result=True)
def process_csv_import(self, task_id: str, file_content: bytes, filename: str):
    """
    Process CSV file import asynchronously using streaming to avoid memory issues.
    
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
        
        # Count total rows first (for progress tracking)
        # We'll do this by counting newlines (approximate)
        text_preview = file_content[:10000].decode('utf-8', errors='ignore')  # Preview first 10KB
        estimated_total = text_preview.count('\n')
        if estimated_total < 100:
            # If preview is small, count all
            estimated_total = file_content.decode('utf-8', errors='ignore').count('\n')
        estimated_total = max(estimated_total - 1, 1)  # Subtract header row
        
        update_progress(
            task_id,
            total_rows=estimated_total,
            message=f"Processing approximately {estimated_total} rows..."
        )
        
        # Create database session (sync for Celery)
        db = SessionLocal()
        
        try:
            # OPTIMIZATION: Load all existing products into memory for fast lookup
            # This avoids doing a database query for every row
            update_progress(task_id, message="Loading existing products...")
            existing_products = db.query(Product).all()
            # Create a dictionary keyed by normalized SKU for O(1) lookup
            existing_by_sku = {normalize_sku(p.sku): p for p in existing_products}
            update_progress(task_id, message=f"Found {len(existing_by_sku)} existing products. Processing CSV...")
            
            processed_rows = 0
            successful_rows = 0
            failed_rows = 0
            errors = []
            to_create = []
            to_update = []
            actual_total = 0
            
            # Process rows using streaming generator (memory efficient)
            for row_data in parse_csv_file_streaming(file_content):
                actual_total += 1
                
                # Update total if we underestimated
                if actual_total > estimated_total:
                    estimated_total = actual_total
                    update_progress(task_id, total_rows=estimated_total)
                
                try:
                    # Validate row
                    is_valid, error_msg = validate_product_row(row_data)
                    if not is_valid:
                        failed_rows += 1
                        errors.append(f"Row {row_data['row_number']}: {error_msg}")
                        processed_rows += 1
                        # Update progress immediately for small files
                        if estimated_total < 100:
                            update_progress(
                                task_id,
                                processed_rows=processed_rows,
                                successful_rows=successful_rows,
                                failed_rows=failed_rows,
                                total_rows=estimated_total,
                                message=f"Processed {processed_rows}/{estimated_total} rows..."
                            )
                        continue
                    
                    # Normalize SKU for case-insensitive lookup
                    normalized_sku = normalize_sku(row_data['sku'])
                    
                    # Check if product exists using in-memory dictionary (O(1) lookup)
                    existing = existing_by_sku.get(normalized_sku)
                    
                    if existing:
                        # Update existing product
                        existing.name = row_data['name']
                        existing.sku = row_data['sku']  # Keep original case
                        existing.description = row_data.get('description')
                        existing.active = True  # Reactivate if it was inactive
                        to_update.append(existing)
                    else:
                        # Create new product
                        new_product = Product(
                            name=row_data['name'],
                            sku=row_data['sku'],
                            description=row_data.get('description'),
                            active=True
                        )
                        to_create.append(new_product)
                        # Add to lookup dict to avoid duplicates in same import
                        existing_by_sku[normalized_sku] = new_product
                    
                    successful_rows += 1
                    processed_rows += 1
                    
                    # Commit in batches for better performance
                    if len(to_create) >= BATCH_SIZE:
                        db.add_all(to_create)
                        db.commit()
                        to_create = []
                    
                    if len(to_update) >= BATCH_SIZE:
                        db.commit()  # Updates are already tracked by SQLAlchemy
                        to_update = []
                    
                    # Update progress more frequently for better UX
                    # For small files (< 100 rows), update every row
                    # For larger files, update every 10 rows
                    update_interval = 1 if estimated_total < 100 else 10
                    if processed_rows % update_interval == 0 or processed_rows == actual_total:
                        update_progress(
                            task_id,
                            processed_rows=processed_rows,
                            successful_rows=successful_rows,
                            failed_rows=failed_rows,
                            total_rows=estimated_total,
                            errors=errors[-10:] if errors else [],  # Keep last 10 errors
                            message=f"Processed {processed_rows}/{estimated_total} rows..."
                        )
                
                except Exception as e:
                    failed_rows += 1
                    error_msg = f"Row {row_data.get('row_number', 'unknown')}: {str(e)}"
                    errors.append(error_msg)
                    processed_rows += 1
                    # Update progress immediately for small files
                    if estimated_total < 100:
                        update_progress(
                            task_id,
                            processed_rows=processed_rows,
                            successful_rows=successful_rows,
                            failed_rows=failed_rows,
                            total_rows=estimated_total,
                            message=f"Processed {processed_rows}/{estimated_total} rows..."
                        )
                    continue
            
            # Update final total
            if actual_total != estimated_total:
                update_progress(task_id, total_rows=actual_total)
            
            # Commit remaining items
            if to_create:
                db.add_all(to_create)
            if to_create or to_update:
                db.commit()
            
            # Final progress update
            update_progress(
                task_id,
                status="completed",
                processed_rows=processed_rows,
                successful_rows=successful_rows,
                failed_rows=failed_rows,
                total_rows=actual_total,
                errors=errors[-20:] if errors else [],  # Keep last 20 errors
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
