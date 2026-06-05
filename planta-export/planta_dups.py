#!/usr/bin/env python3
"""
planta_dups.py - capture photos for the flagged duplicate-named ("different
plant") names into ONE flat folder for manual review/dedup. Uses Planta's SEARCH
(not a full-list scroll-walk, which kept false-stopping on sparse targets): type a
clean prefix per name, the list filters to just that plant's instances, capture
every distinct photo. Dedup by (plant name, photo date) so re-visits don't dup and
genuinely different instances are all kept. Detail title is verified against the
row name to guard against mis-taps. ~0 tokens (screenshots are files).

OUTPUT
  planta_dups_review/<plant-slug>__<date>[_k].png   (flat; review/dedup by eye)
  planta_dups_review/_index.csv                      (file, plant, date)

USAGE  python3 planta_dups.py
"""
import csv
import io
import os
import sys
import time

import planta_photos as P

# name -> search prefix (letters/spaces only; avoids escaping parens/quotes in
# `adb input text`). We only ACT on rows whose EXACT name is a key here, so a
# prefix that also matches a non-target (e.g. "Peperomia dolabriformis" vs
# "...(Prayer Pepper)") is fine - the non-target row is ignored.
TARGETS = {
    "Anthurium scherzianum": "Anthurium scherzianum",
    "Neoregalia carolinae": "Neoregalia carolinae",
    "Peperomia clusiifolia": "Peperomia clusiifolia",
    "Peperomia dolabriformis": "Peperomia dolabriformis",
    "Oncidium Intergeneric Hybrid": "Oncidium Intergeneric Hybrid",
    "Diaphanthe fragrantissima (Kakamega)": "Diaphanthe",
}
REVIEW_DIR = os.path.join(P.HERE, "planta_dups_review")
INDEX = os.path.join(REVIEW_DIR, "_index.csv")


def detail_title(root):
    xs = sorted((y0, t) for x0, y0, x1, y1, t, d, clk, cls in P.nodes(root)
                if x0 == 36 and t)
    return xs[0][1] if xs else ""


def title_matches(title, name):
    a, b = title.lower(), name.lower()
    return a.startswith(b[:18]) or b in a or a in b


def screencap_crop(path):
    from PIL import Image
    png = P.adb("exec-out", "screencap", "-p", binary=True)
    Image.open(io.BytesIO(png)).crop(P.PHOTO_CROP).save(path)


def find_search(w, h):
    """Fling to the top until the search EditText is visible; return its tap point.
    Matched by class (its text becomes the query once typed, so a text match only
    works the first time)."""
    for _ in range(8):
        root = P.dump()
        for x0, y0, x1, y1, t, d, clk, cls in P.nodes(root):
            if cls == "EditText" or "Search" in t:
                return ((x0 + x1) // 2, (y0 + y1) // 2)
        for _ in range(8):
            P.adb("shell", "input", "swipe", str(w // 2), str(h // 4),
                  str(w // 2), str(h * 9 // 10), "50")
    return None


def run_search(w, h, sxy, prefix):
    P.adb("shell", "input", "tap", str(sxy[0]), str(sxy[1])); time.sleep(0.6)
    P.adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(40):                       # clear any prior query
        P.adb("shell", "input", "keyevent", "KEYCODE_DEL")
    P.adb("shell", "input", "text", prefix.replace(" ", "%s")); time.sleep(1.2)


def capture_into_flat(w, h, name, seen, iw):
    target = None
    for _ in range(P.MAX_DETAIL_SCROLLS):
        root = P.dump()
        target = P.find_text(root, "View all updates")
        if target:
            break
        P.swipe(w, h, 0.80, 0.35)
    if not target:
        return 0
    P.adb("shell", "input", "tap", *map(str, target)); time.sleep(P.SETTLE)
    if P.PHOTOS_ACT not in P.top_activity():
        return 0
    saved, stale = 0, 0
    while stale < 2:
        cards = [c for c in P.photo_cards(P.dump()) if (name, c[0]) not in seen]
        if not cards:
            stale += 1
            P.swipe(w, h, 0.80, 0.40)
            continue
        stale = 0
        date, cx, cy = cards[0]
        seen.add((name, date))
        P.adb("shell", "input", "tap", str(cx), str(cy)); time.sleep(P.SETTLE)
        fn = os.path.join(REVIEW_DIR, f"{P.slug(name)}__{P.slug(date)}.png")
        k = 1
        while os.path.exists(fn):
            fn = os.path.join(REVIEW_DIR, f"{P.slug(name)}__{P.slug(date)}_{k}.png"); k += 1
        try:
            screencap_crop(fn); iw.writerow([os.path.basename(fn), name, date]); saved += 1
        except Exception as e:
            print(f"    ! screencap failed {name} {date}: {e}")
        P.back()
    return saved


def main():
    if "device" not in P.adb("get-state").strip():
        sys.exit("No device.")
    try:
        import PIL  # noqa
    except ImportError:
        sys.exit("Need Pillow.")
    w, h = P.screen_size()
    # Clear any stale search filter first (a leftover query empties the list and
    # makes ensure_plant_list's header-verify fail).
    P.adb("shell", "am", "start", "-n", f"{P.PKG}/.main.views.MainActivity"); time.sleep(1.5)
    P.adb("shell", "input", "tap", "303", "2073"); time.sleep(1)   # Plants bottom-nav
    sxy0 = find_search(w, h)
    if sxy0:
        P.adb("shell", "input", "tap", str(sxy0[0]), str(sxy0[1])); time.sleep(0.5)
        P.adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
        for _ in range(60):
            P.adb("shell", "input", "keyevent", "KEYCODE_DEL")
        P.adb("shell", "input", "keyevent", "KEYCODE_BACK"); time.sleep(0.5)  # drop keyboard
    if not P.ensure_plant_list(w, h):
        sys.exit("Couldn't reach the flat Plants list (unlock phone, open Planta).")
    os.makedirs(REVIEW_DIR, exist_ok=True)
    idx = open(INDEX, "w", newline="", encoding="utf-8")
    iw = csv.writer(idx); iw.writerow(["file", "plant", "date"]); idx.flush()

    seen = set()
    for name, prefix in TARGETS.items():
        sxy = find_search(w, h)
        if not sxy:
            print(f"  search field not found for {name!r}; skipping")
            continue
        run_search(w, h, sxy, prefix)
        opened_y = set()
        total = 0
        for _ in range(12):                    # filtered view is short; bounded
            rows = [(n, ty) for n, ty in P.list_plant_rows(P.dump()) if n == name]
            todo = [(n, ty) for n, ty in rows if ty // 100 not in opened_y]
            if not todo:
                break
            n, ty = todo[0]
            opened_y.add(ty // 100)
            P.adb("shell", "input", "tap", str((P.LEFT_X + 700) // 2), str(ty)); time.sleep(P.SETTLE)
            if P.LIST_ACT not in P.top_activity():
                if "MainActivity" not in P.top_activity():
                    P.back()
                continue
            if not title_matches(detail_title(P.dump()), name):
                pass
            else:
                total += capture_into_flat(w, h, name, seen, iw); idx.flush()
            for _ in range(4):                 # back to the filtered list
                ta = P.top_activity()
                if ("UserPlantActivity" in ta or P.PHOTOS_ACT in ta or P.PHOTO_VIEW_ACT in ta):
                    P.back()
                else:
                    break
            if P.PKG not in P.top_activity():
                P.adb("shell", "am", "start", "-n", f"{P.PKG}/.main.views.MainActivity"); time.sleep(2)
                P.ensure_plant_list(w, h)
                sxy = find_search(w, h)
                if sxy:
                    run_search(w, h, sxy, prefix)
        print(f"{name!r}: {total} new photo(s)")
        # next name: don't re-navigate (that doesn't clear the filter and loses the
        # search bar); the next find_search + run_search re-uses / clears the field.
    idx.close()
    print(f"\nDone. {len(seen)} distinct photos in {os.path.basename(REVIEW_DIR)}/")


if __name__ == "__main__":
    main()
