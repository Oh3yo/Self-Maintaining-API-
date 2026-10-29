#!/usr/bin/env python3
"""Impact scanner: find code in a target repo that uses changed API endpoints/fields.

Input  : changes.json  (output of the drift detector, see CHANGE FORMAT)
Output : impact_report.json + a readable summary on stdout

CHANGE FORMAT (list of objects):
  {"kind": "endpoint_removed" | "endpoint_changed" | "field_removed" | "field_renamed" | "field_type_changed",
   "method": "GET",              # optional, endpoints
   "path": "/v1/users/{id}",     # endpoints (and optionally fields, to boost confidence)
   "schema": "User",             # optional, fields
   "field": "email",             # fields
   "new_name": "email_address"}  # optional, renames

Strategy:
  * Endpoints -> regex over every source file (path templates show up as {id}, :id, ${id}, <id>, f-strings...)
  * Fields    -> Python: real AST (attribute access, ["key"], .get("key"), kwargs, dict keys)
                 other languages: regex fallback
  * Every hit gets a confidence score; field hits are boosted when the same file also touches
    the schema name or one of the changed endpoints (bare field names like `id` are noisy).
"""
import argparse, ast, json, os, re, sys
from collections import defaultdict
from dataclasses import dataclass, asdict

SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".next", "vendor", "target"}
EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".go", ".java", ".kt", ".rb", ".php", ".cs", ".rs", ".swift"}
MAX_BYTES = 1_000_000
HTTP_WORDS = ("get", "post", "put", "patch", "delete", "head", "options")

# one path parameter in any common templating style
PARAM = r"(?:\{[^}/]*\}|\$\{[^}]*\}|:\w+|<[^>/]*>|[\w.\-~%]+)"


@dataclass
class Hit:
    change_id: int
    file: str
    line: int
    kind: str          # endpoint_ref | field_access | field_key | field_kwarg | field_regex
    confidence: float
    snippet: str


def path_regex(path, strip_version=False):
    if strip_version:
        path = re.sub(r"^/v\d+(?=/)", "", path)
    segs = [s for s in path.strip("/").split("/") if s]
    parts = []
    for s in segs:
        if re.fullmatch(r"\{[^}]*\}|:\w+|<[^>]*>", s):
            parts.append(PARAM)
        else:
            parts.append(re.escape(s))
    return re.compile(r"(?<![\w/.\-])/?" + "/".join(parts) + r"(?![\w\-])")


def iter_files(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if os.path.splitext(fn)[1] in EXTS:
                p = os.path.join(dp, fn)
                try:
                    if os.path.getsize(p) <= MAX_BYTES:
                        yield p
                except OSError:
                    pass


def read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def method_nearby(lines, i, method):
    if not method:
        return False
    window = "\n".join(lines[max(0, i - 2): i + 3]).lower()
    m = method.lower()
    return bool(re.search(rf"[.\"'`\s]{m}\b|method\W+{m}\b|@\w*{m}\b", window))


def scan_endpoint(cid, ch, rel, lines):
    hits = []
    full = path_regex(ch["path"])
    bare = path_regex(ch["path"], strip_version=True) if re.match(r"^/v\d+/", ch["path"]) else None
    for i, line in enumerate(lines):
        base = 0.0
        if full.search(line):
            base = 0.8
        elif bare and bare.search(line):
            base = 0.6   # version prefix often lives in a base-URL constant
        if base:
            if method_nearby(lines, i, ch.get("method")):
                base = min(1.0, base + 0.15)
            hits.append(Hit(cid, rel, i + 1, "endpoint_ref", round(base, 2), line.strip()[:200]))
    return hits


class PyFieldVisitor(ast.NodeVisitor):
    def __init__(self, field):
        self.field, self.found = field, []

    def _add(self, node, kind):
        self.found.append((node.lineno, kind))

    def visit_Attribute(self, n):
        if n.attr == self.field:
            self._add(n, "field_access")
        self.generic_visit(n)

    def visit_Subscript(self, n):
        s = n.slice
        if isinstance(s, ast.Constant) and s.value == self.field:
            self._add(n, "field_key")
        self.generic_visit(n)

    def visit_Call(self, n):
        # d.get("email"), getattr(o, "email"), Model(email=...)
        if (isinstance(n.func, ast.Attribute) and n.func.attr in ("get", "pop", "setdefault")
                and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == self.field):
            self._add(n, "field_key")
        if (isinstance(n.func, ast.Name) and n.func.id in ("getattr", "hasattr", "setattr")
                and len(n.args) > 1 and isinstance(n.args[1], ast.Constant) and n.args[1].value == self.field):
            self._add(n, "field_access")
        for kw in n.keywords:
            if kw.arg == self.field:
                self._add(kw.value, "field_kwarg")
        self.generic_visit(n)

    def visit_Dict(self, n):
        for k in n.keys:
            if isinstance(k, ast.Constant) and k.value == self.field:
                self._add(k, "field_key")
        self.generic_visit(n)


def scan_field_py(cid, ch, rel, src, lines, context_boost):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return scan_field_regex(cid, ch, rel, lines, context_boost)
    v = PyFieldVisitor(ch["field"])
    v.visit(tree)
    out, seen = [], set()
    for ln, kind in v.found:
        if (ln, kind) in seen:
            continue
        seen.add((ln, kind))
        conf = 0.45 + (0.4 if context_boost else 0)
        out.append(Hit(cid, rel, ln, kind, round(min(conf, 0.95), 2), lines[ln - 1].strip()[:200]))
    return out


def scan_field_regex(cid, ch, rel, lines, context_boost):
    f = re.escape(ch["field"])
    pat = re.compile(rf"\.{f}\b|[\"'`]{f}[\"'`]|[{{,]\s*{f}\s*[,}}:]|\b{f}\s*:")
    out = []
    for i, line in enumerate(lines):
        if pat.search(line):
            conf = 0.35 + (0.4 if context_boost else 0)
            out.append(Hit(cid, rel, i + 1, "field_regex", round(min(conf, 0.9), 2), line.strip()[:200]))
    return out


def scan(repo, changes, min_conf=0.0):
    ep_changes = [(i, c) for i, c in enumerate(changes) if c.get("path") and not c.get("field")]
    fld_changes = [(i, c) for i, c in enumerate(changes) if c.get("field")]
    all_paths = [path_regex(c["path"]) for _, c in ep_changes]
    hits = []
    for p in iter_files(repo):
        rel = os.path.relpath(p, repo)
        src = read(p)
        lines = src.splitlines()
        for cid, ch in ep_changes:
            hits += scan_endpoint(cid, ch, rel, lines)
        if fld_changes:
            touches_endpoint = any(rx.search(src) for rx in all_paths)
            for cid, ch in fld_changes:
                schema = ch.get("schema")
                boost = touches_endpoint or bool(schema and re.search(rf"\b{re.escape(schema)}\b", src))
                if p.endswith(".py"):
                    hits += scan_field_py(cid, ch, rel, src, lines, boost)
                else:
                    hits += scan_field_regex(cid, ch, rel, lines, boost)
    return [h for h in hits if h.confidence >= min_conf]


def build_report(repo, changes, hits):
    by_change = defaultdict(list)
    for h in hits:
        by_change[h.change_id].append(h)
    items = []
    for cid, ch in enumerate(changes):
        hs = sorted(by_change.get(cid, []), key=lambda h: (-h.confidence, h.file, h.line))
        items.append({"change": ch, "hit_count": len(hs),
                      "files": sorted({h.file for h in hs}), "hits": [asdict(h) for h in hs]})
    return {"repo": os.path.abspath(repo), "changes": items,
            "affected_files": sorted({h.file for h in hits})}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("changes", help="changes.json from the detector")
    ap.add_argument("-o", "--out", default="impact_report.json")
    ap.add_argument("--min-confidence", type=float, default=0.3)
    a = ap.parse_args()

    with open(a.changes, encoding="utf-8") as f:
        changes = json.load(f)
    hits = scan(a.repo, changes, a.min_confidence)
    rep = build_report(a.repo, changes, hits)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)

    for it in rep["changes"]:
        c = it["change"]
        label = f'{c.get("method", "")} {c["path"]}'.strip() if c.get("path") and not c.get("field") \
            else f'{c.get("schema", "?")}.{c["field"]}'
        print(f'\n[{c["kind"]}] {label}  ->  {it["hit_count"]} hit(s) in {len(it["files"])} file(s)')
        for h in it["hits"][:10]:
            print(f'  {h["confidence"]:.2f}  {h["file"]}:{h["line"]}  {h["snippet"]}')
    print(f'\nReport written to {a.out}')


if __name__ == "__main__":
    sys.exit(main())
