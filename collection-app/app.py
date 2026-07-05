"""Local (localhost-only) collection app.

Serves the existing desktop viewer (collection.html) with a small injected adapter
that loads data from /api/collection instead of the baked-in array, lets you edit a
note per plant and pick a cover photo, and persists both to the SQLite sidecar.

    python app.py    ->  http://127.0.0.1:8000

No cloud, no auth. Workbook is never written here (that is the v1.1 apply step).
"""
import json

from flask import Flask, Response, abort, jsonify, request, send_from_directory

import apply as apply_mod
import config
import db

app = Flask(__name__, static_folder="static", static_url_path="/static")
db.init_db()


def _load_plants():
    return json.loads(config.COLLECTION_JSON.read_text(encoding="utf-8"))


def _load_baked_covers():
    try:
        return json.loads(config.COVERS_JSON.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return {}


@app.route("/")
def index():
    html = config.COLLECTION_HTML.read_text(encoding="utf-8")
    html = html.replace("</body>", '<script src="/static/adapter.js"></script>\n</body>', 1)
    return Response(html, mimetype="text/html")


@app.route("/api/collection")
def api_collection():
    plants = _load_plants()
    notes = db.get_notes()          # {uid: note}
    covers_sc = db.get_covers()     # {uid: photo}  (unapplied picks)

    for p in plants:
        if p["uid"] in notes:
            p["notes"] = notes[p["uid"]]

    # effective cover per uid = applied covers.json, overridden by sidecar picks
    covers = {int(k): v for k, v in _load_baked_covers().items()}
    covers.update(covers_sc)

    return jsonify({
        "plants": plants,
        "baked_covers": {str(k): v for k, v in covers.items()},
        "pending_notes": list(notes.keys()),
        "pending_covers": list(covers_sc.keys()),
    })


@app.route("/api/plant/<int:uid>/note", methods=["POST"])
def set_note(uid):
    note = (request.get_json(silent=True) or {}).get("note", "")
    db.upsert_note(uid, note)
    return jsonify({"ok": True})


@app.route("/api/plant/<int:uid>/cover", methods=["POST"])
def set_cover(uid):
    photo = (request.get_json(silent=True) or {}).get("photo", "")
    if not photo:
        abort(400)
    db.upsert_cover(uid, photo)
    return jsonify({"ok": True})


@app.route("/api/pending")
def api_pending():
    notes, covers = db.pending()
    return jsonify({"notes": notes, "covers": covers})


@app.route("/api/apply", methods=["POST"])
def api_apply():
    # Merge sidecar notes -> workbook Notes column and cover picks -> covers.json,
    # via the safe protocol (backup, local copy, LibreOffice recalc, validator,
    # optimistic-lock copy-back). See apply.py.
    payload, status = apply_mod.apply_edits()
    return jsonify(payload), status


@app.route("/Photos/<path:sub>")
def photos(sub):
    return send_from_directory(config.PHOTOS_DIR, sub)


if __name__ == "__main__":
    print(f"DATA_DIR = {config.DATA_DIR}")
    print(f"sidecar  = {config.DB_PATH}")
    print(f"serving  http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=False)
