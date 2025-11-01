#!/usr/bin/env python3
"""
Health check HTTP server for Kubernetes probes.
Provides /healthz (liveness) and /readyz (readiness) endpoints.
"""

import http.server
import socketserver
import threading
import logging

logger = logging.getLogger(__name__)

# Global flag to track operator readiness
_operator_ready = False


def set_ready():
    """Mark the operator as ready."""
    global _operator_ready
    _operator_ready = True
    logger.info("Operator marked as ready")


def is_ready():
    """Check if the operator is ready."""
    return _operator_ready


class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoints."""

    def log_message(self, format, *args):
        """Override to use our logger instead of default logging."""
        logger.debug(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        """Handle GET requests for health endpoints."""
        if self.path == "/healthz":
            # Liveness probe - always returns 200 once server is running
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == "/readyz":
            # Readiness probe - returns 200 if ready, 503 if not
            if is_ready():
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(503)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Not Ready")
        else:
            # Unknown endpoint
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


def start_health_server(host="0.0.0.0", port=8081):
    """
    Start the health check HTTP server in a background thread.

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to listen on (default: 8081)

    Returns:
        Thread object and server object
    """
    server = socketserver.TCPServer((host, port), HealthCheckHandler)
    server.allow_reuse_address = True

    def run_server():
        logger.info(f"Starting health check server on {host}:{port}")
        try:
            server.serve_forever()
        except Exception as e:
            logger.error(f"Health check server error: {e}")
        finally:
            server.server_close()
            logger.info("Health check server stopped")

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    logger.info("Health check server thread started")

    return thread, server


def stop_health_server(server):
    """Stop the health check server gracefully."""
    if server:
        logger.info("Stopping health check server...")
        server.shutdown()
        server.server_close()
