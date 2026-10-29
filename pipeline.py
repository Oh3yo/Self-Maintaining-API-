"""Scanner -> fix generator -> one patch.

    python pipeline.py REPO changes.json [-o fix.patch] [--model ID]

REPO         folder of the code to fix (the scanner walks it)
changes.json the detector's JSON output (diff --json, or a run report), or a hand-written list
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

from fix_generator import DEFAULT_MODEL, AffectedFile, generate_fix
from impact_scanner import scan

NOTE = ("The list above is the COMPLETE set of breaking API changes. Update only "
        "usages of exactly these changes. Change nothing else: do not alter URLs, "
        "API versions, or unrelated code, even if you think it would be an improvement. "
        "Lines marked '>' are where the scanner found usages.")


def describe(c):
    """Plain-English line per change. Raw JSON made the model invent endpoint changes."""
    ep = f'{c.get("method", "")} {c.get("path", "")}'.strip()
    fld = f'{c["schema"]}.{c["field"]}' if c.get("schema") else c.get("field", "")
    text = {
        "endpoint_removed": f"Endpoint {ep} was removed.",
        "endpoint_changed": f"Endpoint {ep} changed: {c.get('detail')}" if c.get("detail")
                            else f"Endpoint {ep} changed (details unknown).",
        "field_removed": f"Field {fld} was removed.",
        "field_renamed": f'Field {fld} was renamed to "{c.get("new_name")}".',
        "field_type_changed": f"Field {fld} changed type.",
    }.get(c["kind"], json.dumps(c))
    if c.get("field") and c.get("path"):
        where = "requests to" if c.get("in") == "request" else "responses of"
        text += f" (It appears in {where} {c['path']}, which is itself unchanged.)"
    return text


LOC = re.compile(r"(?:([A-Z]+) )?(/\S*)(.*)$")  # "GET /users/{id} response 200[application/json].email"
FIELD = re.compile(r"\.([^.\[\]\s]+)$")


def from_detector(data, severities=("breaking",)):
    """Detector output -> the change list the scanner reads.

    Takes `detector.py diff --json` (a list), a `run` report (dict with results[]), or a list
    already in scanner format (passed through). The detector only gives a location string, so the
    schema name is lost, and a rename arrives as one removed + one added property.
    """
    if isinstance(data, dict):
        data = [c for r in data.get("results", []) for c in r.get("changes", [])]
    out = [c for c in data if "location" not in c]  # already scanner format
    rows = []  # (change, base, field, parent object location)
    for c in data:
        m = LOC.match(c.get("location", ""))
        if not m:
            continue  # info.version, servers, changelog, sdk: nothing in the code to point at
        f = FIELD.search(m[3])
        base = {k: v for k, v in (("method", m[1]), ("path", m[2])) if v}
        if re.search(r"requestBody| param ", m[3]):
            base["in"] = "request"
        rows.append((c, base, f and f[1], f and c["location"][:-len(f[0])]))
    added, gone = defaultdict(list), defaultdict(int)
    for c, _, field, parent in rows:
        if field and c["kind"] == "property_added":
            added[parent].append(field)
        if field and c["kind"] == "property_removed" and c["severity"] in severities:
            gone[parent] += 1
    for c, base, field, parent in rows:
        if c["severity"] not in severities:
            continue
        k = c["kind"]
        if k in ("operation_removed", "path_removed"):
            e = {"kind": "endpoint_removed", **base}
        elif k == "property_removed" and field:
            # ponytail: 1 removed + 1 added property in the same object is called a rename (types not compared)
            new = added[parent]
            e = ({"kind": "field_renamed", "field": field, "new_name": new[0], **base}
                 if len(new) == 1 and gone[parent] == 1 else {"kind": "field_removed", "field": field, **base})
        elif k == "type_changed" and field:
            e = {"kind": "field_type_changed", "field": field, **base}
        else:
            e = {"kind": "endpoint_changed", "detail": f'{c["message"]} ({c["location"]})', **base}
        if e not in out:
            out.append(e)
    return out


COPY_IGNORE = shutil.ignore_patterns(".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build")


def detect_cmd(root):
    """Pick the repo's own test command; fall back to a syntax check. None if nothing applies."""
    r = Path(root)
    pkg = r / "package.json"
    if pkg.exists() and '"test"' in pkg.read_text(encoding="utf-8", errors="replace"):
        return "npm test --silent"
    if (r / "go.mod").exists():
        return "go test ./..."
    if (r / "pytest.ini").exists() or (r / "tests").is_dir() or any(r.glob("test_*.py")):
        return [sys.executable, "-m", "pytest", "-q", "-x"]
    if any(r.rglob("*.py")):
        return [sys.executable, "-m", "compileall", "-q", "."]  # ponytail: syntax only, add a linter if wanted
    return None


def _run(cmd, cwd):
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return False, "timed out after 300s"
    return r.returncode == 0, (r.stdout + r.stderr)[-3000:]


def check_patch(repo, patch, cmd=None):
    """Apply the patch to a temporary copy of the repo and run its tests/lint there.

    Returns (status, label, output); status is pass | fail | preexisting | skipped.
    'preexisting' = checks fail with the patch but also fail without it, so they prove nothing.
    The real working copy is never touched. ponytail: full copy, use git worktree for huge repos.
    """
    cmd = cmd or detect_cmd(repo)
    if cmd is None:
        return "skipped", "", ""
    label = cmd if isinstance(cmd, str) else "python -m " + " ".join(cmd[2:])
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        work = Path(tmp, "patched")
        shutil.copytree(repo, work, ignore=COPY_IGNORE)
        pf = Path(tmp, "fix.patch")
        pf.write_text(patch, encoding="utf-8", newline="\n")
        a = subprocess.run(["git", "apply", "--ignore-whitespace", str(pf)], cwd=work, capture_output=True, text=True)
        if a.returncode:
            return "fail", label, "patch does not apply: " + a.stderr.strip()
        ok, out = _run(cmd, work)
        if ok:
            return "pass", label, out
        base = Path(tmp, "base")
        shutil.copytree(repo, base, ignore=COPY_IGNORE)
        base_ok, _ = _run(cmd, base)
        return ("fail" if base_ok else "preexisting"), label, out


def make_check(repo, cmd=None, log=None):
    """Build the callback generate_fix uses: None if fine, else the failure text for the model."""
    def check(patch):
        status, label, out = check_patch(repo, patch, cmd)
        if log is not None:
            log.update(status=status, label=label)
        if status == "fail":
            return f"The patch applies, but the repo's checks (`{label}`) now fail:\n{out}"
        return None
    return check


def check_note(log):
    s, label = log.get("status"), log.get("label")
    return {
        "pass": f"Passed `{label}` on a temporary copy with the patch applied.",
        "preexisting": f"`{label}` was already failing before the fix, so it could not confirm the patch.",
        "skipped": "No tests or lint found in the repo; nothing was run.",
    }.get(s, "")


def run(repo, changes, min_conf=0.3, client=None, model=DEFAULT_MODEL, check=None):
    """Return a FixResult, or None if nothing in the repo uses the changed API."""
    hits = scan(repo, changes, min_conf)
    if not hits:
        return None
    flagged = defaultdict(list)
    for h in hits:
        flagged[h.file].append(h.line)
    files = [
        AffectedFile(
            path=f.replace("\\", "/"),  # forward slashes so the patch is valid on Windows
            content=(Path(repo) / f).read_text(encoding="utf-8"),  # text mode: CRLF -> LF
            lines=sorted(set(ls)),
        )
        for f, ls in sorted(flagged.items())
    ]
    listing = "\n".join(f"{i}. {describe(c)}" for i, c in enumerate(changes, 1))
    return generate_fix(listing, files, NOTE, client=client, model=model, check=check)


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode:
        msg = f"git {' '.join(args)} failed:\n{r.stderr.strip()}"
        tok = os.environ.get("GITHUB_TOKEN")
        raise SystemExit(msg.replace(tok, "***") if tok else msg)  # never print the token
    return r.stdout.strip()


def _auth_url(url, token):
    """Push with the token so Windows' saved login for another GitHub account is not used."""
    if token and url.startswith("https://github.com/"):
        return url.replace("https://", f"https://x-access-token:{token}@", 1)
    return url


def _github_pr(remote_url, title, head, base, body):
    """Open the PR through GitHub's REST API. Needs GITHUB_TOKEN in the environment."""
    m = re.search(r"github\.com[:/]([^/]+)/(.+?)(?:\.git)?$", remote_url)
    if not m:
        raise SystemExit(f"origin is not a GitHub remote: {remote_url}")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set (needs Contents + Pull requests write on the repo)")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{m[1]}/{m[2]}/pulls",
        data=json.dumps({"title": title, "head": head, "base": base, "body": body}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "self-maintaining-api"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)["html_url"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GitHub API error {e.code}: {e.read().decode()[:500]}")


def open_pr(repo, patch_path, result, changes, create=_github_pr, checks=""):
    """Branch, apply the patch, commit, push, open a PR. Returns the PR URL."""
    if _git(repo, "status", "--porcelain"):
        raise SystemExit(f"{repo} has uncommitted changes. Commit or stash them first.")
    base = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    branch = f"api-fix/{time.strftime('%Y%m%d-%H%M%S')}"
    _git(repo, "checkout", "-b", branch)
    _git(repo, "apply", "--ignore-whitespace", str(Path(patch_path).resolve()))
    title = "Fix breaking API change: " + "; ".join(describe(c).split(" (")[0].rstrip(".") for c in changes)[:100]
    changed = _git(repo, "diff", "--name-only")
    body = ("## Upstream API changes\n" + "\n".join(f"- {describe(c)}" for c in changes)
            + f"\n\n## Fix\n{result.summary}\n\nFiles changed: {', '.join(changed.splitlines())}\n\n"
            + (f"## Validation\n{checks}\n\n" if checks else "") + "---\n"
            f"Generated automatically by Self-Maintaining API using `{result.model}` on Nebius "
            f"Token Factory. Review before merging.")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", title)
    remote = _git(repo, "remote", "get-url", "origin")
    _git(repo, "push", _auth_url(remote, os.environ.get("GITHUB_TOKEN")), branch)
    return create(remote, title, branch, base, body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pr", action="store_true", help="also open a GitHub pull request (needs GITHUB_TOKEN)")
    ap.add_argument("--no-checks", action="store_true", help="skip running the repo's tests/lint on the patch")
    ap.add_argument("--test-cmd", help='command to run instead of auto-detecting, e.g. "pytest -q"')
    ap.add_argument("repo")
    ap.add_argument("changes")
    ap.add_argument("-o", "--out", default="fix.patch")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--min-confidence", type=float, default=0.3)
    a = ap.parse_args()

    src = Path(a.changes)
    if src.is_dir():  # e.g. "reports": use the newest report
        src = max(src.glob("*.json"), key=lambda f: f.stat().st_mtime)
    changes = from_detector(json.loads(src.read_text(encoding="utf-8")))
    if not changes:
        print("No breaking API changes that map to code. Nothing to fix.")
        return 0
    print("API changes:", *map(describe, changes), sep="\n- ")
    log = {}
    check = None if a.no_checks else make_check(a.repo, a.test_cmd, log)
    result = run(a.repo, changes, a.min_confidence, model=a.model, check=check)

    if result is None:
        print("Scanner found no code using the changed API. Nothing to fix.")
        return 0
    for e in result.errors:
        print(e, file=sys.stderr)
    if not result.ok:
        print(f"Fix generator failed after {result.attempts} attempts.", file=sys.stderr)
        return 1
    if not result.patch:
        print(f"Model says no change needed: {result.summary}")
        return 0
    Path(a.out).write_text(result.patch, encoding="utf-8", newline="\n")
    print(f"[{result.model}] {result.summary}")
    print("Affected files:", ", ".join(re.findall(r"^\+\+\+ b/(.+)$", result.patch, re.M)))
    print(f"\nPatch written to {a.out}")
    note = check_note(log)
    if note:
        print("Checks:", note)
    if a.pr:
        print("Pull request:", open_pr(a.repo, a.out, result, changes, checks=note))
    else:
        print(f'Apply it with:  git -C "{a.repo}" apply --ignore-whitespace "{Path(a.out).resolve()}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
