#!/usr/bin/env python3
"""The house's concurrency guards (IR-13; AP-review-0002, A1). Ported from Jetsam's
house/guards.py at f97c6f7, which re-derived the soul house's (by way of Grade's
port), and re-derived for Review's house: the never-store list is read from the
house's one copy, catalog/never-store.json, and the banned-address check also
refuses a fingerprint committed anywhere in the house (AT.765).

Review's house can be worked by more than one session at once, so it carries
IR-13's four guards. Two are git configuration and two are this check:

  1. A branch claims its name on the remote the moment it is created
     (`house/branch.sh`, whose first commit is the branch's creation line, A2).
  2. The append-only logs merge line-wise: the house block of `.gitattributes`
     carries a `merge=union` line for every log `house/guards.json` declares.
     A union merge never conflicts, so two sessions that mint the same id
     merge silently; this check is what refuses the duplicate.
  3. The hand-maintained handoff files have one owner at a time, named in
     `house/guards.json`; a branch that changes an owned file must contain the
     base it will merge into, i.e. a session that is not the owner rebases on
     main before touching one.
  4. `.gitignore` mirrors the never-store list between its marker lines, so
     `git add -A` cannot stage a listed path; no tracked file may match one,
     and no tracked text file may match one of its content patterns. The list
     is the atlas's (`charter/never-store.yaml`), recall paths included, read
     from `catalog/never-store.json` (the copy `tools/atlas_copy.py` keeps,
     named by `never_store_file` in `house/guards.json`), so the house holds
     one copy, never two.

And one check for the operator's banned-address rule: `banned` hashes git's
user.email, the author and committer of every commit on main and on the branch
committed after the banned list's `since`, and every email-shaped string in the
staged changes (sha256 of the lowercase form), and compares each with the
fingerprints in the atlas's `ops/banned-authors.yaml` at its main. A finding
names the commit or file and the fingerprint's first 8 characters, never the
address. A match is red and has no override; an atlas it cannot read is
UNREACHABLE and exits 0, said and never taken for a clean read. This house is
public, so it never holds the list (AT.765): the check reads it from the atlas
each time, and also refuses any tracked file carrying one of its fingerprints.

  python3 -I -B house/guards.py [ROOT] check  [--base REF]
  python3 -I -B house/guards.py [ROOT] mirror [--atlas DIR | --repo OWNER/NAME] [--commit SHA]
  python3 -I -B house/guards.py [ROOT] banned [--atlas DIR | --repo OWNER/NAME | --file PATH] [--commit SHA] [--base REF]

`check` reads the house alone. ROOT defaults to the repository holding this
file; REF (default `origin/main`) is read as it stands locally, so fetch first
for a fresh answer. Exit 1 on any finding. A check that needs a repository and
has none (an archive unpacked without `.git`) says NOT RUN and is never counted
as a pass.

`mirror` compares this house's copy of the never-store list with the atlas's at
its main (or SHA): from a local checkout with `--atlas`, else through `gh` for
the repository `SUBSTRATE.md`'s atlas row names. CURRENT exits 0; DIFFERS
exits 1 and names each difference (the atlas wins, and the copy here is
corrected from it); an atlas it cannot read is UNREACHABLE and exits 0, said
and never taken for a match.
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = "house/guards.json"
LOG = "house/branches.jsonl"
NEVER_STORE = "charter/never-store.yaml"
ATTR_BEGIN = "# house guards: union logs (IR-13): begin"
ATTR_END = "# house guards: union logs (IR-13): end"
IGNORE_BEGIN = "# never-store mirror: begin"
IGNORE_END = "# never-store mirror: end"
HOUSE_BEGIN = "# house never-store (this house's own): begin"
HOUSE_END = "# house never-store (this house's own): end"
BANNED = "ops/banned-authors.yaml"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
HEX64 = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])")
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".jsonl", ".py", ".sh", ".txt", ".csv", ".toml", ".cfg"}


def git(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def is_repo(root: Path) -> bool:
    return git(root, "rev-parse", "--git-dir").returncode == 0 and (root / ".git").exists()


def block(text: str, begin: str, end: str):
    m = re.search(rf"^{re.escape(begin)}\s*$(.*?)^{re.escape(end)}\s*$", text, re.S | re.M)
    if not m:
        return None
    return [l.strip() for l in m.group(1).splitlines() if l.strip() and not l.strip().startswith("#")]


def check_union(root: Path, cfg: dict) -> list[str]:
    p = root / ".gitattributes"
    lines = block(p.read_text(encoding="utf-8"), ATTR_BEGIN, ATTR_END) if p.exists() else None
    if lines is None:
        return [f".gitattributes: no `{ATTR_BEGIN}` ... `end` block"]
    have = {}
    for l in lines:
        parts = l.split()
        have[parts[0]] = parts[1:]
    out = []
    for pat in cfg.get("union_logs", []):
        if "merge=union" not in have.get(pat, []):
            out.append(f".gitattributes: `{pat}` is declared union-merged in {CONFIG} but has no `merge=union` line in the house block")
    for pat in have:
        if pat not in cfg.get("union_logs", []):
            out.append(f".gitattributes: the house block names `{pat}`, which {CONFIG} does not declare")
    return out


def ids_in(root: Path, space: dict) -> list[tuple[str, str]]:
    """(id, where) for every id the space's files define."""
    found = []
    for rel in space.get("files", []):
        p = root / rel
        if not p.exists():
            continue
        if "jsonl_key" in space:
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    row = json.loads(line) if line.strip() else None
                except ValueError:
                    continue
                if not isinstance(row, dict) or any(row.get(k) is None for k in space["jsonl_key"]):
                    continue
                found.append((":".join(str(row[k]) for k in space["jsonl_key"]), f"{rel}:{n}"))
        else:
            rx = re.compile(space["pattern"], re.M)
            text = p.read_text(encoding="utf-8")
            for m in rx.finditer(text):
                found.append((m.group(1), f"{rel}:{text.count(chr(10), 0, m.start()) + 1}"))
    return found


def check_ids(root: Path, cfg: dict) -> list[str]:
    out = []
    for space in cfg.get("id_spaces", []):
        where = collections.defaultdict(list)
        for i, w in ids_in(root, space):
            where[i].append(w)
        for i, ws in where.items():
            if len(ws) > 1:
                out.append(f"{space['name']}: `{i}` appears {len(ws)} times ({', '.join(ws[:4])}): two sessions minted it; the later renumbers")
    return out


def check_branch_log(root: Path) -> list[str]:
    """The creation log (A2): every line JSON; events created, pruned, due or ready (IR-16);
    `by` claude or not-claude; no branch created twice and no line written twice; every pruned
    or due line carries its tip, every ready line the 40-hex commit it marks as finished work."""
    p = root / LOG
    if not p.exists():
        return []
    out, created, lines = [], {}, {}
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        if line.strip() in lines:
            out.append(f"{LOG}:{n}: the same line as line {lines[line.strip()]}: a union merge kept both copies")
            continue
        lines[line.strip()] = n
        try:
            e = json.loads(line)
        except ValueError:
            out.append(f"{LOG}:{n}: not JSON")
            continue
        if not isinstance(e, dict):
            out.append(f"{LOG}:{n}: not a JSON object")
            continue
        ev, b = e.get("event"), e.get("branch")
        if ev not in ("created", "pruned", "due", "ready") or not b:
            out.append(f"{LOG}:{n}: event `{ev}` with branch `{b}`: want created|pruned|due|ready and a branch")
        elif ev == "ready":
            if not re.match(r"^[0-9a-f]{40}$", str(e.get("work", ""))):
                out.append(f"{LOG}:{n}: ready line for {b} names no `work` commit (40 hex)")
        elif ev == "created":
            if e.get("by") not in ("claude", "not-claude"):
                out.append(f"{LOG}:{n}: `by` is `{e.get('by')}`: want claude or not-claude")
            if b in created:
                out.append(f"{LOG}:{n}: {b} already created at line {created[b]}")
            created.setdefault(b, n)
        elif not re.match(r"^[0-9a-f]{40}$", str(e.get("tip", ""))):
            out.append(f"{LOG}:{n}: {ev} {b} has no 40-hex tip to restore from")
    return out


def load_cfg(root: Path) -> dict:
    """house/guards.json, with the never-store list read from the file it names (`never_store_file`, the house's
    one copy, flat `paths` and `content` lists) when it names one."""
    cfg = json.loads((root / CONFIG).read_text(encoding="utf-8"))
    rel = cfg.get("never_store_file")
    if rel:
        data = json.loads((root / rel).read_text(encoding="utf-8"))
        cfg["never_store"] = {"paths": {"the atlas's list": list(data.get("paths") or [])},
                              "content": list(data.get("content") or [])}
    return cfg


def never_store_paths(cfg: dict) -> list[str]:
    paths = (cfg.get("never_store") or {}).get("paths") or {}
    return [p for ps in paths.values() for p in ps]


def house_paths(cfg: dict) -> list[str]:
    paths = (cfg.get("house_never_store") or {}).get("paths") or {}
    return [p for ps in paths.values() for p in ps]


def never_store_content(cfg: dict) -> list[str]:
    return list((cfg.get("never_store") or {}).get("content") or [])


def check_mirror(root: Path, cfg: dict) -> list[str]:
    gi = root / ".gitignore"
    have = block(gi.read_text(encoding="utf-8"), IGNORE_BEGIN, IGNORE_END) if gi.exists() else None
    if have is None:
        return [f".gitignore: no `{IGNORE_BEGIN}` ... `end` block mirroring {CONFIG}'s never_store paths"]
    want = never_store_paths(cfg)
    out = [f".gitignore: never-store path `{p}` is not in the mirror block" for p in want if p not in have]
    out += [f".gitignore: the mirror block has `{p}`, which {CONFIG}'s never_store does not list" for p in have if p not in want]
    own = house_paths(cfg)
    have_own = block(gi.read_text(encoding="utf-8"), HOUSE_BEGIN, HOUSE_END)
    if own and have_own is None:
        out.append(f".gitignore: no `{HOUSE_BEGIN}` ... `end` block carrying {CONFIG}'s house_never_store paths")
    elif have_own is not None:
        out += [f".gitignore: this house's never-store path `{p}` is not in its block" for p in own if p not in have_own]
        out += [f".gitignore: this house's block has `{p}`, which {CONFIG}'s house_never_store does not list"
                for p in have_own if p not in own]
    return out


def check_tracked(root: Path, cfg: dict) -> list[str]:
    out = []
    cats = dict((cfg.get("never_store") or {}).get("paths") or {})
    cats.update((cfg.get("house_never_store") or {}).get("paths") or {})
    for category, pats in cats.items():
        with tempfile.NamedTemporaryFile("w", suffix=".ignore", delete=False) as f:
            f.write("\n".join(pats) + "\n")
        hit = git(root, "ls-files", "-c", "-i", f"--exclude-from={f.name}").stdout.split("\n")
        Path(f.name).unlink(missing_ok=True)
        out += [f"never-store: `{h}` is tracked and on the list ({category})" for h in hit if h.strip()]
    return out


def is_text(p: Path) -> bool:
    if p.suffix.lower() in TEXT_SUFFIXES:
        return True
    try:
        with open(p, "rb") as f:
            return b"\0" not in f.read(4096)
    except OSError:
        return False


def check_content(root: Path, cfg: dict) -> list[str]:
    """Every tracked text file but the config that holds the patterns, read for the
    atlas's content patterns (a credential pasted into a document has no path to stop)."""
    pats = [re.compile(p) for p in never_store_content(cfg)]
    if not pats:
        return []
    out = []
    for rel in git(root, "ls-files", "-c", "-z").stdout.split("\0"):
        p = root / rel
        if not rel or rel in (CONFIG, cfg.get("never_store_file")) or not p.is_file() or not is_text(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for cp in pats:
            if cp.search(text):
                out.append(f"never-store: `{rel}` matches the content pattern `{cp.pattern}`; its contents never enter the house")
                break
    return out


def check_owned(root: Path, cfg: dict, base: str):
    """(findings, note): a branch that changes an owned file must contain `base`."""
    owned = (cfg.get("owned") or {})
    files = owned.get("files", [])
    tip = git(root, "rev-parse", "-q", "--verify", f"{base}^{{commit}}").stdout.strip()
    if not tip:
        return [], f"owned files: NOT RUN: no `{base}` here to compare with"
    merging = git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD").stdout.strip()
    if any(git(root, "merge-base", "--is-ancestor", tip, h).returncode == 0 for h in ("HEAD", merging) if h):
        return [], None          # the branch contains the base, or is merging it in now
    mb = git(root, "merge-base", tip, "HEAD").stdout.strip()
    if not mb and git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        return [], (f"owned files: NOT DECIDED: this clone is shallow and holds no commit common to HEAD and {base}; "
                    "deepen it (git fetch --deepen=1000 origin) and run again")
    changed = set(git(root, "diff", "--name-only", mb, "--").stdout.split()) if mb else set(files)
    out = [f"owned: `{f}` is changed on a branch that does not contain {base} ({tip[:7]}); rebase on main before touching it "
           f"(one owner at a time: {owned.get('owner', 'the line')})" for f in files if f in changed]
    return out, None


def run_check(root: Path, base: str) -> int:
    cfg_path = root / CONFIG
    if not cfg_path.exists():
        print(f"house guards: {CONFIG} is missing: nothing declares the guards, so none can be checked")
        return 1
    cfg = load_cfg(root)
    findings, notes = [], []
    findings += check_union(root, cfg)
    findings += check_ids(root, cfg)
    findings += check_branch_log(root)
    findings += check_mirror(root, cfg)
    if is_repo(root):
        findings += check_tracked(root, cfg)
        findings += check_content(root, cfg)
        owned, note = check_owned(root, cfg, base)
        findings += owned
        if note:
            notes.append(note)
    else:
        notes.append("tracked never-store files, content patterns and owned files: NOT RUN: no repository on this "
                     "surface (an unpacked archive carries no .git); a check that cannot run is not a pass")
    for f in findings:
        print(f"  {f}")
    for n in notes:
        print(f"  {n}")
    print(f"house guards: {len(findings)} finding(s): union logs {len(cfg.get('union_logs', []))}, id spaces "
          f"{len(cfg.get('id_spaces', []))}, never-store paths {len(never_store_paths(cfg))}, content patterns "
          f"{len(never_store_content(cfg))}, this house's own never-store paths {len(house_paths(cfg))}, owned files "
          f"{len((cfg.get('owned') or {}).get('files', []))}")
    return 1 if findings else 0


# ------------------------------------------------------------------ the atlas's copy (mirror)

def parse_never_store(text: str) -> dict:
    """The atlas's never-store.yaml: top-level keys, each a list of scalars. A line reader,
    so the check needs no YAML library; a line it cannot read raises, never guesses."""
    out, key = {}, None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(?:#.*)?$", line)
        if m:
            key = m.group(1)
            out.setdefault(key, [])
            continue
        m = re.match(r"""^\s+-\s+("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^#\s][^#]*?)\s*(?:#.*)?$""", line)
        if m and key:
            v = m.group(1)
            if v.startswith('"'):
                v = json.loads(v)
            elif v.startswith("'"):
                v = v[1:-1].replace("''", "'")
            out[key].append(v)
            continue
        raise ValueError(f"an unreadable line in {NEVER_STORE}: {line!r}")
    return out


def atlas_repo(root: Path) -> str | None:
    p = root / "SUBSTRATE.md"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    m = re.search(r"(?m)^\|\s*atlas\s*\|[^|]*github\.com/([\w.-]+/[\w.-]+)", text)
    return m.group(1) if m else None


def read_atlas_list(root: Path, args: list) -> tuple[str, str]:
    """(text, where) of the atlas's never-store.yaml, or raise RuntimeError(why)."""
    val = lambda flag: args[args.index(flag) + 1] if flag in args[:-1] else None  # noqa: E731
    sha = val("--commit")
    if val("--atlas"):
        d = Path(val("--atlas"))
        if not d.exists():
            raise RuntimeError(f"no atlas checkout at {d}")
        refs = [sha] if sha else ["origin/main", "main", "HEAD"]
        for ref in refs:
            p = git(d, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}")
            if p.returncode == 0 and p.stdout.strip():
                full = p.stdout.strip()
                s = git(d, "show", f"{full}:{NEVER_STORE}")
                if s.returncode != 0:
                    raise RuntimeError(f"{NEVER_STORE} is not at {full[:7]} in {d}")
                return s.stdout, f"checkout {d} at {full[:7]}"
        raise RuntimeError(f"the atlas checkout at {d} has no main to read")
    repo = val("--repo") or atlas_repo(root)
    if not repo:
        raise RuntimeError("SUBSTRATE.md names no atlas repository on GitHub")
    try:
        if not sha:
            p = subprocess.run(["gh", "api", f"repos/{repo}/commits/main", "--jq", ".sha"],
                               capture_output=True, text=True, timeout=60)
            if p.returncode != 0 or not p.stdout.strip():
                raise RuntimeError(f"gh could not read {repo}'s main ({(p.stderr or 'no answer').strip()[:120]})")
            sha = p.stdout.strip()
        p = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw",
                            f"repos/{repo}/contents/{NEVER_STORE}?ref={sha}"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"gh could not run ({type(e).__name__})")
    if p.returncode != 0:
        raise RuntimeError(f"gh could not read {NEVER_STORE} at {sha[:7]} ({(p.stderr or '').strip()[:120]})")
    return p.stdout, f"api {repo} at {sha[:7]}"


def run_mirror(root: Path, args: list) -> int:
    cfg = load_cfg(root)
    try:
        text, where = read_atlas_list(root, args)
    except RuntimeError as e:
        print(f"never-store mirror: UNREACHABLE: {e}; not a match, and the check goes on")
        return 0
    try:
        atlas = parse_never_store(text)
    except ValueError as e:
        print(f"never-store mirror: UNREACHABLE: {e}")
        return 0
    out = []
    for key, mine in (("paths", never_store_paths(cfg)), ("content", never_store_content(cfg))):
        theirs = [str(x) for x in atlas.get(key) or []]
        out += [f"{key}: the atlas lists `{x}`, which {CONFIG} does not" for x in theirs if x not in mine]
        out += [f"{key}: {CONFIG} lists `{x}`, which the atlas does not" for x in mine if x not in theirs]
    for f in out:
        print(f"  {f}")
    if out:
        print(f"never-store mirror: DIFFERS from the atlas ({where}): {len(out)} difference(s); the atlas wins, "
              f"so re-copy it (tools/atlas_copy.py write <atlas>), correct .gitignore and report the difference (IR-14)")
        return 1
    print(f"never-store mirror: CURRENT with the atlas ({where}): {len(never_store_paths(cfg))} paths, "
          f"{len(never_store_content(cfg))} content patterns")
    return 0


# ------------------------------------------------------------------ the banned addresses (fingerprints only)

def fingerprint(address: str) -> str:
    return hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()


def parse_banned(text: str) -> tuple[str, dict[str, str]]:
    """`since` and {fingerprint: ruling} from the atlas's ops/banned-authors.yaml: a line reader, so no YAML
    library is needed; a fingerprints entry it cannot read raises, never guesses."""
    since, fps, inside = "", {}, False
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        m = re.match(r"""^since:\s*["']?([^"'\s]+)["']?\s*$""", line)
        if m:
            since = m.group(1)
            continue
        if re.match(r"^fingerprints:\s*$", line):
            inside = True
            continue
        if inside and line.startswith((" ", "-")):
            m = re.search(r"sha256:\s*['\"]?([0-9a-fA-F]{64})", line)
            if not m:
                raise ValueError(f"an unreadable fingerprints entry in {BANNED}: {line.strip()[:40]!r}")
            r = re.search(r"ruling:\s*['\"]?([A-Za-z0-9.\-]+)", line)
            fps[m.group(1).lower()] = r.group(1) if r else ""
            continue
        inside = False
    return since, fps


def read_banned(root: Path, args: list) -> tuple[str, str]:
    """(text, where) of the banned list, or raise RuntimeError(why)."""
    val = lambda flag: args[args.index(flag) + 1] if flag in args[:-1] else None  # noqa: E731
    if val("--file"):
        f = Path(val("--file"))
        if not f.is_file():
            raise RuntimeError(f"no banned list at {f}")
        return f.read_text(encoding="utf-8"), f"file {f}"
    sha = val("--commit")
    if val("--atlas"):
        d = Path(val("--atlas"))
        if not d.exists():
            raise RuntimeError(f"no atlas checkout at {d}")
        for ref in ([sha] if sha else ["origin/main", "main", "HEAD"]):
            p = git(d, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}")
            if p.returncode == 0 and p.stdout.strip():
                full = p.stdout.strip()
                s = git(d, "show", f"{full}:{BANNED}")
                if s.returncode != 0:
                    raise RuntimeError(f"{BANNED} is not at {full[:7]} in {d}")
                return s.stdout, f"checkout {d} at {full[:7]}"
        raise RuntimeError(f"the atlas checkout at {d} has no main to read")
    repo = val("--repo") or atlas_repo(root)
    if not repo:
        raise RuntimeError("SUBSTRATE.md names no atlas repository on GitHub")
    try:
        if not sha:
            p = subprocess.run(["gh", "api", f"repos/{repo}/commits/main", "--jq", ".sha"],
                               capture_output=True, text=True, timeout=60)
            if p.returncode != 0 or not p.stdout.strip():
                raise RuntimeError(f"gh could not read {repo}'s main ({(p.stderr or 'no answer').strip()[:120]})")
            sha = p.stdout.strip()
        p = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw",
                            f"repos/{repo}/contents/{BANNED}?ref={sha}"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"gh could not run ({type(e).__name__})")
    if p.returncode != 0:
        raise RuntimeError(f"gh could not read {BANNED} at {sha[:7]} ({(p.stderr or '').strip()[:120]})")
    return p.stdout, f"api {repo} at {sha[:7]}"


def scan_banned(root: Path, since: str, fps: dict[str, str], base: str) -> tuple[list[str], list[str]]:
    """(findings, notes). Each finding names a commit or file and a fingerprint's first 8 characters."""
    out, notes = [], []
    hit = lambda a: (fingerprint(a) if a.strip() and fingerprint(a) in fps else "")  # noqa: E731
    email = git(root, "config", "user.email").stdout.strip()
    if hit(email):
        h = hit(email)
        out.append(f"git user.email matches fingerprint {h[:8]} ({fps[h]}): every commit made here would carry it")
    refs = [r for r in (base, "HEAD") if git(root, "rev-parse", "-q", "--verify", f"{r}^{{commit}}").returncode == 0]
    if not refs:
        notes.append("commits: NOT RUN: no main and no HEAD to read")
    seen, n = set(), 0
    for ref in refs:
        args = ["log", ref, "--format=%H%x00%ae%x00%ce"] + ([f"--since={since}"] if since else [])
        for line in git(root, *args).stdout.splitlines():
            sha, ae, ce = (line.split("\x00") + ["", "", ""])[:3]
            if sha in seen:
                continue
            seen.add(sha)
            n += 1
            for role, addr in (("author", ae), ("committer", ce)):
                h = hit(addr)
                if h:
                    out.append(f"commit {sha[:8]} {role} matches fingerprint {h[:8]} ({fps[h]})")
    staged = git(root, "diff", "--cached", "-U0", "--no-color", "--no-ext-diff").stdout
    rel = None
    for line in staged.splitlines():
        if line.startswith("+++ "):
            rel = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("+") and rel:
            for a in EMAIL.findall(line):
                h = hit(a)
                if h:
                    out.append(f"staged `{rel}` carries an address matching fingerprint {h[:8]} ({fps[h]})")
    # AT.765: a public house commits no fingerprint, so a tracked file carrying one is refused
    for rel in git(root, "ls-files", "-c", "-z").stdout.split("\0"):
        p = root / rel
        if not rel or not p.is_file() or not is_text(p):
            continue
        for hx in set(HEX64.findall(p.read_text(encoding="utf-8", errors="replace"))):
            if hx.lower() in fps:
                out.append(f"`{rel}` holds fingerprint {hx.lower()[:8]} ({fps[hx.lower()]}): this public house never "
                           "commits a fingerprint (AT.765)")
    notes.append(f"read: git user.email, {n} commit(s) on {' and '.join(refs) or 'nothing'}"
                 f"{' committed after ' + since if since else ''}, the staged changes and every tracked text file")
    return out, notes


def run_banned(root: Path, args: list) -> int:
    try:
        text, where = read_banned(root, args)
        since, fps = parse_banned(text)
    except (RuntimeError, ValueError) as e:
        print(f"banned addresses: UNREACHABLE: {e}; not a clean read, and the check goes on")
        return 0
    if not fps:
        print(f"banned addresses: the list ({where}) holds no fingerprints; nothing checked")
        return 0
    if not is_repo(root):
        print("banned addresses: NOT RUN: no repository on this surface; a check that cannot run is not a pass")
        return 1
    base = args[args.index("--base") + 1] if "--base" in args[:-1] else "origin/main"
    found, notes = scan_banned(root, since, fps, base)
    for f in found:
        print(f"  {f}")
    for n in notes:
        print(f"  {n}")
    if found:
        print(f"banned addresses: BANNED: {len(found)} finding(s) against {len(fps)} fingerprint(s) ({where}); "
              "no override exists: the commit stops, and a merged one is reported to the operator at once")
        return 1
    print(f"banned addresses: CLEAN against {len(fps)} fingerprint(s) ({where})")
    return 0


def main(argv) -> int:
    args = argv[1:]
    verbs = ("check", "mirror", "banned")
    root = Path(args.pop(0)).resolve() if args and args[0] not in verbs and Path(args[0]).is_dir() else HERE.parent
    if not args or args[0] not in verbs:
        print(__doc__)
        return 2
    if args[0] == "mirror":
        return run_mirror(root, args[1:])
    if args[0] == "banned":
        return run_banned(root, args[1:])
    base = args[args.index("--base") + 1] if "--base" in args[:-1] else "origin/main"
    return run_check(root, base)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
