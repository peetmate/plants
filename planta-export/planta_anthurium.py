#!/usr/bin/env python3
"""
planta_anthurium.py - archive full-res detail photos for the genuinely-duplicated
Anthurium plants (each instance is a different plant: different thumbnail/flower).
Only these names, only their instances - NOT a full-list revisit.

Robust method: Planta's search filter CLEARS when you open a plant and press back,
so we re-search the EXACT name before opening each instance and open by index
(the instances fit one filtered screen). Each instance's photos saved with an
instance tag for manual review.

OUTPUT  planta_dups_review/<slug>_i<inst>__<date>[_k].png  (+ _index.csv)
USAGE   python3 planta_anthurium.py
"""
import csv
import io
import os
import sys
import time

import planta_photos as P
import planta_dups as PD

NAMES = ["Anthurium scherzianum", "Anthurium andraenum", "Anthurium andreanum"]
REVIEW_DIR = PD.REVIEW_DIR
INDEX = PD.INDEX


def research(w, h, query):
    sxy = PD.find_search(w, h)
    if not sxy:
        return False
    P.adb("shell", "input", "tap", str(sxy[0]), str(sxy[1])); time.sleep(0.5)
    P.adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(60):
        P.adb("shell", "input", "keyevent", "KEYCODE_DEL")
    P.adb("shell", "input", "text", query.replace(" ", "%s")); time.sleep(1.3)
    # dismiss the on-screen keyboard (it covers the lower filtered rows, so taps by
    # row-y would hit the keyboard instead of the plant). BACK closes the IME but
    # keeps the query + filter.
    P.adb("shell", "input", "keyevent", "KEYCODE_BACK"); time.sleep(0.8)
    return True


def rows_named(name):
    return [(n, ty) for n, ty in P.list_plant_rows(P.dump()) if n == name]


def capture_instance(w, h, name, inst, iw):
    """On the plant detail page: open Photos & Notes, save every photo of THIS
    instance tagged with the instance index. Returns count."""
    target = None
    for _ in range(P.MAX_DETAIL_SCROLLS):
        t = P.find_text(P.dump(), "View all updates")
        if t:
            target = t; break
        P.swipe(w, h, 0.80, 0.35)
    if not target:
        return 0
    P.adb("shell", "input", "tap", *map(str, target)); time.sleep(P.SETTLE)
    if P.PHOTOS_ACT not in P.top_activity():
        return 0
    seen, saved, stale = set(), 0, 0
    while stale < 2:
        cards = [c for c in P.photo_cards(P.dump()) if c[0] not in seen]
        if not cards:
            stale += 1; P.swipe(w, h, 0.80, 0.40); continue
        stale = 0
        date, cx, cy = cards[0]; seen.add(date)
        P.adb("shell", "input", "tap", str(cx), str(cy)); time.sleep(P.SETTLE)
        fn = os.path.join(REVIEW_DIR, f"{P.slug(name)}_i{inst}__{P.slug(date)}.png")
        k = 1
        while os.path.exists(fn):
            fn = os.path.join(REVIEW_DIR, f"{P.slug(name)}_i{inst}__{P.slug(date)}_{k}.png"); k += 1
        try:
            from PIL import Image
            Image.open(io.BytesIO(P.adb("exec-out", "screencap", "-p", binary=True))).crop(P.PHOTO_CROP).save(fn)
            iw.writerow([os.path.basename(fn), name, date]); saved += 1
        except Exception as e:
            print(f"    ! {name} i{inst} {date}: {e}")
        P.back()
    return saved


def nav_to_search(w, h, query):
    """Deterministically return to the flat Plants list and (re)apply a search,
    via `am start` (recovers from ANY state - detail page, photo viewer, even the
    launcher) instead of fragile BACK presses that kept exiting the app."""
    P.adb("shell", "am", "start", "-n", f"{P.PKG}/.main.views.MainActivity"); time.sleep(1.5)
    P.adb("shell", "input", "tap", "303", "2073"); time.sleep(1)   # Plants bottom-nav
    return research(w, h, query)


def main():
    for _ in range(24):
        if "device" in P.adb("get-state").strip():
            break
        time.sleep(5)
    try:
        import PIL  # noqa
    except ImportError:
        sys.exit("Need Pillow.")
    w, h = P.screen_size()
    os.makedirs(REVIEW_DIR, exist_ok=True)
    new = not os.path.exists(INDEX) or os.path.getsize(INDEX) == 0
    idx = open(INDEX, "a", newline="", encoding="utf-8"); iw = csv.writer(idx)
    if new:
        iw.writerow(["file", "plant", "date"]); idx.flush()

    for name in NAMES:
        if not nav_to_search(w, h, name):
            print(f"  {name}: search field not found"); continue
        n_inst = len(rows_named(name))
        print(f"{name}: {n_inst} instance(s) on screen")
        for k in range(n_inst):
            if not nav_to_search(w, h, name):   # fresh deterministic nav per instance
                break
            rows = rows_named(name)
            if k >= len(rows):
                break
            _, ty = rows[k]
            P.adb("shell", "input", "tap", str((P.LEFT_X + 700) // 2), str(ty)); time.sleep(P.SETTLE)
            if P.LIST_ACT not in P.top_activity():
                print(f"  {name} i{k+1}: detail didn't open (skipped)")
                continue
            tt = PD.detail_title(P.dump())
            if not PD.title_matches(tt, name):
                print(f"  {name} i{k+1}: title mismatch {tt!r} (skipped)")
                continue
            got = capture_instance(w, h, name, k + 1, iw); idx.flush()
            print(f"  {name} i{k+1}: +{got}")
            # no BACK-to-list: the next nav_to_search() am-starts the main screen
    idx.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
