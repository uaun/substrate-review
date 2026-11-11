#!/usr/bin/env python3
"""The boot's self-check (IR-17, IR-18; AP-review-0002, A7; ported from Jetsam's house/ at f97c6f7 for Review's house (AP-review-0002), which re-derived the soul house's tools): the house reads its own row in the
atlas's registry and sets it against itself.

At every boot the house reads `frameworks/REGISTRY.yaml` at the atlas's main and finds the row for
the slug its `SUBSTRATE.md` records. It compares the repository it is (this checkout's `origin`)
and the stage, parent, house and gate its `SUBSTRATE.md` records with that row. A house row with
no `gate` reads open, by AT.142, the ruling that gave every house a gate.

  python3 -I -B house/selfcheck.py [ROOT] [--atlas DIR | --repo OWNER/NAME] [--commit SHA]

SOURCE is `--atlas DIR` (a local git checkout of the atlas; its origin/main, else main, else
HEAD, unless `--commit SHA`) or, by default, the GitHub API through `gh`, for the repository
`SUBSTRATE.md`'s atlas row names (or `--repo OWNER/NAME`).

Prints the gate line the boot checklist shows, then MATCH, or DIFFERS with each difference
named. A difference is answered by a correcting card: on an atlas branch when the session can
reach the atlas, otherwise in its handoff and close under the heading UNREGISTERED (Rule 1).
Exit 0 on MATCH; 1 on DIFFERS; 3 when the registry holds this house's gate closed, which stops
all work here unless the operator explicitly asks (the house rule, AT.142); 0 on UNREACHABLE,
which is said and never taken for a match. The registry is read by a line reader, so no YAML
library is needed; a row it cannot read is UNREACHABLE, never guessed.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = "frameworks/REGISTRY.yaml"
GATE_DEFAULT_RULING = "AT.142"
FIELDS = ("stage", "parent", "house")


def git(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def registration(root: Path) -> dict:
    """The registration table of SUBSTRATE.md: {field: value}."""
    p = root / "SUBSTRATE.md"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    out = {}
    for m in re.finditer(r"(?m)^\|\s*([a-z]+)\s*\|\s*(.*?)\s*\|\s*$", text):
        out.setdefault(m.group(1), m.group(2))
    return out


def repo_of(url: str | None) -> str | None:
    """owner/name of a GitHub URL or a git remote (proxied remotes included), lowercased."""
    if not url:
        return None
    u = url.strip().rstrip("/")
    u = re.sub(r"\.git$", "", u)
    parts = [x for x in re.split(r"[/:]", u) if x]
    if len(parts) < 2:
        return None
    return f"{parts[-2]}/{parts[-1]}".lower()


def scalar(v: str) -> str | None:
    v = v.strip()
    if v in ("", "null", "~"):
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1].replace("''", "'") if v[0] == "'" else v[1:-1]
    return v


def registry_row(text: str, slug: str) -> dict | None:
    """The row for `slug`: its top-level scalars and its gate's state and ruling; None when absent.
    Rows are `- slug: <slug>` blocks under `frameworks:`, keys two spaces in."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(rf"^- slug:\s*['\"]?{re.escape(slug)}['\"]?\s*$", l)), None)
    if start is None:
        return None
    row, i, in_gate = {"slug": slug}, start + 1, False
    while i < len(lines) and not lines[i].startswith("- ") and not re.match(r"^\S", lines[i]):
        line = lines[i]
        i += 1
        m = re.match(r"^  ([a-z_]+):\s*(.*)$", line)
        if m:
            key, rest = m.group(1), m.group(2)
            in_gate = key == "gate" and not rest.strip()
            if rest.strip() and not rest.strip().startswith(("|", ">")):
                row[key] = scalar(rest)
            elif key == "gate":
                row["gate"] = {}
            continue
        m = re.match(r"^    ([a-z_]+):\s*(.*)$", line)
        if m and in_gate:
            row["gate"][m.group(1)] = scalar(m.group(2))
    return row


def read_registry(root: Path, args: list) -> tuple[str, str]:
    """(text, where), or raise RuntimeError(why)."""
    val = lambda flag: args[args.index(flag) + 1] if flag in args[:-1] else None  # noqa: E731
    sha = val("--commit")
    if val("--atlas"):
        d = Path(val("--atlas"))
        if not d.exists():
            raise RuntimeError(f"no atlas checkout at {d}")
        for ref in ([sha] if sha else ["origin/main", "main", "HEAD"]):
            p = git(d, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}")
            if p.returncode == 0 and p.stdout.strip():
                full = p.stdout.strip()
                s = git(d, "show", f"{full}:{REGISTRY}")
                if s.returncode != 0:
                    raise RuntimeError(f"{REGISTRY} is not at {full[:7]} in {d}")
                return s.stdout, f"checkout {d} at {full[:7]}"
        raise RuntimeError(f"the atlas checkout at {d} has no main to read")
    reg = registration(root)
    repo = val("--repo") or repo_of((reg.get("atlas") or "").split(",")[0])
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
                            f"repos/{repo}/contents/{REGISTRY}?ref={sha}"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"gh could not run ({type(e).__name__})")
    if p.returncode != 0:
        raise RuntimeError(f"gh could not read {REGISTRY} at {sha[:7]} ({(p.stderr or '').strip()[:120]})")
    return p.stdout, f"api {repo} at {sha[:7]}"


def compare(root: Path, row: dict | None, reg: dict) -> tuple[list[str], dict]:
    """(differences, the registry's gate {state, ruling})."""
    slug = reg.get("slug") or ""
    if row is None:
        return [f"the atlas's registry holds no row for `{slug}`: this house has not announced itself (IR-18)"], {}
    out = []
    for f in FIELDS:
        mine, theirs = reg.get(f), row.get(f)
        if f == "house":
            mine, theirs = repo_of(mine), repo_of(theirs)
        if (mine or None) != (theirs or None):
            out.append(f"{f}: the registry has `{theirs}`, SUBSTRATE.md has `{mine}`")
    origin = repo_of(git(root, "remote", "get-url", "origin").stdout.strip() or None)
    if origin and repo_of(row.get("house")) != origin:
        out.append(f"repository: this checkout is `{origin}`, the registry's house is `{repo_of(row.get('house'))}`")
    g = row.get("gate") if isinstance(row.get("gate"), dict) else {}
    gate = {"state": (g.get("state") or "open"), "ruling": g.get("ruling") or GATE_DEFAULT_RULING}
    mine_gate = (reg.get("gate") or "").split(",")[0].split()[0].lower() if reg.get("gate") else None
    if mine_gate != gate["state"]:
        out.append(f"gate: the registry has `{gate['state']}` ({gate['ruling']}), SUBSTRATE.md has `{mine_gate}`")
    return out, gate


def main(argv) -> int:
    args = argv[1:]
    root = Path(args.pop(0)).resolve() if args and not args[0].startswith("--") and Path(args[0]).is_dir() else HERE.parent
    reg = registration(root)
    slug = reg.get("slug")
    if not slug:
        print("self-check: SUBSTRATE.md records no slug; the house cannot name its own row")
        return 1
    try:
        text, where = read_registry(root, args)
    except RuntimeError as e:
        print(f"self-check: UNREACHABLE: {e}; never a match, and the boot goes on")
        return 0
    try:
        row = registry_row(text, slug)
    except Exception as e:  # noqa: BLE001
        print(f"self-check: UNREACHABLE: the registry row for `{slug}` could not be read ({type(e).__name__})")
        return 0
    diffs, gate = compare(root, row, reg)
    if gate:
        print(f"gate: {gate['state']} ({gate['ruling']}), from the atlas's registry ({where})")
    for d in diffs:
        print(f"  {d}")
    if diffs:
        print(f"self-check: DIFFERS from the registry ({where}): {len(diffs)} difference(s); answer each with a "
              "correcting card on an atlas branch, or in the handoff and close under UNREGISTERED (Rule 1)")
    else:
        print(f"self-check: MATCH with the registry ({where}): slug {slug}, stage {row.get('stage')}, "
              f"parent {row.get('parent')}, house {repo_of(row.get('house'))}")
    if gate.get("state") == "closed":
        print("self-check: the gate is CLOSED: no work in this house unless the operator explicitly asks (AT.142)")
        return 3
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
