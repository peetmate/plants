#!/usr/bin/env python3
"""
planta_photos.py - capture every plant's in-app photos as screenshots, attributed
to the plant, driven entirely by the accessibility tree (uiautomator). No OCR, no
per-image model calls - runs on the host (Python + adb). Token cost ~ zero.

PER-PLANT FLOW (learned from the live app on a Pixel 9 Pro XL, Compose UI - no
resource-ids, so we key off visible text / content-desc + bounds):
  1. Plants tab, flat list  -> tap a plant name (x-left == LEFT_X) -> plant detail
     (UserPlantActivity).
  2. Scroll the detail down until "View all updates" appears; tap it ->
     PlantPhotosNotesActivity ("Photos & Notes"). If it never appears, the plant
     has no history -> skip.
  3. The Photos&Notes screen lists photo cards: a View whose content-desc ends
     " photo" (e.g. "June 13, 2021 photo"), with a date label. Scroll to load all,
     dedup by content-desc.
  4. Tap each photo card -> full-screen viewer -> screencap (crop to the image
     band) -> file. Back to the list.
  5. Back to the plant list; advance to the next not-yet-visited plant.

OUTPUT
  planta_photos/<UID>_<plant-slug>/<UID>_<plant-slug>__<date-slug>.png
  planta_photos_manifest.csv   (uid, plant, n_photos, files)

USAGE
  python3 planta_photos.py            # all plants from the top of the Plants list
  python3 planta_photos.py 3          # only the first 3 plants (smoke test)
  Start ON the flat Plants list (Plants tab -> "Plants" sub-tab), scrolled to top.
  Keep screen awake + phone idle: adb shell svc power stayon true
"""
import csv
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "planta_photos")
MANIFEST = os.path.join(HERE, "planta_photos_manifest.csv")
REMOTE_XML = "/sdcard/planta_ui.xml"

PKG = "com.stromming.planta"
LIST_ACT = "myplants.plants.detail.compose.UserPlantActivity"   # plant detail
PHOTOS_ACT = "PlantPhotosNotesActivity"                          # photos & notes
PHOTO_VIEW_ACT = "PicturesActivity"                              # full-screen viewer
LEFT_X = 252                  # x-left of plant name Textviews in the flat list
CARD_GAP = 60                 # vertical gap = new card (name/category grouping)
PHOTO_CROP = (0, 275, 1008, 2037)   # full-screen photo band (status/action bars out)
SETTLE = 0.6
MAX_DETAIL_SCROLLS = 8        # detail scrolls hunting for "View all updates"
MAX_PHOTO_SCROLLS = 30        # photos-list scrolls to load all entries
MAX_LIST_STALE = 3            # list scrolls with no new plant = bottom


def _load_categories():
    """Category/family strings (the lighter 2nd line of each card). Used to drop a
    dangling category line that lands at screen-top on resume and would otherwise be
    misread as a plant name. Sourced from planta_plants.csv + a built-in fallback."""
    cats = {"Cacti", "Bromeliads", "Orchids", "Ferns", "Echeverias & Allies"}
    p = os.path.join(HERE, "planta_plants.csv")
    if os.path.exists(p):
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                c = (row.get("Category") or "").strip()
                if c:
                    cats.add(c)
    return cats


CATEGORIES = _load_categories()


def adb(*a, binary=False):
    r = subprocess.run(["adb", *a], capture_output=True)
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def screen_size():
    out = adb("shell", "wm", "size")
    w, h = (int(v) for v in out.strip().split(":")[-1].strip().split("x"))
    return w, h


def top_activity():
    for line in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "topResumedActivity" in line:
            return line
    return ""


def dump():
    last_err = None
    for _ in range(8):
        adb("shell", "uiautomator", "dump", REMOTE_XML)
        xml = adb("exec-out", "cat", REMOTE_XML, binary=True)
        if xml.strip():
            try:
                return ET.fromstring(xml)
            except ET.ParseError as e:
                last_err = e
        else:
            # empty dump usually = screen off/locked; wake it and retry
            adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
        time.sleep(1)
    if last_err:
        raise last_err
    raise ET.ParseError("empty uiautomator dump")


def nodes(root):
    """Yield (x0,y0,x1,y1,text,desc,clickable,cls) for every node with a box."""
    for n in root.iter("node"):
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
        if not m:
            continue
        x0, y0, x1, y1 = (int(g) for g in m.groups())
        yield (x0, y0, x1, y1,
               (n.get("text") or "").strip(),
               (n.get("content-desc") or "").strip(),
               n.get("clickable"), n.get("class", "").split(".")[-1])


def slug(s, n=60):
    s = re.sub(r"[^\w\s.-]", "", s).strip()
    s = re.sub(r"\s+", "_", s)
    return s[:n] or "untitled"


def find_text(root, want, contains=False):
    """Return tap (cx,cy) of the first node whose text == want (or contains)."""
    for x0, y0, x1, y1, t, d, clk, cls in nodes(root):
        if (want in t if contains else t == want):
            return (x0 + x1) // 2, (y0 + y1) // 2
    return None


def tap(xy):
    adb("shell", "input", "tap", str(xy[0]), str(xy[1]))
    time.sleep(SETTLE)


def ensure_plant_list(w, h, tries=5):
    """Navigate to the FLAT alphabetical Plants list and verify, instead of
    trusting blind pre-positioning. Bottom-nav Plants (by resource-id) -> the
    'Plants' sub-tab (by text) -> confirm the 'N Plants -dot- M Sites' header and
    that rows look like plants (not care-feed task verbs)."""
    # back out of any sub-screen (plant detail, photo viewer, ...) to the main
    # tabbed screen, where the bottom nav exists
    for _ in range(6):
        if "MainActivity" in top_activity():
            break
        back()
    if "MainActivity" not in top_activity():
        adb("shell", "am", "start", "-n", f"{PKG}/.main.views.MainActivity"); time.sleep(2)
    def fling_top():
        for _ in range(20):
            adb("shell", "input", "swipe", str(w // 2), str(h // 4),
                str(w // 2), str(h * 9 // 10), "50")

    for _ in range(tries):
        # bottom-nav Plants tab, by resource-id
        root = dump()
        for n in root.iter("node"):
            if "tab_plants" in n.get("resource-id", ""):
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
                if m:
                    tap(((int(m.group(1)) + int(m.group(3))) // 2,
                         (int(m.group(2)) + int(m.group(4))) // 2))
                break
        fling_top()                      # bring header + sub-tabs into view
        # 'Plants' sub-tab (top row), by text -> selects the flat list
        root = dump()
        for x0, y0, x1, y1, t, d, clk, cls in nodes(root):
            if t == "Plants" and y0 < 700 and x0 > 200:
                tap(((x0 + x1) // 2, (y0 + y1) // 2))
                break
        fling_top()
        # verify: header present + rows look like plants (not care-feed tasks)
        root = dump()
        header = any(re.search(r"\d+\s+Plants\s+.\s+\d+\s+Sites", t)
                     for *_, t, d, clk, cls in nodes(root))
        rows = list_plant_rows(root)
        if header and len(rows) >= 4 and (" " in rows[0][0] or len(rows[0][0]) > 10):
            return True
        time.sleep(1)
    return False


def list_plant_rows(root):
    """Flat-list plant NAME lines: LEFT_X TextViews, grouped by vertical gap,
    first line of each card = name. Returns [(name, tap_y)] top-to-bottom."""
    lines = sorted((y0, y1, t) for x0, y0, x1, y1, t, d, clk, cls in nodes(root)
                   if x0 == LEFT_X and t)
    cards, cur, prev_b = [], [], None
    for top, bot, t in lines:
        if prev_b is not None and top - prev_b > CARD_GAP and cur:
            cards.append(cur); cur = []
        cur.append((top, bot, t)); prev_b = bot
    if cur:
        cards.append(cur)
    out = []
    for c in cards:
        # drop dangling category line(s) that lead a card (top-of-screen partial on
        # resume), so the real name below them is used - not the category
        while c and c[0][2] in CATEGORIES:
            c = c[1:]
        if len(c) < 2:            # need name line + its category line = a full card;
            continue              # name-only edge partials show fully elsewhere
        top, bot, name = c[0]
        if name.endswith("aceae") and " " not in name:
            continue
        out.append((name, (top + bot) // 2))
    return out


def photo_cards(root):
    """Photo entries on the Photos&Notes screen: content-desc ending ' photo'."""
    out = []
    for x0, y0, x1, y1, t, d, clk, cls in nodes(root):
        if d.endswith(" photo") and (x1 - x0) > 300 and (y1 - y0) > 150:
            date = d[:-6].strip()
            out.append((date, (x0 + x1) // 2, (y0 + y1) // 2))
    return out


def screencap_crop(path):
    png = adb("exec-out", "screencap", "-p", binary=True)
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(png))
    img.crop(PHOTO_CROP).save(path)


def back():
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(SETTLE)


def swipe(w, h, frm, to, ms=400):
    x = w // 2
    adb("shell", "input", "swipe", str(x), str(int(h * frm)), str(x), str(int(h * to)), str(ms))
    time.sleep(SETTLE)


def capture_plant_photos(w, h, uid, name):
    """On the plant detail page. Returns list of saved file paths (maybe empty)."""
    # 1. find "View all updates"
    target = None
    for _ in range(MAX_DETAIL_SCROLLS):
        root = dump()
        target = find_text(root, "View all updates")
        if target:
            break
        swipe(w, h, 0.80, 0.35)
    if not target:
        return []                       # no history/photos for this plant
    adb("shell", "input", "tap", *map(str, target)); time.sleep(SETTLE)
    if PHOTOS_ACT not in top_activity():
        return []
    # Single downward pass: tap each uncaptured photo card as we go (tap -> full
    # screen -> screencap -> back), and swipe down only when the current screen has
    # no new cards. No wasteful scroll-back-to-top. Stop when swiping reveals nothing
    # new twice in a row.
    pdir = os.path.join(OUT_DIR, f"{uid}_{slug(name)}")
    saved, captured, stale = [], set(), 0
    for _ in range(MAX_PHOTO_SCROLLS * 3):
        root = dump()
        cards = [c for c in photo_cards(root) if c[0] not in captured]
        if not cards:
            stale += 1
            if stale >= 2:
                break
            swipe(w, h, 0.80, 0.40)
            continue
        stale = 0
        date, cx, cy = cards[0]
        captured.add(date)
        adb("shell", "input", "tap", str(cx), str(cy)); time.sleep(SETTLE)
        adb("shell", "input", "tap", str(w // 2), str(h // 2)); time.sleep(SETTLE)
        os.makedirs(pdir, exist_ok=True)
        fn = os.path.join(pdir, f"{uid}_{slug(name)}__{slug(date)}.png")
        if os.path.exists(fn):
            fn = fn[:-4] + f"_{len(saved)}.png"
        try:
            screencap_crop(fn); saved.append(fn)
        except Exception as e:
            print(f"    ! screencap failed for {date}: {e}")
        for _ in range(4):              # back to Photos&Notes list
            act = top_activity()
            if PHOTOS_ACT in act:
                break
            if PKG in act:
                back()
            else:
                break
    return saved


def main():
    max_plants = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
    if "device" not in adb("get-state").strip():
        sys.exit("No device.")
    try:
        import PIL  # noqa
    except ImportError:
        sys.exit("Need Pillow: pip3 install pillow")
    w, h = screen_size()
    os.makedirs(OUT_DIR, exist_ok=True)
    if not ensure_plant_list(w, h):
        sys.exit("Couldn't reach the flat Plants list. Open Planta -> Plants tab -> "
                 "'Plants' sub-tab, then re-run.")
    for _ in range(20):                 # fling to top of list
        adb("shell", "input", "swipe", str(w // 2), str(h // 4), str(w // 2), str(h * 9 // 10), "50")
    # Resume: if a manifest already exists, skip plants already done and keep
    # numbering, so an interrupted long run continues instead of restarting.
    visited, uid = set(), 0
    if os.path.exists(MANIFEST):
        with open(MANIFEST, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                visited.add(row["plant"])
                m = re.match(r"P(\d+)", row.get("uid", ""))
                if m:
                    uid = max(uid, int(m.group(1)))
        print(f"Resuming: {len(visited)} plants already in manifest (next P{uid+1:04d}).")
        man = open(MANIFEST, "a", newline="", encoding="utf-8")
        mw = csv.writer(man)
    else:
        man = open(MANIFEST, "w", newline="", encoding="utf-8")
        mw = csv.writer(man); mw.writerow(["uid", "plant", "n_photos", "files"]); man.flush()

    stale, prev_sig, processed = 0, None, 0
    while processed < max_plants:
        root = dump()
        allrows = list_plant_rows(root)
        sig = tuple(n for n, _ in allrows)
        rows = [r for r in allrows if r[0] not in visited]
        if not rows:
            # nothing new on screen: keep scrolling through already-done regions.
            # Real bottom only when the list also stops moving (sig unchanged).
            if sig == prev_sig:
                stale += 1
                if stale >= MAX_LIST_STALE:
                    print(f"\nDone. Bottom of list. {processed} plants this run.")
                    break
            else:
                stale = 0
            prev_sig = sig
            swipe(w, h, 0.80, 0.45)
            continue
        stale = 0
        prev_sig = sig
        name, ty = rows[0]
        visited.add(name)
        uid += 1
        processed += 1
        uid_s = f"P{uid:04d}"
        adb("shell", "input", "tap", str((LEFT_X + 700) // 2), str(ty)); time.sleep(SETTLE)
        if LIST_ACT not in top_activity():
            print(f"{uid_s} {name!r}: detail didn't open, skipping")
            # only back if we actually drilled into a sub-screen; pressing BACK on
            # the list root (MainActivity) would EXIT Planta to the launcher
            if "MainActivity" not in top_activity():
                back()
            continue
        files = capture_plant_photos(w, h, uid_s, name)
        print(f"{uid_s} {name!r}: {len(files)} photo(s)")
        mw.writerow([uid_s, name, len(files), ";".join(os.path.relpath(f, HERE) for f in files)])
        man.flush()
        # back to the flat plant list (detail -> list)
        for _ in range(4):
            if ("UserPlantActivity" in top_activity() or
                    PHOTOS_ACT in top_activity() or PHOTO_VIEW_ACT in top_activity()):
                back()
            else:
                break
        if PKG not in top_activity():   # lost focus (call/popup) -> recover list view
            adb("shell", "am", "start", "-n", f"{PKG}/.main.views.MainActivity"); time.sleep(2)
            ensure_plant_list(w, h)
    man.close()
    print(f"manifest: {os.path.basename(MANIFEST)}  |  photos in {os.path.basename(OUT_DIR)}/")


if __name__ == "__main__":
    main()
