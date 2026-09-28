"""Vercel Python entry point - exposes the existing Flask app (app.py at
the project root) as the WSGI callable Vercel's Python runtime expects.
The `if __name__ == "__main__":` dev-server block in app.py never runs
here since Vercel imports this module rather than executing app.py
directly."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
