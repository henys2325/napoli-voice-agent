"""
Entry point for Render.com deployment.
Adds the backend directory to sys.path so imports work correctly.
"""
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import the FastAPI app
from main import app

__all__ = ["app"]
