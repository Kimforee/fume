from fastapi import APIRouter, HTTPException
from app.schemas import TaskProgressResponse
from app.tasks.celery_app import celery_app
from celery.result import GroupResult
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
    try:
        progress_key = f"task_progress:{task_id}"
        progress_data = redis_client.get(progress_key)
        
        if not progress_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        progress = json.loads(progress_data)
        
        # Check Celery group status if we have group_id
        celery_group_id = progress.get("celery_group_id")
        if celery_group_id:
            try:
                group_result = GroupResult.restore(celery_group_id, app=celery_app)
                if group_result:
                    # Check if all tasks are complete
                    if group_result.ready():
                        if progress["status"] != "completed" and progress["status"] != "cancelled":
                            progress["status"] = "completed"
                            progress["progress"] = 100.0
                            progress["completed_at"] = datetime.utcnow().isoformat()
                            # Update Redis with final status
                            redis_client.setex(progress_key, 3600, json.dumps(progress))
                    elif progress["status"] == "cancelled":
                        # Task was cancelled
                        pass
                    else:
                        # Still processing - ensure status is processing
                        if progress["status"] != "cancelled":
                            progress["status"] = "processing"
            except Exception as e:
                # If we can't get group status, use Redis data
                pass
        
        return TaskProgressResponse(**progress)
        
    except redis.exceptions.RedisError as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to Redis: {str(e)}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error parsing progress data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task progress: {str(e)}")


@router.post("/{task_id}/cancel", status_code=200)
async def cancel_task(task_id: str):
    """Cancel a running CSV import task."""
    try:
        progress_key = f"task_progress:{task_id}"
        progress_data = redis_client.get(progress_key)
        
        if not progress_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        progress = json.loads(progress_data)
        
        if progress["status"] in ["completed", "failed", "cancelled"]:
            raise HTTPException(status_code=400, detail=f"Task is already {progress['status']}")
        
        # Mark as cancelled in Redis
        progress["status"] = "cancelled"
        progress["message"] = "Task cancelled by user"
        progress["completed_at"] = datetime.utcnow().isoformat()
        redis_client.setex(progress_key, 3600, json.dumps(progress))
        
        # Try to revoke Celery tasks
        celery_group_id = progress.get("celery_group_id")
        if celery_group_id:
            try:
                group_result = GroupResult.restore(celery_group_id, app=celery_app)
                if group_result:
                    group_result.revoke(terminate=True)
            except Exception:
                pass  # If we can't revoke, at least mark as cancelled in Redis
        
        return {"message": "Task cancelled successfully", "task_id": task_id}
        
    except redis.exceptions.RedisError as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to Redis: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling task: {str(e)}")

