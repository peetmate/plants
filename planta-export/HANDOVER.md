# HANDOVER — Planta inventory extraction

**Goal:** Pull the full plant list (861 plants, 45 sites) out of the Planta app
into a clean spreadsheet — ideally a new sheet in the master Orchids workbook.

**Why this route:** Planta has no export, no public API, and no Claude connector.
Plan: screenshot-automation -> OCR -> dedup.

## Repo location
`/Users/pstewarda/Library/CloudStorage/GoogleDrive-peetmate@gmail.com/My Drive/Plants`

> ⚠️ Google Drive + git: Drive Desktop syncs the many tiny files in `.git` and
> races on them, which can corrupt history. Prefer a **local** working repo
> (e.g. `~/code/Plants`) with GitHub as the remote/backup, OR pause Drive sync
> while running git commands. Use the Drive folder for screenshots and outputs.

## Pipeline (two phases)
1. **Capture** — `planta_capture.py` auto-scrolls the Plants tab over ADB,
   screenshots each step with deliberate overlap, and auto-stops at the bottom.
2. **Process** — `planta_process.py` *(NOT YET WRITTEN)*: OCR the shots, stitch
   the overlapping frames, drop duplicates, output Latin name / common name /
   category to a spreadsheet.

## Built so far
- `planta_capture.py` — ADB capture; tunable swipe distance; auto-stop via a
  cropped frame-diff (status bar cropped out so the ticking clock doesn't fool
  end-detection).
- `README.md`, `.gitignore` (ignores screenshots + `*.xlsx`), `requirements.txt`
  (pillow).

## Environment
Mac + Android phone over USB. Setup:
```bash
brew install android-platform-tools
pip3 install pillow
# phone: Settings > About > tap Build number 7x > Developer options > USB debugging ON
```

## GitHub
Ready to init / commit / push:
```bash
git init && git add . && git commit -m "Planta export tooling"
gh repo create plants --private --source=. --remote=origin --push
```

## Next steps / open items
- [ ] Write `planta_process.py` — needs **2–3 sample screenshots** to calibrate
      OCR to Planta's list layout.
- [ ] Capture tuning: test run, confirm consecutive shots overlap by ~a row;
      nudge `Y_END_F` up if any plants get skipped.
- [ ] Confirm output target — new sheet in the Orchids workbook vs standalone file.

## Key decisions
- Swipe < one screen for guaranteed overlap; dedup handles the repeats.
- Screenshots and `*.xlsx` are never committed (regenerated / large).
