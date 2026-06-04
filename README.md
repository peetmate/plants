# plants

Software and tooling for Pete Steward's orchid & succulent collection (Nairobi, Kenya).

This repo will grow over time. The collection's source-of-truth data (Excel
workbooks, photos, handovers) lives in Google Drive — **not** here, to avoid
Drive syncing git's internals. This repo holds code and tooling only.

## Components

- **`planta-export/`** — pull the full plant inventory out of the
  [Planta](https://getplanta.com) app (which has no export or public API) via
  screenshot automation → OCR → dedup. See `planta-export/README.md`.

## Conventions

- Large/binary artefacts (screenshots, `*.xlsx`) are git-ignored — they're
  regenerated or live in Drive.
- Keep this repo local (it is, under `~/Documents/rprojects/`) so git never
  runs inside a Drive-synced folder.
