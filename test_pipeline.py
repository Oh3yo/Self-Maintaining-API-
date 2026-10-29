"""pipeline.py end to end with a fake model (no network)."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import sys

from dataclasses import asdict

from fix_generator import AffectedFile, make_patch
from pipeline import _auth_url, check_patch, from_detector, make_check, open_pr, run

HERE = Path(__file__).parent
REPLY = """FILE: client.py
<<<<<<< SEARCH
    return user["email"]
=======
    return user["email_address"]
>>>>>>> REPLACE

SUMMARY: field email was renamed to email_address.
"""


class Fake:
    def __init__(self):
        self.prompts = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.prompts.append(kw["messages"][1]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=REPLY))])


class T(unittest.TestCase):
    def test_scan_to_patch(self):
        changes = json.loads((HERE / "changes.json").read_text())
        fake = Fake()
        r = run(HERE / "demo_repo", changes, client=fake)
        self.assertTrue(r.ok)
        self.assertIn('+    return user["email_address"]', r.patch)
        self.assertIn("a/client.py", r.patch)
        # the scanner's flagged line (the ["email"] access, line 13) reached the prompt
        self.assertIn(">   13 |     return user[\"email\"]", fake.prompts[0])
        # the prompt must not claim the endpoint was removed (a real model once acted on that)
        self.assertIn('renamed to "email_address"', fake.prompts[0])
        self.assertNotIn("removed", fake.prompts[0].split("## Context")[0])

    def test_open_pr_branches_commits_pushes(self):
        env = dict(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        os.environ.update(env)
        with tempfile.TemporaryDirectory() as d:
            origin, work = Path(d, "origin.git"), Path(d, "work")
            subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
            shutil.copytree(HERE / "demo_repo", work)
            for c in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "init"],
                      ["remote", "add", "origin", str(origin)], ["push", "-q", "origin", "main"]):
                subprocess.run(["git", "-C", str(work), *c], check=True)
            changes = json.loads((HERE / "changes.json").read_text())
            r = run(work, changes, client=Fake())
            Path(d, "fix.patch").write_text(r.patch, newline="\n")
            seen = {}
            url = open_pr(work, Path(d, "fix.patch"), r, changes,
                          create=lambda *a: seen.update(zip("remote title head base body".split(), a)) or "http://pr/1")
            self.assertEqual(url, "http://pr/1")
            self.assertEqual(seen["base"], "main")
            self.assertTrue(seen["head"].startswith("api-fix/"))
            self.assertIn("renamed", seen["body"])
            pushed = subprocess.run(["git", "-C", str(origin), "show", f'{seen["head"]}:client.py'],
                                    capture_output=True, text=True, check=True).stdout
            self.assertIn('user["email_address"]', pushed)

    def test_auth_url_only_rewrites_github_https(self):
        self.assertEqual(_auth_url("https://github.com/o/r.git", "T"),
                         "https://x-access-token:T@github.com/o/r.git")
        self.assertEqual(_auth_url("/tmp/origin.git", "T"), "/tmp/origin.git")
        self.assertEqual(_auth_url("https://github.com/o/r.git", None), "https://github.com/o/r.git")

    def test_validator_pass_fail_preexisting(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.py").write_text("x = 1\n")
            f = [AffectedFile("a.py", "x = 1\n", [1])]
            good = make_patch(f, {"a.py": "x = 2\n"})
            bad = make_patch(f, {"a.py": "x = (\n"})
            self.assertEqual(check_patch(d, good)[0], "pass")
            self.assertEqual(check_patch(d, bad)[0], "fail")
            self.assertEqual(Path(d, "a.py").read_text(), "x = 1\n")  # real copy untouched
            self.assertIn("now fail", make_check(d)(bad))
            self.assertIsNone(make_check(d)(good))
            always_fail = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
            self.assertEqual(check_patch(d, good, always_fail)[0], "preexisting")  # not the patch's fault

    def test_run_with_validator_on_demo_repo(self):
        log = {}
        changes = json.loads((HERE / "changes.json").read_text())
        r = run(HERE / "demo_repo", changes, client=Fake(), check=make_check(HERE / "demo_repo", None, log))
        self.assertTrue(r.ok)
        self.assertEqual(log["status"], "pass")

    def test_detector_rename_to_fix(self):
        """The real detector's output (not hand-written JSON) drives scanner + generator."""
        import detector

        def spec(email):
            user = {"type": "object", "properties": {"id": {"type": "integer"}, email: {"type": "string"}}}
            return {"openapi": "3.0.3", "info": {"title": "t", "version": "1"}, "paths": {"/v1/users/{id}": {
                "get": {"responses": {"200": {"description": "ok", "content": {"application/json": {"schema": user}}}}}}}}

        report = [asdict(c) for c in detector.diff_openapi("x", spec("email"), spec("email_address"))]
        changes = from_detector(report)
        self.assertEqual(changes, [{"kind": "field_renamed", "field": "email", "new_name": "email_address",
                                    "method": "GET", "path": "/v1/users/{id}"}])
        r = run(HERE / "demo_repo", changes, client=Fake())
        self.assertTrue(r.ok)
        self.assertIn('+    return user["email_address"]', r.patch)

    def test_from_detector_kinds(self):
        def ch(kind, sev, loc, msg="m"):
            return {"kind": kind, "severity": sev, "location": loc, "message": msg}

        body = "[application/json]"
        got = from_detector({"results": [{"changes": [
            ch("operation_removed", "breaking", "DELETE /users/{id}"),
            ch("path_removed", "breaking", "/old"),
            ch("property_removed", "breaking", f"GET /u response 200{body}.a"),
            ch("type_changed", "breaking", f"GET /u response 200{body}.id"),
            ch("type_changed", "breaking", f"GET /u response 200{body}.friends[].id"),  # same field again: deduped
            ch("required_property_added", "breaking", f"POST /u requestBody{body}.name", "new required"),
            ch("property_removed", "warning", f"POST /u requestBody{body}.x"),  # below 'breaking': skipped
            ch("spec_version_changed", "info", "info.version"),
            ch("sdk_major_bump", "breaking", "sdk"),
            {"kind": "field_removed", "field": "z"},  # already scanner format: passed through
        ]}]})
        self.assertEqual(got, [
            {"kind": "field_removed", "field": "z"},
            {"kind": "endpoint_removed", "method": "DELETE", "path": "/users/{id}"},
            {"kind": "endpoint_removed", "path": "/old"},
            {"kind": "field_removed", "field": "a", "method": "GET", "path": "/u"},
            {"kind": "field_type_changed", "field": "id", "method": "GET", "path": "/u"},
            {"kind": "endpoint_changed", "method": "POST", "path": "/u", "in": "request",
             "detail": f"new required (POST /u requestBody{body}.name)"},
        ])
        # two removals + one addition is not a rename
        amb = from_detector([ch("property_removed", "breaking", f"GET /p response 200{body}.a"),
                             ch("property_removed", "breaking", f"GET /p response 200{body}.b"),
                             ch("property_added", "info", f"GET /p response 200{body}.c")])
        self.assertEqual([c["kind"] for c in amb], ["field_removed", "field_removed"])

    def test_no_hits_returns_none(self):
        other = [{"kind": "field_removed", "schema": "X", "field": "zzz_nothing"}]
        self.assertIsNone(run(HERE / "demo_repo", other, client=Fake()))


if __name__ == "__main__":
    unittest.main()
