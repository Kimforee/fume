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
    print("Starting Celery worker...")
    celery_cmd = [
        "celery",
        "-A", "app.tasks.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=2"
    ]
    
    sys.exit(subprocess.run(celery_cmd).returncode)

if __name__ == "__main__":
    main()

