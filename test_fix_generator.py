"""Tests for fix_generator using a fake model client (no network, no API key)."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fix_generator import AffectedFile, generate_fix, parse_response

DIFF = """\
--- a/payments.py
+++ b/payments.py
-def charge(amount, currency):
+def charge(amount_cents, currency, *, idempotency_key):
"""

CODE = """\
import payments


def checkout(cart):
    total = sum(i.price for i in cart)
    return payments.charge(total, "USD")
"""

GOOD = """\
FILE: app.py
<<<<<<< SEARCH
    return payments.charge(total, "USD")
=======
    return payments.charge(int(total * 100), "USD", idempotency_key=str(id(cart)))
>>>>>>> REPLACE

SUMMARY: charge() now takes cents and requires an idempotency key.
"""


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        msg = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def files():
    return [AffectedFile("app.py", CODE, [6])]


class Tests(unittest.TestCase):
    def test_happy_path_and_patch_applies(self):
        r = generate_fix(DIFF, files(), client=FakeClient([GOOD]))
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 1)
        self.assertIn("+    return payments.charge(int(total * 100)", r.patch)
        with tempfile.TemporaryDirectory() as d:
            Path(d, "app.py").write_text(CODE)
            Path(d, "x.patch").write_text(r.patch)
            subprocess.run(["git", "apply", "x.patch"], cwd=d, check=True)
            self.assertIn("idempotency_key", Path(d, "app.py").read_text())

    def test_think_block_is_stripped(self):
        r = generate_fix(DIFF, files(), client=FakeClient(["<think>hmm FILE: nope</think>\n" + GOOD]))
        self.assertTrue(r.ok)

    def test_retry_when_search_does_not_match(self):
        bad = GOOD.replace("payments.charge(total", "payments.charge(totl")
        c = FakeClient([bad, GOOD])
        r = generate_fix(DIFF, files(), client=c)
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)
        self.assertIn("not found", r.errors[0])
        # the error was fed back to the model
        self.assertIn("not found", c.calls[1]["messages"][-1]["content"])

    def test_retry_on_syntax_error(self):
        broken = GOOD.replace('"USD", idempotency_key=str(id(cart)))', '"USD", idempotency_key=')
        r = generate_fix(DIFF, files(), client=FakeClient([broken, GOOD]))
        self.assertTrue(r.ok)
        self.assertIn("syntax error", r.errors[0])

    def test_gives_up_after_max_attempts(self):
        r = generate_fix(DIFF, files(), client=FakeClient(["no idea"] * 3))
        self.assertFalse(r.ok)
        self.assertEqual(len(r.errors), 3)

    def test_no_change_needed(self):
        r = generate_fix(DIFF, files(), client=FakeClient(["NO_CHANGE_NEEDED\nSUMMARY: not used."]))
        self.assertTrue(r.ok)
        self.assertEqual(r.patch, "")

    def test_ambiguous_search_rejected(self):
        f = [AffectedFile("app.py", "x = 1\nx = 1\n")]
        reply = "FILE: app.py\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n"
        r = generate_fix(DIFF, f, client=FakeClient([reply, reply, reply]))
        self.assertFalse(r.ok)
        self.assertIn("matches 2", r.errors[0])

    def test_rejects_edits_outside_flagged_lines(self):
        code = "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n"
        f = [AffectedFile("x.py", code, [9])]
        wrong = "FILE: x.py\n<<<<<<< SEARCH\nb\n=======\n>>>>>>> REPLACE\n"   # line 2, not flagged
        right = "FILE: x.py\n<<<<<<< SEARCH\ni\n=======\ni = 1\n>>>>>>> REPLACE\n"
        r = generate_fix(DIFF, f, client=FakeClient([wrong, right]))
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)
        self.assertIn("did not flag", r.errors[0])

    def test_deleting_whole_functions_is_rejected(self):
        f = [AffectedFile("c.py", "import r\n\n\ndef g():\n    return 1\n\n\ndef u():\n    return g()['email']\n", [9])]
        nuke = ("FILE: c.py\n<<<<<<< SEARCH\ndef g():\n    return 1\n\n\ndef u():\n"
                "    return g()['email']\n=======\n>>>>>>> REPLACE\n")
        r = generate_fix(DIFF, f, client=FakeClient([nuke] * 3))
        self.assertFalse(r.ok)

    def test_failing_check_triggers_retry(self):
        calls = []

        def check(patch):
            calls.append(patch)
            return "tests failed: boom" if len(calls) == 1 else None

        c = FakeClient([GOOD, GOOD])
        r = generate_fix(DIFF, files(), client=c, check=check)
        self.assertTrue(r.ok)
        self.assertEqual(r.attempts, 2)
        self.assertIn("boom", c.calls[1]["messages"][-1]["content"])  # failure text went back to the model

    def test_empty_replace_deletes_lines(self):
        edits, _, _ = parse_response("FILE: a.py\n<<<<<<< SEARCH\nold\n=======\n>>>>>>> REPLACE\n")
        self.assertEqual(edits, [("a.py", "old", "")])


if __name__ == "__main__":
    unittest.main()
