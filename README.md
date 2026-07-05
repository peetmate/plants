# plants

A public, photo-illustrated catalogue of Pete Steward's orchid collection grown
in Nairobi, Kenya.

### 🌸 Live site → **https://peetmate.github.io/plants/**

## The website

The live site is served via **GitHub Pages** from the [`gh-pages`](../../tree/gh-pages)
branch: **https://peetmate.github.io/plants/**

Each plant card shows the accepted name, photos, and cultural notes (light,
temperature, humidity, air movement, feeding, watering and media). It's a
read-only showcase built from a personal collection database; personal details
(acquisition sources, prices, private notes) have been removed.

## Repo layout

- **`gh-pages` branch** — the published website: a self-contained `index.html`
  plus `Photos/` keyed by plant UID.
- **`main` branch** — code/tooling, incl. `collection-app/` (a localhost app for
  editing the private collection and publishing this site). The source-of-truth
  data (Excel workbooks, full-resolution photos) lives in Google Drive, not here.

Earlier screenshot/OCR tooling (`planta-export/`, used to pull the inventory out
of the [Planta](https://getplanta.com) app) has been archived and lives in the
git history.

## Conventions

- Large/binary artefacts are git-ignored — they're regenerated or live in Drive.
- The repo is kept outside any Drive-synced folder so git never runs inside one.
