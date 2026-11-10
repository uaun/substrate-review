"""The catalog's checks (A3): each refuses the thing it exists to refuse, planted once."""
from __future__ import annotations

import json
import unittest

from tests.house import ACCOUNT, body, scratch, lib  # noqa: F401
import catalog
import intake


def proposal(root, pid="RV-0001"):
    return json.loads((root / "catalog" / "proposals" / f"{pid}.json").read_text(encoding="utf-8"))


def write(root, p):
    (root / "catalog" / "proposals" / f"{p['id']}.json").write_text(json.dumps(p), encoding="utf-8")


def log_lines(root):
    return (root / "catalog" / "events.jsonl").read_text(encoding="utf-8").splitlines()


class Catalog(unittest.TestCase):
    def setUp(self):
        self.root = scratch()

    def test_the_house_catalog_is_clean(self):
        self.assertEqual(catalog.check(lib.ROOT), [])

    def test_empty_scratch_is_clean(self):
        self.assertEqual(catalog.check(self.root), [])

    def test_received_then_refused_on_a_missing_field(self):
        # R1's own done-when: a test proposal goes from received to refused on a missing field
        p = intake.receive(body(why=lib.NO_RESPONSE), ACCOUNT, 7, self.root)
        self.assertEqual((p["id"], p["state"], p["checks"]), ("RV-0001", "refused", ["missing-field"]))
        events = [json.loads(l) for l in log_lines(self.root)]
        self.assertEqual([(e["from"], e["to"]) for e in events], [(None, "received"), ("received", "refused")])
        self.assertEqual(catalog.check(self.root), [])

    def test_a_complete_proposal_stays_received(self):
        p = intake.receive(body(), ACCOUNT, None, self.root)
        self.assertEqual((p["state"], p["frameworks"]), ("received", ["review", "atlas"]))
        self.assertEqual(catalog.check(self.root), [])

    def test_duplicate_event_id_is_refused(self):
        intake.receive(body(), ACCOUNT, None, self.root)
        line = log_lines(self.root)[0]
        with open(self.root / "catalog" / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")      # what a union merge of two branches leaves
        self.assertTrue(any("appears twice" in p for p in catalog.check(self.root)))

    def test_a_file_off_its_shape_is_refused(self):
        for change, says in (({"extra": 1}, "keys differ"), ({"state": "approved"}, "is not one of"),
                             ({"account": "a-name"}, "account is not"), ({"frameworks": ["nowhere"]}, "frameworks is not")):
            root = scratch()
            intake.receive(body(), ACCOUNT, None, root)
            write(root, {**proposal(root), **change})
            self.assertTrue(any(says in x for x in catalog.check(root)), f"{change} passed")
        root = scratch()
        intake.receive(body(), ACCOUNT, None, root)
        p = proposal(root)
        del p["marks"]
        write(root, p)
        self.assertTrue(any("keys differ" in x for x in catalog.check(root)))

    def test_an_edited_text_is_refused(self):
        intake.receive(body(), ACCOUNT, None, self.root)
        p = proposal(self.root)
        p["text"]["change"] = "something else"
        write(self.root, p)
        self.assertTrue(any("never edited" in x for x in catalog.check(self.root)))

    def test_an_illegal_transition_is_refused(self):
        intake.receive(body(), ACCOUNT, None, self.root)
        catalog.append_event(self.root, {"id": "RV-0001/2", "proposal": "RV-0001", "from": "received",
                                         "to": "ruled", "day": "2026-11-10"})
        self.assertTrue(any("cannot go from" in x for x in catalog.check(self.root)))
        with self.assertRaises(ValueError):
            catalog.move(self.root, "RV-0001", "contested")

    def test_file_state_must_match_the_log(self):
        intake.receive(body(), ACCOUNT, None, self.root)
        p = proposal(self.root)
        p["state"] = "read"
        write(self.root, p)
        self.assertTrue(any("last event reads" in x for x in catalog.check(self.root)))

    def test_refused_must_name_a_check(self):
        intake.receive(body(), ACCOUNT, None, self.root)
        p = proposal(self.root)
        p["state"] = "refused"
        write(self.root, p)
        self.assertTrue(any("no check named" in x for x in catalog.check(self.root)))

    def test_allowlist_takes_ids_not_names(self):
        (self.root / "catalog" / "allowlist.json").write_text(json.dumps({"accounts": [{"id": "someone"}]}))
        self.assertTrue(any("allowlist" in x for x in catalog.check(self.root)))

    def test_the_house_allowlist_is_empty(self):
        # RV.2 (AT.716): no contributor can be verified until soul marks exist
        self.assertEqual(lib.read_json(lib.ROOT / "catalog" / "allowlist.json"), {"accounts": []})


if __name__ == "__main__":
    unittest.main()
