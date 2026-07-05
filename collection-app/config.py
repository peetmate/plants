"""Runtime config for the local collection app.

Data (workbook, collection.json, Photos, sidecar DB) lives in Google Drive and is
referenced by DATA_DIR — never committed. Override any value via env var.
"""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get(
    "DATA_DIR",
    os.path.expanduser(
        "~/Library/CloudStorage/GoogleDrive-peetmate@gmail.com/My Drive/Plants/Collection"
    ),
))

COLLECTION_JSON = DATA_DIR / "collection.json"
COLLECTION_HTML = DATA_DIR / "collection.html"
PHOTOS_DIR = DATA_DIR / "Photos"
COVERS_JSON = PHOTOS_DIR / "covers.json"
DB_PATH = Path(os.environ.get("EDITS_DB", DATA_DIR / "edits.sqlite"))

# Git repo that holds the gh-pages branch (this app lives inside it).
REPO_DIR = Path(os.environ.get("REPO_DIR", Path(__file__).resolve().parent.parent))
# build_public.py (redacted public-site builder) lives beside the Claude notes.
BUILD_PUBLIC = Path(os.environ.get(
    "BUILD_PUBLIC", DATA_DIR.parent / "Claude" / "build_public.py"))

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
