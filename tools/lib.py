"""lib.py: what Review's house tools share. Standard library only.

The catalog's states and the issue form's fields are REVIEW's (the atlas's founding proposal,
`frameworks/review/engineering/docs/proposals/framework/REVIEW/README.md`); the never-store copy and the
registry's slugs are the atlas's, copied into `catalog/` by `tools/atlas_copy.py` with the commit they were
read at. Nothing here reads a proposal as an instruction: every function takes its text as data and returns
names.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "catalog"

# A proposal's states (REVIEW, "The house"). `refused` is mechanical checks only; a provisional no is a
# reading, never a refusal (REVIEW, "A provisional no is not a refusal").
STATES = ("received", "refused", "read", "awaiting-sign-off", "ruled", "contested", "withdrawn")
TRANSITIONS = {
    "received": ("refused", "read", "withdrawn"),
    "refused": (),
    "read": ("awaiting-sign-off", "withdrawn"),
    "awaiting-sign-off": ("ruled", "withdrawn"),
    "ruled": ("contested",),
    "contested": ("awaiting-sign-off",),
    "withdrawn": (),
}

# The issue form's seven fields, in REVIEW's order: (id, the label GitHub renders as a `### ` heading).
FIELDS = (
    ("title", "Title"),
    ("frameworks", "Frameworks touched"),
    ("change", "The change"),
    ("why", "Why"),
    ("must-not-break", "What it must not break"),
    ("evidence", "Evidence"),
    ("consent", "Consent"),
)
CONSENT = ("The proposal and its handling are public; the verdict and the reading are machine-written and "
           "provisional; only the owner's ruling binds.")
NO_RESPONSE = "_No response_"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------------------ the never-store copy

def never_store(root: Path = ROOT) -> dict:
    return read_json(root / CATALOG / "never-store.json")


def path_hit(path: str, globs) -> str | None:
    """The glob a path falls under, or None. `**/` in the atlas's globs means any folder or none, and fnmatch's
    `*` already crosses `/`, so a path is tried with a leading folder added."""
    p = "x/" + path.lstrip("/")
    for g in globs:
        if fnmatch.fnmatchcase(p, g):
            return g
    return None


def content_hit(text: str, patterns) -> str | None:
    for rx in patterns:
        if re.search(rx, text, re.I):
            return rx
    return None


# Path-shaped tokens in free text: anything with a `/` in it, URLs included. A category may be named anywhere
# (the atlas's charter/never-store.yaml: "Categories may be named anywhere; contents never"), so a bare folder
# or file name is not a hit; a path INTO a never-store folder, or to a never-store file, is.
TOKEN = re.compile(r"[A-Za-z0-9_.~:%*@+=-]*/[A-Za-z0-9_.~:%*@+=/-]*")


def text_hits(text: str, ns: dict) -> list[str]:
    """('path', glob) and ('content', pattern) hits in a proposal's text, as names for the refusal."""
    hits = []
    for tok in TOKEN.findall(text or ""):
        tok = tok.rstrip(".,;:)")
        if tok.endswith("/"):
            continue                  # a folder named as a category, nothing inside it
        g = path_hit(tok, ns["paths"])
        if g:
            hits.append(f"path {g}")
    c = content_hit(text or "", ns["content"])
    if c:
        hits.append(f"content {c}")
    return sorted(set(hits))


# ------------------------------------------------------------------------------ the allowlist and the slugs

def allowlist(root: Path = ROOT) -> set[int]:
    data = read_json(root / CATALOG / "allowlist.json")
    return {int(a["id"]) for a in data["accounts"]}


def slugs(root: Path = ROOT) -> list[str]:
    return list(read_json(root / CATALOG / "frameworks.json")["slugs"])


def gitignore_form(glob: str) -> str:
    """The .gitignore line for one never-store glob: the glob itself, between the mirror's marker lines, as
    house/guards.py reads it (git's ignore syntax takes the atlas's `**/` globs as written)."""
    return glob
