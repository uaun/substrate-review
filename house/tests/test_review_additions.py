"""What review-T2 adds to Jetsam's kit, or re-derives from it (AP-review-0002, A1, A2, A3 and A7; ratified
AT.769): the never-store list read from the house's one copy, the banned-address check reading the atlas's list
and refusing a committed fingerprint (AT.765), the creation log's seed, the merge commit read after a landing, and
the boot's self-check against the atlas's registry (IR-17, IR-18). The banned, self-check and merge tests are
ported from Jetsam's house/tests/test_jetsam_additions.py at f97c6f7; its `jetsam/local/` tests are left behind.

The prompt's negative controls, each a test named CONTROL or FALSIFIER below: a fixture commit authored by an
address whose fingerprint the test plants is refused; a tracked line holding a planted fingerprint is refused,
never printed whole; a registry row edited to another stage in a test copy of the atlas is named as a difference.

No address in this file is real: each is invented for the test and hashed by it.

Run: bash house/check.sh, or python3 -I -B -m pytest -q -p no:cacheprovider house/tests
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOUSE = ROOT / "house"
PY = sys.executable
INVENTED = "nobody-real@example.invalid"          # never anyone's: the test bans it and hashes it
OTHER = "someone-else@example.invalid"


def fp(addr: str) -> str:
    return hashlib.sha256(addr.lower().encode()).hexdigest()


@pytest.fixture
def env(tmp_path):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = t\n\temail = t@t\n[commit]\n\tgpgsign = false\n"
                   "[init]\n\tdefaultBranch = main\n[advice]\n\tdetachedHead = false\n")
    base = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "GIT_AUTHOR", "GIT_COMMITTER"))}
    base.update(GIT_CONFIG_GLOBAL=str(cfg), GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")
    return base


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def git(repo, *args, env=None):
    return run(["git", "-C", str(repo), *args], env=env)


def tool(repo, name, *args, env=None):
    return run([PY, "-I", "-B", str(repo / "house" / name), str(repo), *args], env=env)


def live_config() -> dict:
    return json.loads((HOUSE / "guards.json").read_text(encoding="utf-8"))


def house_repo(tmp_path, env) -> Path:
    """A repository carrying this house's live guards, guards config, .gitattributes and .gitignore."""
    h = tmp_path / "h"
    run(["git", "init", "-q", "-b", "main", str(h)], env=env)
    (h / "house").mkdir()
    for name in ("guards.py", "guards.json", "selfcheck.py"):
        shutil.copy(HOUSE / name, h / "house" / name)
    shutil.copytree(ROOT / "catalog", h / "catalog")        # the never-store copy guards.json names
    shutil.copy(ROOT / ".gitattributes", h / ".gitattributes")
    shutil.copy(ROOT / ".gitignore", h / ".gitignore")
    (h / "WORK.md").write_text("# WORK\n\n<!-- house section: atlas items -->\n- **AP-review-0002/A1** (now). x\n"
                                  "<!-- end house section -->\n")
    (h / "notes.md").write_text("notes\n")
    git(h, "add", "-A", env=env)
    git(h, "commit", "-q", "-m", "seed", env=env)
    return h


def banned_file(tmp_path, *addrs, since="2026-01-01T00:00:00Z") -> Path:
    f = tmp_path / "banned-authors.yaml"
    f.write_text("# a temporary banned list for the test\n"
                 f'since: "{since}"\nfingerprints:\n'
                 + "".join(f"  - {{sha256: {fp(a)}, ruling: AT.000}}\n" for a in addrs))
    return f


# ------------------------------------------------------------------ AT.765: one copy, no committed fingerprint (A1)

def test_the_house_reads_its_one_never_store_copy():
    sys.path.insert(0, str(HOUSE))
    import guards
    cfg = guards.load_cfg(ROOT)
    copy = json.loads((ROOT / "catalog" / "never-store.json").read_text())
    assert guards.never_store_paths(cfg) == copy["paths"] and guards.never_store_content(cfg) == copy["content"]
    assert "never_store" not in json.loads((HOUSE / "guards.json").read_text()), "a second copy in guards.json"


def test_FALSIFIER_a_tracked_file_holding_a_fingerprint_is_refused_and_never_printed_whole(tmp_path, env):
    h = house_repo(tmp_path, env)
    (h / "pasted.md").write_text(f"a pasted list: {fp(INVENTED)}\n")
    git(h, "add", "pasted.md", env=env); git(h, "commit", "-q", "-m", "paste", env=env)
    p = tool(h, "guards.py", "banned", "--file", str(banned_file(tmp_path, INVENTED)), "--base", "main", env=env)
    FP = fp(INVENTED)
    assert p.returncode == 1 and "never commits a fingerprint (AT.765)" in p.stdout, p.stdout
    assert FP not in p.stdout and INVENTED not in p.stdout and FP[:8] in p.stdout, p.stdout


def test_CONTROL_another_hash_in_a_tracked_file_reads_clean(tmp_path, env):
    other = hashlib.sha256(b"not an address").hexdigest()
    h = house_repo(tmp_path, env)
    (h / "hash.md").write_text(f"a content hash: {other}\n")
    git(h, "add", "hash.md", env=env); git(h, "commit", "-q", "-m", "hash", env=env)
    p = tool(h, "guards.py", "banned", "--file", str(banned_file(tmp_path, INVENTED)), "--base", "main", env=env)
    assert p.returncode == 0 and "CLEAN" in p.stdout, p.stdout


def test_the_house_config_names_no_fingerprint_and_no_list():
    sys.path.insert(0, str(HOUSE))
    import guards
    text = (HOUSE / "guards.json").read_text()
    assert not guards.HEX64.search(text) and "fingerprints" not in json.loads(text)["banned"]


# ------------------------------------------------------------------ the banned addresses (A1)

def test_banned_author_is_refused_CONTROL(tmp_path, env):
    h = house_repo(tmp_path, env)
    (h / "x.md").write_text("x\n")
    git(h, "add", "x.md", env=env)
    git(h, "-c", f"user.email={INVENTED}", "commit", "-q", "-m", "a fixture authored with the invented address", env=env)
    clean = tool(h, "guards.py", "banned", "--file", str(banned_file(tmp_path, OTHER)), "--base", "main", env=env)
    assert clean.returncode == 0 and "CLEAN against 1 fingerprint" in clean.stdout, clean.stdout
    r = tool(h, "guards.py", "banned", "--file", str(banned_file(tmp_path, INVENTED)), "--base", "main", env=env)
    assert r.returncode == 1 and "BANNED" in r.stdout, r.stdout
    assert f"author matches fingerprint {fp(INVENTED)[:8]}" in r.stdout and f"committer matches fingerprint {fp(INVENTED)[:8]}" in r.stdout
    assert INVENTED not in r.stdout and INVENTED.split("@")[0] not in r.stdout        # never the address


def test_banned_history_before_since_is_left(tmp_path, env):
    """Commits before the list's `since` are history, left as they are (AT.434), as the atlas reads them."""
    h = house_repo(tmp_path, env)
    (h / "old.md").write_text("old\n")
    git(h, "add", "old.md", env=env)
    old = dict(env, GIT_AUTHOR_DATE="2026-01-02T00:00:00Z", GIT_COMMITTER_DATE="2026-01-02T00:00:00Z")
    git(h, "-c", f"user.email={INVENTED}", "commit", "-q", "-m", "history", env=old)
    after = tool(h, "guards.py", "banned", "--file", str(banned_file(tmp_path, INVENTED, since="2026-06-01T00:00:00Z")),
                 "--base", "main", env=env)
    assert after.returncode == 0, after.stdout
    before = tool(h, "guards.py", "banned", "--file", str(banned_file(tmp_path, INVENTED, since="2025-12-01T00:00:00Z")),
                  "--base", "main", env=env)
    assert before.returncode == 1, before.stdout


def test_banned_staged_address_is_refused(tmp_path, env):
    h = house_repo(tmp_path, env)
    (h / "contact.md").write_text(f"write to {INVENTED} about it\n")
    git(h, "add", "contact.md", env=env)
    r = tool(h, "guards.py", "banned", "--file", str(banned_file(tmp_path, INVENTED)), "--base", "main", env=env)
    assert r.returncode == 1 and f"staged `contact.md` carries an address matching fingerprint {fp(INVENTED)[:8]}" in r.stdout
    assert INVENTED not in r.stdout


def test_banned_user_email_is_refused(tmp_path, env):
    h = house_repo(tmp_path, env)
    git(h, "config", "user.email", INVENTED.upper(), env=env)                  # the lowercase form is hashed
    r = tool(h, "guards.py", "banned", "--file", str(banned_file(tmp_path, INVENTED)), "--base", "main", env=env)
    assert r.returncode == 1 and "git user.email matches fingerprint" in r.stdout, r.stdout


def test_banned_unreachable_is_said_and_green(tmp_path, env):
    h = house_repo(tmp_path, env)
    r = tool(h, "guards.py", "banned", "--atlas", str(tmp_path / "nowhere"), env=env)
    assert r.returncode == 0 and "UNREACHABLE" in r.stdout and "not a clean read" in r.stdout, r.stdout


def test_banned_reads_the_atlas_checkout(tmp_path, env):
    h = house_repo(tmp_path, env)
    a = tmp_path / "atlas"
    run(["git", "init", "-q", "-b", "main", str(a)], env=env)
    (a / "ops").mkdir()
    shutil.copy(banned_file(tmp_path, INVENTED), a / "ops" / "banned-authors.yaml")
    git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "list", env=env)
    git(h, "config", "user.email", INVENTED, env=env)
    r = tool(h, "guards.py", "banned", "--atlas", str(a), env=env)
    assert r.returncode == 1 and "checkout" in r.stdout, r.stdout


# ------------------------------------------------------------------ the creation log's seed (A2)


# ------------------------------------------------------------------ the creation log's seed (A2)

def test_live_log_names_review_t1_s_branch_as_claudes():
    rows = [json.loads(l) for l in (HOUSE / "branches.jsonl").read_text().splitlines() if l.strip()]
    created = {r["branch"]: r for r in rows if r["event"] == "created"}
    b = created["session/2026-11-10/01-review-t1-setup"]
    assert b["by"] == "claude" and "recorded after the fact" in b["note"] and "merged into main at 8af23f4" in b["note"], b



SUBSTRATE = ("# SUBSTRATE.md\n\n| field | value |\n| --- | --- |\n| slug | review |\n| name | Substrate Review |\n"
             "| stage | house |\n| parent | reflection |\n| house | https://github.com/uaun/substrate-review |\n"
             "| gate | open, by DU's ruling AT.142: sessions opened for this house work here as usual |\n"
             "| atlas | https://github.com/uaun/substrate-atlas, `frameworks/REGISTRY.yaml` |\n")
ROW = ("- slug: review\n  name: Substrate Review\n  stage: house\n  parent: reflection\n"
       "  origin: founding proposal REVIEW\n  house: https://github.com/uaun/substrate-review\n  registered: '2026-10-27'\n"
       "  purpose:\n    sentence: 'Substrate Review is: a test.'\n    approved: AT.373\n")
REGISTRY = ("# the registry\nframeworks:\n- slug: grade\n  name: Grade\n  stage: house\n  parent: null\n"
            "  house: https://github.com/uaun/substrate-grade\n" + "{row}" + "- slug: kernel\n  stage: house\n")


def atlas_with(tmp_path, env, row: str) -> Path:
    a = tmp_path / "atlas"
    if a.exists():
        shutil.rmtree(a)
    run(["git", "init", "-q", "-b", "main", str(a)], env=env)
    (a / "frameworks").mkdir()
    (a / "frameworks" / "REGISTRY.yaml").write_text(REGISTRY.replace("{row}", row))
    git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "registry", env=env)
    return a


def self_house(tmp_path, env) -> Path:
    h = house_repo(tmp_path, env)
    (h / "SUBSTRATE.md").write_text(SUBSTRATE)
    git(h, "remote", "add", "origin", "https://github.com/uaun/substrate-review.git", env=env)
    return h


def test_selfcheck_matches_its_row(tmp_path, env):
    h = self_house(tmp_path, env)
    r = tool(h, "selfcheck.py", "--atlas", str(atlas_with(tmp_path, env, ROW)), env=env)
    assert r.returncode == 0 and "self-check: MATCH" in r.stdout and "gate: open (AT.142)" in r.stdout, r.stdout


def test_selfcheck_names_a_stage_edited_in_the_registry_CONTROL(tmp_path, env):
    h = self_house(tmp_path, env)
    r = tool(h, "selfcheck.py", "--atlas", str(atlas_with(tmp_path, env, ROW.replace("stage: house", "stage: proposal"))), env=env)
    assert r.returncode == 1 and "stage: the registry has `proposal`, SUBSTRATE.md has `house`" in r.stdout, r.stdout
    assert "UNREGISTERED" in r.stdout


def test_selfcheck_names_parent_and_house_differences(tmp_path, env):
    h = self_house(tmp_path, env)
    row = ROW.replace("parent: reflection", "parent: null").replace("substrate-review\n", "substrate-elsewhere\n")
    r = tool(h, "selfcheck.py", "--atlas", str(atlas_with(tmp_path, env, row)), env=env)
    assert r.returncode == 1 and "parent: the registry has `None`" in r.stdout and "house: the registry has" in r.stdout
    assert "repository: this checkout is `uaun/substrate-review`" in r.stdout, r.stdout


def test_selfcheck_closed_gate_stops_work(tmp_path, env):
    h = self_house(tmp_path, env)
    row = ROW + "  gate:\n    state: closed\n    ruling: AT.999\n    since: '2026-11-09'\n"
    r = tool(h, "selfcheck.py", "--atlas", str(atlas_with(tmp_path, env, row)), env=env)
    assert r.returncode == 3 and "gate: closed (AT.999)" in r.stdout and "CLOSED" in r.stdout, r.stdout
    assert "gate: the registry has `closed`" in r.stdout          # SUBSTRATE.md still says open: a difference too


def test_selfcheck_no_row_is_a_house_that_has_not_announced_itself(tmp_path, env):
    h = self_house(tmp_path, env)
    r = tool(h, "selfcheck.py", "--atlas", str(atlas_with(tmp_path, env, "")), env=env)
    assert r.returncode == 1 and "holds no row for `review`" in r.stdout and "IR-18" in r.stdout, r.stdout


def test_selfcheck_unreachable_is_never_a_match(tmp_path, env):
    h = self_house(tmp_path, env)
    r = tool(h, "selfcheck.py", "--atlas", str(tmp_path / "nowhere"), env=env)
    assert r.returncode == 0 and "UNREACHABLE" in r.stdout and "MATCH" not in r.stdout, r.stdout


# ------------------------------------------------------------------ the merge commit, read after a landing (A3)
# ------------------------------------------------------------------ the merge commit, read after a landing (A3)

def test_merge_commit_with_a_banned_author_is_reported_at_once(tmp_path, env):
    """GitHub authors a merge commit with the merging account's email, which no pre-commit check sees:
    `merge` reads it through the API afterwards; a match is reported, never the address, and exits 6."""
    import test_house_guards as th
    origin, a, name, g = th._claude_branch(tmp_path, env)
    tip = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    listed = banned_file(tmp_path, INVENTED)
    clean = th.tool(a, "unmerged.py", "merge", name, "--tip", tip[:7], env=dict(g, HOUSE_BANNED=str(listed)))
    assert clean.returncode == 0 and "author and committer are clean against 1 fingerprint" in clean.stdout, clean.stdout
    sub = tmp_path / "again"; sub.mkdir()
    origin, a, name, g = th._claude_branch(sub, env)
    g = th._gh(sub, env, author=INVENTED)
    tip = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    r = th.tool(a, "unmerged.py", "merge", name, "--tip", tip[:7], env=dict(g, HOUSE_BANNED=str(listed)))
    assert r.returncode == 6 and "BANNED" in r.stdout and f"author matches fingerprint {fp(INVENTED)[:8]}" in r.stdout, r.stdout
    assert INVENTED not in r.stdout


def test_merge_commit_unreadable_is_unmeasured_never_clean(tmp_path, env):
    import test_house_guards as th
    origin, a, name, g = th._claude_branch(tmp_path, env)
    tip = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    r = th.tool(a, "unmerged.py", "merge", name, "--tip", tip[:7], env=dict(g, HOUSE_BANNED=str(tmp_path / "none.yaml")))
    assert r.returncode == 0 and "UNMEASURED" in r.stdout and "are clean" not in r.stdout, r.stdout
