/* collection-app adapter — injected into the generated collection.html.
 * Boots the viewer from /api/collection (instead of the baked-in array), makes
 * the per-plant note editable, and persists note + cover-photo picks to the
 * server sidecar. Reuses the page's existing render()/photoHTML()/row()/esc().
 * The generated collection.html is never hand-edited; this lives with the app. */
window.addEventListener("load", function () {
  var st = document.createElement("style");
  st.textContent =
    ".edited-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#e08a00;margin-left:6px;vertical-align:middle}" +
    ".note-edit{margin-top:10px}" +
    ".note-edit label{font-weight:600;font-size:.9em}" +
    ".note-edit .pend{color:#e08a00;font-size:.82em;margin-left:8px}" +
    ".note-edit textarea{width:100%;box-sizing:border-box;min-height:64px;margin-top:4px;font:inherit;padding:6px;border:1px solid #ccc;border-radius:6px;resize:vertical}" +
    ".note-edit .note-save{margin-top:5px;padding:4px 14px;border-radius:6px;border:1px solid #bbb;background:#f4f4f4;cursor:pointer;font:inherit}" +
    "#apply-bar{position:fixed;right:16px;bottom:16px;z-index:9999;background:#222;color:#fff;border-radius:10px;padding:10px 14px;box-shadow:0 4px 16px #0005;font:14px/1.3 system-ui,sans-serif;display:none;max-width:320px}" +
    "#apply-bar button{margin-top:8px;padding:6px 14px;border-radius:7px;border:0;background:#e08a00;color:#fff;font:inherit;font-weight:600;cursor:pointer}" +
    "#apply-bar button:disabled{opacity:.6;cursor:default}" +
    "#apply-bar .ab-msg{font-size:.85em;opacity:.85;margin-top:6px}";
  document.head.appendChild(st);

  var bar = document.createElement("div");
  bar.id = "apply-bar";
  document.body.appendChild(bar);

  window.PENDING_NOTES = new Set();
  window.PENDING_COVERS = new Set();

  window.refreshApplyBar = function (msg, busy) {
    var n = PENDING_NOTES.size, c = PENDING_COVERS.size;
    if (!n && !c && !msg) { bar.style.display = "none"; return; }
    bar.style.display = "block";
    bar.innerHTML =
      "<div><b>Unapplied edits:</b> " + n + " note" + (n === 1 ? "" : "s") +
      ", " + c + " cover" + (c === 1 ? "" : "s") + "</div>" +
      '<button id="apply-btn"' + (busy ? " disabled" : "") + ">" +
      (busy ? "Applying…" : "Apply to workbook") + "</button>" +
      (msg ? '<div class="ab-msg">' + msg + "</div>" : "");
    var b = document.getElementById("apply-btn");
    if (b) b.onclick = applyEdits;
  };

  window.applyEdits = function () {
    refreshApplyBar("", true);
    fetch("/api/apply", { method: "POST" })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (res.ok && res.d.ok) {
          PENDING_NOTES.clear(); PENDING_COVERS.clear();
          refreshApplyBar("Applied: " + res.d.applied_notes + " notes, " +
            res.d.applied_covers + " covers. Backup saved.", false);
          render();
          setTimeout(function () { refreshApplyBar("", false); }, 6000);
        } else {
          refreshApplyBar("Failed: " + (res.d.error || "unknown error"), false);
        }
      })
      .catch(function () { refreshApplyBar("Failed: network error", false); });
  };

  // cover pick -> persist server-side (replaces the localStorage-only version)
  window.setCover = function (e, uid, fname) {
    if (e) e.stopPropagation();
    userCovers[uid] = fname;
    BAKED_COVERS[uid] = fname;
    fetch("/api/plant/" + uid + "/cover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ photo: fname }),
    }).then(function (r) {
      if (r.ok) { PENDING_COVERS.add(uid); render(); refreshApplyBar(); }
    });
    var p = PLANTS.find(function (x) { return x.uid === uid; });
    if (p) photoPos[uid] = coverIndex(p);
    render();
  };

  window.saveNote = function (uid) {
    var ta = document.getElementById("note-" + uid);
    if (!ta) return;
    var val = ta.value;
    var btn = document.getElementById("note-save-" + uid);
    btn.disabled = true; btn.textContent = "Saving…";
    fetch("/api/plant/" + uid + "/note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: val }),
    })
      .then(function (r) { if (!r.ok) throw 0;
        var p = PLANTS.find(function (x) { return x.uid === uid; });
        if (p) p.notes = val;
        PENDING_NOTES.add(uid);
        btn.textContent = "Saved ✓";
        refreshApplyBar();
        setTimeout(function () { render(); }, 500);
      })
      .catch(function () { btn.disabled = false; btn.textContent = "Save (failed)"; });
  };

  // enhanced card: same as the baked cardHTML but with an edited dot + note editor
  window.cardHTML = function (p) {
    var hb = p.health_bucket;
    var badges = "";
    if (p.temp) badges += '<span class="badge temp">🌡 ' + esc(p.temp) + "</span>";
    if (p.light_fc) badges += '<span class="badge light">☀ ' + esc(p.light_fc) + " fc</span>";
    else if (p.light) badges += '<span class="badge light">☀ ' + esc(p.light) + "</span>";
    if (p.health) badges += '<span class="badge h' + (hb || "Other").replace(/[^A-Za-z]/g, "") + '">' + esc(p.health) + "</span>";
    if (p.label_status === "none") badges += '<span class="badge lblNone">No label</span>';
    else if (p.label_status === "replace") badges += '<span class="badge lblRepl">Needs label</span>';
    var loc = p.location
      ? '<span class="locpill">📍 ' + esc(p.location) + (p.location_dry ? " · rest: " + esc(p.location_dry) : "") + "</span>"
      : "";
    var det =
      row("Light", p.light) + row("Light fc", p.light_fc) + row("Temp", p.temp_graph || p.temp) +
      row("Humidity", p.humidity) + row("Air", p.air) + row("Fert", p.fert) +
      row("Watering", p.watering) + row("Pot/Mount", p.pot) + row("Media", p.media) +
      row("Shade", p.shade) + row("Acquired", p.acquired) + row("Repotted", p.repotted) +
      row("Source", p.source) + row("Cost", p.cost) + row("Blooms", p.blooms) +
      row("Diseases", p.diseases);
    var edited = (PENDING_NOTES.has(p.uid) || PENDING_COVERS.has(p.uid))
      ? '<span class="edited-dot" title="Edited, not yet applied to workbook"></span>' : "";
    var pend = PENDING_NOTES.has(p.uid) ? '<span class="pend">edited</span>' : "";
    var noteEditor =
      '<div class="note-edit"><label>Notes' + pend + "</label>" +
      '<textarea id="note-' + p.uid + '">' + esc(p.notes) + "</textarea>" +
      '<button class="note-save" id="note-save-' + p.uid + '" onclick="saveNote(' + p.uid + ')">Save</button></div>';
    return '<div class="card">' + photoHTML(p) + '<div class="info">' +
      '<div class="uidline"><span>UID ' + p.uid + (p.code ? " · " + esc(p.code) : "") + edited + "</span><span>" + esc(p.group) + "</span></div>" +
      '<div class="name">' + esc(p.name) + (p.common && p.name.indexOf(p.common) < 0 ? " ‘" + esc(p.common) + "’" : "") + "</div>" +
      '<div class="badges">' + badges + "</div>" + loc +
      "<details><summary>Details</summary><table>" + det + "</table>" + noteEditor + "</details>" +
      "</div></div>";
  };

  fetch("/api/collection")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      window.PLANTS = d.plants;
      (d.pending_notes || []).forEach(function (u) { PENDING_NOTES.add(u); });
      (d.pending_covers || []).forEach(function (u) { PENDING_COVERS.add(u); });
      window.BAKED_COVERS = d.baked_covers || {};
      photoPos = {};
      render();
      refreshApplyBar();
    });
});
