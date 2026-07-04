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

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
