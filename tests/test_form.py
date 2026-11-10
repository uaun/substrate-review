"""The intake form (A4): generated from the registry's slugs, REVIEW's seven fields in order."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.house import ROOT, lib
import form


def copy_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="review-form-"))
    shutil.copytree(ROOT / "catalog", root / "catalog")
    (root / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
    shutil.copy(ROOT / form.FORM, root / form.FORM)
    return root


class Form(unittest.TestCase):
    def test_the_house_form_is_its_generation(self):
        self.assertEqual(form.check(ROOT), [])

    def test_options_are_the_registry_slugs(self):
        text = (ROOT / form.FORM).read_text(encoding="utf-8")
        options = [json.loads(m) for m in re.findall(r"^        - (\".*\")$", text, re.M)]
        self.assertEqual(options, lib.slugs(ROOT))
        self.assertIn("review", options)

    def test_every_field_is_required(self):
        text = (ROOT / form.FORM).read_text(encoding="utf-8")
        self.assertEqual(text.count("required: true"), len(lib.FIELDS))

    def test_a_hand_edit_is_refused(self):
        root = copy_root()
        p = root / form.FORM
        p.write_text(p.read_text(encoding="utf-8").replace('- "review"', '- "reviews"'), encoding="utf-8")
        self.assertTrue(any("differs" in x for x in form.check(root)))

    def test_a_new_slug_needs_a_regeneration(self):
        root = copy_root()
        f = root / "catalog" / "frameworks.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        data["slugs"] = sorted(data["slugs"] + ["zzz-new"])
        f.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(form.check(root))

    def test_fields_out_of_order_are_refused(self):
        # a generator that put the fields out of REVIEW's order would pass the equality check; the order check
        # must still refuse it
        root = copy_root()
        real = form.generate(root)
        swapped = real.replace('label: "Why"', 'label: "TMP"').replace('label: "The change"', 'label: "Why"') \
                      .replace('label: "TMP"', 'label: "The change"')
        (root / form.FORM).write_text(swapped, encoding="utf-8")
        with mock.patch.object(form, "generate", lambda r=None: swapped):
            self.assertTrue(any("REVIEW's seven" in x for x in form.check(root)))

    def test_blank_issues_are_off(self):
        self.assertIn("blank_issues_enabled: false", (ROOT / ".github/ISSUE_TEMPLATE/config.yml").read_text())


if __name__ == "__main__":
    unittest.main()
