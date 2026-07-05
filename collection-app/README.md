# collection-app

A small **local, localhost-only** web app for the full (private) orchid
collection. It serves the existing desktop viewer and lets you:

- edit a **note** per plant, and
- pick the **cover photo** per plant,

persisting both to a SQLite sidecar. The Excel workbook stays the source of
truth; it is written only by the separate, deliberate **apply** step
(`/api/apply`), which follows the project's safe protocol.

## Run

```bash
cd collection-app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py          # -> http://127.0.0.1:8000
```

Data (workbook, `collection.json`, `Photos/`, sidecar DB) is **not** in this
repo — it lives in Google Drive and is located at runtime via `DATA_DIR`.

The **apply** step needs **LibreOffice** (`soffice`) for headless recalc:

```bash
brew install --cask libreoffice
```

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
| POST   | `/api/apply`                | merge sidecar → workbook + covers.json (safe)|
| POST   | `/api/refresh`              | rebuild viewers (`build_collection.py`)  |
| GET    | `/Photos/<path>`            | photo files from `DATA_DIR/Photos`       |

## Apply workflow (implemented — `apply.py`)

`POST /api/apply` (or the amber **Apply to workbook** button that appears when
edits are pending) merges sidecar notes into the workbook Notes column (col L,
keyed by UID) and cover picks into `Photos/covers.json`, following the safe
protocol — nothing touches the Drive workbook until every check passes:

1. work on a **local copy**, never the Drive file directly;
2. openpyxl writes only the Notes column (culture/formula columns untouched);
3. **LibreOffice headless recalc** rebuilds formula caches (openpyxl save drops
   them and the downstream viewers read `data_only`);
4. verify readback — notes written, col-F keys resolve, sheets/charts intact,
   and `validate_workbook.py` shows **no new** issues vs the current workbook;
5. **optimistic-lock** copy-back — abort if the Drive workbook changed meanwhile;
6. back up the workbook to `Backups/`, then atomically replace it;
7. update `covers.json`, log to `apply_log`, clear the applied sidecar rows.

## Refresh the viewers (`refresh.py`)

After applying (or any workbook/photo change), rebuild the viewers so
`collection.json` + `collection.html` + `collection-portable.html` reflect the
current workbook. Either:

- click **Refresh viewers** (offered in the apply bar after an apply), which
  `POST`s `/api/refresh`, or
- run it from the terminal: `python refresh.py`.

Both run the project's `build_collection.py` in `DATA_DIR`. The **public**
GitHub Pages site is a separate step — rebuild the redacted copy with
`build_public.py` and push `gh-pages` (see `PLAYBOOK.md`); refresh only reminds.
