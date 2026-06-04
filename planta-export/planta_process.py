#!/usr/bin/env python3
"""
planta_process.py - stitch the per-shot OCR transcripts into one ordered,
de-overlapped plant list and export it to CSV + XLSX.

PIPELINE
  planta_capture.py  ->  planta_shots/*.png            (auto-scroll screenshots)
  [Claude vision OCR] ->  shots.json                    (one entry per screenshot)
  planta_process.py  ->  planta_plants.csv / .xlsx      (this script)

INPUT  shots.json : [{"shot": N, "plants": [{"name","category","partial"}, ...]}, ...]
       Each screenshot's plant rows, top-to-bottom, transcribed verbatim. The shots
       deliberately OVERLAP (~1 row), and periodic rejected swipes during capture
       produced some fully-duplicated consecutive shots.

WHY A SEQUENCE STITCH (not a set-dedup)
  The collection genuinely contains many repeated names (the owner really has
  several "Anthurium andraenum", three "Fittonia albivens 'Red Nerve Plant'",
  etc.). A plain unique() would wrongly collapse those. Instead we stitch by
  sequence overlap: for each new shot, find the largest k where the TAIL of the
  merged list equals the HEAD of the shot (matched by name), and append only the
  remainder. That removes the scroll overlap while preserving genuine duplicates.

USAGE
  python3 planta_process.py            # reads ./shots.json, writes CSV (+ XLSX if openpyxl)
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "shots.json")
OUT_CSV = os.path.join(HERE, "planta_plants.csv")
OUT_XLSX = os.path.join(HERE, "planta_plants.xlsx")


def norm(s):
    """Collapse whitespace; return None for empty."""
    if s is None:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def is_garbage_name(name):
    """A few partial top-of-screen rows had the family line mis-read AS the name
    (e.g. "Euphorbiaceae", "Crassulaceae"). A real name is "Genus species ...",
    always with a space. Single-token *-aceae strings are family names, not plants."""
    if not name:
        return True
    return " " not in name and name.endswith("aceae")


def clean_shot(plants):
    rows = []
    for p in plants:
        name = norm(p.get("name"))
        if is_garbage_name(name):
            continue
        rows.append({"name": name, "category": norm(p.get("category"))})
    return rows


def overlap_k(tail_names, head_names):
    """Largest k such that the last k of tail_names == first k of head_names."""
    maxk = min(len(tail_names), len(head_names))
    for k in range(maxk, 0, -1):
        if tail_names[-k:] == head_names[:k]:
            return k
    return 0


def stitch(shots):
    merged = []
    for shot in sorted(shots, key=lambda s: s["shot"]):
        rows = clean_shot(shot["plants"])
        if not rows:
            continue
        m_names = [r["name"] for r in merged]
        s_names = [r["name"] for r in rows]
        k = overlap_k(m_names, s_names)
        # Backfill categories: an overlap row first seen as a cut-off partial may
        # have had a null category; fill it from this shot's full row.
        base = len(merged) - k
        for i in range(k):
            if merged[base + i]["category"] is None and rows[i]["category"]:
                merged[base + i]["category"] = rows[i]["category"]
        merged.extend(rows[k:])
    return merged


def split_name(full):
    """Best-effort split of the bold name line into a leading binomial / genus
    string and a trailing common-name or cultivar note, for an extra column.
    Conservative: only splits on a trailing (parenthetical) or 'quoted' bit."""
    common = None
    m = re.search(r"\s*\(([^()]*)\)\s*$", full)
    if m:
        common = m.group(1).strip()
        return full[:m.start()].strip(), common
    return full, None


def write_csv(rows):
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["#", "Name", "Common / cultivar", "Category"])
        for i, r in enumerate(rows, 1):
            base, common = split_name(r["name"])
            w.writerow([i, r["name"], common or "", r["category"] or ""])


def write_xlsx(rows):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment
    except ImportError:
        return False
    wb = Workbook()
    ws = wb.active
    ws.title = "Planta export"
    headers = ["#", "Name", "Common / cultivar", "Category"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, r in enumerate(rows, 1):
        base, common = split_name(r["name"])
        ws.append([i, r["name"], common or "", r["category"] or ""])
    widths = [5, 52, 28, 22]
    for col, wd in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + col)].width = wd
    ws.freeze_panes = "A2"
    wb.save(OUT_XLSX)
    return True


def main():
    if not os.path.exists(SHOTS):
        sys.exit(f"Missing {SHOTS}. Generate it from planta_shots/ first.")
    with open(SHOTS, encoding="utf-8") as f:
        shots = json.load(f)
    rows = stitch(shots)
    write_csv(rows)
    xlsx = write_xlsx(rows)
    print(f"{len(rows)} plants stitched from {len(shots)} screenshots.")
    print(f"  wrote {os.path.basename(OUT_CSV)}")
    print(f"  wrote {os.path.basename(OUT_XLSX)}" if xlsx
          else "  (openpyxl not installed - CSV only; `pip3 install openpyxl` for XLSX)")


if __name__ == "__main__":
    main()
