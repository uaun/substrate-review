"""AP-all-0007 (atlas delivery): the reply writer learns not-applicable, which must name its item.

The atlas-reply contract gained the kind on DU's ruling (TODO-228, AT.534); the atlas records it and
confirms it at once (tools/atlasreply.py), so it is not one of WAITS. FALSIFIER: a not-applicable
reply with no item is written. CONTROLS: one naming its item is written; an unknown kind is refused.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("atlas_replies_ap7", ROOT / "house" / "atlas_replies.py")
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)
SHA = "a" * 40
RAW = "---\nid: AP-all-0006\n---\n# body\n"


def test_not_applicable_naming_its_item_is_written(tmp_path):
    reply, why = ar.write(tmp_path, "h", "AP-all-0006", "not-applicable", "no byte-exact vectors here", SHA, RAW, item="A3")
    assert why == "" and reply["kind"] == "not-applicable" and reply["item"] == "A3"
    assert [r["kind"] for r in ar.load(tmp_path)] == ["not-applicable"]
    assert "not-applicable" not in ar.WAITS


def test_falsifier_not_applicable_without_its_item_writes_nothing(tmp_path):
    reply, why = ar.write(tmp_path, "h", "AP-all-0006", "not-applicable", "no byte-exact vectors here", SHA, RAW)
    assert reply is None and "names the item" in why and ar.load(tmp_path) == []


def test_an_unknown_kind_is_still_refused(tmp_path):
    reply, why = ar.write(tmp_path, "h", "AP-all-0006", "maybe", "text", SHA, RAW, item="A1")
    assert reply is None and "not one of" in why and ar.load(tmp_path) == []
