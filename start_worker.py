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
    
    # Import celery_app to trigger URL conversion
    # This ensures the converted URLs are set before Celery starts
    from app.tasks.celery_app import celery_app, celery_broker_url, celery_result_backend
    
    # Set environment variables with converted URLs so Celery uses them
    # This ensures Celery reads the correct TLS URLs
    os.environ["CELERY_BROKER_URL"] = celery_broker_url
    os.environ["CELERY_RESULT_BACKEND"] = celery_result_backend
    
    print(f"[Worker] Using broker: {celery_broker_url[:50]}...")
    print(f"[Worker] Using backend: {celery_result_backend[:50]}...")
    
    # Start health check server in background thread
    print(f"Starting health check server on port {port}...")
    start_health_server(port)
    
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

