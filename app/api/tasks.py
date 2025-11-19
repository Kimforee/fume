from fastapi import APIRouter, HTTPException
from app.schemas import TaskProgressResponse
from app.tasks.celery_app import celery_app
import redis
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Redis connection for progress tracking
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(redis_url, decode_responses=True)


@router.get("/{task_id}/progress", response_model=TaskProgressResponse)
async def get_task_progress(task_id: str):
    """Get progress of a CSV import task."""
    # Check Celery task status
    try:
        # Find the Celery task by task_id (we'll need to store the mapping)
        # For now, we'll use Redis to store progress
        progress_key = f"task_progress:{task_id}"
        progress_data = redis_client.get(progress_key)
        
        if not progress_data:
            # Check if task exists in Celery
            # Since we're using task_id as UUID, we need to track it differently
            # Let's check Redis first, then try to find in Celery
            raise HTTPException(status_code=404, detail="Task not found")
        
        progress = json.loads(progress_data)
        
        # Also check Celery task status if we have the celery_task_id
        celery_task_id = progress.get("celery_task_id")
        if celery_task_id:
            celery_task = celery_app.AsyncResult(celery_task_id)
            if celery_task.state == "FAILURE":
                progress["status"] = "failed"
                progress["message"] = str(celery_task.info)
            elif celery_task.state == "SUCCESS":
                if progress["status"] != "completed":
                    progress["status"] = "completed"
                    progress["progress"] = 100.0
                    progress["completed_at"] = datetime.utcnow().isoformat()
            elif celery_task.state == "PENDING":
                progress["status"] = "pending"
            else:
                progress["status"] = "processing"
        
        return TaskProgressResponse(**progress)
        
    except redis.exceptions.RedisError as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to Redis: {str(e)}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error parsing progress data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task progress: {str(e)}")

