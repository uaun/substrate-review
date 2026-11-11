"""THE READY GATE IN THE HOUSE'S BRANCH TOOLS (AP-review-0002/A3, which meets
AP-all-0003/A2; IR-16). Ported from the soul house's house/tests/test_ready_gate.py
at f6468fe, by way of Grade's port at 26c4a9d, and re-derived for this house.

DONE WHEN, in the atlas's words: an in-progress branch is listed and never offered;
a ready branch merged on DU's word lands through a pull request at the tip he was
shown (and AP-all-0003/A2's: a branch of Claude's with no ready mark is refused by
`merge` with nothing pushed, and the same branch merges once marked ready).
CONTROL: a commit after the ready mark returns the branch to in progress. Around
it: DU's own branch is offered as before; his `--as-is` closes out an unready one; a
stalled branch is reviewed and never merged; the guards accept a ready line and
refuse one naming no commit.

Built on the fixtures of test_house_guards.py: a bare origin, clones carrying the
house tools, and a recording `gh`. Nothing here reads or writes the live tree.

Run: bash house/check.sh, or python3 -I -B -m pytest -q -p no:cacheprovider house/tests
"""
from __future__ import annotations

import json

from test_house_guards import (DAY, _gh, _gh_calls, _on_github, _pushed_branch, branch_sh,  # noqa: F401
                               check, claude, env, git, seed, tool)


def _unready(tmp_path, env):
    origin, a = seed(tmp_path, env)
    _on_github(a, origin, env)
    g = _gh(tmp_path, env)
    branch_sh(a, "work", env=claude(g))
    name = f"session/{DAY}/01-work"
    (a / "work.txt").write_text("work\n"); git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "work", env=env)
    git(a, "push", "-q", "origin", name, env=env)
    return origin, a, name, g


def _tip(origin, ref, env):
    return git(origin, "rev-parse", f"refs/heads/{ref}", env=env).stdout.strip()


def _writes(tmp_path):
    return [c for c in _gh_calls(tmp_path) if "PUT" in c["args"] or "POST" in c["args"]]


def test_IR16_FALSIFIER_an_unready_branch_of_claude_s_is_refused_with_nothing_pushed(tmp_path, env):
    origin, a, name, g = _unready(tmp_path, env)
    git(a, "checkout", "-q", "main", env=env)
    main0, tip0 = _tip(origin, "main", env), _tip(origin, name, env)
    r = tool(a, "unmerged.py", "merge", name, "--tip", tip0[:7], env=g)
    assert r.returncode == 4 and "only a ready branch" in r.stdout, r.stdout + r.stderr
    assert _tip(origin, "main", env) == main0 and _tip(origin, name, env) == tip0
    assert not _writes(tmp_path)


def test_A3_DONE_WHEN_the_same_branch_merges_once_marked_ready_by_pull_request_at_the_tip_shown(tmp_path, env):
    origin, a, name, g = _unready(tmp_path, env)
    m = tool(a, "unmerged.py", "ready", env=claude(g))
    assert m.returncode == 0 and "marked ready" in m.stdout, m.stdout + m.stderr
    git(a, "checkout", "-q", "main", env=env)
    tip = _tip(origin, name, env)
    shown = tool(a, "unmerged.py", "check", env=g)
    assert "1 ready" in shown.stdout and tip[:7] in shown.stdout, shown.stdout
    r = tool(a, "unmerged.py", "merge", name, "--tip", tip[:7], env=g)
    assert r.returncode == 0 and "pull request #7" in r.stdout, r.stdout + r.stderr


def test_A3_CONTROL_a_commit_after_the_mark_returns_the_branch_to_in_progress(tmp_path, env):
    origin, a, name, g = _unready(tmp_path, env)
    tool(a, "unmerged.py", "ready", env=claude(g))
    (a / "late.txt").write_text("late\n"); git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "late", env=env)
    git(a, "push", "-q", "origin", name, env=env)
    git(a, "checkout", "-q", "main", env=env)
    shown = tool(a, "unmerged.py", "check", env=g)
    assert "1 in progress" in shown.stdout and "never offered" in shown.stdout, shown.stdout
    r = tool(a, "unmerged.py", "merge", name, "--tip", _tip(origin, name, env)[:7], env=g)
    assert r.returncode == 4 and "commits came after" in r.stdout, r.stdout + r.stderr


def test_IR16_a_branch_of_DU_s_is_offered_and_merges_as_before(tmp_path, env):
    origin, a, name = _pushed_branch(tmp_path, env)
    shown = tool(a, "unmerged.py", "check", env=env)
    assert "1 yours" in shown.stdout, shown.stdout
    r = tool(a, "unmerged.py", "merge", name, env=env)
    assert r.returncode == 0 and _tip(origin, name, env) == _tip(origin, "main", env), r.stdout + r.stderr


def test_IR16_on_his_word_as_is_closes_out_an_unready_branch(tmp_path, env):
    origin, a, name, g = _unready(tmp_path, env)
    git(a, "checkout", "-q", "main", env=env)
    r = tool(a, "unmerged.py", "merge", name, "--tip", _tip(origin, name, env)[:7], "--as-is", env=g)
    assert r.returncode == 0 and "pull request #7" in r.stdout, r.stdout + r.stderr


def test_IR16_a_stalled_branch_is_reviewed_and_never_merged(tmp_path, env):
    origin, a, name, g = _unready(tmp_path, env)
    git(a, "checkout", "-q", "main", env=env)
    (a / "ops").mkdir(exist_ok=True)
    (a / "ops" / "branch-policy.yaml").write_text("quiet_days: 0\nreview: python3 -I -B house/guards.py check\n")
    git(a, "add", "-A", env=env); git(a, "commit", "-q", "-m", "policy", env=env)   # a clean tree: the gate refuses, not the tree
    shown = tool(a, "unmerged.py", "check", env=g)
    assert "1 stalled" in shown.stdout and "review at" in shown.stdout, shown.stdout
    assert "closable" in shown.stdout or "needs work" in shown.stdout, shown.stdout
    main0 = _tip(origin, "main", env)
    r = tool(a, "unmerged.py", "merge", name, "--tip", _tip(origin, name, env)[:7], env=g)
    assert r.returncode == 4 and "is stalled" in r.stdout and _tip(origin, "main", env) == main0, r.stdout + r.stderr
    assert not _writes(tmp_path)


def test_IR16_ready_is_refused_on_main(tmp_path, env):
    origin, a = seed(tmp_path, env)
    r = tool(a, "unmerged.py", "ready", env=claude(env))
    assert r.returncode == 1 and "never main" in r.stdout, r.stdout + r.stderr


def test_IR16_the_guards_accept_a_ready_line_and_refuse_one_naming_no_commit(tmp_path, env):
    origin, a = seed(tmp_path, env)
    log = a / "house" / "branches.jsonl"
    log.write_text(json.dumps({"event": "ready", "branch": "session/x/01-y", "work": "a" * 40}) + "\n")
    assert "ready line" not in check(a, env).stdout
    log.write_text(json.dumps({"event": "ready", "branch": "session/x/01-y"}) + "\n")
    r = check(a, env)
    assert "names no `work` commit" in r.stdout, r.stdout
