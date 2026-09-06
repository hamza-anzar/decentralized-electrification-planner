"""Shared filesystem paths, used by every core module and page.

Mirrors the PROJECT_ROOT / DATA_DIR pattern used throughout the notebooks, so the app reads and
writes the exact same data/ folder they built and validated.
"""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]      # .../backend
# backend/ lives one level deeper than the old app/ folder did (inside rural-electrification-webapp/),
# so the project root is two levels up from here, not one — this must stay in sync with that nesting.
PROJECT_ROOT = APP_DIR.parent.parent                  # .../Rural Electrification (the actual project root)
DATA_DIR = PROJECT_ROOT / "data"                      # the shared data/ folder used by every notebook and this app
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

DATA_DIR.mkdir(exist_ok=True)
