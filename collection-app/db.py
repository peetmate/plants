"""SQLite sidecar store: per-plant note + cover overrides, kept in DATA_DIR.

The workbook stays the source of truth; these are unapplied edits, overlaid on the
collection at load and merged back only by the (v1.1) apply step.
"""
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS note_edits (
  uid        INTEGER PRIMARY KEY,
  note       TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS cover_edits (
  uid        INTEGER PRIMARY KEY,
  photo      TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS apply_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ran_at     TEXT,
  summary    TEXT
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.executescript(SCHEMA)


def _now():
    return datetime.now(timezone.utc).isoformat()


def upsert_note(uid, note):
    with _conn() as c:
        c.execute(
            "INSERT INTO note_edits(uid, note, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(uid) DO UPDATE SET note=excluded.note, updated_at=excluded.updated_at",
            (uid, note, _now()),
        )


def upsert_cover(uid, photo):
    with _conn() as c:
        c.execute(
            "INSERT INTO cover_edits(uid, photo, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(uid) DO UPDATE SET photo=excluded.photo, updated_at=excluded.updated_at",
            (uid, photo, _now()),
        )


def get_notes():
    with _conn() as c:
        return {r["uid"]: r["note"] for r in c.execute("SELECT uid, note FROM note_edits")}


def get_covers():
    with _conn() as c:
        return {r["uid"]: r["photo"] for r in c.execute("SELECT uid, photo FROM cover_edits")}


def pending():
    with _conn() as c:
        notes = [r["uid"] for r in c.execute("SELECT uid FROM note_edits")]
        covers = [r["uid"] for r in c.execute("SELECT uid FROM cover_edits")]
    return notes, covers
