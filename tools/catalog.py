#!/usr/bin/env python3
"""catalog.py: the house's record, in git (AP-review-0001, A3; REVIEW, "The house"). Standard library only.

  catalog/proposals/<id>.json   one file per proposal, its shape below; the submitted text stored once and
                                never edited (its sha256 is kept beside it and in the `received` event)
  catalog/events.jsonl          append-only, one event per line, merged line-wise (`merge=union`); every
                                state change is an event, and a proposal's file reads the state of its last
  catalog/allowlist.json        the verified contributors' GitHub account ids; empty until soul marks exist
                                (RV.2, the atlas's AT.716)

A proposal file holds exactly: id (`RV-` and four digits), state (one of lib.STATES), account (the
contributor's GitHub account id, a number, never a name), issue (the intake issue's number, or null),
frameworks (registered slugs; empty only when refused), text (the seven fields as submitted), text_sha256, checks (the names of the
mechanical checks that refused it), marks (the instruction shapes its text matched), verdict, reading and
ruling (null until R3 and R4 write them; a ruling is the owner's ruling id).

  python3 -I -B tools/catalog.py check       the log, the files and the allowlist against their shapes
  python3 -I -B tools/catalog.py next-id     the next proposal id
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

ID = re.compile(r"^RV-\d{4}$")
EVENT_ID = re.compile(r"^(RV-\d{4})/(\d+)$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEYS = {"id", "state", "account", "issue", "frameworks", "text", "text_sha256", "checks", "marks", "verdict",
        "reading", "ruling"}
EVENT_KEYS = {"id", "proposal", "from", "to", "day"}
EVENT_OPTIONAL = {"checks", "marks", "text_sha256", "ruling"}


def today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def paths(root: Path):
    c = root / lib.CATALOG
    return c / "proposals", c / "events.jsonl", c / "allowlist.json"


def read_events(root: Path) -> tuple[list[dict], list[str]]:
    _, log, _ = paths(root)
    events, problems = [], []
    try:
        lines = log.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], ["catalog/events.jsonl is missing"]
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            problems.append(f"events.jsonl line {n}: not JSON")
            continue
        if not isinstance(e, dict):
            problems.append(f"events.jsonl line {n}: not an object")
            continue
        e["_line"] = n
        events.append(e)
    return events, problems


def text_sha(text: dict) -> str:
    return lib.sha256(lib.canonical(text))


def proposal_problems(p, name: str, slugs: set[str]) -> list[str]:
    """A proposal file off its shape, by name. Only the shape: what the text says is never judged here."""
    if not isinstance(p, dict):
        return [f"{name}: not an object"]
    out = []
    if set(p) != KEYS:
        out.append(f"{name}: keys differ from the shape (missing {sorted(KEYS - set(p))}, extra {sorted(set(p) - KEYS)})")
        return out
    if not ID.match(str(p["id"])) or name != f"{p['id']}.json":
        out.append(f"{name}: id `{p['id']}` is not RV-nnnn or does not name its file")
    if p["state"] not in lib.STATES:
        out.append(f"{name}: state `{p['state']}` is not one of {', '.join(lib.STATES)}")
    if not isinstance(p["account"], int) or isinstance(p["account"], bool) or p["account"] <= 0:
        out.append(f"{name}: account is not a GitHub account id (a positive number)")
    if p["issue"] is not None and (not isinstance(p["issue"], int) or p["issue"] <= 0):
        out.append(f"{name}: issue is not null or an issue number")
    if not isinstance(p["frameworks"], list) or any(f not in slugs for f in p["frameworks"]) \
            or (not p["frameworks"] and p["state"] != "refused"):
        out.append(f"{name}: frameworks is not a list of registered slugs (empty only when refused)")
    t = p["text"]
    if not isinstance(t, dict) or set(t) != {f for f, _ in lib.FIELDS}:
        out.append(f"{name}: text does not hold exactly the form's seven fields")
    elif p["text_sha256"] != text_sha(t):
        out.append(f"{name}: text_sha256 does not match the text; the submitted text is never edited")
    for k in ("checks", "marks"):
        if not isinstance(p[k], list) or not all(isinstance(x, str) for x in p[k]):
            out.append(f"{name}: {k} is not a list of names")
    if p["state"] == "refused" and not p["checks"]:
        out.append(f"{name}: refused with no check named; a refusal is mechanical and names its check")
    if p["state"] != "refused" and p["checks"]:
        out.append(f"{name}: checks named but the state is `{p['state']}`")
    for k in ("verdict", "reading"):
        if p[k] is not None and not isinstance(p[k], str):
            out.append(f"{name}: {k} is not null or text")
    if p["ruling"] is not None and not re.fullmatch(r"[A-Z]+\.\d+", str(p["ruling"])):
        out.append(f"{name}: ruling is not null or a ruling id")
    if p["state"] in ("ruled", "contested") and p["ruling"] is None:
        out.append(f"{name}: state `{p['state']}` with no ruling id")
    return out


def check(root: Path = lib.ROOT) -> list[str]:
    folder, _, allow = paths(root)
    problems = []
    try:
        slugs = set(lib.slugs(root))
    except (OSError, ValueError, KeyError):
        return ["catalog/frameworks.json cannot be read"]
    # the allowlist: an object with a list of accounts, each a numeric id, never a name
    try:
        al = lib.read_json(allow)
        accounts = al["accounts"]
        ids = [a["id"] for a in accounts]
        if any(not isinstance(i, int) or isinstance(i, bool) or i <= 0 for i in ids) or len(ids) != len(set(ids)):
            problems.append("allowlist.json: an account id is not a positive number, or appears twice")
        if any(set(a) - {"id", "since", "merge", "mark"} for a in accounts):
            problems.append("allowlist.json: an account carries a field other than id, since, merge, mark")
    except (OSError, ValueError, KeyError, TypeError):
        problems.append("allowlist.json: not an object with an `accounts` list of {id, ...}")
    # the proposals
    props = {}
    for f in sorted(folder.glob("*.json")):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            problems.append(f"{f.name}: not JSON")
            continue
        found = proposal_problems(p, f.name, slugs)
        problems += found
        if not found:
            props[p["id"]] = p
    # the events: ids unique, each proposal's numbered in order from 1, each a legal transition
    events, found = read_events(root)
    problems += found
    seen, state, count = {}, {}, {}
    for e in events:
        n = e.pop("_line")
        if not EVENT_KEYS <= set(e) or set(e) - EVENT_KEYS - EVENT_OPTIONAL:
            problems.append(f"events.jsonl line {n}: keys off the shape")
            continue
        if e["id"] in seen:
            problems.append(f"events.jsonl line {n}: event id {e['id']} appears twice (first at line {seen[e['id']]})")
            continue
        seen[e["id"]] = n
        m = EVENT_ID.match(str(e["id"]))
        if not m or m.group(1) != e["proposal"]:
            problems.append(f"events.jsonl line {n}: id {e['id']} is not <proposal>/<n>")
            continue
        if not DAY.match(str(e["day"])):
            problems.append(f"events.jsonl line {n}: day is not YYYY-MM-DD")
        pid, k = e["proposal"], int(m.group(2))
        if k != count.get(pid, 0) + 1:
            problems.append(f"events.jsonl line {n}: {e['id']} out of order (expected {pid}/{count.get(pid, 0) + 1})")
        count[pid] = k
        prev = state.get(pid)
        if prev is None:
            if e["from"] is not None or e["to"] != "received":
                problems.append(f"events.jsonl line {n}: a proposal's first event is from null to received")
        elif e["from"] != prev or e["to"] not in lib.TRANSITIONS.get(prev, ()):
            problems.append(f"events.jsonl line {n}: {pid} cannot go from `{e['from']}` to `{e['to']}` (it is `{prev}`)")
        state[pid] = e["to"]
        if e["to"] == "received" and pid in props and e.get("text_sha256") != props[pid]["text_sha256"]:
            problems.append(f"events.jsonl line {n}: {pid}'s text_sha256 differs from its file's; the text was edited")
    for pid, p in props.items():
        if state.get(pid) != p["state"]:
            problems.append(f"{pid}.json: state `{p['state']}` but its last event reads `{state.get(pid)}`")
    for pid in state:
        if pid not in props and not (folder / f"{pid}.json").exists():
            problems.append(f"events.jsonl: {pid} has events but no file")
    return problems


def next_id(root: Path = lib.ROOT) -> str:
    folder, _, _ = paths(root)
    nums = [int(f.stem[3:]) for f in folder.glob("RV-*.json") if ID.match(f.stem)]
    return f"RV-{(max(nums) + 1 if nums else 1):04d}"


def append_event(root: Path, event: dict) -> None:
    _, log, _ = paths(root)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")


def events_for(root: Path, pid: str) -> int:
    events, _ = read_events(root)
    return sum(1 for e in events if e.get("proposal") == pid)


def receive(root: Path, account: int, issue, frameworks: list[str], text: dict, marks: list[str], day: str | None = None) -> dict:
    """A proposal enters the catalog in state `received`: its file written, its first event appended."""
    folder, _, _ = paths(root)
    pid = next_id(root)
    p = {"id": pid, "state": "received", "account": account, "issue": issue, "frameworks": frameworks, "text": text,
         "text_sha256": text_sha(text), "checks": [], "marks": sorted(marks), "verdict": None, "reading": None,
         "ruling": None}
    (folder / f"{pid}.json").write_text(json.dumps(p, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    append_event(root, {"id": f"{pid}/1", "proposal": pid, "from": None, "to": "received", "day": day or today(),
                        "text_sha256": p["text_sha256"], "marks": p["marks"]})
    return p


def move(root: Path, pid: str, to: str, day: str | None = None, **extra) -> dict:
    """One state change: the transition must be legal; the file's state and the log move together."""
    folder, _, _ = paths(root)
    f = folder / f"{pid}.json"
    p = json.loads(f.read_text(encoding="utf-8"))
    if to not in lib.TRANSITIONS[p["state"]]:
        raise ValueError(f"{pid} cannot go from {p['state']} to {to}")
    n = events_for(root, pid) + 1
    event = {"id": f"{pid}/{n}", "proposal": pid, "from": p["state"], "to": to, "day": day or today()}
    if to == "refused":
        p["checks"] = sorted(extra["checks"])
        event["checks"] = p["checks"]
    if "ruling" in extra:
        p["ruling"] = extra["ruling"]
        event["ruling"] = extra["ruling"]
    p["state"] = to
    f.write_text(json.dumps(p, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    append_event(root, event)
    return p


def main(argv: list[str]) -> int:
    if argv[:1] == ["next-id"]:
        print(next_id())
        return 0
    if argv[:1] != ["check"]:
        print(__doc__)
        return 2
    problems = check()
    for p in problems:
        print(f"CATALOG: {p}")
    print(f"catalog check: {len(problems)} findings")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
