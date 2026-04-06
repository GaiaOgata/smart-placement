"""
run.py — Entry point for the Heatmap Optimization API.

Usage:
    python run.py

The API will print instructions on how to expose it publicly via expose.sh.
"""

import os
import socket

from app import create_app


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True


def find_available_port(start_port: int = 5000) -> int:
    """Find the first available port, starting from start_port."""
    port = start_port
    while is_port_in_use(port):
        port += 1
    return port


app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    preferred_port = int(os.getenv("PORT", 5000))

    if is_port_in_use(preferred_port):
        print(f"⚠️  Port {preferred_port} is in use.")
        port = find_available_port(preferred_port + 1)
        print(f"✅ Starting server on port {port} instead.\n")
    else:
        port = preferred_port
        print(f"✅ Starting server on port {port}.\n")

    # Print instructions for exposing the API
    print(f"{'='*70}")
    print(f"🔗 Local API URL:")
    print(f"   http://localhost:{port}/api/optimize")
    print(f"\n{'='*70}")
    print(f"🌐 To expose publicly, run this command in ANOTHER terminal:")
    print(f"\n   curl -L https://expose.sh | bash -s -- --port {port}")
    print(f"\n   Or use SSH tunneling:")
    print(f"   ssh -R 80:localhost:{port} ssh.localhost.run")
    print(f"\n{'='*70}\n")

    # Start Flask app
    app.run(host="0.0.0.0", port=port, debug=False)
