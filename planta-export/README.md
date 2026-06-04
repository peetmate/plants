# planta-export

Tooling to pull a full plant inventory out of the [Planta](https://getplanta.com)
app, which has no export feature or public API. Two phases:

1. **Capture** — `planta_capture.py` drives the phone over ADB: it auto-scrolls
   the Plants tab, screenshots each step with deliberate overlap, and stops itself
   when it reaches the bottom of the list.
2. **Process** — `planta_process.py` *(added next)* OCRs the screenshots, stitches
   the overlapping frames, drops duplicates, and writes a clean inventory
   (Latin name, common name, category) to a spreadsheet.

## Setup (macOS)

```bash
brew install android-platform-tools   # adb
pip3 install -r requirements.txt
```

On the phone: Settings > About phone > tap **Build number** 7x to unlock
Developer options, then turn on **USB debugging**. Plug in via USB, run
`adb devices`, and accept the prompt on the phone.

## Capture

1. Open Planta > **Plants** tab > scroll to the very top.
2. Keep the phone unlocked on that screen.
3. Run:

   ```bash
   python3 planta_capture.py
   ```

Screenshots land in `planta_shots/`. The run stops automatically at the bottom
of the list (or at `MAX_SHOTS`). See the docstring in `planta_capture.py` for
swipe-distance tuning if any rows get skipped.

## Process

Coming next — calibrated to Planta's list layout. Until then, the screenshots
can be handed to Claude directly for transcription.

## Notes

- `planta_shots/` and `*.png` are git-ignored — screenshots are large and
  regenerated each run, so they don't belong in version control.
- The inventory is just species names; nothing sensitive, but `--private` is a
  sensible default for a personal repo.
