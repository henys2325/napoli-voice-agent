"""
Entry point for Render.com deployment.
Adds the backend directory to sys.path before importing the FastAPI app.
"""
import sys
import os

# Add backend to path so relative imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Ensure data directory exists
os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)

# Import the app
from backend.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
