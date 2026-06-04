#!/usr/bin/env python3
"""
planta_list.py - capture the full Planta plant list as EXACT text, no OCR.

Token-minimal replacement for the screenshot->vision-OCR route: instead of
photographing each screen and reading pixels, we pull Android's accessibility
tree (`uiautomator dump`) at each scroll step and parse the plant names straight
out of it as exact strings. Runs entirely on the host (Python driving adb) - no
model calls per plant, no per-image cost.

HOW IT READS A SCREEN
  Each plant card contributes two left-aligned (x-left == LEFT_X) TextViews in
  vertical order: the bold NAME line, then the lighter CATEGORY line. The "76%"
  badge sits further right (x-left ~607), so filtering on LEFT_X isolates card
  text. Cards are separated by a large vertical gap (thumbnail spacing); the
  name->category gap within a card is ~0. We group lines into cards by that gap:
  first line = name, the rest = category.

DE-OVERLAP
  Consecutive scroll dumps overlap. We stitch by the largest suffix/prefix
  name-overlap (same logic as planta_process.py), which preserves genuine
  duplicate names while dropping the scroll overlap. Names are exact here, so
  the overlap match is reliable.

USAGE
  python3 planta_list.py            # full run from the current scroll position
  python3 planta_list.py 6          # stop after 6 dumps (smoke test)
  Output: planta_plants.csv (+ .xlsx if openpyxl). Start at the TOP of the
  Plants tab. Keep the screen awake: adb shell svc power stayon true
"""
import csv
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(HERE, "planta_plants.csv")
OUT_XLSX = os.path.join(HERE, "planta_plants.xlsx")
REMOTE_XML = "/sdcard/planta_ui.xml"
LOCAL_XML = os.path.join(HERE, ".planta_ui.xml")

LEFT_X = 252          # x-left pixel of card name/category text (Pixel 9 Pro XL)
CARD_GAP = 60         # vertical gap (px) larger than this = new card
SETTLE = 0.6          # seconds after a swipe before dumping
STABLE_HITS = 3       # consecutive no-new-plants dumps that mean "bottom"
MAX_DUMPS = 400       # safety cap
Y_START_F = 0.85      # swipe travel: 0.85 -> 0.45 ~= half screen, generous overlap
Y_END_F = 0.45


def adb(*args, binary=False):
    cmd = ["adb", *args]
    if binary:
        return subprocess.run(cmd, capture_output=True).stdout
    return subprocess.run(cmd, capture_output=True, text=True).stdout


PKG = "com.stromming.planta"


def screen_size():
    out = adb("shell", "wm", "size")
    w, h = (int(v) for v in out.strip().split(":")[-1].strip().split("x"))
    return w, h


def planta_foreground():
    out = adb("shell", "dumpsys", "activity", "activities")
    for line in out.splitlines():
        if "topResumedActivity" in line:
            return PKG in line
    return False


def ensure_planta(max_wait=120):
    """Block until Planta is foreground again (survives calls/notifications).
    Tries to relaunch; if something else is up (e.g. a phone call), waits."""
    waited = 0
    while not planta_foreground():
        adb("shell", "am", "start", "-n", f"{PKG}/.main.views.MainActivity")
        time.sleep(2)
        waited += 2
        if waited >= max_wait:
            sys.exit("Planta not foreground after {}s (phone in use?). Re-run when free."
                     .format(max_wait))
        if waited % 10 == 0:
            print(f"  ...waiting for Planta foreground ({waited}s) - dismiss any call/popup")


def is_garbage_name(name):
    if not name:
        return True
    return " " not in name and name.endswith("aceae")


def dump_cards():
    """Pull the accessibility tree and return this screen's cards top-to-bottom
    as [{name, category}], grouping LEFT_X text lines by vertical gap."""
    adb("shell", "uiautomator", "dump", REMOTE_XML)
    xml = adb("exec-out", "cat", REMOTE_XML, binary=True)
    root = ET.fromstring(xml)
    lines = []  # (top, bottom, text)
    for n in root.iter("node"):
        if n.get("class") != "android.widget.TextView":
            continue
        txt = (n.get("text") or "").strip()
        if not txt:
            continue
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
        if not m:
            continue
        x0, y0, x1, y1 = (int(g) for g in m.groups())
        if x0 != LEFT_X:
            continue
        lines.append((y0, y1, re.sub(r"\s+", " ", txt)))
    lines.sort()
    cards, cur = [], []
    prev_bottom = None
    for top, bottom, txt in lines:
        if prev_bottom is not None and top - prev_bottom > CARD_GAP and cur:
            cards.append(cur)
            cur = []
        cur.append(txt)
        prev_bottom = bottom
    if cur:
        cards.append(cur)
    out = []
    for c in cards:
        name = c[0]
        cat = c[1] if len(c) > 1 else None
        if is_garbage_name(name):
            continue
        out.append({"name": name, "category": cat})
    return out


def overlap_k(tail, head):
    maxk = min(len(tail), len(head))
    for k in range(maxk, 0, -1):
        if tail[-k:] == head[:k]:
            return k
    return 0


def stitch(merged, cards):
    m = [r["name"] for r in merged]
    s = [r["name"] for r in cards]
    k = overlap_k(m, s)
    base = len(merged) - k
    for i in range(k):  # backfill categories from fuller occurrences
        if merged[base + i]["category"] is None and cards[i]["category"]:
            merged[base + i]["category"] = cards[i]["category"]
    added = cards[k:]
    merged.extend(added)
    return len(added)


def swipe(w, h):
    x = w // 2
    adb("shell", "input", "swipe", str(x), str(int(h * Y_START_F)),
        str(x), str(int(h * Y_END_F)), "500")


def split_name(full):
    m = re.search(r"\s*\(([^()]*)\)\s*$", full)
    if m:
        return full[:m.start()].strip(), m.group(1).strip()
    return full, None


def write_outputs(rows):
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["#", "Name", "Common / cultivar", "Category"])
        for i, r in enumerate(rows, 1):
            _, common = split_name(r["name"])
            wr.writerow([i, r["name"], common or "", r["category"] or ""])
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        return False
    wb = Workbook(); ws = wb.active; ws.title = "Planta export"
    ws.append(["#", "Name", "Common / cultivar", "Category"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, r in enumerate(rows, 1):
        _, common = split_name(r["name"])
        ws.append([i, r["name"], common or "", r["category"] or ""])
    for col, wd in zip("ABCD", (5, 52, 28, 22)):
        ws.column_dimensions[col].width = wd
    ws.freeze_panes = "A2"
    wb.save(OUT_XLSX)
    return True


def main():
    max_dumps = int(sys.argv[1]) if len(sys.argv) > 1 else MAX_DUMPS
    if "device" not in adb("get-state").strip():
        sys.exit("No device. Plug in + USB debugging.")
    w, h = screen_size()
    merged, stable = [], 0
    for i in range(1, max_dumps + 1):
        # Retry empty dumps: a 0-card screen means Planta isn't showing the list
        # (a call/popup stole focus, or a transient render). Re-foreground + retry
        # rather than mistaking it for the bottom of the list.
        cards = []
        for attempt in range(5):
            cards = dump_cards()
            if cards:
                break
            ensure_planta()
            time.sleep(1.0)
        if not cards:
            print(f"dump {i:03d}: still empty after retries - skipping swipe")
            continue
        added = stitch(merged, cards) if merged else (merged.extend(cards) or len(cards))
        print(f"dump {i:03d}: saw {len(cards):2} cards, +{added} new, total {len(merged)}")
        if added == 0:                 # cards present but all already seen = real bottom
            stable += 1
            if stable >= STABLE_HITS:
                print(f"\nBottom reached. {len(merged)} plants.")
                break
        else:
            stable = 0
        swipe(w, h)
        time.sleep(SETTLE)
    else:
        print(f"\nHit max dumps ({max_dumps}). {len(merged)} plants.")
    n = write_outputs(merged)
    print(f"  wrote {os.path.basename(OUT_CSV)}" +
          (f" + {os.path.basename(OUT_XLSX)}" if n else " (CSV only; pip install openpyxl)"))


if __name__ == "__main__":
    main()
