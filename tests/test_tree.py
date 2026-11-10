"""The tree guard: no tracked path under a never-store glob, no tracked text carrying a never-store pattern."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.house import ROOT
import intake


def repo(files: dict) -> Path:
    root = Path(tempfile.mkdtemp(prefix="review-tree-"))
    shutil.copytree(ROOT / "catalog", root / "catalog")
    shutil.copy(ROOT / ".gitignore", root / ".gitignore")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A", "-f"], check=True)
    return root


class Tree(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(intake.tree(repo({"notes.md": "SubstrateSoulData/ is a category; naming it is fine.\n"})), [])

    def test_a_never_store_path_is_refused(self):
        found = intake.tree(repo({"x/SubstrateSoulData/f.json": "{}\n"}))
        self.assertTrue(any("never-store glob" in p for p in found))

    def test_never_store_content_is_refused(self):
        key = "-----BEGIN " + "PRIVATE KEY-----"
        found = intake.tree(repo({"notes.md": f"{key}\nabc\n"}))
        self.assertTrue(any("content pattern" in p for p in found))

    def test_gitignore_mirrors_never_store(self):
        root = repo({})
        lines = (root / ".gitignore").read_text(encoding="utf-8").replace("transcripts/\n", "")
        (root / ".gitignore").write_text(lines, encoding="utf-8")
        self.assertTrue(any("does not mirror" in p and "transcripts" in p for p in intake.tree(root)))

    def test_the_house_tree_is_clean(self):
        self.assertEqual(intake.tree(ROOT), [])


if __name__ == "__main__":
    unittest.main()
