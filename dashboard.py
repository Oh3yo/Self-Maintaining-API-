"""Live demo console: runs the mock API and a web page that drives and shows the whole pipeline.

    python dashboard.py            then open http://localhost:8001
    python dashboard.py --no-pr    rehearsal: stop at the patch, never open a pull request

If ui/dist exists (built with `npm run build` in ui/) the React page is served; otherwise the built-in page is.

Run it from the project folder. It starts the mock API itself, so close any other
`python mock_api.py` window first. Set NEBIUS_API_KEY (and GITHUB_TOKEN for PRs) before starting.
"""
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import mock_api

ROOT = Path(__file__).resolve().parent
PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
DIST = ROOT / "ui" / "dist"  # the React UI, if it has been built (npm run build in ui/)
for ext, t in ((".js", "text/javascript"), (".css", "text/css"), (".woff2", "font/woff2"), (".svg", "image/svg+xml")):
    mimetypes.add_type(t, ext)  # Windows registry sometimes maps .js to text/plain, which browsers refuse for modules
S = {"busy": None, "log": {}, "app": ("", 0.0), "no_pr": "--no-pr" in sys.argv}


def sh(*cmd):
    p = subprocess.run(cmd, cwd=ROOT, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr



def do(name):
    try:
        if name in ("break", "reset"):
            mock_api.state["field"] = "email_address" if name == "break" else "email"

        elif name == "detect":
            rc, out = sh(
                PY, "detector.py", "run",
                "--config", "demo_apis.yaml", "--once"
            )
            S["log"]["detect"] = {
                "ok": rc in (0, 2),
                "out": out,
            }  # exit 2 = breaking changes found

        elif name == "fix":
            if S["no_pr"]:
                rc, out = sh(
                    PY, "pipeline.py", "demo_repo", "reports"
                )
            else:
                with tempfile.TemporaryDirectory(
                    prefix="api-pr-"
                ) as temp_dir:
                    remote_url = (
                        os.environ.get("GITHUB_REPOSITORY_URL", "").strip()
                        or "https://github.com/Oh3yo/Self-Maintaining-API-.git"
                    )

                    clone_dir = Path(temp_dir) / "repo"
                    clone_rc, clone_out = sh(
                        "git", "clone",
                        "--depth", "1",
                        "--branch", "main",
                        remote_url,
                        str(clone_dir),
                    )

                    if clone_rc != 0:
                        raise RuntimeError(
                            "Could not clone the GitHub repository:\n"
                            + clone_out
                        )

                    pr_repo = clone_dir / "demo_repo"

                    rc, out = sh(
                        PY, "pipeline.py", "demo_repo", "reports",
                        "--pr",
                        "--pr-repo", str(pr_repo),
                        "--pr-test",
                        str(ROOT / "demo_repo" / "tests" / "test_client.py"),
                    )

            S["log"]["fix"] = {
                "ok": rc == 0,
                "out": out,
            }

        elif name == "restart":
            mock_api.state["field"] = "email"
            S["log"].clear()

            for p in (".demo_state", "reports"):
                shutil.rmtree(ROOT / p, ignore_errors=True)

            (ROOT / "fix.patch").unlink(missing_ok=True)

        S["app"] = ("", 0.0)

    finally:
        S["busy"] = None


def app():
    """What the demo repo's client sees right now (cached a few seconds: it is a subprocess)."""
    if time.time() - S["app"][1] > 4:
        S["app"] = (sh(PY, "mock_api.py", "try")[1].strip(), time.time())
    return S["app"][0]


def detect_view(log):
    files = sorted((ROOT / "reports").glob("*.json"), key=lambda f: f.stat().st_mtime)
    rep = json.loads(files[-1].read_text(encoding="utf-8")) if files else {"summary": {}, "results": []}
    return {"ok": log["ok"], "out": log["out"][-2000:], "summary": rep["summary"],
            "status": [r["status"] for r in rep["results"]],
            "changes": [c for r in rep["results"] for c in r["changes"]]}


def fix_view(log):
    out = log["out"]

    def g(pat):
        m = re.search(pat, out, re.M)
        return m.group(1).strip() if m else None

    block = re.search(r"API changes:\n((?:- .*\n)+)", out)
    patch = ROOT / "fix.patch"
    return {"ok": log["ok"], "out": out[-2500:], "none": "Nothing to fix" in out,
            "changes": [re.sub(r" \(It appears.*\)$", "", l[2:]) for l in block.group(1).splitlines()] if block else [],
            "model": g(r"^\[([^\]]+)\] "), "summary": g(r"^\[[^\]]+\] (.*)$"),
            "files": g(r"^Affected files: (.*)$"), "checks": g(r"^Checks: (.*)$"), "pr": g(r"^Pull request: (\S+)"),
            "patch": patch.read_text(encoding="utf-8") if log["ok"] and "Patch written" in out and patch.exists() else ""}


def state():
    d, f = S["log"].get("detect"), S["log"].get("fix")
    return {"busy": S["busy"], "field": mock_api.state["field"], "app": app(), "no_pr": S["no_pr"],
            "detect": d and detect_view(d), "fix": f and fix_view(f)}


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json", code=200):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        text = ctype.startswith("text/") or ctype.endswith(("json", "javascript", "svg+xml"))
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if text else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/state":
            self._send(json.dumps(state()))
        elif DIST.is_dir():
            f = (DIST / path.lstrip("/")).resolve()
            if not (f.is_file() and DIST.resolve() in f.parents):
                f = DIST / "index.html"
            self._send(f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        else:
            self._send(PAGE, "text/html")

    def do_POST(self):
        name = self.path.rsplit("/", 1)[-1]
        if name not in ("break", "reset", "detect", "fix", "restart") or S["busy"]:
            return self._send("{}", code=409)
        S["busy"] = name
        threading.Thread(target=do, args=(name,), daemon=True).start()
        self._send("{}", code=202)

    def log_message(self, *a):
        pass


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#dce7dd">
<title>Self-Maintaining API</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..800&display=swap" rel="stylesheet">
<style>
:root{--ink:#11161c;--ground:#f3f4f1;--surface:#e7e9e4;--dim:#3d4650;--code:#11161c;
--mono:ui-monospace,"Cascadia Code","SF Mono",Consolas,monospace;
--ease:cubic-bezier(.2,.7,.2,1)}
*{box-sizing:border-box}
html{color-scheme:light;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);
  font:400 17px/1.55 "Bricolage Grotesque",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;text-wrap:pretty}
.wrap{max-width:1240px;margin:0 auto;padding:0 clamp(16px,4vw,48px)}
.sp{flex:1}
button,a.btn{font:inherit}
:focus-visible{outline:3px solid var(--fg,var(--ink));outline-offset:3px}
.panelbtns .btn:focus-visible{outline-color:#fff}

/* the field: one flat colour for the whole top of the page, crossfaded by opacity */
.hero{position:relative;overflow:hidden;color:var(--fg);--fg:var(--ink);--btn:var(--ink);--btnfg:var(--ground);
  padding:0 0 clamp(36px,6vw,80px)}
.hero[data-state=run],.hero[data-state=ready],.hero[data-state=opened],.hero[data-state=fail]{--fg:#fff;--btn:#fff;--btnfg:var(--ink)}
.fields{position:absolute;inset:0}
.f{position:absolute;inset:0;opacity:0;transition:opacity .6s ease}
.f-stable{background:#dce7dd}.f-broken{background:#ff4b2b}.f-run{background:#2358ff}
.f-ready{background:#17744a}.f-opened{background:#0e4d32}.f-fail{background:#7a1410}
.hero[data-state=stable] .f-stable,.hero[data-state=broken] .f-broken,.hero[data-state=run] .f-run,
.hero[data-state=ready] .f-ready,.hero[data-state=opened] .f-opened,.hero[data-state=fail] .f-fail{opacity:1}
.hero .wrap{position:relative}
.bar{display:flex;align-items:center;gap:12px;padding:20px 0;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:-.01em;font-size:18px;color:inherit;text-decoration:none}
.tag{font-size:14px;font-weight:600;padding:3px 12px;border-radius:99px;background:color-mix(in srgb,currentColor 16%,transparent)}
h1{margin:clamp(24px,5vw,64px) 0 0;font-weight:800;font-size:clamp(42px,8.2vw,116px);line-height:.95;letter-spacing:-.035em;text-wrap:balance;max-width:16ch}
.grid2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,540px);gap:clamp(24px,4vw,56px);align-items:end;margin-top:clamp(20px,3vw,40px)}
#sub{margin:0 0 24px;font-size:clamp(18px,1.9vw,24px);line-height:1.35;max-width:34ch}
.panel{background:var(--code);color:#d7e0ee;padding:clamp(16px,2.4vw,28px)}
.panel pre{margin:0;font:clamp(14px,1.6vw,20px)/1.6 var(--mono);white-space:pre-wrap;word-break:break-word}
.panel .k{padding:0 .3em;background:#7ee0a0;color:var(--ink);font-weight:700}
.panel .k.bad{background:#ff4b2b}
.panelbtns{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;color:#fff}

.btn{display:inline-block;border:0;border-radius:99px;padding:11px 22px;background:var(--btn,var(--ink));color:var(--btnfg,var(--ground));
  font-weight:650;line-height:1.2;cursor:pointer;text-decoration:none;touch-action:manipulation;-webkit-tap-highlight-color:transparent;
  text-wrap:balance;transition:transform .15s var(--ease),opacity .15s}
.btn:hover:not(:disabled){opacity:.86}
.btn:active:not(:disabled){transform:scale(.97)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn.xl{font-size:clamp(17px,1.7vw,20px);padding:16px 30px}
.btn.alt{background:color-mix(in srgb,currentColor 14%,transparent);color:inherit}
.btn.ghost{background:transparent;color:inherit}
.bar .btn.ghost{padding-left:0;padding-right:0}
.btn.ghost:hover:not(:disabled){background:color-mix(in srgb,currentColor 12%,transparent);opacity:1}

.rows{padding-top:12px;padding-bottom:24px}
.row{display:grid;grid-template-columns:minmax(170px,250px) minmax(0,1fr);gap:clamp(16px,3vw,40px);background:var(--surface);
  padding:clamp(20px,3vw,34px);margin-top:12px}
.rt{display:grid;grid-template-columns:14px 1fr;column-gap:12px;align-content:start}
.dot{width:14px;height:14px;border-radius:50%;background:#bfc3ba;margin-top:9px}
.ok .dot{background:#17744a}.bad .dot{background:#d4361d}.run .dot{background:#2358ff;animation:blink 1.1s ease-in-out infinite}
@keyframes blink{50%{opacity:.25}}
.rt h2{margin:0;font-size:26px;line-height:1.2;letter-spacing:-.015em;font-weight:750}
.st,#sub{font-variant-numeric:tabular-nums}
.st{grid-column:2;margin:2px 0 0;color:var(--dim)}
.acts{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.acts:empty{display:none}
.rc{min-width:0}
.rc pre{margin:0;padding:16px 18px;background:var(--code);color:#d7e0ee;font:14px/1.6 var(--mono);overflow:auto;white-space:pre-wrap;word-break:break-word}
.rc pre .l{display:block;min-height:1.6em}
.rc pre .add{color:#7ee0a0;background:rgba(46,160,67,.16)}
.rc pre .del{color:#ff8a78;background:rgba(248,81,73,.16)}
.rc pre .hunk{color:#7d8da6}
.hint{margin:0;color:var(--dim);max-width:60ch}
.list{margin:0;padding:0;list-style:none;display:grid;gap:12px}
.list li{display:grid;gap:2px}
.sev{display:inline-block;margin-right:8px;padding:1px 10px;border-radius:99px;background:#cfd3cb;font-size:14px;font-weight:650}
.sev.breaking{background:#ff4b2b}
code{font:14px var(--mono);background:rgba(17,22,28,.09);padding:1px 6px}
.facts{display:grid;gap:18px}
.facts dt{color:var(--dim);font-size:15px}
.facts dd{margin:2px 0 0;font-size:19px;line-height:1.4}
.okline{display:inline-block;background:#bfe3cc;padding:2px 10px;font-weight:600;font-size:15px}
a.pr{font:650 clamp(16px,2vw,22px)/1.3 var(--mono);color:#0b3fcc;word-break:break-all}
footer{padding:28px 0 56px;color:var(--dim);font-size:14px}

.rise{animation:rise .55s var(--ease) both;animation-delay:calc(var(--i,0)*70ms)}
@keyframes rise{from{opacity:0;transform:translateY(18px)}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
@media (max-width:760px){.grid2{grid-template-columns:1fr}.row{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="hero" id="hero" data-state="stable">
  <div class="fields" aria-hidden="true"><i class="f f-stable"></i><i class="f f-broken"></i><i class="f f-run"></i><i class="f f-ready"></i><i class="f f-opened"></i><i class="f f-fail"></i></div>
  <div class="wrap">
    <header class="bar">
      <a class="brand" href="/" translate="no">Self-Maintaining API</a>
      <span class="sp"></span>
      <span id="mode" class="tag" hidden>Rehearsal: no pull requests</span>
      <button id="restart" class="btn ghost" type="button" data-act="restart">Reset Demo</button>
    </header>
    <main>
    <div aria-live="polite"><h1 id="t"></h1></div>
    <div class="grid2">
      <div>
        <p id="sub" aria-live="polite"></p>
        <div id="primary"></div>
      </div>
      <div class="panel">
        <pre id="api" translate="no"></pre>
        <div class="panelbtns" id="apibtns"></div>
      </div>
    </div>
    </main>
  </div>
</div>
<section class="wrap rows" aria-label="Pipeline stages"><div id="rows"></div></section>
<footer class="wrap">The mock API runs at localhost:8000 and this page refreshes every 1.5 seconds.</footer>
<script>
"use strict";
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const calm = !matchMedia("(prefers-reduced-motion: reduce)").matches;
const COLORS = {stable:"#dce7dd", broken:"#ff4b2b", run:"#2358ff", ready:"#17744a", opened:"#0e4d32", fail:"#7a1410"};
const btn = (act, label, cls, off) => `<button class="btn ${cls || ""}" type="button" data-act="${act}"${off ? " disabled" : ""}>${esc(label)}</button>`;
const tidy = t => String(t ?? "").replace(/`/g, "");
const last = out => (String(out).trim().split("\n").filter(Boolean).pop() || "").slice(0, 160);
const plural = n => n === 1 ? "1 breaking change" : n + " breaking changes";
const diff = p => p.split("\n").map(l => {
  const c = l.startsWith("+++") || l.startsWith("---") || l.startsWith("@@") ? "hunk" : l[0] == "+" ? "add" : l[0] == "-" ? "del" : "";
  return `<span class="l ${c}">${esc(l)}</span>`;
}).join("");

function plan(s) {
  const d = s.detect, f = s.fix, broken = s.field !== "email", crash = /crashed/.test(s.app);
  const stale = d && d.summary.breaking && !broken;           // API restored after a detection
  const D = stale ? null : d, F = stale ? null : f;
  const fixLabel = s.no_pr ? "Generate Fix" : "Fix And Open Pull Request";
  if (s.busy === "detect") return {st: "run", t: "Checking the API…", sub: "Comparing the live spec with the saved baseline."};
  if (s.busy === "fix") return {st: "run", t: "Writing the fix…", sub: "Finding the affected code, asking the model, checking the patch" + (s.no_pr ? "." : ", then opening the pull request.")};
  if (D && !D.ok) return {st: "fail", t: "Detector failed.", sub: last(D.out), act: ["detect", "Run Detector Again"]};
  if (F && !F.ok) return {st: "fail", t: "The fix failed.", sub: last(F.out), act: ["fix", "Try Again"]};
  if (F && F.pr) return {st: "opened", t: "Pull request opened.", sub: "The fix, the explanation and the check result are waiting for review.", link: F.pr};
  if (F && F.patch) return {st: "ready", t: "The fix is ready.", sub: tidy(F.checks) || "Review the patch below."};
  if (F && F.none) return {st: "stable", t: "Nothing to fix.", sub: "No code in the repo uses what changed."};
  if (D && D.summary.breaking) return {st: "broken", t: "Change detected.", sub: plural(D.summary.breaking) + " in the API. Next, the model writes the fix.", act: ["fix", fixLabel]};
  if (broken) return {st: "broken", t: "The API changed.", sub: crash ? "Your app is crashing. Run the detector to find out why." : "Run the detector to see what changed.", act: ["detect", "Run Detector"]};
  if (stale) return {st: "stable", t: "API restored.", sub: "Reset the demo to start again.", act: ["restart", "Reset Demo"]};
  if (!D) return {st: "stable", t: "Everything works.", sub: "Save the API’s current shape as a baseline first.", act: ["detect", "Save Baseline"]};
  return {st: "stable", t: "Baseline saved.", sub: "Now break the API and watch what happens.", act: ["break", "Break The API"]};
}

function row(i, id, st, title, status, acts, body) {
  return `<section class="row ${st} ${first ? "rise" : ""}" style="--i:${i}" aria-labelledby="h-${id}">
    <div class="rt"><span class="dot" aria-hidden="true"></span><h2 id="h-${id}">${title}</h2><p class="st">${status}</p></div>
    <div class="rc"><div class="acts">${acts}</div>${body}</div></section>`;
}

let first = true, shown = {};
function put(key, el, html) {
  if (shown[key] === html) return;
  shown[key] = html;
  const a = document.activeElement, act = el.contains(a) && a.dataset ? a.dataset.act : null;
  el.innerHTML = html;
  if (act) { const n = el.querySelector(`[data-act="${act}"]:not(:disabled)`); if (n) n.focus(); }
}

function render(s) {
  const off = !!s.busy, d = s.detect, f = s.fix, p = plan(s);
  const broken = s.field !== "email", crash = /crashed/.test(s.app), works = /->/.test(s.app);

  $("#hero").dataset.state = p.st;
  document.querySelector('meta[name="theme-color"]').content = COLORS[p.st];
  document.title = p.t.replace(/[….]+$/, "") + " · Self-Maintaining API";
  if (shown.t !== p.t) {
    shown.t = p.t; $("#t").textContent = p.t;
    if (calm && !first) $("#t").animate([{opacity: 0, transform: "translateY(14px)"}, {opacity: 1, transform: "none"}], {duration: 380, easing: "cubic-bezier(.2,.7,.2,1)"});
  }
  if (shown.sub !== p.sub) { shown.sub = p.sub; $("#sub").textContent = p.sub; }
  put("primary", $("#primary"), p.link
    ? `<a class="btn xl" href="${esc(p.link)}" target="_blank" rel="noopener noreferrer">Open Pull Request</a>`
    : p.act ? btn(p.act[0], p.act[1], "xl", off) : "");
  put("api", $("#api"), `GET /v1/users/1\n{\n  "id": 1,\n  "<b class="k ${broken ? "bad" : ""}">${esc(s.field)}</b>": "tsu@example.com"\n}`);
  put("apibtns", $("#apibtns"), btn("break", "Break The API", "alt", off || broken) + btn("reset", "Restore", "alt", off || !broken));
  $("#mode").hidden = !s.no_pr;
  $("#restart").disabled = off;

  const appRow = row(0, "app", crash ? "bad" : works ? "ok" : "", "Your App", crash ? "Crashing" : works ? "Working" : "Checking…", "",
    `<pre translate="no">${esc(s.app || "…")}</pre>` + (works && broken && f && f.pr ? `<p class="hint" style="margin-top:12px">This is the fixed code from the pull request branch, running against the changed API.</p>` : ""));

  const dst = s.busy === "detect" ? "run" : !d ? "" : !d.ok ? "bad" : "ok";
  const dstat = s.busy === "detect" ? "Running…" : !d ? "Not run yet" : !d.ok ? "Failed"
    : d.summary.breaking ? plural(d.summary.breaking) : d.status.includes("baseline") ? "Baseline saved" : "No changes";
  const dbody = !d ? `<p class="hint">Run it once while the API is stable to save a baseline, then again after you break it.</p>`
    : !d.ok ? `<pre>${esc(d.out)}</pre>`
    : d.changes.length ? `<ul class="list">${d.changes.map(c => `<li><span><span class="sev ${esc(c.severity)}">${esc(c.severity)}</span><code translate="no">${esc(c.location)}</code></span><span>${esc(c.message)}</span></li>`).join("")}</ul>`
    : `<p class="hint">${d.status.includes("baseline") ? "Saved the current API as the baseline." : "The API matches the saved baseline."}</p>`;
  const detRow = row(1, "detector", dst, "Change Detector", dstat, btn("detect", "Run Detector", "alt", off), dbody);

  const fst = s.busy === "fix" ? "run" : !f ? "" : !f.ok ? "bad" : f.none ? "" : "ok";
  const fstat = s.busy === "fix" ? "Working…" : !f ? "Not run yet" : !f.ok ? "Failed" : f.none ? "Nothing to fix" : "Patch ready";
  let fbody = `<p class="hint">Finds the code that uses the changed API, asks the model for a fix, and checks it before opening a pull request.</p>`;
  if (f && !f.ok) fbody = `<pre>${esc(f.out)}</pre>`;
  else if (f && f.none) fbody = `<p class="hint">${esc(f.out.trim())}</p>`;
  else if (f) fbody = `<dl class="facts">
      <div><dt>Upstream change</dt>${f.changes.map(c => `<dd>${esc(c)}</dd>`).join("")}</div>
      <div><dt>Fix from <span translate="no">${esc(f.model)}</span></dt><dd>${esc(f.summary)}</dd></div>
      <div><dt>Files changed</dt><dd><code translate="no">${esc(f.files)}</code></dd></div>
      <div><dt>Checks</dt><dd>${f.checks ? `<span class="okline">${esc(tidy(f.checks))}</span>` : "None ran"}</dd></div>
      </dl><pre translate="no" style="margin-top:20px">${diff(f.patch)}</pre>`;
  const fixRow = row(2, "fix", fst, "Fix Generator", fstat, btn("fix", s.no_pr ? "Generate Fix" : "Fix And Open Pull Request", "alt", off || !d), fbody);

  const prRow = row(3, "pr", f && f.pr ? "ok" : "", "Pull Request", f && f.pr ? "Opened" : s.no_pr && f && f.patch ? "Skipped in rehearsal" : "Waiting", "",
    f && f.pr ? `<a class="pr" href="${esc(f.pr)}" target="_blank" rel="noopener noreferrer">${esc(f.pr)}</a>`
      : `<p class="hint">The fix, an explanation and the check result land here as a pull request for review.</p>`);

  put("rows", $("#rows"), appRow + detRow + fixRow + prRow);
  first = false;
}

let last_ = "", armed = null;
async function poll() {
  try {
    const t = await (await fetch("/state")).text();
    if (t !== last_) { last_ = t; render(JSON.parse(t)); }
  } catch (e) { /* server stopped: keep the last view */ }
}
async function act(n) { await fetch("/do/" + n, {method: "POST"}); poll(); }

document.addEventListener("click", e => {
  const b = e.target.closest("[data-act]");
  if (!b || b.disabled) return;
  if (b.id === "restart") {                       // clears the baseline and reports: ask twice
    if (!armed) {
      b.textContent = "Click Again To Reset";
      armed = setTimeout(() => { armed = null; b.textContent = "Reset Demo"; }, 3000);
      return;
    }
    clearTimeout(armed); armed = null; b.textContent = "Reset Demo";
  }
  act(b.dataset.act);
});
poll(); setInterval(poll, 1500);
</script>
</body>
</html>
"""






def main():
    os.chdir(ROOT)

    hosted = os.environ.get("HOSTED", "").lower() == "true"
    host = "0.0.0.0" if hosted else "localhost"
    dashboard_port = int(os.environ.get("PORT", "8001")) if hosted else 8001

    # The mock API is needed in both local and hosted modes.
    try:
        api = ThreadingHTTPServer(("127.0.0.1", 8000), mock_api.Handler)
    except OSError:
        sys.exit(
            "Port 8000 is busy. Close any other window running mock_api.py, "
            "then start the dashboard again."
        )

    threading.Thread(target=api.serve_forever, daemon=True).start()
    print("Mock API on http://127.0.0.1:8000")
    print(f"Console on http://{host}:{dashboard_port}")

    if not hosted:
        try:
            webbrowser.open("http://localhost:8001")
        except Exception:
            pass

    ThreadingHTTPServer((host, dashboard_port), H).serve_forever()


if __name__ == "__main__":
    main()
