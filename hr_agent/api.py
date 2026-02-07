"""
API Module - Compatibility Shim

Exports the FastAPI app from apps/api/server.py for backwards compatibility.
"""

from apps.api.server import app
from .cli import main as cli_main

__all__ = ["app", "cli_main"]
