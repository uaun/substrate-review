"""The workflows: the issue's text never reaches a shell, permissions are named, and the checks run."""
from __future__ import annotations

import re
import unittest

from tests.house import ROOT

WF = ROOT / ".github" / "workflows"


class Workflows(unittest.TestCase):
    def test_no_issue_text_in_any_expression(self):
        for f in WF.glob("*.yml"):
            text = f.read_text(encoding="utf-8")
            for expr in re.findall(r"\$\{\{(.*?)\}\}", text):
                self.assertNotRegex(expr, r"issue\.(title|body)|comment\.body|head_ref|\.login", f"{f.name}: {expr}")

    def test_permissions_are_named(self):
        for f in WF.glob("*.yml"):
            self.assertRegex(f.read_text(encoding="utf-8"), r"(?m)^permissions:\n  contents: read", f.name)

    def test_intake_reads_the_author_first(self):
        text = (WF / "intake.yml").read_text(encoding="utf-8")
        self.assertIn("tools/intake.py event", text)
        self.assertIn("issues: write", text)
        self.assertIn("persist-credentials: false", text)

    def test_verify_runs_the_house_check(self):
        text = (WF / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("bash tools/check.sh", text)
        self.assertIn("pull_request:", text)


if __name__ == "__main__":
    unittest.main()
