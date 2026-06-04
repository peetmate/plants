# HANDOVER — Planta inventory extraction

**Goal:** Pull the full plant list (861 plants, 45 sites) out of the Planta app
into a clean spreadsheet — ideally a new sheet in the master Orchids workbook.

**Why this route:** Planta has no export, no public API, and no Claude connector.
Plan: screenshot-automation -> OCR -> dedup.

## Repo location  (set up 2026-06-04)
**Local git repo:** `~/Documents/rprojects/plants/`  — this tooling lives in
`plants/planta-export/`. Pushed to GitHub as a private repo (`gh repo create plants`).

> ⚠️ Kept deliberately **out** of Google Drive: Drive Desktop syncs the many tiny
> files in `.git` and races on them, which can corrupt history. Source-of-truth
> data (Orchids workbook, photos) stays in Drive; code/tooling stays in this repo.

> Note: git can't be run from the Cowork sandbox (it can't unlink `.git` lock/temp
> files — "Operation not permitted"). Run git natively — **Claude Code in VSCode**.

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
✅ Done — repo created and pushed (private). Routine flow from here:
```bash
git add . && git commit -m "what changed" && git push
```

## Next steps / open items  (do these in Claude Code / VSCode — needs USB phone + native git)
- [ ] **Test capture run:** phone plugged in, USB debugging on, Planta open at top
      of the Plants tab → `python3 planta_capture.py`. Confirms capture works and
      produces sample shots.
- [ ] **Write `planta_process.py`** — the OCR → stitch → dedup step. NOT YET WRITTEN.
      Needs **2–3 sample screenshots** from the test run to calibrate to Planta's
      list layout (row height, text regions, column positions).
- [ ] Capture tuning: confirm consecutive shots overlap by ~a row; nudge `Y_END_F`
      up if any plants get skipped.
- [ ] Confirm output target — new sheet in the Orchids workbook vs standalone file.

## Key decisions
- Swipe < one screen for guaranteed overlap; dedup handles the repeats.
- Screenshots and `*.xlsx` are never committed (regenerated / large).
