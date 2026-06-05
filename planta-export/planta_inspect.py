#!/usr/bin/env python3
"""
planta_inspect.py - for duplicate-named plants, open EACH instance and read its
detail title + subtitle (the scientific / cultivar line) straight from the
accessibility tree. No photos, no OCR, no model calls -> ~0 tokens. Lets us tell
whether two same-named rows are distinct varieties (different subtitle) or just
repeats.

Walks the flat Plants list positionally (dedup by scroll-overlap, NOT by name, so
the 2nd "Neoregalia carolinae" is treated as its own row), but only stops to open
rows whose name is in TARGETS. Prints a report grouped by name.

USAGE
  python3 planta_inspect.py      # inspects the TARGETS below
Start anywhere - it self-navigates to the flat Plants list (reuses planta_photos).
"""
import re
import sys
import time
from collections import Counter

import planta_photos as P   # reuse adb/dump/nodes/ensure_plant_list/list_plant_rows/...

# Duplicate names to inspect (Pete's "check for varieties" + "2 different plants")
TARGETS = {
    "Algaonema commutatum", "Alocasia micholitziana", "Anthurium andraenum",
    "Anthurium andreanum", "Caladium bicolor", "Cereus repandus",
    "Crassula ovata (Jade Plant)", "Diaphanthe fragrantissima (Kakamega)",
    "Dracaena trifasciata", "Fittonia albivens", "Fittonia albivens 'Red Nerve Plant'",
    "Goeppertia ornata", "Guzmania", "Haworthia cymbiformis", "Opuntia microdasys",
    "Peperomia dolabriformis (Prayer Pepper)", "Oncidium Intergeneric Hybrid",
}


def detail_title_subtitle(root):
    """On UserPlantActivity: the two left (x-left==36) text lines near the top are
    the plant title (list name) then the scientific/cultivar subtitle."""
    xs = sorted((y0, t) for x0, y0, x1, y1, t, d, clk, cls in P.nodes(root)
                if x0 == 36 and t)
    texts = [t for _, t in xs][:2]
    title = texts[0] if texts else ""
    sub = texts[1] if len(texts) > 1 else ""
    return title, sub


def main():
    if "device" not in P.adb("get-state").strip():
        sys.exit("No device.")
    w, h = P.screen_size()
    if not P.ensure_plant_list(w, h):
        sys.exit("Couldn't reach the flat Plants list.")
    for _ in range(20):
        P.adb("shell", "input", "swipe", str(w // 2), str(h // 4),
              str(w // 2), str(h * 9 // 10), "50")

    seq = []                  # positional sequence of row names already consumed
    found = {}                # name -> [ (occ, subtitle), ... ]
    stale, prev_sig = 0, None
    while True:
        root = P.dump()
        rows = P.list_plant_rows(root)
        names = [n for n, _ in rows]
        if not names:
            P.ensure_plant_list(w, h)
            continue
        k = P.overlap_k(seq, names)
        new = rows[k:]
        if not new:
            sig = tuple(names)
            if sig == prev_sig:
                stale += 1
                if stale >= 3:
                    break
            else:
                stale = 0
            prev_sig = sig
            P.swipe(w, h, 0.80, 0.45)
            continue
        stale = 0
        prev_sig = tuple(names)
        # consume non-target new rows in bulk (just advance the sequence)
        i = 0
        while i < len(new) and new[i][0] not in TARGETS:
            seq.append(new[i][0]); i += 1
        if i >= len(new):
            P.swipe(w, h, 0.80, 0.45)   # no target on this screen; scroll for more
            continue
        name, ty = new[i]
        seq.append(name)
        occ = seq.count(name)
        P.adb("shell", "input", "tap", str((P.LEFT_X + 700) // 2), str(ty)); time.sleep(P.SETTLE)
        if P.LIST_ACT not in P.top_activity():
            if "MainActivity" not in P.top_activity():
                P.back()
            continue
        title, sub = detail_title_subtitle(P.dump())
        found.setdefault(name, []).append((occ, sub))
        print(f"  {name}  [#{occ}]  subtitle: {sub!r}")
        # back to list
        for _ in range(3):
            if "MainActivity" in P.top_activity():
                break
            P.back()
        if P.PKG not in P.top_activity():
            P.adb("shell", "am", "start", "-n", f"{P.PKG}/.main.views.MainActivity"); time.sleep(2)
            P.ensure_plant_list(w, h)

    print("\n===== VARIETY REPORT (by name) =====")
    for name in sorted(found):
        insts = found[name]
        subs = [s for _, s in insts]
        verdict = "DISTINCT subtitles" if len(set(subs)) > 1 else "same subtitle"
        print(f"\n{name}  ({len(insts)} instance(s) opened) - {verdict}")
        for occ, s in insts:
            print(f"   #{occ}: {s!r}")
    missing = TARGETS - set(found)
    if missing:
        print("\nNOT FOUND on this pass:", ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()
