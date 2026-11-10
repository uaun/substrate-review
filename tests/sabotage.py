#!/usr/bin/env python3
"""sabotage.py: each check broken once must turn the tests red (B10; train review-T1, A3 and A5).

For every mutation below, a throwaway copy of the house is made, the one check is disabled in it, and the
house's tests are run there; a mutation the tests do not catch is a check nothing tests. Run by the house
check, and by hand:

  python3 -I -B tests/sabotage.py [-v]
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (what is broken, file, the text that does the check, what replaces it)
MUTATIONS = (
    ("catalog: duplicate event id", "tools/catalog.py", 'if e["id"] in seen:', "if False:"),
    ("catalog: a file's keys", "tools/catalog.py", "if set(p) != KEYS:", "if False:"),
    ("catalog: the text never edited", "tools/catalog.py", 'elif p["text_sha256"] != text_sha(t):', "elif False:"),
    ("catalog: legal transitions", "tools/catalog.py",
     'elif e["from"] != prev or e["to"] not in lib.TRANSITIONS.get(prev, ()):', "elif False:"),
    ("catalog: file state against the log", "tools/catalog.py", 'if state.get(pid) != p["state"]:', "if False:"),
    ("catalog: a refusal names its check", "tools/catalog.py", 'if p["state"] == "refused" and not p["checks"]:', "if False:"),
    ("catalog: the allowlist takes ids", "tools/catalog.py",
     "if any(not isinstance(i, int) or isinstance(i, bool) or i <= 0 for i in ids) or len(ids) != len(set(ids)):", "if False:"),
    ("intake: not-allowlisted", "tools/intake.py", "if account not in lib.allowlist(root):", "if False:"),
    ("intake: closed unread", "tools/intake.py",
     'if not isinstance(account, int) or account not in lib.allowlist(root):', "if False:"),
    ("intake: form-shape", "tools/intake.py", 'checks = [] if shape_ok else ["form-shape"]', "checks = []"),
    ("intake: missing-field", "tools/intake.py", 'checks.append("missing-field")', "pass"),
    ("intake: unknown-framework", "tools/intake.py", "if any(f not in slugs for f in fws):", "if False:"),
    ("intake: never-store in a proposal", "tools/intake.py", "if lib.text_hits(joined, lib.never_store(root)):", "if False:"),
    ("intake: instruction marks", "tools/intake.py",
     "return [name for name, rx in INSTRUCTION if text and rx.search(text)]", "return []"),
    ("intake: tree content", "tools/intake.py", 'c = lib.content_hit(text, ns["content"])', "c = None"),
    ("intake: .gitignore mirror", "tools/intake.py", "if lib.gitignore_form(g) not in ignored:", "if False:"),
    ("lib: never-store paths", "tools/lib.py", "if fnmatch.fnmatchcase(p, g):", "if False:"),
    ("form: equal to its generation", "tools/form.py", "if have != generate(root):", "if False:"),
    ("form: REVIEW's order", "tools/form.py", "if order != [label for _, label in lib.FIELDS]:", "if False:"),
    ("atlas copy: slugs sorted and distinct", "tools/atlas_copy.py",
     "if not slugs or slugs != sorted(set(slugs))", "if False and (not slugs or slugs != sorted(set(slugs)))"),
    ("workflow: permissions named", ".github/workflows/intake.yml", "permissions:\n  contents: read", "permissions:\n  contents: write"),
)


def copy_house(dest: Path) -> None:
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "add", "-A"], check=True)


def tests_pass(root: Path) -> bool:
    r = subprocess.run([sys.executable, "-I", "-B", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"],
                       cwd=root, capture_output=True, text=True)
    return r.returncode == 0


def main(argv: list[str]) -> int:
    verbose = "-v" in argv
    base = Path(tempfile.mkdtemp(prefix="review-sabotage-"))
    clean = base / "clean"
    copy_house(clean)
    if not tests_pass(clean):
        print("sabotage: the tests are red before any mutation; fix them first")
        return 1
    missed = []
    for i, (name, rel, old, new) in enumerate(MUTATIONS):
        root = base / f"m{i}"
        copy_house(root)
        f = root / rel
        text = f.read_text(encoding="utf-8")
        if old not in text:
            missed.append(f"{name}: the check's text is not in {rel} (the mutation list is stale)")
            continue
        f.write_text(text.replace(old, new), encoding="utf-8")
        caught = not tests_pass(root)
        if verbose:
            print(f"  {'red ' if caught else 'MISS'}  {name}")
        if not caught:
            missed.append(f"{name}: broken in {rel}, the tests stayed green")
    shutil.rmtree(base, ignore_errors=True)
    for m in missed:
        print(f"SABOTAGE: {m}")
    print(f"sabotage: {len(MUTATIONS) - len(missed)} of {len(MUTATIONS)} broken checks turned the tests red")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
