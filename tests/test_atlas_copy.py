"""The atlas copies: the never-store list and the registry's slugs, read without PyYAML and stamped."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.house import ROOT, lib
import atlas_copy

SAMPLE_NS = '''# header
paths:
  - "**/SubstrateSoulData/**"          # a comment
  - "**/.env"

content:
  - "-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
  - "(?i)aws_secret_access_key\\\\s*="
'''
SAMPLE_REG = '''version: 1
frameworks:
- slug: zeta
  name: Z
- slug: alpha
  name: A
  intent: '- slug: not-a-row'
'''


class Copy(unittest.TestCase):
    def test_never_store_parse(self):
        ns = atlas_copy.read_never_store(SAMPLE_NS)
        self.assertEqual(ns["paths"], ["**/SubstrateSoulData/**", "**/.env"])
        self.assertEqual(ns["content"][1], "(?i)aws_secret_access_key\\s*=")
        self.assertTrue(re.search(ns["content"][1], "AWS_SECRET_" + "ACCESS_KEY = x", re.I))

    def test_slug_parse(self):
        self.assertEqual(atlas_copy.read_slugs(SAMPLE_REG), ["alpha", "zeta"])

    def test_the_house_copies_are_well_formed(self):
        self.assertEqual(atlas_copy.well_formed(ROOT), [])
        for name in ("frameworks.json", "never-store.json"):
            doc = lib.read_json(ROOT / "catalog" / name)
            self.assertRegex(doc["atlas_commit"], r"^[0-9a-f]{7,40}$")

    def test_a_broken_copy_is_refused(self):
        root = Path(tempfile.mkdtemp(prefix="review-copy-"))
        shutil.copytree(ROOT / "catalog", root / "catalog")
        f = root / "catalog" / "frameworks.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        data["slugs"] = data["slugs"][::-1]
        f.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(atlas_copy.well_formed(root))


if __name__ == "__main__":
    unittest.main()
