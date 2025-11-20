#!/usr/bin/env python3
"""
Startup script for Celery worker with health check server.
Runs both the health check HTTP server and Celery worker.
"""
import os
import subprocess
import sys
from app.worker_health import start_health_server

def main():
    # Get port from environment (Cloud Run sets this)
    port = int(os.getenv("PORT", 8080))
    
    # Import celery_app to trigger URL conversion and environment variable updates
    # This ensures the converted URLs are set in os.environ before Celery starts
    # The import triggers the URL conversion code in celery_app.py
    try:
        from app.tasks.celery_app import celery_app  # noqa - triggers URL conversion
    except Exception as e:
        print(f"ERROR: Failed to import celery_app: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Read the converted URLs from environment (they were set by celery_app.py)
    celery_broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    
    if not celery_broker_url or not celery_result_backend:
        print("ERROR: CELERY_BROKER_URL or CELERY_RESULT_BACKEND not set", file=sys.stderr)
        sys.exit(1)
    
    print(f"[Worker] Using broker: {celery_broker_url[:50]}...")
    print(f"[Worker] Using backend: {celery_result_backend[:50]}...")
    
    # Start health check server in background thread
    print(f"Starting health check server on port {port}...")
    server = start_health_server(port)
    
    # Give health server a moment to start listening
    import time
    time.sleep(1)
    print(f"Health check server started on port {port}")
    
    # Start Celery worker (this will block)
    print("Starting Celery worker...")
    celery_cmd = [
        "celery",
        "-A", "app.tasks.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=2",
        "--without-gossip",  # Disable gossip to reduce network overhead
        "--without-mingle",   # Disable mingle to reduce startup time
        "--without-heartbeat"  # Disable heartbeat to reduce network overhead
    ]
    
    # Run Celery worker - output directly to stdout/stderr so Cloud Run captures it
    # Don't buffer output - we need to see errors immediately
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    # Run worker with unbuffered output
    # Use Popen so we can stream output in real-time
    import subprocess
    process = subprocess.Popen(
        celery_cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
        bufsize=0,  # Unbuffered
        env=os.environ.copy()
    )
    
    # Wait for process to complete
    returncode = process.wait()
    if returncode != 0:
        print(f"ERROR: Celery worker exited with code {returncode}", file=sys.stderr)
        sys.stderr.flush()
        # Sleep a bit before exiting to allow health check to respond
        import time
        time.sleep(5)
    sys.exit(returncode)

if __name__ == "__main__":
    main()

