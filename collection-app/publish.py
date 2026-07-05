"""One-click publish of the PUBLIC GitHub Pages site.

Chains the full pipeline the PLAYBOOK describes by hand:
  1. refresh the viewers (build_collection.py) so collection.html is current
  2. build the redacted, web-optimized public site (build_public.py -> staging)
  3. sync it into a temporary gh-pages worktree (photos replaced, scaffolding kept)
  4. commit + push origin gh-pages  (GitHub Pages rebuilds in ~1 min)

Isolated in a temp worktree so the app's main checkout is never disturbed.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import config
import refresh

PUBLIC_URL = "https://peetmate.github.io/plants/"


def _run(cmd, cwd=None, env=None, timeout=900):
    return subprocess.run(
        cmd, cwd=(str(cwd) if cwd else None), env=env,
        capture_output=True, text=True, timeout=timeout,
    )


def publish(dry_run=False):
    """Returns (payload dict, http status). dry_run stops before the push."""
    repo = config.REPO_DIR
    bp = config.BUILD_PUBLIC
    if not bp.exists():
        return {"ok": False, "error": f"build_public.py not found at {bp}"}, 404

    # 1. refresh viewers (collection.html must reflect current data/covers)
    rpayload, _ = refresh.run_build_collection()
    if not rpayload["ok"]:
        return {"ok": False, "step": "refresh", "error": rpayload.get("error", "")}, 500

    work = Path(tempfile.mkdtemp(prefix="publish_"))
    try:
        # 2. build redacted public site into staging
        staging = work / "site"
        env = dict(os.environ, PUBLIC_SRC=str(config.DATA_DIR), PUBLIC_OUT=str(staging))
        r = _run([sys.executable, str(bp)], env=env)
        if r.returncode != 0 or not (staging / "index.html").exists():
            return {"ok": False, "step": "build_public",
                    "error": (r.stderr or r.stdout or "")[-800:]}, 500

        # 3. fresh gh-pages worktree pinned to origin
        _run(["git", "worktree", "prune"], cwd=repo)
        _run(["git", "fetch", "origin", "gh-pages"], cwd=repo)
        wt = work / "ghpages"
        add = _run(["git", "worktree", "add", "--force", "-B", "gh-pages", str(wt), "origin/gh-pages"], cwd=repo)
        if not (wt / ".git").exists():
            return {"ok": False, "step": "worktree", "error": (add.stderr or add.stdout or "")[-500:]}, 500
        try:
            # sync: replace Photos (drop stale) + index.html; keep .nojekyll/README/LICENSE
            (wt / "Photos").mkdir(exist_ok=True)
            _run(["rsync", "-a", "--delete", str(staging / "Photos") + "/", str(wt / "Photos") + "/"])
            shutil.copy2(staging / "index.html", wt / "index.html")

            _run(["git", "add", "-A"], cwd=wt)
            st = _run(["git", "status", "--porcelain"], cwd=wt)
            if not st.stdout.strip():
                return {"ok": True, "pushed": False, "note": "Public site already up to date.",
                        "url": PUBLIC_URL}, 200

            _run(["git", "commit", "-m", "Update public site"], cwd=wt)
            sha = _run(["git", "rev-parse", "--short", "HEAD"], cwd=wt).stdout.strip()
            if dry_run:
                return {"ok": True, "pushed": False, "dry_run": True, "commit": sha,
                        "url": PUBLIC_URL}, 200

            push = _run(["git", "push", "origin", "gh-pages"], cwd=wt)
            if push.returncode != 0:
                return {"ok": False, "step": "push", "error": (push.stderr or "")[-500:]}, 500
            return {"ok": True, "pushed": True, "commit": sha, "url": PUBLIC_URL,
                    "note": "Pushed. GitHub Pages rebuilds in ~1 min."}, 200
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt)], cwd=repo)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    payload, status = publish(dry_run=dry)
    print(payload)
    sys.exit(0 if payload.get("ok") else 1)
