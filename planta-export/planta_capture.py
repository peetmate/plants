#!/usr/bin/env python3
"""
planta_capture.py - auto-scroll-screenshot a long Planta plant list via ADB.

ONE-TIME SETUP (macOS)
  1. brew install android-platform-tools      # gives you `adb`
  2. pip3 install pillow                       # for end-of-list detection
  3. On the phone: Settings > About phone > tap "Build number" 7x to unlock
     Developer options, then turn ON "USB debugging".
  4. Plug the phone into the Mac with a USB cable. Run:  adb devices
     Accept the "Allow USB debugging?" prompt on the phone.
     You should see one line ending in `device`.

EACH RUN
  1. Open Planta -> Plants tab -> scroll to the VERY TOP of the list.
  2. Keep the phone unlocked and on that screen.
  3. python3 planta_capture.py
  Screenshots land in ./planta_shots/ as shot_0001.png, shot_0002.png, ...
  It stops by itself when the list stops moving (bottom), or at MAX_SHOTS.

TUNING (if shots skip rows or overlap too much)
  - Shots SKIP plants  -> decrease the swipe travel (raise Y_END toward Y_START).
  - Too much overlap    -> increase the swipe travel (lower Y_END).
  Do a quick test: run it, watch the first ~8 shots print, Ctrl-C, eyeball
  ./planta_shots, adjust, re-run. The auto-stop makes full runs cheap.
"""

import os
import subprocess
import sys
import time

OUT_DIR     = "planta_shots"
MAX_SHOTS   = 600     # safety cap
SETTLE      = 0.6     # seconds to wait after each swipe for the list to settle
SWIPE_MS    = 600     # swipe duration; longer = controlled drag, not a fling
STABLE_HITS = 4       # stop after this many near-identical frames in a row
                      # (>=4: rides out lazy-load pauses + periodic rejected swipes)
DIFF_THRESH = 2.0     # mean per-pixel difference below this = "no movement"
Y_START_F   = 0.85    # swipe starts here (fraction of screen height)
Y_END_F     = 0.35    # ...and ends here. Gap ~0.50H = ~5 rows/swipe, ~3 rows overlap.
                      # List area (crop 0.10-0.90 = 0.80H) shows ~8 rows. The wider
                      # 0.70H swipe left near-ZERO overlap and skipped ~11% of plants;
                      # this trades shot count for a guaranteed overlap (no skips).


def adb(*args, binary=False):
    cmd = ["adb", *args]
    if binary:
        return subprocess.run(cmd, capture_output=True).stdout
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def screen_size():
    out = adb("shell", "wm", "size")          # e.g. "Physical size: 1080x2400"
    dims = out.strip().split(":")[-1].strip()
    w, h = (int(v) for v in dims.split("x"))
    return w, h


def grab(path):
    png = adb("exec-out", "screencap", "-p", binary=True)
    with open(path, "wb") as f:
        f.write(png)


def main():
    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError:
        sys.exit("Pillow not found. Run:  pip3 install pillow")

    lines = [l for l in adb("devices").splitlines() if l.strip() and not l.startswith("List of")]
    if not any(l.endswith("device") for l in lines):
        sys.exit("No device detected. Plug in, enable USB debugging, run `adb devices`.")

    os.makedirs(OUT_DIR, exist_ok=True)
    w, h = screen_size()
    x = w // 2
    y_start, y_end = int(h * Y_START_F), int(h * Y_END_F)
    # Crop out the status bar (clock/battery tick every minute) and bottom nav,
    # so identical list content compares as identical.
    crop = (0, int(h * 0.10), w, int(h * 0.90))

    prev, stable = None, 0
    for i in range(1, MAX_SHOTS + 1):
        path = os.path.join(OUT_DIR, f"shot_{i:04d}.png")
        grab(path)
        cur = Image.open(path).convert("L").crop(crop)
        if prev is not None:
            diff = ImageStat.Stat(ImageChops.difference(prev, cur)).mean[0]
            if diff < DIFF_THRESH:
                stable += 1
                print(f"shot {i:04d}: no movement (diff={diff:.2f}) [{stable}/{STABLE_HITS}]")
                if stable >= STABLE_HITS:
                    os.remove(path)   # drop the redundant tail frame
                    print(f"\nBottom reached. {i-1} screenshots in ./{OUT_DIR}/")
                    return
            else:
                stable = 0
                print(f"shot {i:04d}: captured (diff={diff:.2f})")
        else:
            print(f"shot {i:04d}: captured (first frame)")
        prev = cur
        adb("shell", "input", "swipe", str(x), str(y_start), str(x), str(y_end), str(SWIPE_MS))
        time.sleep(SETTLE)

    print(f"\nHit MAX_SHOTS ({MAX_SHOTS}). If the list wasn't done, raise MAX_SHOTS and re-run.")


if __name__ == "__main__":
    main()
