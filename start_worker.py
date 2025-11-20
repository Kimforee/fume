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
    
    # Start health check server in background thread
    print(f"Starting health check server on port {port}...")
    start_health_server(port)
    
    # Start Celery worker (this will block)
    # Use exec to replace process so signals work correctly
    # Add broker_connection_retry_on_startup to handle connection issues
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
    
    # Run Celery worker - it will retry connections automatically
    # Don't exit on failure, let Cloud Run handle restarts
    result = subprocess.run(celery_cmd)
    if result.returncode != 0:
        print(f"Celery worker exited with code {result.returncode}")
        # Sleep a bit before exiting to allow health check to respond
        import time
        time.sleep(5)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()

