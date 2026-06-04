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

## Pipeline (now three phases)
1. **List capture** — `planta_capture.py` auto-scrolls the Plants tab over ADB,
   screenshots each step with deliberate overlap, and auto-stops at the bottom.
2. **Per-plant photo capture** — `planta_photos.py` *(NOT YET WRITTEN)*: for each
   plant, drill in and screenshot its photos. See "Per-plant photo capture" below.
3. **Process** — `planta_process.py` *(NOT YET WRITTEN)*: OCR the list shots, stitch
   the overlapping frames, drop duplicates, output Latin name / common name /
   category to a spreadsheet.

## Per-plant photo capture  (NEW requirement, 2026-06-04)
Each plant may have photos attached. Desired per-plant flow:
tap plant entry → scroll down to **History** → tap an **"Added photo"** entry →
screenshot the photo → back → look for the next "Added photo" entry → repeat →
exit/back to the list → next plant.

**Decisions (from Pete):**
- **Photos: screenshots only.** Planta has no export; photos live only in-app, so
  screenshotting the in-app photo is the only route. (Lossy — on-screen render, not
  the original upload — but accepted.)
- **Capture per plant = photos + plant name.** Grab the plant's name/ID from the
  detail page so each screenshot can be filed to the right plant (→ collection UID).
- **Skip plants with no photo in History.** If a plant's History has no "Added photo"
  entry, back out and move on — don't record it. Only plants with ≥1 photo matter here.
- **Every captured plant gets a UID.** Assign each captured plant a UID so its
  photo(s) can be filed and later reconciled. (Open: reuse the collection's existing
  col-A UID where the plant already exists, vs. a temp capture-ID resolved during
  harmonization — see harmonization step.)

## Harmonization against the Orchid workbook  (NEW, 2026-06-04 — separate exercise)
After capture, reconcile the captured Planta plants (name + photo + UID) against the
master Orchids workbook (`Plants/Collection/…Orchids.xlsx`). Match each Planta plant
to its existing collection row / UID where it exists; flag plants in Planta but not in
the workbook (and vice-versa). This is a distinct manual-ish step after the capture
+ process phases — not part of the automation. File matched photos to the plant's
collection UID via the existing `orchid-photo-filing` convention.

**Build guidance — do NOT use blind coordinate taps.** With 861 plants and a
variable number of photos each, hard-coded tap positions desync and silently
corrupt the run. Instead drive by the UI tree each step:
```bash
adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml
```
Parse the XML for element text / resource-id / bounds → find the plant name, find &
count the "Added photo" history rows, tap by real bounds, self-correct per screen.
Save shots named with the plant name so attribution survives. Robust back-navigation
+ "advance to next plant" logic is the crux; develop iteratively against the live phone.

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

## Cost / tokens
Whole pipeline runs **locally in Python — no API tokens.** Screen-grabs are ADB
(`adb exec-out screencap`). **OCR = local** (Tesseract via `pytesseract`, or macOS
Vision) — do NOT hand each image to the model. Plant names come from the
`uiautomator dump` accessibility tree as exact text (no OCR), and the flat list may
expose names there too — check before OCR'ing the 133 shots. Model is for writing the
scripts + harmonization judgement, not per-image processing. Claude-vision OCR only as
a fallback if Tesseract chokes on Planta's font.

## Next steps / open items  (do these in Claude Code / VSCode — needs USB phone + native git)
- [x] **Test capture run** (2026-06-04): full run captured **133 shots, A→Z, all
      861 plants** into `planta_shots/`. Tuning that worked: swipe `Y_START_F=0.85`
      → `Y_END_F=0.15` (~8 plants/shot, 1-row overlap), `STABLE_HITS=4` to ride out
      periodic single-swipe stalls + the lazy-load pause. Keep screen awake during a
      run: `adb shell svc power stayon true` (revert: `... stayon false`).
- [ ] **Write `planta_photos.py`** — per-plant photo capture (see section above).
      UI-tree-driven (uiautomator dump), not blind taps. Grab plant name + screenshot
      each "Added photo". **Skip plants with no photo in History.** Assign each
      captured plant a **UID**. Biggest unknown; build iteratively against live phone.
- [x] **`planta_process.py`** (2026-06-04): DONE — stitches overlapping shots
      (largest suffix/prefix name-overlap per shot, preserves genuine duplicate names)
      → `planta_plants.csv` + `.xlsx`. **Result: 874 plants, full A→Z** (vs app's 861;
      ~13 over from repeated-name overlap misses + owner's own spelling variants kept
      verbatim, e.g. Mammilaria/Mammillaria, Echeveria/Echiveria). Regenerate anytime:
      `python3 planta_process.py`. `shots.json` = the OCR transcript it reads.
      ⚠️ **OCR was done by Claude-vision subagents, NOT the local route this doc prefers
      (see Cost/tokens).** It worked well, but cost tokens and introduced spelling drift.
      For any RE-capture, switch to `uiautomator dump` → exact accessibility-tree text
      (zero OCR, zero tokens, no Mammilaria-style typos). Worth redoing list capture that
      way before the photo phase, which is uiautomator-driven anyway.
- [x] **Capture overlap fix** (2026-06-04): first run (swipe 0.85→0.15) skipped ~11%
      (near-zero overlap). Re-ran at `Y_END_F=0.35` (~3-row overlap) → caught everything.
      That run wrapped and re-scanned (A→Z→A→Z); only shots 1–139 (clean first pass) are
      in `shots.json`. Pass-1 data kept as `shots_pass1.json`.
- [ ] Capture tuning: confirm consecutive shots overlap by ~a row; nudge `Y_END_F`
      up if any plants get skipped.
- [ ] Confirm output target — new sheet in the Orchids workbook vs standalone file.
- [ ] **Harmonize captured plants ↔ Orchids workbook** (separate exercise, see above):
      match Planta plant → collection UID, flag mismatches, file photos by UID.

## Key decisions
- Swipe < one screen for guaranteed overlap; dedup handles the repeats.
- Screenshots and `*.xlsx` are never committed (regenerated / large).
