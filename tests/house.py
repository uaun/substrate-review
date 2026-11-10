"""Shared helpers for the house's tests: a scratch catalog, and a proposal body as GitHub renders an issue form."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import lib  # noqa: E402

ACCOUNT = 4242   # an invented account id, allowlisted only inside a scratch catalog


def scratch(allow=(ACCOUNT,)) -> Path:
    """A temporary root holding a copy of the house's catalog, its allowlist replaced."""
    root = Path(tempfile.mkdtemp(prefix="review-test-"))
    shutil.copytree(ROOT / "catalog", root / "catalog")
    for f in (root / "catalog" / "proposals").glob("*.json"):
        f.unlink()
    (root / "catalog" / "events.jsonl").write_text("", encoding="utf-8")
    (root / "catalog" / "allowlist.json").write_text(
        json.dumps({"accounts": [{"id": a, "since": "2026-11-10"} for a in allow]}), encoding="utf-8")
    return root


def body(**over) -> str:
    """A complete proposal body in GitHub's rendering; a field set to None is left out, its heading too."""
    fields = {
        "title": "Name the reading's atlas commit in the verdict line",
        "frameworks": "review, atlas",
        "change": "The verdict line names the atlas commit the reading was made at.",
        "why": "A contributor can then see which rulings the reading saw.",
        "must-not-break": "The reading stays provisional; nothing here binds.",
        "evidence": "none",
        "consent": f"- [X] {lib.CONSENT}",
    }
    fields.update(over)
    out = []
    for fid, label in lib.FIELDS:
        if fields.get(fid) is None:
            continue
        out += [f"### {label}", "", fields[fid], ""]
    return "\n".join(out)
