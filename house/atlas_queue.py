#!/usr/bin/env python3
"""The atlas request queue, pulled by the house (AP-review-0002/A4, ported from Jetsam's house/ at f97c6f7 for Review's house (AP-review-0002), which re-derived the soul house's tools; IR-8 as the
atlas amended it at ruleset 1.2.0). Ported from the soul house's
house/atlas_queue.py at f6468fe (by way of Grade's port at 26c4a9d, read as an aid; the reference read at 7c339e8, house/ only) and re-derived for this house: Review keeps no
numbered backlog, so an atlas item is filed under its own key in WORK.md's
atlas items, and the soul's allocator and survey pointers have no place here.

The atlas publishes, per framework, the ratified items of its alignment prompts
at `frameworks/<slug>/engineering/alignment/QUEUE.json` on its main (the contract
`atlas-queue`). This tool reads that queue at a named commit, read-only and
shallow-safe, and accepts an item only where the atlas's
`alignment/ledger.jsonl` at the same commit holds a prompt-level `ratified` line
for its prompt. It compares the queue with the house's state file,
`house/atlas-queue.json` (the shape the atlas's `tools/atlasqueue.py status`
reads), and reports new, changed and closed items. It never writes into the
atlas. An atlas it cannot reach reads UNREACHABLE and exits 0: never an empty
queue, and the boot goes on.

  python3 -I -B house/atlas_queue.py [ROOT] check   [SOURCE]           read-only
  python3 -I -B house/atlas_queue.py [ROOT] sync    [SOURCE]           boot and close
  python3 -I -B house/atlas_queue.py [ROOT] card    [SOURCE] [--text]  DU's choice
  python3 -I -B house/atlas_queue.py [ROOT] set KEY STATE [--reason R] [--commit SHA]
  python3 -I -B house/atlas_queue.py [ROOT] verify                     the state file's own check
  python3 -I -B house/atlas_queue.py [ROOT] reply PROMPT[/A<n>] KIND TEXT [SOURCE]   IR-15

SOURCE is `--atlas DIR` (a local git checkout of the atlas; its origin/main, else
main, else HEAD, unless `--commit SHA`) or, by default, the GitHub API through
`gh`, for the repository `SUBSTRATE.md`'s atlas row names (or `--repo OWNER/NAME`).

SYNC files each new item in WORK.md's atlas items, between the markers
`<!-- house section: atlas items -->` and `<!-- end house section -->`, as one
entry led by its key in bold, and records it in the state file under that key.
An item whose key already leads an entry (filed by hand, or by an earlier pull)
is recorded and never filed twice, and the run says so; a key merely mentioned
inside another entry is not a filing. The entry carries the queue's title,
priority, rank, DONE WHEN and dependencies, and the `- Negative control:` line of
the item's `### A<n>.` section in its prompt, read at the same commit; a prompt
that names none is said so in the entry (the soul house refuses such an item for
its register's census, which this house does not keep). A prompt that cannot be
read files nothing for that item, says why and leaves it new for the next pull.
A run that files says the open work changed: a tree edit, to be checked before
the commit. Writes are the two explicit verbs, `sync` and `set`; `check` and
`card` write nothing.

CARD prints the question a widget carries (JSON), or with `--text` the same card
as text for a surface with no widget: the open items by rank, up to four, the
first marked (Recommended). An item the state file holds as landed or refused is
never offered.

NO LANDING AHEAD OF ITS DEPENDENCY. `sync` records each accepted item's
`depends_on` in the state file. A dependency the queue no longer holds and the
state file never held was closed at the atlas (landed, refused, or covered by a
newer install, AT.109) and is recorded apart, under `depends_on_closed`, where it
blocks nothing. `set KEY landed` refuses, writing nothing, while any recorded
dependency is not landed; `verify` refuses a state file holding such a landing.

REPLIES TO THE ATLAS (IR-15). `house/atlas_replies.py`, beside this file, keeps
`house/atlas-replies.jsonl`: `sync` writes one `arrival` per prompt at the pull
that first takes any of its items into the state file, filed or recorded; `reply`
writes the other kinds (refusing, writing nothing, on bad input); every pull reads
the atlas's answers from its ledger, records them in the state file and shows the
open replies and the new answers. An UNREACHABLE pull shows the last pull's.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

QUEUE_PATH = "frameworks/{slug}/engineering/alignment/QUEUE.json"
LEDGER_PATH = "alignment/ledger.jsonl"
STATE_FILE = "house/atlas-queue.json"
OPEN_WORK = "WORK.md"
SECTION_BEGIN = "<!-- house section: atlas items -->"
SECTION_END = "<!-- end house section -->"
ENTRY_KEY = re.compile(r"(?m)^- \*\*(AP-[a-z0-9]+-\d{4}/A\d+)\*\*")
ITEM_STATES = ("filed", "started", "landed", "refused")
VERBS = ("check", "sync", "card", "set", "verify", "reply")
FLAGS_WITH_VALUE = ("--atlas", "--repo", "--commit", "--reason")
FLAGS_BARE = ("--text", "--json")


class Unreachable(Exception):
    """The atlas could not be read; the reason travels in the message."""


class Absent(Unreachable):
    """The atlas was read at its commit and holds no file at the path asked."""


# ---------------------------------------------------------------- the house's own facts

def registration(root: Path) -> dict:
    """slug and atlas repository from SUBSTRATE.md's registration table."""
    out = {}
    p = root / "SUBSTRATE.md"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    for key in ("slug", "atlas"):
        m = re.search(rf"(?m)^\|\s*{key}\s*\|\s*([^|]+?)\s*\|\s*$", text)
        if m:
            out[key] = m.group(1)
    if "atlas" in out:
        m = re.search(r"github\.com/([\w.-]+/[\w.-]+)", out["atlas"])
        out["repo"] = m.group(1) if m else None
    return out


def load_state(root: Path) -> dict:
    p = root / STATE_FILE
    if not p.exists():
        return {"atlas_commit": None, "items": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(root: Path, st: dict) -> None:
    (root / STATE_FILE).write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def replies():
    """The replies module beside this file, a library (IR-15)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import atlas_replies  # noqa: E402
    return atlas_replies


# ---------------------------------------------------------------- reading the atlas

def _run(cmd: list) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))


def read_atlas(root: Path, args: dict, slug: str) -> tuple:
    """(commit, source label, queue rows, ledger lines, reader of a path at that
    commit) or raise Unreachable."""
    qpath = QUEUE_PATH.format(slug=slug)
    if args.get("--atlas"):
        d = Path(args["--atlas"])
        if not (d / ".git").exists() and not (d / "HEAD").exists():
            raise Unreachable(f"no git checkout of the atlas at {d}")
        sha = args.get("--commit")
        for ref in ([sha] if sha else ["origin/main", "main", "HEAD"]):
            p = _run(["git", "-C", str(d), "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"])
            if p.returncode == 0 and p.stdout.strip():
                sha = p.stdout.strip()
                break
        else:
            raise Unreachable(f"the atlas checkout at {d} has no main to read")

        def show(rel):
            p = _run(["git", "-C", str(d), "show", f"{sha}:{rel}"])
            if p.returncode != 0:
                raise Absent(f"{rel} is not at {sha[:7]} in {d}")
            return p.stdout
        source = f"checkout {d}"
    else:
        repo = args.get("--repo") or registration(root).get("repo")
        if not repo:
            raise Unreachable("SUBSTRATE.md names no atlas repository on GitHub")
        sha = args.get("--commit")
        if not sha:
            p = _run(["gh", "api", f"repos/{repo}/commits/main", "--jq", ".sha"])
            if p.returncode != 0 or not p.stdout.strip():
                raise Unreachable(f"gh could not read {repo}'s main ({(p.stderr or 'no answer').strip()[:120]})")
            sha = p.stdout.strip()

        def show(rel):
            p = _run(["gh", "api", "-H", "Accept: application/vnd.github.raw",
                      f"repos/{repo}/contents/{rel}?ref={sha}"])
            if p.returncode != 0:
                raise (Absent if "404" in (p.stderr or "") else Unreachable)(
                    f"gh could not read {rel} at {sha[:7]} ({(p.stderr or '').strip()[:120]})")
            return p.stdout
        source = f"api {repo}"
    try:
        rows = json.loads(show(qpath)).get("items") or []
        lines = [json.loads(x) for x in show(LEDGER_PATH).splitlines() if x.strip()]
    except ValueError as e:
        raise Unreachable(f"the atlas's queue or ledger at {sha[:7]} is not readable JSON ({e})")
    return sha, source, rows, lines, show


def ratified_prompts(lines: list) -> set:
    return {x.get("prompt") for x in lines if x.get("event") == "ratified" and not x.get("item")}


def compare(rows: list, lines: list, st: dict) -> dict:
    """new, changed, closed, refused, accepted (rank order), by the state file."""
    ok = ratified_prompts(lines)
    accepted = sorted((r for r in rows if r.get("prompt") in ok), key=lambda r: r.get("rank", 10**6))
    refused = [r for r in rows if r.get("prompt") not in ok]
    items = st.get("items") or {}
    keys = {r["key"] for r in accepted}
    new = [r for r in accepted if r["key"] not in items]
    changed = [r for r in accepted if r["key"] in items and any(
        items[r["key"]].get(f) not in (None, r.get(f)) for f in ("title", "done_when", "priority"))]
    closed = [k for k in items if k not in keys]
    return {"new": new, "changed": changed, "closed": closed, "refused": refused, "accepted": accepted}


def line(cmp: dict, st: dict, sha: str, source: str) -> str:
    items = st.get("items") or {}
    states = [items.get(r["key"], {}).get("state") for r in cmp["accepted"]]
    landed = sum(1 for v in items.values() if v.get("state") == "landed")
    refused = sum(1 for v in items.values() if v.get("state") == "refused")
    open_ = sum(1 for s in states if s not in ("landed", "refused"))
    return (f"atlas queue (IR-8): {len(cmp['new'])} new · {open_} open · {landed} landed · "
            f"{refused} refused · atlas {sha[:7]} via {source}")


def report(cmp: dict, st: dict, sha: str) -> list:
    items = st.get("items") or {}
    out = [f"  NEW {r['key']} rank {r.get('rank')} {r.get('priority')}: {r.get('title')}" for r in cmp["new"]]
    out += [f"  CHANGED {r['key']} (house: {items[r['key']].get('state')})" for r in cmp["changed"]]
    out += [f"  CLOSED {k} (house: {items[k].get('state')})" for k in cmp["closed"]]
    out += [f"  REFUSED {r['key']}: its prompt has no ratified line on the atlas's ledger at {sha[:7]}"
            for r in cmp["refused"]]
    return out


# ---------------------------------------------------------------- filing into the open work

def section(text: str) -> tuple[int, int] | None:
    """(start, end) offsets of the atlas items section's body, or None."""
    b = text.find(SECTION_BEGIN)
    if b < 0:
        return None
    e = text.find(SECTION_END, b)
    if e < 0:
        return None
    return b + len(SECTION_BEGIN), e


def filed_keys(text: str) -> set:
    """The keys that lead an entry anywhere in the open work (the guards' id space)."""
    return set(ENTRY_KEY.findall(text))


def prompt_control(text: str, item: str) -> str | None:
    """The `- Negative control:` (or `controls:`) line of the item's `### A<n>.` section, or None."""
    sec = re.search(rf"(?ms)^### {re.escape(item)}\.[^\n]*\n(.*?)(?=^##+ |\Z)", text)
    hit = re.search(r"(?mi)^- Negative controls?:\s*(.+?)\s*$", sec.group(1)) if sec else None
    return hit.group(1).rstrip(".") if hit else None


def entry(r: dict, sha: str, control: str | None) -> str:
    deps = ", ".join(r.get("depends_on") or []) or "none"
    ctl = control if control else "the prompt names none"
    title = " ".join(str(r.get("title", "")).split()).rstrip(".")
    return (f"- **{r['key']}** ({r.get('priority')}, rank {r.get('rank')}; filed by the queue pull from the "
            f"atlas's queue at `{sha[:7]}`, its prompt `{r.get('prompt_path')}` ratified "
            f"{r.get('ratified') or '(date not given)'}). {title}. DONE WHEN: "
            f"{str(r.get('done_when')).rstrip('.')}. CONTROL: {ctl.rstrip('.')}. DEPENDS ON: {deps}. "
            f"Re-derive the change against this tree before building (IR-4).")


def insert(path: Path, text_entries: list) -> None:
    src = path.read_text(encoding="utf-8")
    at = section(src)
    if at is None:
        raise SystemExit(f"atlas_queue: {path.name} has no `{SECTION_BEGIN}` ... `{SECTION_END}` section; nothing filed")
    _, end = at
    before = src[:end].rstrip("\n") + "\n"
    path.write_text(before + "".join(t + "\n" for t in text_entries) + src[end:], encoding="utf-8")


def sync(root: Path, args: dict, cmp: dict, st: dict, sha: str, show) -> list:
    reg = root / OPEN_WORK
    if not reg.exists() or section(reg.read_text(encoding="utf-8")) is None:
        raise SystemExit(f"atlas_queue: {OPEN_WORK} has no atlas items section; nothing filed, nothing written")
    out, items, prompts, to_file = [], st.setdefault("items", {}), {}, []
    ar = replies()
    # a prompt arrives once, at the pull that first takes any of its items in (IR-15)
    held = {k.split("/")[0] for k in items} | {x.get("prompt") for x in ar.load(root) if x.get("kind") == "arrival"}
    first: dict[str, list] = {}
    have = filed_keys(reg.read_text(encoding="utf-8"))
    for r in cmp["new"]:
        path = r.get("prompt_path") or ""
        if r["key"] in have:
            out.append(f"RECORDED {r['key']} (it already leads an entry in {OPEN_WORK}; not filed twice)")
        else:
            if path not in prompts:
                try:
                    prompts[path] = show(path) if path else None
                except Unreachable:
                    prompts[path] = None
            if prompts[path] is None:
                out.append(f"NOT FILED {r['key']}: its prompt `{path or 'unnamed'}` could not be read at "
                           f"{sha[:7]}, so its control is unknown; left new for the next pull")
                continue
            control = prompt_control(prompts[path], str(r.get("item", "")))
            to_file.append(entry(r, sha, control))
            have.add(r["key"])
            out.append(f"FILED {r['key']}" + ("" if control else " (its prompt names no control; said in the entry)"))
        if r.get("prompt") not in held:
            first.setdefault(r["prompt"], (path, []))[1].append(str(r.get("item")))
        items[r["key"]] = {"state": "filed", "house_item": r["key"], "title": r.get("title"),
                           "done_when": r.get("done_when"), "priority": r.get("priority"),
                           "filed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if to_file:
        insert(reg, to_file)
    queued = {r["key"] for r in cmp["accepted"]}
    for r in cmp["accepted"]:   # every held item carries the queue's dependencies
        if r["key"] in items:
            deps = list(r.get("depends_on") or [])
            items[r["key"]]["depends_on"] = [d for d in deps if d in queued or d in items]
            closed = [d for d in deps if d not in queued and d not in items]
            if closed:
                items[r["key"]]["depends_on_closed"] = closed
            else:
                items[r["key"]].pop("depends_on_closed", None)
    slug = registration(root).get("slug") or "review"
    for pid, (path, done) in first.items():
        raw = prompts.get(path)
        if raw is None and path:
            try:
                raw = prompts[path] = show(path)
            except Unreachable:
                raw = None
        rep, why = ar.write(root, slug, pid, "arrival", f"arrival: the house's queue pull took in "
                            f"{', '.join(done)} of {pid} (IR-15)", sha, raw)
        out.append(f"REPLIED {rep['id']} arrival for {pid}" if rep else f"NOT REPLIED arrival for {pid}: {why}")
    st["atlas_commit"] = sha
    save_state(root, st)
    if to_file:
        out.append(f"atlas queue: {len(to_file)} item(s) filed into {OPEN_WORK}'s open work, a tree edit: "
                   "run the house check before the commit")
    return out


# ---------------------------------------------------------------- the card

def card(cmp: dict, st: dict) -> dict | None:
    items = st.get("items") or {}
    open_ = [r for r in cmp["accepted"] if items.get(r["key"], {}).get("state") not in ("landed", "refused")][:4]
    if not open_:
        return None
    opts, wait = [], replies().waits(st.get("replies") or {})
    for i, r in enumerate(open_):
        state = items.get(r["key"], {}).get("state")
        label = r["key"] + (" (Recommended)" if i == 0 else "")
        desc = f"Rank {r.get('rank')}, {r.get('priority')}: {r.get('title')}."
        if state:
            desc += f" The house holds it as {state}."
        if r.get("depends_on"):
            desc += f" Depends on {', '.join(r['depends_on'])}."
        hold = wait.get(r["key"]) or wait.get(r.get("prompt", ""))
        if hold:
            desc += f" It waits on the atlas's answer to {hold} (IR-15)."
        opts.append({"label": label, "description": desc})
    return {"question": "The atlas requests open for this house, by rank. Which is implemented first?",
            "header": "Atlas queue", "multiSelect": False, "options": opts}


def card_text(c: dict) -> str:
    lines = [f"**{c['header']}**", c["question"]]
    lines += [f"{chr(65 + i)}. {o['label']}: {o['description']}" for i, o in enumerate(c["options"])]
    lines.append("Reply with a letter or in your own words.")
    return "\n".join(lines)


# ---------------------------------------------------------------- the state file

def verify(st: dict) -> list:
    bad = []
    if not isinstance(st.get("items"), dict):
        return ["`items` is not an object"]
    for k, v in st["items"].items():
        s = (v or {}).get("state")
        if s not in ITEM_STATES:
            bad.append(f"{k} has state `{s}`, not one of {', '.join(ITEM_STATES)}")
        elif s == "refused" and not v.get("reason"):
            bad.append(f"{k} is refused with no reason")
        elif s == "landed":
            for d in unlanded_dependencies(st["items"], k):
                bad.append(f"{k} is landed ahead of its dependency {d}")
    return bad


def unlanded_dependencies(items: dict, key: str) -> list:
    """The recorded dependencies of KEY the state file does not hold as landed, each with its state."""
    out = []
    for d in (items.get(key) or {}).get("depends_on") or []:
        s = (items.get(d) or {}).get("state")
        if s != "landed":
            out.append(f"{d}, {s or 'not recorded'}")
    return out


def set_state(root: Path, key: str, state: str, args: dict) -> int:
    if state not in ITEM_STATES:
        print(f"atlas_queue: `{state}` is not one of {', '.join(ITEM_STATES)}; nothing written")
        return 2
    if state == "refused" and not args.get("--reason"):
        print("atlas_queue: a refusal carries its reason (--reason); nothing written")
        return 2
    st = load_state(root)
    if state == "landed":
        ahead = unlanded_dependencies(st.get("items") or {}, key)
        if ahead:
            print(f"atlas_queue: {key} cannot be landed ahead of its dependency: {'; '.join(ahead)}; nothing written")
            return 2
    entry_ = st.setdefault("items", {}).setdefault(key, {})
    entry_["state"] = state
    if args.get("--reason"):
        entry_["reason"] = args["--reason"]
    if state == "landed":
        sha = args.get("--commit") or _run(["git", "-C", str(root), "rev-parse", "HEAD"]).stdout.strip()
        entry_["commit"] = sha or "unknown"
    save_state(root, st)
    print(f"atlas_queue: {key} is {state}" + (f" at {entry_.get('commit')}" if state == "landed" else ""))
    return 0


# ---------------------------------------------------------------- entry

def parse(argv: list) -> tuple[Path, str, list, dict]:
    args, pos, i = {}, [], 0
    while i < len(argv):
        a = argv[i]
        if a in FLAGS_WITH_VALUE:
            if i + 1 >= len(argv):
                raise SystemExit(f"atlas_queue: {a} needs a value")
            args[a] = argv[i + 1]; i += 2; continue
        if a in FLAGS_BARE:
            args[a] = True; i += 1; continue
        if a.startswith("--"):
            raise SystemExit(f"atlas_queue: unknown flag {a}; nothing read")
        pos.append(a); i += 1
    root = Path(__file__).resolve().parent.parent
    if pos and pos[0] not in VERBS and Path(pos[0]).is_dir():
        root = Path(pos.pop(0)).resolve()
    if not pos or pos[0] not in VERBS:
        raise SystemExit("usage: atlas_queue.py [ROOT] check|sync|card|set|verify|reply ... (see the module's doc)")
    return root, pos[0], pos[1:], args


def main(argv: list) -> int:
    root, verb, rest, args = parse(argv[1:])
    if verb == "verify":
        if not (root / STATE_FILE).exists():
            print(f"atlas_queue: no state file yet ({STATE_FILE}); the first `sync` writes it")
            return 0
        bad = verify(load_state(root))
        for b in bad:
            print(f"ATLAS_QUEUE: {b}")
        print(f"atlas_queue: state file {'REFUSED' if bad else 'well-formed'} ({STATE_FILE})")
        return 1 if bad else 0
    if verb == "set":
        if len(rest) != 2:
            raise SystemExit("usage: atlas_queue.py [ROOT] set PROMPT/A<n> STATE [--reason R] [--commit SHA]")
        return set_state(root, rest[0], rest[1], args)
    st, ar = load_state(root), replies()
    slug = registration(root).get("slug") or "review"
    if verb == "reply" and len(rest) < 3:
        raise SystemExit("usage: atlas_queue.py [ROOT] reply PROMPT[/A<n>] KIND TEXT [SOURCE]")
    try:
        sha, source, rows, lines, show = read_atlas(root, args, slug)
    except Unreachable as e:
        print(f"atlas queue (IR-8): UNREACHABLE: {e}; not an empty queue, and the boot goes on")
        if verb == "reply":
            print("atlas_queue: a reply names the prompt's hash at a commit the atlas has; nothing written")
            return 1
        last = ar.shown(st.get("replies") or {}, st.get("atlas_commit"))
        for ln in [x.replace("(IR-15):", f"(IR-15), as of the last pull at {str(st.get('atlas_commit'))[:7]}:", 1)
                   for x in last[:1]] + last[1:]:
            print(ln)
        return 0
    if verb == "reply":
        pid, _, item = rest[0].partition("/")
        path = next((r.get("prompt_path") for r in rows if r.get("prompt") == pid and r.get("prompt_path")), None)
        try:
            raw = show(path) if path else None
        except Unreachable:
            raw = None
        rep, why = ar.write(root, slug, pid, rest[1], " ".join(rest[2:]), sha, raw, item or None) if path else (
            None, f"no item of the atlas's queue at {sha[:7]} names {pid}'s prompt")
        print(f"atlas_queue: REPLIED {rep['id']} {rep['kind']} for {rest[0]}" if rep else
              f"atlas_queue: reply refused: {why}; nothing written")
        return 0 if rep else 2
    cmp = compare(rows, lines, st)
    view = ar.record(root, st, lines, slug, sha)
    if verb == "card":
        c = card(cmp, st)
        if c is None:
            print(f"atlas queue: no open request for {slug} at {sha[:7]}; no card")
        else:
            print(card_text(c) if args.get("--text") else json.dumps(c, indent=1, ensure_ascii=False))
        return 0
    print(line(cmp, st, sha, source))
    for ln in report(cmp, st, sha):
        print(ln)
    if verb == "sync":
        for ln in sync(root, args, cmp, st, sha, show):
            print(ln)
        view = ar.record(root, st, lines, slug, sha)    # the arrivals this pull wrote, too
        save_state(root, st)
    for ln in ar.shown(view, sha):
        print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
