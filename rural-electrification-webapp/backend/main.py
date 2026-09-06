"""Rural Electrification Planner — API server.

Run with:  uvicorn main:app --reload --port 8000   (from the backend/ directory, venv activated)

This wraps the validated calculation modules in core/ (unchanged ports of the original
notebooks/Streamlit app's logic) behind a JSON API for the React frontend in ../frontend.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router

app = FastAPI(title="Rural Electrification Planner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
