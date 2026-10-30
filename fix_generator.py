"""Fix generator.

Takes the upstream API diff plus the affected code (from the impact scanner /
detector), asks a model on Nebius Token Factory for a fix, and returns a
unified-diff patch.

Design choice: the model does NOT write a unified diff. LLMs get hunk headers and
line numbers wrong constantly. Instead the model returns SEARCH/REPLACE edits,
we apply them to the real file contents, and we generate the unified diff
ourselves with difflib. If an edit doesn't match, or the result fails
validation, the error goes back to the model for another attempt.

Setup:
    pip install openai
    set NEBIUS_API_KEY=...        (Windows cmd)   /   export NEBIUS_API_KEY=...
    optional: FIX_MODEL=<model id>   (default below)
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

BASE_URL = "https://api.studio.nebius.com/v1/"
# NVIDIA open model on Token Factory. IDs are case-sensitive; if you get a
# "model not found" error, list the real ones with `python fix_generator.py --list-models`.
DEFAULT_MODEL = os.environ.get("FIX_MODEL", "nvidia/nemotron-3-super-120b-a12b")

MAX_ATTEMPTS = 3
WINDOW = 60              # lines of context kept around each flagged line
FULL_FILE_LIMIT = 24_000  # chars; larger files are sent as windows only


# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #
@dataclass
class AffectedFile:
    """One file the impact scanner says is hit by the API change."""
    path: str                                   # path relative to repo root
    content: str                                # full current file content
    lines: list[int] = field(default_factory=list)  # 1-based flagged lines


@dataclass
class FixResult:
    ok: bool
    patch: str                      # unified diff, "" if nothing to change
    summary: str                    # model's one-paragraph explanation
    attempts: int
    model: str
    errors: list[str] = field(default_factory=list)  # errors seen across attempts


# --------------------------------------------------------------------------- #
# Prompting
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """You are a code maintenance agent. An upstream API changed in a \
backwards-incompatible way. You are given the upstream diff and the files in \
the user's codebase that are affected. Make the smallest change that adapts \
the code to the new API while preserving behaviour.

Output format. For every edit emit exactly:

FILE: <path exactly as given>
<<<<<<< SEARCH
<lines copied verbatim from the current file>
=======
<replacement lines>
>>>>>>> REPLACE

Rules:
- SEARCH text must match the file exactly (whitespace included) and be unique
  in that file. Include enough surrounding lines to make it unique.
- Do not include line numbers in SEARCH or REPLACE.
- Only touch code that the API change requires. No refactors, no reformatting.
- Do not edit files that were not provided.
- Never switch to a different endpoint, URL or API version unless a listed change
  says that endpoint changed. Do not invent API details that are not in the change list.
- You may emit several edits per file.
- After the edits, write one paragraph starting with "SUMMARY:" explaining
  what changed and why.
- If nothing in the provided code needs to change, output only
  "NO_CHANGE_NEEDED" followed by a SUMMARY: line.
"""


def _numbered_view(f: AffectedFile) -> str:
    """Show the file with line numbers (for orientation only). Large files are windowed."""
    lines = f.content.splitlines()
    if len(f.content) <= FULL_FILE_LIMIT or not f.lines:
        keep = range(len(lines))
    else:
        keep_set: set[int] = set()
        for n in f.lines:
            keep_set.update(range(max(0, n - 1 - WINDOW), min(len(lines), n + WINDOW)))
        keep = sorted(keep_set)
    out, prev = [], None
    for i in keep:
        if prev is not None and i != prev + 1:
            out.append("   ...")
        mark = ">" if (i + 1) in f.lines else " "
        out.append(f"{mark}{i + 1:5d} | {lines[i]}")
        prev = i
    return "\n".join(out)


def build_user_prompt(change_diff: str, files: list[AffectedFile], note: str = "") -> str:
    parts = ["## Upstream API change (diff)\n```diff\n" + change_diff.strip() + "\n```"]
    if note:
        parts.append("## Context\n" + note.strip())
    parts.append(
        "## Affected files\n"
        "Line numbers are for orientation only; '>' marks lines the scanner flagged. "
        "Never put them in SEARCH/REPLACE blocks."
    )
    for f in files:
        parts.append(f"### {f.path}\n```\n{_numbered_view(f)}\n```")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Parsing and applying model edits
# --------------------------------------------------------------------------- #
_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_EDIT_RE = re.compile(
    r"^FILE:[ \t]*(?P<path>[^\n]+?)[ \t]*\n"
    r"<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)>>>>>>> REPLACE",
    re.S | re.M,
)
_SUMMARY_RE = re.compile(r"^SUMMARY:\s*(.*)\Z", re.S | re.M)


def _clean(text: str) -> str:
    text = _THINK_RE.sub("", text or "")
    # a stray unterminated <think> (model cut off) -> drop everything before the first FILE:
    if "<think>" in text.lower() and "FILE:" in text:
        text = text[text.index("FILE:"):]
    return text.strip()


def parse_response(text: str) -> tuple[list[tuple[str, str, str]], str, bool]:
    """Return (edits, summary, no_change). Each edit is (path, search, replace)."""
    text = _clean(text)
    edits = []
    for m in _EDIT_RE.finditer(text):
        replace = m.group("replace")
        if replace.endswith("\n"):
            replace = replace[:-1]
        edits.append((m.group("path").strip().strip("`"), m.group("search"), replace))
    sm = _SUMMARY_RE.search(text)
    summary = sm.group(1).strip() if sm else ""
    no_change = "NO_CHANGE_NEEDED" in text and not edits
    return edits, summary, no_change


class EditError(Exception):
    pass


def apply_edits(files: list[AffectedFile], edits: list[tuple[str, str, str]]) -> dict[str, str]:
    """Apply edits to copies of the files. Raises EditError with a message fit for the model."""
    working = {f.path: f.content for f in files}
    for path, search, replace in edits:
        if path not in working:
            raise EditError(
                f"Edit targets '{path}', which was not provided. "
                f"Provided files: {', '.join(working)}."
            )
        if not search.strip():
            raise EditError(f"Empty SEARCH block for {path}.")
        count = working[path].count(search)
        if count == 0:
            raise EditError(
                f"SEARCH block not found in {path} (must match exactly, including "
                f"indentation, with no line numbers). Block was:\n{search}"
            )
        if count > 1:
            raise EditError(
                f"SEARCH block matches {count} places in {path}; add surrounding "
                f"lines so it is unique. Block was:\n{search}"
            )
        working[path] = working[path].replace(search, replace, 1)
    return working


# --------------------------------------------------------------------------- #
# Patch building and validation
# --------------------------------------------------------------------------- #
def make_patch(files: list[AffectedFile], new_contents: dict[str, str]) -> str:
    chunks = []
    for f in files:
        new = new_contents[f.path]
        if new == f.content:
            continue
        old_lines = f.content.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines, fromfile=f"a/{f.path}", tofile=f"b/{f.path}"
        )
        out = []
        for line in diff:
            out.append(line)
            if not line.endswith("\n"):  # file without trailing newline
                out.append("\n\\ No newline at end of file\n")
        chunks.append("".join(out))
    return "".join(chunks)


SCOPE_SLACK = 2  # lines of tolerance around each flagged line


def out_of_scope(f: AffectedFile, new: str) -> list[int]:
    """Original line numbers the model changed that the scanner never flagged (+/- slack)."""
    if not f.lines:  # no flagged lines known -> no restriction
        return []
    ok = {n + d for n in f.lines for d in range(-SCOPE_SLACK, SCOPE_SLACK + 1)}
    old, nw = f.content.splitlines(), new.splitlines()
    bad = []
    for tag, i1, i2, _, _ in difflib.SequenceMatcher(None, old, nw, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if i2 > i1:  # replaced or deleted: every original line touched must be in scope
            bad += [n for n in range(i1 + 1, i2 + 1) if n not in ok]
        elif i1 not in ok and i1 + 1 not in ok:  # pure insert: check neighbours
            bad.append(i1 + 1)
    return bad


def validate(files: list[AffectedFile], new_contents: dict[str, str], patch: str) -> list[str]:
    """Cheap checks that catch most bad fixes. Returns a list of problems."""
    problems = []
    for f in files:
        bad = out_of_scope(f, new_contents[f.path])
        if bad:
            problems.append(
                f"{f.path}: you changed lines {bad} that the scanner did not flag. Only edit "
                f"lines marked '>' (at most {SCOPE_SLACK} lines away). Do not delete or rewrite "
                f"other code, and do not change URLs or API versions."
            )
    for path, text in new_contents.items():
        if path.endswith(".py"):
            try:
                ast.parse(text)
            except SyntaxError as e:
                problems.append(f"{path}: Python syntax error after edit: {e.msg} (line {e.lineno})")
        elif path.endswith(".json"):
            try:
                json.loads(text)
            except ValueError as e:
                problems.append(f"{path}: invalid JSON after edit: {e}")
    if patch and not problems and shutil.which("git"):
        with tempfile.TemporaryDirectory() as tmp:
            for f in files:
                p = Path(tmp, f.path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(f.content.encode())
            patch_file = Path(tmp, "_fix.patch")
            patch_file.write_bytes(patch.encode())
            r = subprocess.run(
                ["git", "apply", "--check", "--unsafe-paths", "_fix.patch"],
                cwd=tmp, capture_output=True, text=True,
            )
            if r.returncode != 0:
                problems.append(f"git apply --check failed: {r.stderr.strip()}")
    return problems


# --------------------------------------------------------------------------- #
# Model call + retry loop
# --------------------------------------------------------------------------- #
def make_client():
    from openai import OpenAI  # imported lazily so tests run without the package

    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("NEBIUS_API_KEY is not set")
    return OpenAI(base_url=BASE_URL, api_key=key)


def generate_fix(
    change_diff: str,
    files: list[AffectedFile],
    note: str = "",
    client=None,
    model: str = DEFAULT_MODEL,
    max_attempts: int = MAX_ATTEMPTS,
    check=None,  # optional: patch -> None if OK, else an error string (e.g. the repo's test output)
) -> FixResult:
    client = client or make_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(change_diff, files, note)},
    ]
    errors: list[str] = []

    for attempt in range(1, max_attempts + 1):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=8192,
        )
        raw = resp.choices[0].message.content or ""
        edits, summary, no_change = parse_response(raw)

        if no_change:
            return FixResult(True, "", summary, attempt, model, errors)

        problem = None
        if not edits:
            problem = (
                "No valid edit blocks found. Use the exact FILE: / <<<<<<< SEARCH / "
                "======= / >>>>>>> REPLACE format, or reply NO_CHANGE_NEEDED."
            )
        else:
            try:
                new_contents = apply_edits(files, edits)
                patch = make_patch(files, new_contents)
                issues = validate(files, new_contents, patch)
                if issues:
                    problem = "The edits applied but the result is invalid:\n" + "\n".join(issues)
                else:
                    failure = check(patch) if check else None
                    if not failure:
                        return FixResult(True, patch, summary, attempt, model, errors)
                    problem = failure  # fed back to the model like any other error
            except EditError as e:
                problem = str(e)

        errors.append(f"attempt {attempt}: {problem}")
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": f"That attempt failed.\n\n{problem}\n\nResend ALL edits, corrected, "
                       f"in the same format.",
        })

    return FixResult(False, "", "", max_attempts, model, errors)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_file_arg(arg: str) -> AffectedFile:
    """path or path:12,40 (flagged lines)."""
    path, _, lines = arg.partition(":")
    flagged = [int(x) for x in lines.split(",") if x.strip()] if lines and not lines.startswith(("\\", "/")) else []
    return AffectedFile(path=path, content=Path(path).read_text(encoding="utf-8"), lines=flagged)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a patch for an API breaking change.")
    ap.add_argument("--diff", help="file containing the upstream API diff")
    ap.add_argument("--file", action="append", default=[], help="affected file, optionally path:12,40")
    ap.add_argument("--note", default="", help="extra context for the model")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", help="write patch here instead of stdout")
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args()

    if args.list_models:
        for m in make_client().models.list():
            print(m.id)
        return 0
    if not args.diff or not args.file:
        ap.error("--diff and at least one --file are required")

    files = [_parse_file_arg(a) for a in args.file]
    result = generate_fix(Path(args.diff).read_text(encoding="utf-8"), files, args.note, model=args.model)

    for e in result.errors:
        print(e, file=sys.stderr)
    if not result.ok:
        print(f"Failed after {result.attempts} attempts.", file=sys.stderr)
        return 1
    print(f"[{result.model}] {result.summary}", file=sys.stderr)
    if args.out:
        Path(args.out).write_text(result.patch, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(result.patch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
