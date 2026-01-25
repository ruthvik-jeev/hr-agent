"""
API Module - REST API Layer

Contains the FastAPI server, routes, and middleware for the HR Agent API.
"""

from .server import app
from .cli import main as cli_main

__all__ = [
    "app",
    "cli_main",
]
