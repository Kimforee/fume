"""
Simple HTTP server for Cloud Run health checks.
Runs alongside Celery worker to satisfy Cloud Run's port requirement.
"""
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple health check endpoint."""
    
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "celery-worker"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress access logs
        pass


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Threading HTTP server."""
    daemon_threads = True


def start_health_server(port=8080):
    """Start HTTP health check server in a separate thread."""
    try:
        server = ThreadingHTTPServer(('0.0.0.0', port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"Health server thread started, listening on 0.0.0.0:{port}")
        return server
    except Exception as e:
        print(f"ERROR: Failed to start health server: {e}", file=sys.stderr)
        raise

