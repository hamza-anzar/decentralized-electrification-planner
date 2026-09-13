"""Rural Electrification Planner — API server.

Run with:  uvicorn main:app --reload --port 8000   (from the backend/ directory, venv activated)

This wraps the validated calculation modules in core/ (unchanged ports of the original
notebooks/Streamlit app's logic) behind a JSON API for the React frontend in ../frontend.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import router

app = FastAPI(title="Rural Electrification Planner API", version="1.0.0")

# Local dev origins are always allowed; a deployed frontend's origin (e.g. Render/Vercel) is added via
# the ALLOWED_ORIGIN env var so this doesn't need a code change per deployment.
_allow_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if os.environ.get("ALLOWED_ORIGIN"):
    _allow_origins.append(os.environ["ALLOWED_ORIGIN"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
