"""v1.2 one-command refresh — rebuild the viewers from the workbook.

Runs the project's build_collection.py (in DATA_DIR), which regenerates
collection.json + collection.html + collection-portable.html from the current
workbook. The public GitHub Pages site is a separate, deliberate step (build the
redacted site + push gh-pages — see PLAYBOOK.md), so this only reminds about it.

    POST /api/refresh      (from the app)
    python refresh.py      (from the terminal)
"""
import subprocess
import sys

import config

PUBLIC_REMINDER = (
    "Viewers rebuilt. To update the PUBLIC site: rebuild the redacted copy with "
    "build_public.py and push the gh-pages branch (see PLAYBOOK.md)."
)


def run_build_collection():
    """Returns (payload dict, http status)."""
    script = config.DATA_DIR / "build_collection.py"
    if not script.exists():
        return {"ok": False, "error": "build_collection.py not found in DATA_DIR"}, 404
    r = subprocess.run(
        [sys.executable, "build_collection.py"],
        cwd=str(config.DATA_DIR), capture_output=True, text=True, timeout=600,
    )
    ok = r.returncode == 0
    payload = {
        "ok": ok,
        "output": "\n".join((r.stdout or "").splitlines()[-12:]),
        "public_reminder": PUBLIC_REMINDER,
    }
    if not ok:
        payload["error"] = (r.stderr or "")[-800:]
    return payload, (200 if ok else 500)


if __name__ == "__main__":
    payload, status = run_build_collection()
    print(payload.get("output", ""))
    if not payload["ok"]:
        print("ERROR:", payload.get("error", ""), file=sys.stderr)
        sys.exit(1)
    print("\n" + payload["public_reminder"])
