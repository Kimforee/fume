from app.tasks.celery_app import celery_app
from app.tasks.csv_import import process_csv_import

# Alias the function for backward compatibility
# This allows upload.py to import process_csv_file
process_csv_file = process_csv_import
