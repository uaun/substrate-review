"""The house's concurrency guards, creation log, pruning and unmerged check
(AP-review-0002, A1 to A3, ratified AT.474; ported from the soul house's
house/tests/test_house_guards.py at f6468fe, by way of Grade's port at 26c4a9d, and re-derived for this house).

Every guard is tried once by a deliberate violation here, against throwaway
repositories built in a temporary folder: a bare `origin` and its clones,
carrying copies of the three house tools. Nothing here reads or writes the
live tree. Git runs with its own config (no host signing, no host identity),
so the fixtures behave the same on any surface.

The prompt's negative controls, each a test named CONTROL or FALSIFIER below:
A1: a duplicate id planted in a union-merged log is refused; a file at a
never-store path cannot be staged; a push refused by a planted clash recomputes
the count. A2: a branch made without the tool is not recorded as Claude's, so
nothing that reads the log prunes or merges it as Claude's. A3: a branch absent
from the creation log is never pruned (and test_ready_gate.py: a commit after
the ready mark returns the branch to in progress).

Run: bash house/check.sh, or python3 -I -B -m pytest -q -p no:cacheprovider house/tests
"""
from __future__ import annotations

import datetime as dt
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
DAY = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
ZERO = "0" * 40

CONFIG = {
    "union_logs": ["docs/LEDGER.md", "log/*.jsonl", "house/branches.jsonl"],
    "id_spaces": [
        {"name": "atlas items", "files": ["HANDOFF.md"], "pattern": "^- \\*\\*(AP-[a-z0-9]+-\\d{4}/A\\d+)\\*\\*"},
        {"name": "events", "files": ["log/events.jsonl"], "jsonl_key": ["writer_id", "seq"]},
    ],
    "owned": {"owner": "the session DU opened for this house", "files": ["HANDOFF.md"]},
    "never_store": {
        "paths": {"recall sets": ["**/RECALL*.md", "**/recall_spec*"], "credentials": ["**/.env", "**/*.pem"],
                  "rollback trees": ["**/.prev/**"]},
        "content": ["(?i)ghp_[A-Za-z0-9]{30,}", "-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"],
    },
}
ATTR = ("# house guards: union logs (IR-13): begin\n"
        + "".join(f"{p} merge=union\n" for p in CONFIG["union_logs"])
        + "# house guards: union logs (IR-13): end\n")
IGNORE = ("__pycache__/\n# never-store mirror: begin\n"
          + "".join(f"{p}\n" for ps in CONFIG["never_store"]["paths"].values() for p in ps)
          + "# never-store mirror: end\n")
HANDOFF = ("# HANDOFF.md\n\n## Open work\n\n<!-- house section: atlas items -->\n"
           "- **AP-review-0002/A1** (now). The guards. DONE WHEN: green.\n"
           "- **AP-review-0002/A2** (now). The log. DONE WHEN: logged.\n<!-- end house section -->\n")


@pytest.fixture
def env(tmp_path):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = t\n\temail = t@t\n[commit]\n\tgpgsign = false\n"
                   "[init]\n\tdefaultBranch = main\n[advice]\n\tdetachedHead = false\n")
    base = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    base.update(GIT_CONFIG_GLOBAL=str(cfg), GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")
    return base


def claude(env):
    return dict(env, CLAUDECODE="1", CLAUDE_CODE_REMOTE_SESSION_ID="cse_test")


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def git(repo, *args, env=None):
    return run(["git", "-C", str(repo), *args], env=env)


def heads(origin, env):
    out = git(origin, "for-each-ref", "--format=%(refname:short)", "refs/heads/", env=env).stdout
    return set(out.split())


def tool(repo, name, *args, env=None):
    return run([PY, "-I", "-B", str(repo / "house" / name), str(repo), *args], env=env)


def branch_sh(repo, *args, env=None):
    return run(["bash", str(repo / "house" / "branch.sh"), *args], cwd=str(repo), env=env)


def seed(tmp_path, env, extra=None):
    """origin (bare) and clone `a` with the house tools, a guards config, its two
    mirror blocks and a little content; main pushed."""
    origin, a = tmp_path / "origin.git", tmp_path / "a"
    run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], env=env)
    run(["git", "clone", "-q", str(origin), str(a)], env=env)
    (a / "house").mkdir()
    for name in ("branch.sh", "unmerged.py", "guards.py"):
        shutil.copy(HOUSE / name, a / "house" / name)
    (a / "house" / "guards.json").write_text(json.dumps(CONFIG, indent=1) + "\n")
    (a / ".gitattributes").write_text(ATTR)
    (a / ".gitignore").write_text(IGNORE)
    (a / "docs").mkdir(); (a / "log").mkdir()
    (a / "docs" / "LEDGER.md").write_text("# ledger\n\nEND\n")
    (a / "log" / "events.jsonl").write_text('{"writer_id": "w1", "seq": 1}\n')
    (a / "HANDOFF.md").write_text(HANDOFF)
    (a / "notes.md").write_text("notes\n")
    for rel, text in (extra or {}).items():
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / rel).write_text(text)
    git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "seed", env=env)
    git(a, "push", "-q", "-u", "origin", "main", env=env)
    return origin, a


def check(repo, env, *extra):
    return tool(repo, "guards.py", "check", *extra, env=env)


# ---------------------------------------------------------------- A1: the four IR-13 guards

def test_a_clean_house_reads_green(tmp_path, env):
    _, a = seed(tmp_path, env)
    r = check(a, env)
    assert r.returncode == 0 and "0 finding(s)" in r.stdout, r.stdout + r.stderr


def test_FALSIFIER_one_duplicate_id_appended_on_two_branches_merges_and_the_check_refuses(tmp_path, env):
    """A1's control: the union merge is clean, so only the check can stop it."""
    _, a = seed(tmp_path, env)
    for b in ("x", "y"):
        git(a, "checkout", "-q", "-b", b, "main", env=env)
        with (a / "log" / "events.jsonl").open("a") as f:
            f.write('{"writer_id": "w1", "seq": 2, "on": "%s"}\n' % b)
        git(a, "commit", "-q", "-am", f"append on {b}", env=env)
    m = git(a, "merge", "-q", "--no-edit", "x", env=env)
    assert m.returncode == 0, m.stdout + m.stderr        # union: no conflict
    assert (a / "log" / "events.jsonl").read_text().count('"seq": 2') == 2
    r = check(a, env, "--base", "main")
    assert r.returncode == 1 and "events" in r.stdout and "w1" in r.stdout and "2 times" in r.stdout, r.stdout


def test_FALSIFIER_one_atlas_item_filed_on_two_branches_merges_and_the_check_refuses(tmp_path, env):
    """Two sessions file the same atlas request in HANDOFF.md's open work, at different places."""
    _, a = seed(tmp_path, env)
    git(a, "checkout", "-q", "-b", "x", "main", env=env)
    (a / "HANDOFF.md").write_text((a / "HANDOFF.md").read_text().replace(
        "<!-- house section: atlas items -->\n", "<!-- house section: atlas items -->\n- **AP-all-0002/A2** (soon). x's.\n"))
    git(a, "commit", "-q", "-am", "file on x", env=env)
    git(a, "checkout", "-q", "-b", "y", "main", env=env)
    (a / "HANDOFF.md").write_text((a / "HANDOFF.md").read_text() + "\n- **AP-all-0002/A2** (soon). y's.\n")
    git(a, "commit", "-q", "-am", "file on y", env=env)
    m = git(a, "merge", "-q", "--no-edit", "x", env=env)
    assert m.returncode == 0, m.stdout + m.stderr
    r = check(a, env, "--base", "main")
    assert r.returncode == 1 and "atlas items" in r.stdout and "`AP-all-0002/A2` appears 2 times" in r.stdout, r.stdout


def test_CONTROL_an_ordinary_append_on_one_branch_merges_clean_and_reads_green(tmp_path, env):
    _, a = seed(tmp_path, env)
    git(a, "checkout", "-q", "-b", "x", "main", env=env)
    with (a / "log" / "events.jsonl").open("a") as f:
        f.write('{"writer_id": "w1", "seq": 2}\n')
    git(a, "commit", "-q", "-am", "append", env=env)
    git(a, "checkout", "-q", "main", env=env)
    m = git(a, "merge", "-q", "--no-edit", "x", env=env)
    r = check(a, env)
    assert m.returncode == 0 and r.returncode == 0, m.stderr + r.stdout


def test_two_entries_inserted_above_one_anchor_union_merge_without_conflict(tmp_path, env):
    _, a = seed(tmp_path, env)
    for b in ("x", "y"):
        git(a, "checkout", "-q", "-b", b, "main", env=env)
        (a / "docs" / "LEDGER.md").write_text(f"# ledger\n\n## entry {b}\nbody {b}\n\nEND\n")
        git(a, "commit", "-q", "-am", b, env=env)
    m = git(a, "merge", "-q", "--no-edit", "x", env=env)
    text = (a / "docs" / "LEDGER.md").read_text()
    assert m.returncode == 0 and "## entry x" in text and "## entry y" in text and text.rstrip().endswith("END"), m.stderr + text


def test_a_declared_log_without_its_union_line_goes_red(tmp_path, env):
    _, a = seed(tmp_path, env)
    (a / ".gitattributes").write_text(ATTR.replace("log/*.jsonl merge=union\n", ""))
    r = check(a, env)
    assert r.returncode == 1 and "`log/*.jsonl`" in r.stdout and "no `merge=union` line" in r.stdout, r.stdout


def test_a_union_line_the_config_does_not_declare_goes_red(tmp_path, env):
    _, a = seed(tmp_path, env)
    (a / ".gitattributes").write_text(ATTR.replace("# house guards: union logs (IR-13): end",
                                                   "HANDOFF.md merge=union\n# house guards: union logs (IR-13): end"))
    r = check(a, env)
    assert r.returncode == 1 and "`HANDOFF.md`" in r.stdout and "does not declare" in r.stdout, r.stdout


def test_a_never_store_path_missing_from_the_ignore_mirror_goes_red(tmp_path, env):
    _, a = seed(tmp_path, env)
    (a / ".gitignore").write_text(IGNORE.replace("**/*.pem\n", ""))
    r = check(a, env)
    assert r.returncode == 1 and "`**/*.pem`" in r.stdout and "not in the mirror block" in r.stdout, r.stdout


def test_an_ignore_mirror_entry_the_list_does_not_name_goes_red(tmp_path, env):
    _, a = seed(tmp_path, env)
    (a / ".gitignore").write_text(IGNORE.replace("# never-store mirror: end", "**/extra/**\n# never-store mirror: end"))
    r = check(a, env)
    assert r.returncode == 1 and "`**/extra/**`" in r.stdout and "does not list" in r.stdout, r.stdout


def test_a_tracked_file_on_the_never_store_list_goes_red(tmp_path, env):
    _, a = seed(tmp_path, env)
    (a / "sub").mkdir(); (a / "sub" / ".env").write_text("X=1\n")
    git(a, "add", "-f", "sub/.env", env=env); git(a, "commit", "-q", "-m", "oops", env=env)
    r = check(a, env)
    assert r.returncode == 1 and "`sub/.env`" in r.stdout and "credentials" in r.stdout, r.stdout


def test_CONTROL_a_file_at_a_never_store_path_cannot_be_staged(tmp_path, env):
    """A1's control: a recall set, a recall spec and a rollback tree are each refused by
    `git add -A` and by a plain `git add`; the ordinary file beside them stages."""
    _, a = seed(tmp_path, env)
    (a / ".prev").mkdir(); (a / ".prev" / "x.md").write_text("old\n")
    (a / "sub").mkdir(); (a / "sub" / "RECALL_set.md").write_text("category only\n")
    (a / "recall_spec.bin").write_text("x\n")
    (a / "ordinary.md").write_text("fine\n")
    git(a, "add", "-A", env=env)
    staged = git(a, "diff", "--cached", "--name-only", env=env).stdout.split()
    assert staged == ["ordinary.md"], staged
    plain = git(a, "add", "sub/RECALL_set.md", env=env)
    assert plain.returncode != 0 and "ignored" in plain.stderr, plain.stderr
    assert "sub/RECALL_set.md" not in git(a, "diff", "--cached", "--name-only", env=env).stdout


def _fake_secret() -> str:
    return "ghp" + "_" + "A1b2C3d4" * 5          # built here, so this file never matches the pattern


def test_FALSIFIER_a_tracked_text_file_carrying_a_never_store_content_pattern_goes_red(tmp_path, env):
    _, a = seed(tmp_path, env)
    (a / "notes.md").write_text("token: " + _fake_secret() + "\n")
    git(a, "commit", "-q", "-am", "a pasted credential", env=env)
    r = check(a, env)
    assert r.returncode == 1 and "`notes.md` matches the content pattern" in r.stdout, r.stdout
    # CONTROL: the config that holds the patterns is never read as a match, and a clean tree is green
    (a / "notes.md").write_text("notes\n"); git(a, "commit", "-q", "-am", "removed", env=env)
    r2 = check(a, env)
    assert r2.returncode == 0, r2.stdout


# ---------------------------------------------------------------- A1: the mirror against the atlas

NEVER_STORE_YAML = """# the atlas's list, in its own shape
paths:
  - "**/RECALL*.md"                    # recall sets
  - "**/recall_spec*"
  - "**/.env"
  - "**/*.pem"
  - "**/.prev/**"

content:
  - "(?i)ghp_[A-Za-z0-9]{30,}"          # a GitHub token
  - "-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
"""


def _atlas(tmp_path, env, text=NEVER_STORE_YAML):
    d = tmp_path / "atlas"
    (d / "charter").mkdir(parents=True)
    (d / "charter" / "never-store.yaml").write_text(text)
    run(["git", "init", "-q", "-b", "main", str(d)], env=env)
    git(d, "add", "-A", env=env); git(d, "commit", "-q", "-m", "atlas", env=env)
    return d


def test_the_mirror_reads_CURRENT_when_the_copy_matches_the_atlas(tmp_path, env):
    _, a = seed(tmp_path, env)
    d = _atlas(tmp_path, env)
    r = tool(a, "guards.py", "mirror", "--atlas", str(d), env=env)
    assert r.returncode == 0 and "CURRENT" in r.stdout, r.stdout + r.stderr


def test_FALSIFIER_the_mirror_reads_DIFFERS_when_the_atlas_lists_a_path_the_copy_lacks(tmp_path, env):
    _, a = seed(tmp_path, env)
    d = _atlas(tmp_path, env, NEVER_STORE_YAML.replace('  - "**/.prev/**"\n', '  - "**/.prev/**"\n  - "**/*.enc"\n'))
    r = tool(a, "guards.py", "mirror", "--atlas", str(d), env=env)
    assert r.returncode == 1 and "DIFFERS" in r.stdout and "`**/*.enc`" in r.stdout, r.stdout


def test_CONTROL_an_unreachable_atlas_reads_UNREACHABLE_and_stays_green(tmp_path, env):
    _, a = seed(tmp_path, env)
    r = tool(a, "guards.py", "mirror", "--atlas", str(tmp_path / "nowhere"), env=env)
    assert r.returncode == 0 and "UNREACHABLE" in r.stdout and "CURRENT" not in r.stdout, r.stdout


def test_the_mirror_parses_the_atlas_s_real_list_without_a_yaml_library(tmp_path):
    """The live house's copy against its own parser: every path and pattern of the atlas's list,
    in the atlas's shape, reads back as the strings guards.json holds."""
    sys.path.insert(0, str(HOUSE))
    try:
        import guards
    finally:
        sys.path.remove(str(HOUSE))
    cfg = guards.load_cfg(ROOT)        # the house's one copy, catalog/never-store.json (Review's re-derivation)
    text = "paths:\n" + "".join(f'  - "{p}"     # a comment\n' for p in guards.never_store_paths(cfg))
    text += "\ncontent:\n" + "".join("  - " + json.dumps(c) + "\n" for c in guards.never_store_content(cfg))
    got = guards.parse_never_store(text)
    assert got["paths"] == guards.never_store_paths(cfg) and got["content"] == guards.never_store_content(cfg), got


def test_an_owned_file_changed_on_a_branch_behind_main_goes_red(tmp_path, env):
    _, a = seed(tmp_path, env)
    git(a, "checkout", "-q", "-b", "x", "main", env=env)
    git(a, "checkout", "-q", "main", env=env)
    (a / "notes.md").write_text("main moved\n"); git(a, "commit", "-q", "-am", "main moves", env=env)
    git(a, "push", "-q", "origin", "main", env=env)
    git(a, "checkout", "-q", "x", env=env)
    (a / "HANDOFF.md").write_text("edited behind main\n"); git(a, "commit", "-q", "-am", "touch the handoff", env=env)
    r = check(a, env)
    assert r.returncode == 1 and "`HANDOFF.md`" in r.stdout and "rebase on main" in r.stdout, r.stdout
    # CONTROL: the same edit, rebased onto main first, reads green
    git(a, "rebase", "-q", "origin/main", env=env)
    r2 = check(a, env)
    assert r2.returncode == 0, r2.stdout


def test_CONTROL_a_branch_behind_main_that_leaves_the_owned_files_alone_reads_green(tmp_path, env):
    _, a = seed(tmp_path, env)
    git(a, "checkout", "-q", "-b", "x", "main", env=env)
    git(a, "checkout", "-q", "main", env=env)
    (a / "notes.md").write_text("main moved\n"); git(a, "commit", "-q", "-am", "main moves", env=env)
    git(a, "push", "-q", "origin", "main", env=env)
    git(a, "checkout", "-q", "x", env=env)
    (a / "docs" / "LEDGER.md").write_text("# ledger\n\n## an entry\n\nEND\n")
    git(a, "commit", "-q", "-am", "a ledger entry", env=env)
    r = check(a, env)
    assert r.returncode == 0, r.stdout


def test_on_a_shallow_clone_with_no_common_commit_the_owned_check_says_so_and_flags_nothing(tmp_path, env):
    origin, a = seed(tmp_path, env)
    git(a, "checkout", "-q", "-b", "x", "main", env=env)
    (a / "HANDOFF.md").write_text("edited\n"); git(a, "commit", "-q", "-am", "edit", env=env)
    git(a, "push", "-q", "origin", "x", env=env)
    git(a, "checkout", "-q", "main", env=env)
    (a / "notes.md").write_text("main moved\n"); git(a, "commit", "-q", "-am", "main moves", env=env)
    git(a, "push", "-q", "origin", "main", env=env)
    s = tmp_path / "s"
    run(["git", "clone", "-q", "--depth", "1", "--no-single-branch", "-b", "x", f"file://{origin}", str(s)], env=env)
    r = check(s, env)
    assert "rebase on main" not in r.stdout and "NOT DECIDED" in r.stdout and "shallow" in r.stdout, r.stdout


def test_without_a_repository_the_git_checks_say_they_did_not_run(tmp_path, env):
    _, a = seed(tmp_path, env)
    bare = tmp_path / "unzipped"
    shutil.copytree(a, bare, ignore=shutil.ignore_patterns(".git"))
    r = check(bare, env)
    assert r.returncode == 0 and "NOT RUN" in r.stdout and "no repository" in r.stdout, r.stdout


def test_without_a_repository_the_unmerged_check_says_NOT_RUN_and_never_a_traceback(tmp_path, env):
    """On an unpacked archive the unmerged check says NOT RUN; the FALSIFIER is a
    traceback or an exit code read as a verdict, with the root given and with it
    taken from the cwd (the soul house's item 1527, carried over)."""
    _, a = seed(tmp_path, env)
    bare = tmp_path / "unzipped"
    shutil.copytree(a, bare, ignore=shutil.ignore_patterns(".git"))
    r = tool(bare, "unmerged.py", "check", env=env)
    assert r.returncode == 0 and "NOT RUN" in r.stdout and "no repository" in r.stdout, r.stdout + r.stderr
    assert "Traceback" not in r.stderr, r.stderr
    r2 = run([PY, "-I", "-B", str(bare / "house" / "unmerged.py"), "check"], cwd=str(bare), env=env)
    assert r2.returncode == 0 and "NOT RUN" in r2.stdout and "Traceback" not in r2.stderr, r2.stdout + r2.stderr
    # CONTROL: where a repository exists the same command never says NOT RUN
    r3 = tool(a, "unmerged.py", "check", "--no-fetch", env=env)
    assert r3.returncode == 0 and "NOT RUN" not in r3.stdout, r3.stdout + r3.stderr


def test_A2_DONE_WHEN_the_log_check_refuses_a_duplicate_line(tmp_path, env):
    """A2's DONE WHEN. Two sessions log one branch name on two branches; the union merge keeps both
    lines and the check refuses the second. (Two byte-identical appends git merges as one change,
    so a line written twice by hand is the other way a copy arrives, and it is refused too.)"""
    _, a = seed(tmp_path, env)
    name = f"session/{DAY}/01-x"
    for b in ("x", "y"):
        git(a, "checkout", "-q", "-b", b, "main", env=env)
        with (a / "house" / "branches.jsonl").open("a") as f:
            f.write(json.dumps({"event": "created", "branch": name, "by": "claude", "session": b}) + "\n")
        git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", f"log on {b}", env=env)
    m = git(a, "merge", "-q", "--no-edit", "x", env=env)
    assert m.returncode == 0 and (a / "house" / "branches.jsonl").read_text().count(name) == 2, m.stdout + m.stderr
    r = check(a, env, "--base", "main")
    assert r.returncode == 1 and f"{name} already created at line 1" in r.stdout, r.stdout
    line = json.dumps({"event": "pruned", "branch": "old", "tip": "a" * 40}) + "\n"
    (a / "house" / "branches.jsonl").write_text(line + line)
    r2 = check(a, env, "--base", "main")
    assert r2.returncode == 1 and "the same line as line 1" in r2.stdout, r2.stdout


def test_the_creation_log_refuses_a_branch_created_twice_and_a_prune_with_no_tip(tmp_path, env):
    _, a = seed(tmp_path, env)
    line = json.dumps({"event": "created", "branch": "b1", "by": "claude", "session": "s"})
    again = json.dumps({"event": "created", "branch": "b1", "by": "claude", "session": "t"})
    (a / "house" / "branches.jsonl").write_text(line + "\n" + again + "\n"
                                                + json.dumps({"event": "pruned", "branch": "b0", "tip": "abc"}) + "\n"
                                                + json.dumps({"event": "created", "branch": "b2", "by": "someone"}) + "\n")
    r = check(a, env)
    assert r.returncode == 1 and "b1 already created" in r.stdout and "no 40-hex tip" in r.stdout and "want claude or not-claude" in r.stdout, r.stdout


# ---------------------------------------------------------------- the branch tool: naming and the claim

def test_a_slug_that_is_not_lowercase_with_dashes_is_refused(tmp_path, env):
    _, a = seed(tmp_path, env)
    r = branch_sh(a, "Bad Slug", "--print", env=env)
    assert r.returncode == 2, r.stdout + r.stderr


def test_the_branch_tool_claims_the_next_free_name_on_origin_at_creation(tmp_path, env):
    origin, a = seed(tmp_path, env)
    git(a, "push", "-q", "origin", f"main:refs/heads/session/{DAY}/01-other", env=env)   # another session claimed 01
    r = branch_sh(a, "probe", env=claude(env))
    assert r.returncode == 0 and "claimed on origin" in r.stdout, r.stdout + r.stderr
    assert f"session/{DAY}/02-probe" in heads(origin, env)


def test_CONTROL_a_push_refused_by_a_planted_clash_recomputes_the_count(tmp_path, env):
    """A1's control: the remote refuses the first claim (a competitor took 01 meanwhile); the tool
    drops its branch, recounts from the remote and claims 02."""
    origin, a = seed(tmp_path, env)
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nwhile read old new ref; do\n  case \"$ref\" in refs/heads/session/*)\n"
                    "    if [ ! -f once ]; then touch once; mkdir -p \"$(dirname \"$ref\")\"; git rev-parse refs/heads/main > \"${ref%-*}-other\"; "
                    "echo competitor >&2; exit 1; fi;;\n  esac\ndone\nexit 0\n")
    hook.chmod(0o755)
    r = branch_sh(a, "again", env=claude(env))
    h = heads(origin, env)
    assert r.returncode == 0 and "recounting" in r.stdout, r.stdout + r.stderr
    assert f"session/{DAY}/01-other" in h and f"session/{DAY}/02-again" in h and f"session/{DAY}/01-again" not in h, h


def test_A2_DONE_WHEN_the_creation_line_is_the_branch_s_own_first_commit(tmp_path, env):
    origin, a = seed(tmp_path, env)
    r = branch_sh(a, "first", env=claude(env))
    name = f"session/{DAY}/01-first"
    assert r.returncode == 0, r.stdout + r.stderr
    commits = git(origin, "rev-list", "--reverse", f"main..{name}", env=env).stdout.split()
    assert len(commits) == 1, commits
    files = git(origin, "show", "--name-only", "--format=", commits[0], env=env).stdout.split()
    log = git(origin, "show", f"{name}:house/branches.jsonl", env=env).stdout
    row = json.loads(log.splitlines()[-1])
    assert files == ["house/branches.jsonl"] and row["branch"] == name and row["by"] == "claude", (files, row)
    assert row["session"] == "https://claude.ai/code/session_test", row


def test_a_branch_made_by_the_tool_outside_a_claude_session_logs_not_claude_and_prunes_nothing(tmp_path, env):
    _, a = seed(tmp_path, env)
    r = branch_sh(a, "by-hand", env=env)
    last = json.loads((a / "house" / "branches.jsonl").read_text().splitlines()[-1])
    assert r.returncode == 0 and last["by"] == "not-claude" and last["session"] is None, last
    assert "not a Claude session; nothing pruned" in r.stdout, r.stdout


def test_a_day_s_number_the_log_holds_is_never_reused(tmp_path, env):
    origin, a = seed(tmp_path, env, extra={"house/branches.jsonl":
        json.dumps({"event": "created", "branch": f"session/{DAY}/05-long-gone", "by": "claude", "session": "s"}) + "\n"})
    r = branch_sh(a, "probe", "--print", env=claude(env))
    assert r.stdout.strip().endswith(f"session/{DAY}/06-probe"), r.stdout + r.stderr


# ---------------------------------------------------------------- A3: pruning

def _twelve(tmp_path, env):
    origin, a = seed(tmp_path, env)
    lines = []
    for i in range(1, 13):
        (a / f"f{i}").write_text(str(i)); git(a, "add", "-A", env=env)
        e = dict(env, GIT_COMMITTER_DATE=f"2026-10-{1 + i // 10:02d} {i % 10:02d}:00:00 +0000")
        git(a, "commit", "-q", "-m", f"c{i}", env=e)
        git(a, "push", "-q", "origin", f"HEAD:refs/heads/c{i:02d}", env=env)
        lines.append(json.dumps({"event": "created", "branch": f"c{i:02d}", "by": "claude", "session": "test"}))
    git(a, "push", "-q", "origin", "HEAD~11:refs/heads/du-own", env=env)
    lines.append(json.dumps({"event": "created", "branch": "du-own", "by": "not-claude", "session": None}))
    git(a, "push", "-q", "origin", "HEAD~11:refs/heads/unlogged", env=env)
    lines.append(json.dumps({"event": "created", "branch": "c00-open", "by": "claude", "session": "test"}))
    (a / "house" / "branches.jsonl").write_text("\n".join(lines) + "\n")
    git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "log", env=env)
    git(a, "push", "-q", "origin", "HEAD:main", env=env)
    git(a, "checkout", "-q", "-b", "c00-open", "HEAD~12", env=env)
    (a / "open.txt").write_text("x"); git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "open work", env=env)
    git(a, "push", "-q", "origin", "c00-open", env=env)
    git(a, "checkout", "-q", "-f", "main", env=env)
    return origin, a


def test_A3_DONE_WHEN_of_twelve_merged_claude_branches_the_two_oldest_are_pruned_and_the_newest_ten_kept(tmp_path, env):
    """A3's control rides here: `unlogged`, merged and older than all, is absent from the creation log
    and is never pruned; `du-own`, logged not-claude, neither."""
    origin, a = _twelve(tmp_path, env)
    r = branch_sh(a, "probe", env=claude(env))
    h = heads(origin, env)
    assert "c01" not in h and "c02" not in h and all(f"c{i:02d}" in h for i in range(3, 13)), r.stdout + " ".join(sorted(h))
    assert {"du-own", "unlogged", "c00-open"} <= h, h                       # CONTROLS
    log = git(origin, "show", f"session/{DAY}/01-probe:house/branches.jsonl", env=env).stdout
    pruned = [json.loads(x) for x in log.splitlines() if '"pruned"' in x]
    assert sorted(p["branch"] for p in pruned) == ["c01", "c02"] and all(len(p["tip"]) == 40 for p in pruned), log[-500:]
    # restore brings one back at its logged tip
    tip = next(p["tip"] for p in pruned if p["branch"] == "c01")
    rr = tool(a, "unmerged.py", "restore", "c01", env=env)
    back = git(origin, "rev-parse", "refs/heads/c01", env=env).stdout.strip()
    assert rr.returncode == 0 and back == tip, rr.stdout + rr.stderr


def test_a_run_outside_a_claude_session_prunes_nothing(tmp_path, env):
    origin, a = _twelve(tmp_path, env)
    git(a, "checkout", "-q", "-b", "work", env=env)
    r = tool(a, "unmerged.py", "prune", env=env)
    assert "not a Claude session; nothing pruned" in r.stdout and "c01" in heads(origin, env), r.stdout


def test_prune_on_main_names_what_is_due_and_deletes_nothing(tmp_path, env):
    origin, a = _twelve(tmp_path, env)
    r = tool(a, "unmerged.py", "prune", env=claude(env))
    assert "on main" in r.stdout and "c01" in heads(origin, env), r.stdout


def test_a_denied_delete_stops_the_prune_is_logged_due_and_is_never_retried(tmp_path, env):
    origin, a = _twelve(tmp_path, env)
    git(a, "checkout", "-q", "-b", "work", env=env)
    git(a, "push", "-q", "-u", "origin", "work", env=env)
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nwhile read old new ref; do\n  [ \"$new\" = %s ] && { echo 'HTTP 403 deletion denied' >&2; exit 1; }\ndone\nexit 0\n" % ZERO)
    hook.chmod(0o755)
    d1 = tool(a, "unmerged.py", "prune", env=claude(env))
    d2 = tool(a, "unmerged.py", "prune", env=claude(env))
    assert "refuses branch deletion (HTTP 403); stopped" in d1.stdout and "c01" in heads(origin, env), d1.stdout
    assert "path: refs/heads/c01" in d1.stdout and "path: refs/heads/c01" in d2.stdout, d1.stdout + d2.stdout
    assert "not retried" in d2.stdout and "stopped" not in d2.stdout and (a / ".git" / "prune-denied").exists(), d2.stdout
    log = (a / "house" / "branches.jsonl").read_text()
    assert log.count('"event": "due"') == 2 and '"c01"' in log, log[-400:]   # c01 and c02, each once


# ---------------------------------------------------------------- A4: the unmerged check, and merging on his word

def _pushed_branch(tmp_path, env, name="session/2026-10-25/01-x"):
    origin, a = seed(tmp_path, env)
    git(a, "checkout", "-q", "-b", name, env=env)
    (a / "work.txt").write_text("work\n"); git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "work", env=env)
    git(a, "push", "-q", "-u", "origin", name, env=env)
    git(a, "checkout", "-q", "main", env=env)
    return origin, a, name


def test_a_pushed_branch_not_in_main_is_listed_as_due(tmp_path, env):
    origin, a, name = _pushed_branch(tmp_path, env)
    r = tool(a, "unmerged.py", "check", env=env)
    assert name in r.stdout and "1 branch(es) not merged" in r.stdout, r.stdout + r.stderr
    single = tmp_path / "single"
    run(["git", "clone", "-q", "--single-branch", "-b", "main", str(origin), str(single)], env=env)
    shutil.copytree(a / "house", single / "house", dirs_exist_ok=True)
    rs = tool(single, "unmerged.py", "check", env=env)
    assert name in rs.stdout and "1 branch(es) not merged" in rs.stdout, rs.stdout + rs.stderr


def test_a_merged_branch_read_from_a_shallow_clone_is_not_listed(tmp_path, env):
    """Measured on this house's own first live run: a depth-1 clone cut main's
    history, so a day branch merged into main read as unmerged (ahead 3)."""
    origin, a = seed(tmp_path, env)
    git(a, "push", "-q", "origin", "main:refs/heads/session/2026-10-25/01-merged", env=env)
    (a / "notes.md").write_text("main moves on\n"); git(a, "commit", "-q", "-am", "later", env=env)
    git(a, "push", "-q", "origin", "main", env=env)
    shallow = tmp_path / "shallow"
    run(["git", "clone", "-q", "--depth", "1", f"file://{origin}", str(shallow)], env=env)
    r = tool(shallow, "unmerged.py", "check", env=env)
    assert "every remote branch is merged" in r.stdout and "01-merged" not in r.stdout, r.stdout + r.stderr


def test_a_snoozed_branch_leaves_the_due_list_and_watch_brings_it_back(tmp_path, env):
    _, a, name = _pushed_branch(tmp_path, env)
    tool(a, "unmerged.py", "snooze", name, "--days", "7", env=env)
    r = tool(a, "unmerged.py", "check", env=env)
    assert "0 branch(es) not merged" in r.stdout and "snoozed until" in r.stdout, r.stdout
    tool(a, "unmerged.py", "watch", name, env=env)
    r2 = tool(a, "unmerged.py", "check", env=env)
    assert "1 branch(es) not merged" in r2.stdout and "watch" in r2.stdout, r2.stdout


def test_merge_on_his_word_fast_forwards_main_and_the_branch_drops_off_the_list(tmp_path, env):
    origin, a, name = _pushed_branch(tmp_path, env)
    r = tool(a, "unmerged.py", "merge", name, env=env)
    tip = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    main = git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip()
    assert r.returncode == 0 and tip == main, r.stdout + r.stderr
    r2 = tool(a, "unmerged.py", "check", env=env)
    assert "every remote branch is merged" in r2.stdout, r2.stdout          # CONTROL: merged, not listed


def test_when_main_refuses_the_push_the_merge_gives_the_pull_request_link(tmp_path, env):
    origin, a, name = _pushed_branch(tmp_path, env)
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nwhile read old new ref; do\n  [ \"$ref\" = refs/heads/main ] && { echo 'protected' >&2; exit 1; }\ndone\nexit 0\n")
    hook.chmod(0o755)
    r = tool(a, "unmerged.py", "merge", name, env=env)
    assert r.returncode == 3 and "pull/new/" + name in r.stdout, r.stdout + r.stderr


def test_a_conflict_the_policy_does_not_cover_aborts_the_merge_and_commits_nothing(tmp_path, env):
    origin, a = seed(tmp_path, env)
    name = "session/2026-10-25/01-x"
    git(a, "checkout", "-q", "-b", name, env=env)
    (a / "notes.md").write_text("branch side\n"); git(a, "commit", "-q", "-am", "branch", env=env)
    git(a, "push", "-q", "-u", "origin", name, env=env)
    git(a, "checkout", "-q", "main", env=env)
    (a / "notes.md").write_text("main side\n"); git(a, "commit", "-q", "-am", "main", env=env)
    git(a, "push", "-q", "origin", "main", env=env)
    before = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    r = tool(a, "unmerged.py", "merge", name, env=env)
    after = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    assert r.returncode == 2 and "notes.md" in r.stdout and before == after, r.stdout + r.stderr
    assert not git(a, "status", "--porcelain", env=env).stdout.strip()


def test_a_merge_whose_merged_tree_fails_the_guards_is_not_committed(tmp_path, env):
    origin, a = seed(tmp_path, env)
    name = "session/2026-10-25/01-x"
    git(a, "checkout", "-q", "-b", name, env=env)
    with (a / "log" / "events.jsonl").open("a") as f:
        f.write('{"writer_id": "w1", "seq": 2, "on": "branch"}\n')
    git(a, "commit", "-q", "-am", "branch append", env=env)
    git(a, "push", "-q", "-u", "origin", name, env=env)
    git(a, "checkout", "-q", "main", env=env)
    with (a / "log" / "events.jsonl").open("a") as f:
        f.write('{"writer_id": "w1", "seq": 2, "on": "main"}\n')
    git(a, "commit", "-q", "-am", "main append", env=env)
    git(a, "push", "-q", "origin", "main", env=env)
    before = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    r = tool(a, "unmerged.py", "merge", name, env=env)
    after = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    assert r.returncode == 2 and "fails the house guards" in r.stdout and before == after, r.stdout + r.stderr


# ---------------------------------------------------------------- A3: merges by pull request, his rules of 2026-10-26 (AT.49)
# A branch the creation log records as Claude's lands through a pull request merged
# on his word, guarded by the tip he was shown; any other branch fast-forwards (the
# pins above stay the control). The boot's check reads GitHub's head-branch setting.
# GitHub is stood in for by a recording `gh` on PATH; the origin carries a GitHub URL
# that git rewrites to the local bare repository, so every push stays local.

FAKE_GH = '''#!{py}
import json, os, sys
state = json.load(open(os.environ["FAKE_GH"]))
args = sys.argv[1:]
data = sys.stdin.read() if "--input" in args else ""
with open(os.environ["FAKE_GH"] + ".log", "a") as f:
    f.write(json.dumps({{"args": args, "input": data}}) + "\\n")
path = args[1] if len(args) > 1 else ""
method = args[args.index("--method") + 1] if "--method" in args else "GET"
if method == "GET" and path.count("/") == 2:
    print(json.dumps({{"delete_branch_on_merge": state.get("delete", False)}}))
elif method == "GET" and path.rstrip("/").split("/")[-1].isdigit() and "/pulls/" in path:
    # one pull request: GitHub's mergeability judgement, None until it has judged
    print(json.dumps({{"number": 7, "mergeable": state.get("mergeable", True), "mergeable_state": "clean",
                      "head": {{"sha": state.get("head", "")}}}}))
elif method == "GET" and "/pulls" in path:
    print(json.dumps(state.get("open", [])))
elif method == "GET" and "/commits/" in path:
    # a merge commit's author and committer (house/unmerged.py's banned-address read, AP-review-0002/A3)
    print(json.dumps({{"commit": {{"author": {{"email": state.get("author", "t@t")}},
                                   "committer": {{"email": state.get("committer", "noreply@github.com")}}}}}}))
elif method == "POST" and path.endswith("/pulls"):
    print(json.dumps({{"number": 7, "html_url": "https://github.com/test/house/pull/7"}}))
elif method == "PUT" and path.endswith("/merge") and state.get("merge_ok", True):
    print(json.dumps({{"merged": True, "sha": "f" * 40}}))
else:
    print("gh: refused by the fake", file=sys.stderr); sys.exit(1)
'''


def _gh(tmp_path, env, **state):
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "gh").write_text(FAKE_GH.format(py=PY)); (bin_ / "gh").chmod(0o755)
    (tmp_path / "gh.json").write_text(json.dumps(state))
    return dict(env, PATH=f"{bin_}:{env['PATH']}", FAKE_GH=str(tmp_path / "gh.json"), HOUSE_PR_WAITS="0,0,0")


def _gh_calls(tmp_path):
    p = tmp_path / "gh.json.log"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def _on_github(a, origin, env):
    git(a, "config", "remote.origin.url", "https://github.com/test/house", env=env)
    git(a, "config", f"url.{origin}.insteadOf", "https://github.com/test/house", env=env)


def _claude_branch(tmp_path, env, github=True):
    origin, a = seed(tmp_path, env)
    if github:
        _on_github(a, origin, env)
    g = _gh(tmp_path, env)
    branch_sh(a, "work", env=claude(g))
    name = f"session/{DAY}/01-work"
    (a / "work.txt").write_text("work\n"); git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "work", env=env)
    git(a, "push", "-q", "origin", name, env=env)
    tool(a, "unmerged.py", "ready", env=claude(g))      # IR-16: only a ready branch of Claude's is merged
    git(a, "checkout", "-q", "main", env=env)
    return origin, a, name, g


def test_A3_FALSIFIER_a_branch_of_claude_s_lands_by_pull_request_never_by_a_push_to_main(tmp_path, env):
    origin, a, name, g = _claude_branch(tmp_path, env)
    main0 = git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip()
    tip = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    shown = tool(a, "unmerged.py", "check", env=g)
    assert tip[:7] in shown.stdout, shown.stdout                         # the tip he is shown
    r = tool(a, "unmerged.py", "merge", name, "--tip", tip[:7], env=g)
    assert git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip() == main0, r.stdout + r.stderr
    calls = _gh_calls(tmp_path)
    merges = [c for c in calls if "PUT" in c["args"] and c["args"][1].endswith("/pulls/7/merge")]
    assert any("POST" in c["args"] and c["args"][1].endswith("/pulls") for c in calls), calls
    assert merges and json.loads(merges[0]["input"])["sha"] == tip, calls
    assert r.returncode == 0 and "pull request #7" in r.stdout, r.stdout + r.stderr


def test_A3_CONTROL_a_tip_he_was_not_shown_or_none_lands_nothing(tmp_path, env):
    origin, a, name, g = _claude_branch(tmp_path, env)
    main0 = git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip()
    r1 = tool(a, "unmerged.py", "merge", name, "--tip", "deadbee", env=g)
    r2 = tool(a, "unmerged.py", "merge", name, env=g)
    assert r1.returncode == 1 and "moved" in r1.stdout, r1.stdout + r1.stderr
    assert r2.returncode == 1 and "--tip" in r2.stdout, r2.stdout + r2.stderr
    assert git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip() == main0
    assert not [c for c in _gh_calls(tmp_path) if "PUT" in c["args"] or "POST" in c["args"]]


def test_A3_without_a_pull_request_route_a_branch_of_claude_s_is_left_pushed_never_on_main(tmp_path, env):
    origin, a, name, g = _claude_branch(tmp_path, env, github=False)
    main0 = git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip()
    tip = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
    r = tool(a, "unmerged.py", "merge", name, "--tip", tip[:7], env=g)
    assert r.returncode == 3 and "no pull request route" in r.stdout, r.stdout + r.stderr
    assert git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip() == main0


def test_A3_a_pull_request_github_has_not_judged_mergeable_or_judged_conflicting_lands_nothing(tmp_path, env):
    """The atlas's measured failure (its pull requests #32 and #92): a merge sent before GitHub has
    judged the pull request is refused as a conflict; the tool waits, and lands nothing when the
    judgement never comes or says it conflicts."""
    for state, why in (({"mergeable": None}, "had not judged"), ({"mergeable": False}, "conflicts with main")):
        sub = tmp_path / why.replace(" ", "-")
        sub.mkdir()
        origin, a, name, g = _claude_branch(sub, env)
        g = _gh(sub, env, **state)
        main0 = git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip()
        tip = git(origin, "rev-parse", f"refs/heads/{name}", env=env).stdout.strip()
        r = tool(a, "unmerged.py", "merge", name, "--tip", tip[:7], env=g)
        assert r.returncode == 3 and why in r.stdout, r.stdout + r.stderr
        assert not [c for c in _gh_calls(sub) if "PUT" in c["args"]], _gh_calls(sub)
        assert git(origin, "rev-parse", "refs/heads/main", env=env).stdout.strip() == main0


def test_A2_CONTROL_a_branch_made_without_the_tool_is_not_claude_s_so_it_is_never_merged_or_pruned_as_claude_s(tmp_path, env):
    """A2's control: a branch pushed by hand (no creation line) reads as DU's: offered as his and
    fast-forwarded on his word, never through Claude's pull request route, and never pruned."""
    origin, a = seed(tmp_path, env)
    _on_github(a, origin, env)
    g = _gh(tmp_path, env)
    name = f"session/{DAY}/01-by-hand"
    git(a, "checkout", "-q", "-b", name, env=env)
    (a / "w.txt").write_text("w\n"); git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "work", env=env)
    git(a, "push", "-q", "-u", "origin", name, env=env)
    git(a, "checkout", "-q", "main", env=env)
    shown = tool(a, "unmerged.py", "check", env=g)
    assert "1 yours" in shown.stdout and "in progress" not in shown.stdout.split("\n")[0], shown.stdout
    r = tool(a, "unmerged.py", "merge", name, env=g)
    assert r.returncode == 0 and "fast-forward" in r.stdout, r.stdout + r.stderr
    assert not [c for c in _gh_calls(tmp_path) if "POST" in c["args"] or "PUT" in c["args"]]
    git(a, "pull", "-q", "origin", "main", env=env)
    git(a, "checkout", "-q", "-b", "work", env=env)
    pr = tool(a, "unmerged.py", "prune", "--dry-run", env=claude(env))
    assert name not in pr.stdout and name in heads(origin, env), pr.stdout


def test_A3_FALSIFIER_the_check_reads_the_head_branch_setting_and_asks_him_where_it_is_off(tmp_path, env):
    origin, a = seed(tmp_path, env)
    _on_github(a, origin, env)
    off = tool(a, "unmerged.py", "check", env=_gh(tmp_path, env, delete=False))
    assert "head-branch deletion: OFF" in off.stdout and "Automatically delete head branches" in off.stdout, off.stdout
    on = tool(a, "unmerged.py", "check", env=_gh(tmp_path, env, delete=True))
    assert "head-branch deletion: on" in on.stdout and "ask DU" not in on.stdout, on.stdout   # CONTROL
    plain = tmp_path / "plain"
    _, b = seed(plain, env) if plain.mkdir() is None else (None, None)
    r = tool(b, "unmerged.py", "check", env=env)
    assert "head-branch deletion: NOT READ" in r.stdout, r.stdout                              # no GitHub, said
