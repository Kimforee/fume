# Async task definitions
from app.tasks.celery_app import celery_app
from app.tasks import csv_import, csv_chunk_import  # Import to register tasks

__all__ = ["celery_app"]

