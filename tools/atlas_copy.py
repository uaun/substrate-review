#!/usr/bin/env python3
"""atlas_copy.py: the two things this house copies from the atlas, each stamped with the atlas commit it was
read at (AP-review-0001, A4 and A5). Standard library only; the atlas is private and this house is public, so
the copies are what the house's checks and CI read, and an atlas checkout is needed only to write or re-check
them.

  catalog/frameworks.json   the registry's slugs (`frameworks/REGISTRY.yaml`), every registered framework,
                            the closed houses' too, since a proposal may touch one; the form's dropdown and
                            the intake's unknown-framework check read it
  catalog/never-store.json  the never-store list (`charter/never-store.yaml`): the path globs and the content
                            patterns; the intake's never-store check and the tree guard read it

  python3 -I -B tools/atlas_copy.py write ATLAS     write both copies from an atlas checkout at its HEAD
  python3 -I -B tools/atlas_copy.py check [ATLAS]   both copies well-formed; with ATLAS, equal in content to
                                                    what `write` would produce there (a newer atlas commit
                                                    with the same content is said, not a failure)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

REGISTRY = "frameworks/REGISTRY.yaml"
NEVER_STORE = "charter/never-store.yaml"
SLUG = re.compile(r"^- slug: ([a-z0-9][a-z0-9-]*)\s*$", re.M)
ITEM = re.compile(r'^\s+-\s+("(?:[^"\\]|\\.)*")\s*(?:#.*)?$')


def atlas_commit(atlas: Path) -> str:
    return subprocess.run(["git", "-C", str(atlas), "rev-parse", "--short=8", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()


def read_slugs(text: str) -> list[str]:
    body = text.split("\nframeworks:\n", 1)[-1]
    return sorted(SLUG.findall(body))


def read_never_store(text: str) -> dict:
    """The two lists of the atlas's never-store file. Its items are YAML double-quoted strings, whose escapes
    (`\\\\`, `\\"`) JSON reads the same way."""
    out, section = {"paths": [], "content": []}, None
    for line in text.splitlines():
        if re.match(r"^(paths|content):\s*$", line):
            section = line.split(":")[0]
            continue
        if re.match(r"^\S", line):
            section = None
            continue
        m = ITEM.match(line)
        if m and section:
            out[section].append(json.loads(m.group(1)))
    return out


def build(atlas: Path) -> dict[str, dict]:
    commit = atlas_commit(atlas)
    reg = (atlas / REGISTRY).read_text(encoding="utf-8")
    ns = (atlas / NEVER_STORE).read_text(encoding="utf-8")
    return {
        "frameworks.json": {"source": REGISTRY, "atlas_commit": commit,
                            "source_sha256": lib.sha256(reg.encode("utf-8")), "slugs": read_slugs(reg)},
        "never-store.json": {"source": NEVER_STORE, "atlas_commit": commit,
                             "source_sha256": lib.sha256(ns.encode("utf-8")), **read_never_store(ns)},
    }


def dump(value: dict) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def well_formed(root: Path) -> list[str]:
    problems = []
    try:
        fw = lib.read_json(root / lib.CATALOG / "frameworks.json")
        ns = lib.read_json(root / lib.CATALOG / "never-store.json")
    except (OSError, ValueError) as e:
        return [f"a copy cannot be read: {e}"]
    for name, doc, keys in (("frameworks.json", fw, ("slugs",)), ("never-store.json", ns, ("paths", "content"))):
        for k in ("source", "atlas_commit", "source_sha256", *keys):
            if k not in doc:
                problems.append(f"{name}: no `{k}`")
    slugs = fw.get("slugs", [])
    if not slugs or slugs != sorted(set(slugs)) or not all(re.fullmatch(r"[a-z0-9][a-z0-9-]*", s) for s in slugs):
        problems.append("frameworks.json: the slugs are not a sorted list of distinct slugs")
    if not ns.get("paths") or not ns.get("content"):
        problems.append("never-store.json: a list is empty")
    for rx in ns.get("content", []):
        try:
            re.compile(rx, re.I)
        except re.error:
            problems.append(f"never-store.json: a content pattern does not compile: {rx}")
    return problems


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("write", "check"):
        print(__doc__)
        return 2
    root = lib.ROOT
    if argv[0] == "write":
        if len(argv) < 2:
            print("atlas_copy: write needs an atlas checkout")
            return 2
        for name, doc in build(Path(argv[1])).items():
            (root / lib.CATALOG / name).write_text(dump(doc), encoding="utf-8")
        print(f"atlas_copy: wrote catalog/frameworks.json and catalog/never-store.json")
        return 0
    problems = well_formed(root)
    if len(argv) > 1 and not problems:
        atlas = Path(argv[1])
        if not (atlas / REGISTRY).exists():
            print(f"atlas_copy: UNREACHABLE: {atlas} holds no {REGISTRY}; the copies are checked for shape only")
        else:
            for name, want in build(atlas).items():
                have = lib.read_json(root / lib.CATALOG / name)
                strip = lambda d: {k: v for k, v in d.items() if k not in ("atlas_commit", "source_sha256")}  # noqa: E731
                if strip(have) != strip(want):
                    problems.append(f"{name}: differs from the atlas at {want['atlas_commit']} (copied at "
                                    f"{have.get('atlas_commit')}); run `tools/atlas_copy.py write <atlas>`")
                elif have.get("atlas_commit") != want["atlas_commit"]:
                    print(f"atlas_copy: {name} was copied at {have.get('atlas_commit')}; the atlas at "
                          f"{want['atlas_commit']} holds the same content")
    for p in problems:
        print(f"ATLAS COPY: {p}")
    print(f"atlas_copy check: {len(problems)} findings")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
