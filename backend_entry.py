"""
Standalone executable entrypoint for Ai PhotoFlow Backend.
Used by PyInstaller to bundle Python + OpenCV + FastAPI into a single executable.
"""
import os
import sys
import multiprocessing
import uvicorn

# Ensure current dir is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app

if __name__ == "__main__":
    multiprocessing.freeze_support()
    port = int(os.environ.get("PORT", 8000))
    print(f"Ai PhotoFlow Backend running on port {port}...")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
