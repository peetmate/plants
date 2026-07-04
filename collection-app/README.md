# collection-app

A small **local, localhost-only** web app for the full (private) orchid
collection. It serves the existing desktop viewer and lets you:

- edit a **note** per plant, and
- pick the **cover photo** per plant,

persisting both to a SQLite sidecar. The Excel workbook stays the source of
truth; this app never writes it directly (that is the separate, deliberate
*apply* step — v1.1, not yet built).

## Run

```bash
cd collection-app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py          # -> http://127.0.0.1:8000
```

Data (workbook, `collection.json`, `Photos/`, sidecar DB) is **not** in this
repo — it lives in Google Drive and is located at runtime via `DATA_DIR`.

## Config (env vars)

| Var         | Default                                                             |
|-------------|---------------------------------------------------------------------|
| `DATA_DIR`  | `~/Library/CloudStorage/GoogleDrive-…/My Drive/Plants/Collection`   |
| `EDITS_DB`  | `$DATA_DIR/edits.sqlite`                                             |
| `HOST`      | `127.0.0.1`                                                          |
| `PORT`      | `8000`                                                               |

`DATA_DIR` must contain `collection.html`, `collection.json`, and `Photos/`
(all produced by `build_collection.py`).

## How it works

- `GET /` serves `collection.html` with `static/adapter.js` injected. The adapter
  loads data from `/api/collection`, makes the Notes field editable, and routes
  the ★ cover picker to the server instead of `localStorage`.
- Edits are stored in the sidecar (`note_edits`, `cover_edits`) and **overlaid**
  on the collection at load, so they appear immediately and survive restarts.
  A small amber dot marks plants with unapplied edits.

## API

| Method | Path                        | Purpose                                  |
|--------|-----------------------------|------------------------------------------|
| GET    | `/`                         | viewer HTML (adapter injected)           |
| GET    | `/api/collection`           | plants with sidecar edits overlaid       |
| POST   | `/api/plant/<uid>/note`     | `{note}` → upsert note                    |
| POST   | `/api/plant/<uid>/cover`    | `{photo}` → upsert cover pick             |
| GET    | `/api/pending`              | uids with unapplied note/cover edits     |
| POST   | `/api/apply`                | **501 in v1** — workbook write-back (v1.1)|
| GET    | `/Photos/<path>`            | photo files from `DATA_DIR/Photos`       |

## Apply workflow (v1.1 — planned, issue #5)

Merges sidecar notes into the workbook Notes column and cover picks into
`Photos/covers.json` using the project's safe protocol: back up the workbook,
work on a local copy, write notes with openpyxl (culture formula columns
untouched), LibreOffice-headless recalc, validate, optimistic-lock copy-back,
log to `apply_log`.
