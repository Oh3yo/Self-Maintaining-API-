"""
Change detector for third-party APIs.

On a schedule it pulls, for each configured API:
  * the OpenAPI spec          -> structural diff, classified breaking / warning / info
  * a changelog page / feed   -> line diff, new lines scanned for breaking-change language
  * the SDK version           -> PyPI / npm / GitHub release, semver-aware

and compares each against the last snapshot it stored. The output is a JSON report
of `Change` objects, which is what a downstream "fix the code" agent consumes.

Usage:
    python detector.py run  --config apis.yaml --once
    python detector.py run  --config apis.yaml --every 6h
    python detector.py diff old_spec.yaml new_spec.yaml        # ad-hoc spec diff

Exit code 2 from `run --once` means breaking changes were found (handy for cron/CI).
Supports OpenAPI 3.x (JSON or YAML). Swagger 2.0 is rejected explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import difflib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

import requests
import yaml

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
SEVERITIES = ("breaking", "warning", "info")
MAX_SCHEMA_DEPTH = 12


# --------------------------------------------------------------------------- model

@dataclass
class Change:
    api: str
    source: str       # openapi | changelog | pypi | npm | github_release
    kind: str         # machine-readable, e.g. "operation_removed"
    severity: str     # breaking | warning | info
    location: str     # e.g. "POST /users requestBody[application/json].email"
    message: str
    old: Any = None
    new: Any = None


Emit = Callable[..., None]


# --------------------------------------------------------------------------- fetching

def _expand(value: str) -> str:
    return os.path.expandvars(value) if isinstance(value, str) else value


def fetch(target: str, headers: dict | None = None, timeout: int = 30, retries: int = 3) -> str:
    """Fetch a URL, file:// URL or local path and return text."""
    target = _expand(target)
    if target.startswith("file://"):
        target = target[7:]
    if not re.match(r"^https?://", target):
        return Path(target).read_text(encoding="utf-8")
    hdrs = {"User-Agent": "api-change-detector/1.0", **{k: _expand(v) for k, v in (headers or {}).items()}}
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(target, headers=hdrs, timeout=timeout)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"fetch failed for {target}: {last}")


def parse_spec(text: str) -> dict:
    try:
        spec = json.loads(text)
    except json.JSONDecodeError:
        spec = yaml.safe_load(text)
    if not isinstance(spec, dict):
        raise ValueError("spec is not a JSON/YAML object")
    if "swagger" in spec:
        raise ValueError("Swagger 2.0 is not supported; convert to OpenAPI 3.x first")
    return spec


# --------------------------------------------------------------------------- $ref + schema helpers

def resolve(node: Any, root: dict, stack: tuple = ()) -> tuple[dict, tuple]:
    """Follow local $refs lazily. A ref already on the stack (recursion) resolves to {}."""
    hops = 0
    while isinstance(node, dict) and isinstance(node.get("$ref"), str):
        ref = node["$ref"]
        if not ref.startswith("#/") or ref in stack or hops > 20:
            return {}, stack
        stack += (ref,)
        target: Any = root
        for part in ref[2:].split("/"):
            part = unquote(part).replace("~1", "/").replace("~0", "~")
            if isinstance(target, dict) and part in target:
                target = target[part]
            elif isinstance(target, list) and part.isdigit() and int(part) < len(target):
                target = target[int(part)]
            else:
                return {}, stack
        node = target
        hops += 1
    return (node if isinstance(node, dict) else {}), stack


def flat(schema: Any, root: dict, stack: tuple = ()) -> tuple[dict, tuple]:
    """Resolve $ref and merge allOf into a single schema."""
    schema, stack = resolve(schema, root, stack)
    if "allOf" not in schema:
        return schema, stack
    merged = {k: v for k, v in schema.items() if k != "allOf"}
    for part in schema["allOf"]:
        p, _ = flat(part, root, stack)
        for k, v in p.items():
            if k == "properties":
                merged["properties"] = {**merged.get("properties", {}), **v}
            elif k == "required":
                merged["required"] = sorted(set(merged.get("required", [])) | set(v))
            else:
                merged.setdefault(k, v)
    return merged, stack


def type_set(s: dict) -> set[str]:
    t = s.get("type")
    ts = set(t) if isinstance(t, list) else ({t} if t else set())
    if s.get("nullable"):
        ts.add("null")
    return ts


def subtype(a: set[str], b: set[str]) -> bool:
    """True if every type in a is accepted by b (integer is a subset of number)."""
    return a <= (b | {"integer"} if "number" in b else b)


def diff_schema(old: Any, new: Any, loc: str, direction: str, emit: Emit,
                old_root: dict, new_root: dict, so: tuple = (), sn: tuple = (), depth: int = 0) -> None:
    """
    direction="request":  the client sends this. Stricter = breaking.
    direction="response": the client receives this. Removed / changed fields = breaking.
    """
    if depth > MAX_SCHEMA_DEPTH:
        return
    o, so = flat(old, old_root, so)
    n, sn = flat(new, new_root, sn)
    req = direction == "request"

    ot, nt = type_set(o), type_set(n)
    if ot and nt and ot != nt:
        incompatible = not subtype(ot, nt) if req else not subtype(nt, ot)
        emit("type_changed", "breaking" if incompatible else "info", loc,
             f"type {sorted(ot)} -> {sorted(nt)}", sorted(ot), sorted(nt))

    oe, ne = o.get("enum"), n.get("enum")
    if isinstance(oe, list) and isinstance(ne, list):
        removed = [v for v in oe if v not in ne]
        added = [v for v in ne if v not in oe]
        if req and removed:
            emit("enum_value_removed", "breaking", loc, f"enum values no longer accepted: {removed}", oe, ne)
        if not req and added:
            emit("enum_value_added", "warning", loc, f"response may now return new enum values: {added}", oe, ne)
    elif ne and not oe and req:
        emit("enum_constraint_added", "breaking", loc, f"input restricted to {ne}", None, ne)

    op, np_ = o.get("properties") or {}, n.get("properties") or {}
    oreq, nreq = set(o.get("required") or []), set(n.get("required") or [])

    for name, sub in op.items():
        ploc = f"{loc}.{name}"
        if name not in np_:
            emit("property_removed", "warning" if req else "breaking", ploc,
                 f"property '{name}' removed from {'request' if req else 'response'}")
            continue
        diff_schema(sub, np_[name], ploc, direction, emit, old_root, new_root, so, sn, depth + 1)

    for name in np_:
        if name in op:
            continue
        if req and name in nreq:
            emit("required_property_added", "breaking", f"{loc}.{name}", f"new required request property '{name}'")
        else:
            emit("property_added", "info", f"{loc}.{name}", f"new property '{name}'")

    if req:
        for name in sorted((nreq - oreq) & set(op)):
            emit("property_became_required", "breaking", f"{loc}.{name}", f"request property '{name}' is now required")
    else:
        for name in sorted((oreq - nreq) & set(np_)):
            emit("property_now_optional", "warning", f"{loc}.{name}",
                 f"response property '{name}' is no longer guaranteed")

    if isinstance(o.get("items"), dict) and isinstance(n.get("items"), dict):
        diff_schema(o["items"], n["items"], f"{loc}[]", direction, emit, old_root, new_root, so, sn, depth + 1)


# --------------------------------------------------------------------------- OpenAPI diff

def _norm_path(p: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", p)


def _params(item: dict, op: dict, root: dict) -> dict:
    out: dict = {}
    for group in (item.get("parameters") or [], op.get("parameters") or []):
        for p in group:
            p, _ = resolve(p, root)
            if "name" in p and "in" in p:
                out[(p["in"], p["name"])] = p
    return out


def _sec_names(op: dict, root: dict) -> set[str]:
    sec = op.get("security", root.get("security")) or []
    return {name for req in sec if isinstance(req, dict) for name in req}


def _diff_operation(oop: dict, nop: dict, oitem: dict, nitem: dict, loc: str,
                    oroot: dict, nroot: dict, emit: Emit) -> None:
    # parameters
    oparams, nparams = _params(oitem, oop, oroot), _params(nitem, nop, nroot)
    for key, op_ in oparams.items():
        ploc = f"{loc} param {key[0]}:{key[1]}"
        if key not in nparams:
            emit("parameter_removed", "warning", ploc, "parameter removed (may now be ignored or rejected)")
            continue
        np_ = nparams[key]
        if not op_.get("required") and np_.get("required"):
            emit("parameter_became_required", "breaking", ploc, "parameter is now required")
        diff_schema(op_.get("schema", {}), np_.get("schema", {}), ploc, "request", emit, oroot, nroot)
    for key, np_ in nparams.items():
        if key not in oparams:
            ploc = f"{loc} param {key[0]}:{key[1]}"
            if np_.get("required"):
                emit("required_parameter_added", "breaking", ploc, "new required parameter")
            else:
                emit("parameter_added", "info", ploc, "new optional parameter")

    # request body
    orb, _ = resolve(oop.get("requestBody") or {}, oroot)
    nrb, _ = resolve(nop.get("requestBody") or {}, nroot)
    if nrb and not orb:
        emit("request_body_added", "breaking" if nrb.get("required") else "info", loc, "request body added")
    elif orb and not nrb:
        emit("request_body_removed", "warning", loc, "request body removed")
    elif orb and nrb:
        if not orb.get("required") and nrb.get("required"):
            emit("request_body_became_required", "breaking", loc, "request body is now required")
        ocont, ncont = orb.get("content") or {}, nrb.get("content") or {}
        for ct, om in ocont.items():
            if ct not in ncont:
                emit("request_media_type_removed", "breaking", f"{loc} requestBody[{ct}]",
                     f"media type '{ct}' no longer accepted")
            else:
                diff_schema(om.get("schema", {}), ncont[ct].get("schema", {}),
                            f"{loc} requestBody[{ct}]", "request", emit, oroot, nroot)

    # responses
    oresp, nresp = oop.get("responses") or {}, nop.get("responses") or {}
    for code, oraw in oresp.items():
        rloc = f"{loc} response {code}"
        if code not in nresp:
            emit("response_removed", "breaking" if str(code).startswith("2") else "info", rloc,
                 f"response {code} removed")
            continue
        o, _ = resolve(oraw, oroot)
        n, _ = resolve(nresp[code], nroot)
        ocont, ncont = o.get("content") or {}, n.get("content") or {}
        for ct, om in ocont.items():
            if ct not in ncont:
                emit("response_media_type_removed", "breaking" if str(code).startswith("2") else "warning",
                     f"{rloc}[{ct}]", f"media type '{ct}' no longer returned")
            else:
                diff_schema(om.get("schema", {}), ncont[ct].get("schema", {}),
                            f"{rloc}[{ct}]", "response", emit, oroot, nroot)
    for code in nresp:
        if code not in oresp:
            emit("response_added", "info", f"{loc} response {code}", f"new response {code}")

    # auth
    osec, nsec = _sec_names(oop, oroot), _sec_names(nop, nroot)
    if nsec and not osec:
        emit("auth_added", "breaking", loc, f"authentication now required: {sorted(nsec)}")
    elif osec != nsec:
        emit("auth_changed", "warning", loc, f"security schemes {sorted(osec)} -> {sorted(nsec)}")

    if nop.get("deprecated") and not oop.get("deprecated"):
        emit("operation_deprecated", "warning", loc, "operation marked deprecated")
    if oop.get("operationId") and nop.get("operationId") and oop["operationId"] != nop["operationId"]:
        emit("operation_id_changed", "warning", loc,
             f"operationId {oop['operationId']} -> {nop['operationId']} (generated SDK method names change)",
             oop["operationId"], nop["operationId"])


def diff_openapi(api: str, old: dict, new: dict, source: str = "openapi") -> list[Change]:
    changes: list[Change] = []

    def emit(kind, severity, location, message, o=None, n=None):
        changes.append(Change(api, source, kind, severity, location, message, o, n))

    for spec in (old, new):
        if "swagger" in spec:
            raise ValueError("Swagger 2.0 is not supported")

    opaths, npaths = old.get("paths") or {}, new.get("paths") or {}
    new_by_norm = {_norm_path(p): p for p in npaths}

    matched_new: set[str] = set()
    for path, oraw in opaths.items():
        npath = path if path in npaths else new_by_norm.get(_norm_path(path))
        if npath is None:
            emit("path_removed", "breaking", path, f"path {path} removed")
            continue
        matched_new.add(npath)
        if npath != path:
            emit("path_param_renamed", "info", path, f"path template {path} -> {npath}", path, npath)
        oitem, _ = resolve(oraw, old)
        nitem, _ = resolve(npaths[npath], new)
        for m in HTTP_METHODS:
            loc = f"{m.upper()} {path}"
            if m in oitem and m not in nitem:
                emit("operation_removed", "breaking", loc, "operation removed")
            elif m in oitem:
                _diff_operation(oitem[m] or {}, nitem[m] or {}, oitem, nitem, loc, old, new, emit)
            elif m in nitem:
                emit("operation_added", "info", f"{m.upper()} {npath}", "new operation")
    for path in npaths:
        if path not in matched_new:
            emit("path_added", "info", path, f"new path {path}")

    ov, nv = (old.get("info") or {}).get("version"), (new.get("info") or {}).get("version")
    if ov != nv:
        emit("spec_version_changed", "info", "info.version", f"spec version {ov} -> {nv}", ov, nv)
    if old.get("servers") != new.get("servers"):
        emit("servers_changed", "warning", "servers", "server list changed", old.get("servers"), new.get("servers"))
    return changes


# --------------------------------------------------------------------------- changelog diff

_BREAKING_RE = re.compile(
    r"\b(breaking|incompatible|removed?|no longer (?:supported|available|works?)|sunset|end[- ]of[- ]life|"
    r"discontinued|will stop working)\b", re.I)
_WARNING_RE = re.compile(r"\b(deprecat\w*|renam\w+|migrat\w+|replaced|changed behaviou?r|action required)\b", re.I)


def _clean_text(raw: str) -> list[str]:
    if "<" in raw and ">" in raw:
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        raw = re.sub(r"(?s)<[^>]+>", "\n", raw)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw.splitlines()]
    return [ln for ln in lines if ln]


def diff_changelog(api: str, old: str, new: str, max_lines: int = 50, source: str = "changelog") -> list[Change]:
    old_lines, new_lines = _clean_text(old), _clean_text(new)
    added = [ln[1:].strip() for ln in difflib.unified_diff(old_lines, new_lines, lineterm="", n=0)
             if ln.startswith("+") and not ln.startswith("+++")]
    changes: list[Change] = []
    for ln in added:
        sev = "breaking" if _BREAKING_RE.search(ln) else "warning" if _WARNING_RE.search(ln) else None
        if sev:
            changes.append(Change(api, source, "changelog_entry", sev, "changelog", ln[:500]))
        if len(changes) >= max_lines:
            break
    if added and not changes:
        changes.append(Change(api, source, "changelog_updated", "info", "changelog",
                              f"{len(added)} new line(s), none flagged", None, added[:5]))
    return changes


# --------------------------------------------------------------------------- SDK versions

def _vtuple(v: str) -> tuple[int, int, int]:
    nums = [int(x) for x in re.findall(r"\d+", v)[:3]]
    return tuple(nums + [0] * (3 - len(nums)))  # type: ignore[return-value]


def latest_sdk_version(src: dict) -> str:
    t = src["type"]
    if t == "pypi":
        return json.loads(fetch(f"https://pypi.org/pypi/{src['package']}/json"))["info"]["version"]
    if t == "npm":
        return json.loads(fetch(f"https://registry.npmjs.org/{src['package']}/latest"))["version"]
    if t == "github_release":
        hdrs = {"Accept": "application/vnd.github+json"}
        if os.environ.get("GITHUB_TOKEN"):
            hdrs["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
        return json.loads(fetch(f"https://api.github.com/repos/{src['repo']}/releases/latest", hdrs))["tag_name"]
    raise ValueError(f"unknown sdk source type {t}")


def diff_sdk(api: str, source: str, old: str, new: str) -> list[Change]:
    if old == new:
        return []
    (omaj, omin, _), (nmaj, nmin, _) = _vtuple(old), _vtuple(new)
    if _vtuple(new) < _vtuple(old):
        return [Change(api, source, "sdk_downgrade", "warning", "sdk", f"{old} -> {new} (version went backwards)", old, new)]
    if nmaj > omaj:
        sev, kind, why = "breaking", "sdk_major_bump", "major version bump; review release notes"
    elif omaj == 0 and nmin > omin:
        sev, kind, why = "warning", "sdk_minor_bump_pre1", "0.x minor bump may contain breaking changes"
    else:
        sev, kind, why = "info", "sdk_update", "new release"
    return [Change(api, source, kind, sev, "sdk", f"{old} -> {new}: {why}", old, new)]


# --------------------------------------------------------------------------- snapshot store

def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


class Store:
    """latest snapshot per (api, source) plus a timestamped archive of every previous one."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _dir(self, api: str) -> Path:
        d = self.root / _safe(api)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get(self, api: str, key: str) -> str | None:
        p = self._dir(api) / f"{_safe(key)}.latest"
        return p.read_text(encoding="utf-8") if p.exists() else None

    def put(self, api: str, key: str, text: str) -> None:
        d = self._dir(api)
        latest = d / f"{_safe(key)}.latest"
        if latest.exists():
            arch = d / "archive"
            arch.mkdir(exist_ok=True)
            stamp = datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            (arch / f"{_safe(key)}.{stamp}").write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")
        tmp = latest.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(latest)


def source_key(src: dict) -> str:
    ident = src.get("url") or src.get("package") or src.get("repo") or ""
    return f"{src['type']}-{hashlib.sha1(ident.encode()).hexdigest()[:8]}"


# --------------------------------------------------------------------------- engine

def check_source(api: str, src: dict, store: Store) -> dict:
    t, key = src["type"], source_key(src)
    res = {"api": api, "source": t, "key": key, "status": "unchanged", "changes": [], "error": None}
    try:
        old = store.get(api, key)
        if t == "openapi":
            text = fetch(src["url"], src.get("headers"))
            new_spec = parse_spec(text)
            if old is None:
                res["status"] = "baseline"
            elif hashlib.sha256(old.encode()).digest() != hashlib.sha256(text.encode()).digest():
                res["changes"] = diff_openapi(api, parse_spec(old), new_spec)
                res["status"] = "changed"
            store.put(api, key, text) if old != text else None
        elif t == "changelog":
            text = fetch(src["url"], src.get("headers"))
            if old is None:
                res["status"] = "baseline"
            elif old != text:
                res["changes"] = diff_changelog(api, old, text, src.get("max_lines", 50))
                res["status"] = "changed" if res["changes"] else "unchanged"
            store.put(api, key, text) if old != text else None
        elif t in ("pypi", "npm", "github_release"):
            ver = latest_sdk_version(src)
            if old is None:
                res["status"] = "baseline"
            elif old != ver:
                res["changes"] = diff_sdk(api, t, old, ver)
                res["status"] = "changed"
            store.put(api, key, ver) if old != ver else None
        else:
            raise ValueError(f"unknown source type '{t}'")
    except Exception as e:  # one broken source must not stop the others
        res["status"], res["error"] = "error", f"{type(e).__name__}: {e}"
    return res


def run_once(cfg: dict) -> dict:
    store = Store(cfg.get("state_dir", ".state"))
    results = []
    for api in cfg.get("apis", []):
        for src in api.get("sources", []):
            results.append(check_source(api["name"], src, store))
    counts = {s: sum(1 for r in results for c in r["changes"] if c.severity == s) for s in SEVERITIES}
    counts["errors"] = sum(1 for r in results if r["error"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": counts,
        "results": [{**r, "changes": [asdict(c) for c in r["changes"]]} for r in results],
    }
    return report


def save_report(cfg: dict, report: dict) -> Path:
    d = Path(cfg.get("reports_dir", "reports"))
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"report-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    p.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return p


def notify(cfg: dict, report: dict) -> None:
    n = cfg.get("notify") or {}
    url = _expand(n.get("webhook", ""))
    if not url or url.startswith("$"):
        return
    min_sev = n.get("min_severity", "breaking")
    if not any(report["summary"][s] for s in SEVERITIES[: SEVERITIES.index(min_sev) + 1]):
        return
    try:
        requests.post(url, json=report, timeout=15).raise_for_status()
    except requests.RequestException as e:
        print(f"[warn] webhook failed: {e}", file=sys.stderr)


def print_report(report: dict) -> None:
    s = report["summary"]
    print(f"\n== {report['generated_at']}  breaking={s['breaking']} warning={s['warning']} "
          f"info={s['info']} errors={s['errors']}")
    for r in report["results"]:
        print(f"[{r['status']:<9}] {r['api']} / {r['source']}" + (f"  !! {r['error']}" if r["error"] else ""))
        for c in sorted(r["changes"], key=lambda c: SEVERITIES.index(c["severity"])):
            print(f"    {c['severity'].upper():<8} {c['location']}: {c['message']}")


# --------------------------------------------------------------------------- CLI

def parse_interval(s: str) -> int:
    m = re.fullmatch(r"(\d+)\s*([smhd])", s.strip().lower())
    if not m:
        raise argparse.ArgumentTypeError("use e.g. 30m, 6h, 1d")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="API change detector")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="check all configured sources")
    r.add_argument("--config", default="apis.yaml")
    r.add_argument("--once", action="store_true", help="run a single pass (default if --every not given)")
    r.add_argument("--every", type=parse_interval, help="loop forever, e.g. 6h")
    r.add_argument("--json", action="store_true", help="print the JSON report instead of the table")

    d = sub.add_parser("diff", help="diff two OpenAPI files directly")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "diff":
        changes = diff_openapi("adhoc", parse_spec(fetch(args.old)), parse_spec(fetch(args.new)))
        if args.json:
            print(json.dumps([asdict(c) for c in changes], indent=2, default=str))
        else:
            for c in sorted(changes, key=lambda c: SEVERITIES.index(c.severity)):
                print(f"{c.severity.upper():<8} {c.location}: {c.message}")
        return 2 if any(c.severity == "breaking" for c in changes) else 0

    cfg = load_config(args.config)
    while True:
        report = run_once(cfg)
        path = save_report(cfg, report)
        notify(cfg, report)
        print(json.dumps(report, indent=2, default=str) if args.json else "", end="")
        if not args.json:
            print_report(report)
            print(f"report saved to {path}")
        if not args.every:
            return 2 if report["summary"]["breaking"] else 0
        try:
            time.sleep(args.every)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())