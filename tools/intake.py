#!/usr/bin/env python3
"""intake.py: the mechanical checks on a proposal (AP-review-0001, A5; REVIEW, "A provisional no is not a
refusal"). Standard library only. A proposal is data: this tool reads its text only to name the checks it
fails and the instruction shapes it matches, and never acts on anything it says.

A refusal is mechanical and names its check, never a judgement:

  not-allowlisted    the author's GitHub account id is not in catalog/allowlist.json (checked first; such a
                     proposal is closed unread, its text never parsed)
  form-shape         the form's seven headings are not each present once, in REVIEW's order
  missing-field      a field is empty or `_No response_`, or the consent box is not ticked
  unknown-framework  a framework touched is not a registered slug (catalog/frameworks.json)
  never-store        the text carries a secret's shape or a path into a never-store category
                     (catalog/never-store.json); a category may be named, its contents never

The open-proposal limit (RV.4) is R2's. A proposal shaped like an instruction is MARKED with the shapes it
matches, kept as data, and never refused for it; the marks travel with it to the readers and the owner.

  python3 -I -B tools/intake.py check BODY_FILE --account N [--json]
  python3 -I -B tools/intake.py event EVENT_JSON --comment OUT    the intake workflow's step: the issue event's
                                         author against the allowlist first, then the checks; prints the
                                         action (close-unread, refuse, receive) and writes the comment
  python3 -I -B tools/intake.py receive BODY_FILE --account N [--issue N]   a session records a proposal in the
                                         catalog: received, then refused at once if a check fails
  python3 -I -B tools/intake.py tree     the tree guard: .gitignore mirrors every never-store glob (IR-13), no
                                         tracked path falls under one, no tracked text file carries a
                                         never-store content pattern
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import lib  # noqa: E402

# Text shaped like an instruction. Copied from the atlas's tools/outside.py at ced555c8 (TODO-56, rulings AT.665
# to AT.668: outside input is adversarial; each match is flagged by its name and nothing is done with the text).
# A change there is copied here by hand, with the commit it was copied at.
INSTRUCTION = (
    ("override", re.compile(r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|any|your|the)\b"
                            r".{0,40}\b(instructions?|rules?|prompts?|guidance|guards?|checks?)\b", re.I | re.S)),
    ("role", re.compile(r"(^|[\n.;!?])\s*(system|assistant|developer|user)\s*:|<\s*/?\s*(system|instructions?|prompt|im_start|im_end)\b", re.I)),
    ("persona", re.compile(r"\b(you are now|from now on,? you|act as|pretend to be|new instructions?)\b", re.I)),
    ("addressed", re.compile(r"\b(claude|chatgpt|assistant|the model|the agent|the session|ai)\b[,:]?\s+(must|should|please|now|will)\b", re.I)),
    ("process", re.compile(r"\b(merge|approve|ratify|delete|push|close|raise|prioriti[sz]e|rank|mark|escalate|rule)\b.{0,30}"
                           r"\b(this|it|now|immediately|at once|first|to the top|as done|as s0)\b", re.I)),
    ("command", re.compile(r"(`[^`]{1,200}`|\$\(|\b(rm -rf|curl|wget|bash -c|sh -c|python3? -c|eval|exec)\b)", re.I)),
)

CHECKS = ("not-allowlisted", "form-shape", "missing-field", "unknown-framework", "never-store")
HEADING = re.compile(r"^### (.+?)\s*$")
TICKED = re.compile(r"^- \[[xX]\] (.+)$")

COMMENTS = {
    "close-unread": ("Closed unread. Substrate Review takes proposals only from verified contributors, and none "
                     "can be verified yet: verification needs a merged pull request plus a soul mark, and soul "
                     "marks do not exist yet. Review's tools did not read or keep this issue's text."),
    "refuse": ("Refused by a mechanical check: {checks}. A refusal names what to fix and judges nothing about "
               "the proposal; fix it and open a new one."),
    "receive": ("Received. Instruction shapes marked: {marks}. Review's readers are not built yet; when they "
                "run, a provisional verdict and a marked reading follow, and only the owner's ruling accepts or "
                "declines a proposal."),
}


def marks(text: str) -> list[str]:
    return [name for name, rx in INSTRUCTION if text and rx.search(text)]


def parse(body: str) -> tuple[dict, bool]:
    """(fields as submitted, shape ok). A `### ` heading that is not one of the seven labels is the
    contributor's own text and stays in the field it is written in."""
    labels = {label: fid for fid, label in lib.FIELDS}
    fields, order, current = {}, [], None
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        m = HEADING.match(line)
        if m and m.group(1) in labels:
            current = labels[m.group(1)]
            order.append(current)
            fields.setdefault(current, [])
            continue
        if current:
            fields[current].append(line)
    text = {fid: "\n".join(fields.get(fid, [])).strip() for fid, _ in lib.FIELDS}
    return text, order == [fid for fid, _ in lib.FIELDS]


def frameworks_of(text: dict) -> list[str]:
    raw = text.get("frameworks", "")
    return [] if raw in ("", lib.NO_RESPONSE) else [s.strip() for s in raw.split(",") if s.strip()]


def check(body: str, account: int, root: Path = lib.ROOT) -> dict:
    """{'checks': [names that refuse], 'marks': [...], 'text': {...}, 'frameworks': [...]}"""
    if account not in lib.allowlist(root):
        return {"checks": ["not-allowlisted"], "marks": [], "text": None, "frameworks": []}
    text, shape_ok = parse(body)
    checks = [] if shape_ok else ["form-shape"]
    for fid, _ in lib.FIELDS:
        v = text[fid]
        if fid == "consent":
            ticked = [m.group(1).strip() for m in map(TICKED.match, v.splitlines()) if m]
            if lib.CONSENT not in ticked:
                checks.append("missing-field")
        elif v in ("", lib.NO_RESPONSE):
            checks.append("missing-field")
    fws = frameworks_of(text)
    slugs = set(lib.slugs(root))
    if any(f not in slugs for f in fws):
        checks.append("unknown-framework")
    joined = "\n".join(text.values())
    if lib.text_hits(joined, lib.never_store(root)):
        checks.append("never-store")
    return {"checks": sorted(set(checks), key=CHECKS.index), "marks": marks(joined), "text": text, "frameworks": fws}


def event_action(payload: dict, root: Path = lib.ROOT) -> dict:
    """The intake workflow's decision for one issue event. The author is read first; an author not on the
    allowlist gets close-unread and the body is never parsed."""
    issue = payload.get("issue") or {}
    account = (issue.get("user") or {}).get("id")
    if not isinstance(account, int) or account not in lib.allowlist(root):
        return {"action": "close-unread", "checks": ["not-allowlisted"], "marks": [], "comment": COMMENTS["close-unread"]}
    r = check(issue.get("body") or "", account, root)
    if r["checks"]:
        return {"action": "refuse", "checks": r["checks"], "marks": r["marks"],
                "comment": COMMENTS["refuse"].format(checks=", ".join(r["checks"]))}
    return {"action": "receive", "checks": [], "marks": r["marks"],
            "comment": COMMENTS["receive"].format(marks=", ".join(r["marks"]) or "none")}


def receive(body: str, account: int, issue, root: Path = lib.ROOT) -> dict:
    """Record a proposal: received, then refused at once when a check fails. An author not on the allowlist is
    never recorded (their text is not kept)."""
    r = check(body, account, root)
    if r["checks"] == ["not-allowlisted"] and r["text"] is None:
        raise PermissionError("not-allowlisted: the proposal is not recorded")
    fws = [f for f in r["frameworks"] if f in set(lib.slugs(root))]   # an unknown slug is never kept
    p = catalog.receive(root, account, issue, fws, r["text"], r["marks"])
    if r["checks"]:
        p = catalog.move(root, p["id"], "refused", checks=r["checks"])
    return p


def tree(root: Path = lib.ROOT) -> list[str]:
    ns = lib.never_store(root)
    files = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
    problems = []
    try:
        ignored = set((root / ".gitignore").read_text(encoding="utf-8").splitlines())
    except OSError:
        ignored = set()
    for g in ns["paths"]:
        if lib.gitignore_form(g) not in ignored:
            problems.append(f".gitignore: does not mirror the never-store glob {g} (as `{lib.gitignore_form(g)}`)")
    for rel in [f for f in files.decode("utf-8").split("\0") if f]:
        g = lib.path_hit(rel, ns["paths"])
        if g:
            problems.append(f"{rel}: tracked under the never-store glob {g}")
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        c = lib.content_hit(text, ns["content"])
        if c:
            problems.append(f"{rel}: carries the never-store content pattern {c}")
    return problems


def opt(argv: list[str], name: str):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "check" and len(argv) > 1 and opt(argv, "--account"):
        r = check(Path(argv[1]).read_text(encoding="utf-8"), int(opt(argv, "--account")))
        if "--json" in argv:
            print(json.dumps({k: r[k] for k in ("checks", "marks", "frameworks")}, sort_keys=True))
        else:
            print(("refused: " + ", ".join(r["checks"])) if r["checks"] else "received", "| marks:", ", ".join(r["marks"]) or "none")
        return 1 if r["checks"] else 0
    if cmd == "event" and len(argv) > 1:
        r = event_action(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
        if opt(argv, "--comment"):
            Path(opt(argv, "--comment")).write_text(r["comment"] + "\n", encoding="utf-8")
        print(json.dumps({k: r[k] for k in ("action", "checks", "marks")}, sort_keys=True))
        return 0
    if cmd == "receive" and len(argv) > 1 and opt(argv, "--account"):
        issue = int(opt(argv, "--issue")) if opt(argv, "--issue") else None
        p = receive(Path(argv[1]).read_text(encoding="utf-8"), int(opt(argv, "--account")), issue)
        print(f"intake: {p['id']} {p['state']}" + (f" ({', '.join(p['checks'])})" if p["checks"] else ""))
        return 0
    if cmd == "tree":
        problems = tree()
        for p in problems:
            print(f"NEVER-STORE: {p}")
        print(f"tree guard: {len(problems)} findings")
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
