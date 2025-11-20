from celery import Celery
import os
from dotenv import load_dotenv
from ssl import CERT_NONE

load_dotenv()

# Celery configuration
celery_broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Upstash Redis requires TLS - convert redis:// to rediss://
# Also remove any trailing slashes or database numbers that might cause issues
if celery_broker_url and "upstash.io" in celery_broker_url:
    # Remove trailing slashes and database numbers
    celery_broker_url = celery_broker_url.rstrip('/').rstrip('/0').rstrip('/1').rstrip('/2')
    # Convert to TLS
    if celery_broker_url.startswith("redis://"):
        celery_broker_url = celery_broker_url.replace("redis://", "rediss://", 1)
    print(f"[Celery] Broker URL converted to: {celery_broker_url[:50]}...")

if celery_result_backend and "upstash.io" in celery_result_backend:
    # Remove trailing slashes and database numbers
    celery_result_backend = celery_result_backend.rstrip('/').rstrip('/0').rstrip('/1').rstrip('/2')
    # Convert to TLS
    if celery_result_backend.startswith("redis://"):
        celery_result_backend = celery_result_backend.replace("redis://", "rediss://", 1)
    print(f"[Celery] Result backend converted to: {celery_result_backend[:50]}...")

# Create Celery app with converted URLs
celery_app = Celery(
    "product_importer",
    broker=celery_broker_url,
    backend=celery_result_backend,
)

# Celery configuration
broker_transport_options = {}
result_backend_transport_options = {}

# Configure SSL for Upstash Redis
# CERT_NONE means don't verify the certificate (needed for Upstash's self-signed certs)
# Kombu requires these options to be set correctly for rediss:// URLs
if "upstash.io" in celery_broker_url:
    broker_transport_options = {
        'ssl_cert_reqs': CERT_NONE,  # Upstash uses self-signed certs, don't verify
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
        'health_check_interval': 30,  # Check connection health
    }

if "upstash.io" in celery_result_backend:
    result_backend_transport_options = {
        'ssl_cert_reqs': CERT_NONE,  # Upstash uses self-signed certs, don't verify
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
    }

# Update configuration with SSL options
celery_app.conf.update(
    broker_url=celery_broker_url,  # Explicitly set the converted URL
    result_backend=celery_result_backend,  # Explicitly set the converted URL
    broker_transport_options=broker_transport_options,
    result_backend_transport_options=result_backend_transport_options,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max for long-running CSV imports
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,  # Retry connection on startup
    result_backend_always_retry=True,  # Retry result backend connections
    result_backend_max_retries=3,  # Limit retries for result backend
)

# Import tasks to register them
from app.tasks import csv_import, csv_chunk_import, csv_chunk_processor  # noqa

