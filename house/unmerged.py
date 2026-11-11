#!/usr/bin/env python3
"""The house's creation log, pruning, unmerged check, ready gate and merges by
pull request (AP-review-0002, A2 and A3; AP-all-0003/A2, IR-16; ported from Jetsam's house/ at f97c6f7 for Review's house (AP-review-0002), which re-derived the soul house's tools). Ported from the
soul house's house/unmerged.py at f6468fe, its PR wait from the atlas's
tools/unmerged.py at c9fc278 (by way of Grade's port at 26c4a9d, read as an aid; the reference read at 7c339e8, house/ only), and re-derived for this house.

THE UNMERGED CHECK. At every branch creation (house/branch.sh calls it) and
every boot: one `git fetch --prune` by explicit refspec (a single-branch clone
otherwise sees no other head and calls everything merged; a shallow clone is
deepened first, since a cut history reads a merged branch as unmerged), then
every remote branch whose tip is not an ancestor of origin/main, minus the ones
snoozed in house/unmerged.json (read from the working tree and from
origin/main; the later entry wins). The session puts each ready branch of
Claude's, and each of DU's, to DU in his question widget: merge now, keep
reminding, snooze a week, snooze a month.

  python3 -I -B house/unmerged.py [ROOT] check [--json] [--no-fetch]
  python3 -I -B house/unmerged.py [ROOT] snooze <branch> --days N [--by WHO]
  python3 -I -B house/unmerged.py [ROOT] watch  <branch> [--by WHO]
  python3 -I -B house/unmerged.py [ROOT] merge  <branch> [--tip SHA] [--by WHO]
      on DU's word only: merge origin/main into the branch in a throwaway
      worktree, refuse the merge if it conflicts (this house has no resolution
      policy beyond the union-merged logs, which do not conflict) or if the
      merged tree fails house/guards.py, and push the branch. Then, by his rules
      of 2026-10-26 (AT.49): a branch the creation log records as Claude's
      (main's log or the branch's own first commit) lands through a pull request
      merged on his word, guarded by the tip he was shown, which `--tip` names
      and the check's table prints, once GitHub has judged it mergeable; any
      other branch fast-forwards main. Where no pull request route exists, or
      main refuses, the branch is left clean and pushed and the link printed; a
      branch of Claude's never reaches main by a push. After a pull request's merge,
      the merge commit's author and committer are read through the API and hashed
      against the banned list (A1's check); a match is reported at once, and the
      merge, which has happened, exits 6.
  python3 -I -B house/unmerged.py [ROOT] merge  <branch> --tip SHA --as-is [--by WHO]
      on DU's word only: merge a branch of Claude's that is not marked ready (a
      stalled one he chose to close out as it stands); without --as-is, merge
      refuses such a branch before anything is merged or pushed (exit 4)

THE READY GATE (IR-16; AT.93, AT.102). A branch the creation log records as
Claude's is merged only at a tip its owning session marked ready, as the last
act of its close. Read at its tip, each such branch is `ready` (the tip is the
commit `ready` made: it adds only a ready line to the creation log, naming the
tip's parent as the finished work), `in progress` (no ready line at the tip,
or commits after it: listed, never offered), or `stalled` (in progress and
quiet for `quiet_days` in ops/branch-policy.yaml, 7 when absent: reviewed
automatically, never merged, put to DU with the review's verdict). Any other
branch is DU's, offered as before.

  python3 -I -B house/unmerged.py [ROOT] ready [--claude-session URL]
      the close's last act: a ready line naming HEAD, committed alone and
      pushed; refused on main or with uncommitted work
  python3 -I -B house/unmerged.py [ROOT] review <branch>
      a throwaway worktree at the branch's tip merges main and runs the policy's
      `review` command (the house check when absent): closable when both pass,
      needs work otherwise, with the reason; nothing committed or pushed. `check`
      runs it for each stalled branch, cached per tip in .git, unless --no-fetch
  python3 -I -B house/unmerged.py [ROOT] brief <branch>
      a resume brief for the agent that owns a stalled branch, for DU to hand on

THE HEAD-BRANCH SETTING (the pruning rule, AT.49). The check also reads
GitHub's "Automatically delete head branches" on the origin's repository;
where it is off it says so, for the session to ask DU by widget at every boot
until it is on, since it is the repository's setting and his to change.

THE CREATION LOG (A2). A branch is Claude's only if house/branches.jsonl
(append-only, merge=union, checked by house/guards.py) records it as created by
a Claude session; house/branch.sh writes that line as the branch's own first
commit. An unlogged branch is DU's, whatever its commits say: never pruned, and
never merged as Claude's.

  python3 -I -B house/unmerged.py [ROOT] log-created <branch> [--claude-session URL]

PRUNING (A3). Of Claude's branches merged into main, the 10 with the most
recent last commit stay; every older one is pruned on the remote (a lease on
its tip) and locally, logged with its tip so `restore` brings it back. The
ranking reads the remote's branches only. Never on main, never outside a Claude
session. A remote that denies the delete (HTTP 403 or 407) stops the prune; the
denial is remembered in .git/prune-denied so this workspace never retries it,
the rest are logged `due`, and each is presented to DU by its full name, its
path and its link.

  python3 -I -B house/unmerged.py [ROOT] prune [--dry-run] [--no-fetch]
  python3 -I -B house/unmerged.py [ROOT] restore <branch>
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNOOZE_PATH = "house/unmerged.json"
LOG_PATH = "house/branches.jsonl"
POLICY_PATH = "ops/branch-policy.yaml"                  # the atlas's name, as delivered (IR-14, IR-16)
POLICY_DEFAULTS = {"quiet_days": 7, "review": "bash house/check.sh"}
REVIEWS = "unmerged-reviews"                            # this clone's review cache, in .git, never committed
KEEP = 10
COMMANDS = ("check", "snooze", "watch", "merge", "log-created", "prune", "restore", "ready", "review", "brief")


def git(root: Path, *args, check=True) -> str:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return (p.stdout or "").strip()


def ok(root: Path, *args) -> bool:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True).returncode == 0


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def shallow(root: Path) -> bool:
    return git(root, "rev-parse", "--is-shallow-repository", check=False) == "true"


def fetch_all(root: Path) -> None:
    """Every head by explicit refspec; on a shallow clone, a bounded deepening first,
    because a cut history makes a merged branch read as unmerged (measured on this
    house's first live run: a depth-1 clone listed a merged day branch as ahead 3)."""
    deepen = ["--deepen=1000"] if shallow(root) else []   # from the boundary: --depth re-cuts at each tip
    git(root, "fetch", "--prune", "--quiet", *deepen, "origin", "+refs/heads/*:refs/remotes/origin/*")
    # The Tenant's fix (RC-tenant-T2, deviation 4; the atlas's TODO-237): on GitHub's runner (git 2.56.0) a head new
    # to a shallow clone arrives cut at its own tip, a boundary the first deepen does not reach, so a merged branch
    # reads "undecidable"; one more deepen from every boundary reaches it. Measured on this house's first CI run.
    if deepen and shallow(root):
        git(root, "fetch", "--quiet", "--deepen=1000", "origin", "+refs/heads/*:refs/remotes/origin/*")


def read_both(root: Path, rel: str) -> list[str]:
    """The working tree's copy, then origin/main's."""
    here = (root / rel).read_text(encoding="utf-8") if (root / rel).exists() else ""
    return [here, git(root, "show", f"origin/main:{rel}", check=False)]


# ------------------------------------------------------------------ snoozes

def read_snoozes(root: Path) -> dict:
    entries: dict[str, dict] = {}
    for text in read_both(root, SNOOZE_PATH):
        try:
            data = json.loads(text) if text.strip() else {}
        except ValueError:
            continue
        for branch, e in (data.get("branches") or {}).items():
            if branch not in entries or str(e.get("on", "")) >= str(entries[branch].get("on", "")):
                entries[branch] = dict(e)
    return entries


def write_snooze(root: Path, branch: str, entry: dict) -> None:
    p = root / SNOOZE_PATH
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    data.setdefault("_doc", "Per-branch state for the unmerged rule, written by house/unmerged.py on DU's word; "
                            "state: snoozed (until a date) | watch (keep reminding). Merged branches drop out on their own.")
    data.setdefault("branches", {})[branch] = entry
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def unmerged(root: Path, fetch: bool = True) -> list[dict]:
    if fetch:
        try:
            fetch_all(root)
        except RuntimeError as e:
            print(f"unmerged: fetch failed ({e}); using the last known remote state", file=sys.stderr)
    main = git(root, "rev-parse", "origin/main")
    today = dt.date.today().isoformat()
    snoozes = read_snoozes(root)
    policy = read_policy(root)
    rows = []
    fmt = "%(refname:short)\t%(objectname)\t%(committerdate:short)\t%(authorname)"
    for line in git(root, "for-each-ref", f"--format={fmt}", "refs/remotes/origin/").splitlines():
        ref, sha, date, author = line.split("\t")
        name = ref[len("origin/"):]
        if name in ("main", "HEAD") or ok(root, "merge-base", "--is-ancestor", sha, main):
            continue
        s = snoozes.get(name, {})
        state = s.get("state", "new")
        if state == "snoozed" and str(s.get("until", "")) < today:
            state = "expired"
        if shallow(root) and not git(root, "merge-base", sha, main, check=False):
            state = "undecidable (shallow history)"   # no common commit in what was fetched: said, not guessed
        rows.append({"branch": name, "sha": sha[:7], "tip": sha, "date": date, "author": author,
                     "ahead": int(git(root, "rev-list", "--count", f"{main}..{sha}")),
                     "behind": int(git(root, "rev-list", "--count", f"{sha}..{main}")),
                     "state": state, "until": s.get("until"), "snoozed": state == "snoozed",
                     **gate(root, name, sha, policy)})
    return sorted(rows, key=lambda r: (r["snoozed"], r["date"], r["branch"]))


# ------------------------------------------------------------------ the creation log

def read_log(root: Path) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for text in read_both(root, LOG_PATH):
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def claude_logged(root: Path) -> dict[str, dict]:
    return {e["branch"]: e for e in read_log(root)
            if e.get("event") == "created" and e.get("by") == "claude" and e.get("branch")}


def is_claude(root: Path, branch: str) -> bool:
    """Claude's by the creation log: main's copy and the working tree's, or the
    branch's own, since its creation line is its first commit and reaches main
    only at the merge (AT.49)."""
    if branch in claude_logged(root):
        return True
    own = git(root, "show", f"origin/{branch}:{LOG_PATH}", check=False)
    for line in own.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("event") == "created" and e.get("by") == "claude" and e.get("branch") == branch:
            return True
    return False


# ------------------------------------------------------------------ the ready gate (IR-16)

def read_policy(root: Path) -> dict:
    """ops/branch-policy.yaml (the working tree's, else origin/main's) over the defaults, set by
    DU's word. Two scalar keys, so a line reader serves where the atlas uses its YAML loader."""
    text = next((t for t in read_both(root, POLICY_PATH) if t), "")
    data = {}
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Za-z_]+)\s*:\s*(.*?)\s*(?:#.*)?$", line)
        if m and m.group(2):
            data[m.group(1)] = m.group(2).strip("'\"")
    out = dict(POLICY_DEFAULTS)
    out.update({k: data[k] for k in POLICY_DEFAULTS if data.get(k)})
    try:
        out["quiet_days"] = max(0, int(out["quiet_days"]))
    except (TypeError, ValueError):
        out["quiet_days"] = POLICY_DEFAULTS["quiet_days"]
    return out


def log_at(root: Path, sha: str) -> list[dict]:
    """The creation log as the branch holds it at sha: its own lines live on it until it merges."""
    out = []
    for line in git(root, "show", f"{sha}:{LOG_PATH}", check=False).splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def ready_mark(root: Path, name: str, sha: str) -> str:
    """'ready' when sha is the commit `ready` made (it changes only the creation log, and its ready
    line names sha's parent); 'moved' when a ready line exists but commits came after; else 'none'."""
    marks = [e for e in log_at(root, sha) if e.get("event") == "ready" and e.get("branch") == name]
    if not marks:
        return "none"
    parent = git(root, "rev-parse", "-q", "--verify", f"{sha}^", check=False)
    changed = git(root, "diff", "--name-only", f"{sha}^", sha, check=False).splitlines()
    return "ready" if parent and parent == marks[-1].get("work") and changed == [LOG_PATH] else "moved"


def gate(root: Path, name: str, sha: str, policy: dict) -> dict:
    """The ready gate's reading of one branch: whose it is, its state and how long it has been quiet."""
    ct = git(root, "log", "-1", "--format=%ct", sha, check=False)
    quiet = round((time.time() - int(ct)) / 86400, 1) if ct.isdigit() else 0.0
    if not is_claude(root, name):
        return {"claude": False, "kind": "yours", "mark": "n/a", "quiet": quiet, "owner": None}
    created = next((e for e in log_at(root, sha) if e.get("event") == "created" and e.get("branch") == name),
                   None) or claude_logged(root).get(name) or {}
    mark = ready_mark(root, name, sha)
    kind = "ready" if mark == "ready" else ("stalled" if quiet >= policy["quiet_days"] else "in progress")
    return {"claude": True, "kind": kind, "mark": mark, "quiet": quiet, "owner": created.get("session")}


# ------------------------------------------------------------------ GitHub, by its REST API (AT.49)

def github_repo(root: Path) -> str | None:
    """owner/repo from the origin URL as configured (before any insteadOf rewrite)."""
    url = git(root, "config", "--get", "remote.origin.url", check=False)
    m = re.match(r"^(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None


def gh_api(path: str, method: str = "GET", body: dict | None = None):
    """(data, None) or (None, reason): one `gh api` call; GraphQL is not used."""
    exe = shutil.which("gh")
    if not exe:
        return None, "no gh on this surface"
    cmd = [exe, "api", path, "--method", method] + (["--input", "-"] if body is not None else [])
    try:
        p = subprocess.run(cmd, input=json.dumps(body) if body is not None else None,
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"gh could not run ({type(e).__name__})"
    if p.returncode != 0:
        why = (p.stderr or p.stdout or "").strip().splitlines()
        return None, why[-1] if why else f"gh exited {p.returncode}"
    try:
        return json.loads(p.stdout or "null"), None
    except ValueError:
        return None, "gh printed no JSON"


def head_branch_line(root: Path) -> str:
    repo = github_repo(root)
    if not repo:
        return "head-branch deletion: NOT READ: origin is not a GitHub repository"
    data, why = gh_api(f"repos/{repo}")
    if why or not isinstance(data, dict):
        return f"head-branch deletion: NOT READ: {why or 'no answer'}"
    if data.get("delete_branch_on_merge"):
        return "head-branch deletion: on: GitHub deletes each merged head (the pruning rule)"
    return (f"head-branch deletion: OFF on {repo}: ask DU by widget to turn on \"Automatically delete head "
            "branches\" (the repository's Settings, General, Pull Requests); asked at every boot until it is on "
            "(the pruning rule, AT.49)")


def pr_waits() -> list[float]:
    """Seconds to wait before each look at a pull request's mergeability (HOUSE_PR_WAITS; the tests set zeros)."""
    raw = os.environ.get("HOUSE_PR_WAITS", "0,2,3,5,5,5,10")
    try:
        return [float(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        return [0, 2, 3, 5, 5, 5, 10]


def wait_mergeable(repo: str, number: int, tip: str) -> tuple[bool, str]:
    """GitHub judges a pull request's mergeability after each push, and until it has, a merge is
    refused as a conflict; it also moves the pull request's head a few seconds after the push.
    Both are waited for, and refused only when they never arrive (the atlas's tools/unmerged.py,
    measured on its pull requests #32 and #92)."""
    lag = ""
    for wait in pr_waits():
        time.sleep(wait)
        pr, why = gh_api(f"repos/{repo}/pulls/{number}")
        if why or not isinstance(pr, dict):
            continue
        head = (pr.get("head") or {}).get("sha") or ""
        if head and tip and head != tip:
            lag = f"pull request #{number}'s head is {head[:7]}, not the pushed tip {tip[:7]}"
            continue
        lag = ""
        if pr.get("mergeable") is True:
            return True, ""
        if pr.get("mergeable") is False:
            return False, f"pull request #{number} conflicts with main ({pr.get('mergeable_state')})"
    if lag:
        return False, f"{lag} after {sum(pr_waits()):g} seconds; nothing merged, look again before merging"
    return False, (f"GitHub had not judged whether pull request #{number} can merge after "
                   f"{sum(pr_waits()):g} seconds; nothing merged, try again")


def land_by_pull_request(root: Path, branch: str, tip: str, by: str) -> int:
    """Open (or find) the branch's pull request and merge it on his word once GitHub has judged
    it mergeable, the pushed tip as the API's guard; never a push to main. 0 landed · 3 left
    pushed, link given."""
    repo, link = github_repo(root), f"{web_url(root)}/compare/main...{branch}"
    if not repo:
        print(f"unmerged: {branch} is clean against main and pushed; no pull request route here "
              f"(origin is not a GitHub repository), so it does not reach main: open one at {link}")
        return 3
    owner = repo.split("/")[0]
    q = urllib.parse.quote(f"{owner}:{branch}", safe=":/")
    prs, why = gh_api(f"repos/{repo}/pulls?head={q}&base=main&state=open")
    if why is None and not prs:
        prs, why = gh_api(f"repos/{repo}/pulls", "POST", {
            "title": f"{branch} (on {by}'s word)", "head": branch, "base": "main",
            "body": ("Opened by house/unmerged.py on DU's word: a branch the creation log records as "
                     "Claude's lands through a pull request (his rules of 2026-10-26, AT.49).")})
        prs = [prs] if isinstance(prs, dict) else prs
    if why or not prs:
        print(f"unmerged: {branch} is clean against main and pushed; the pull request could not be opened "
              f"({why or 'no answer'}), so it does not reach main: open one at {link}")
        return 3
    n, url = prs[0].get("number"), prs[0].get("html_url", link)
    mergeable, why = wait_mergeable(repo, n, tip)
    if not mergeable:
        print(f"unmerged: {branch} is pushed and pull request #{n} is open, but it was not merged: {why}; "
              f"its page: {url}")
        return 3
    done, why = gh_api(f"repos/{repo}/pulls/{n}/merge", "PUT", {
        "sha": tip, "merge_method": "merge", "commit_title": f"Merge pull request #{n}: {branch}, on {by}'s word"})
    if why or not (isinstance(done, dict) and done.get("merged")):
        print(f"unmerged: {branch} is pushed and pull request #{n} is open, but its merge was refused "
              f"({why or 'not merged'}); merge it at {url}")
        return 3
    print(f"unmerged: {branch} landed on main through pull request #{n} ({url}), merge commit "
          f"{str(done.get('sha', ''))[:7]}, guarded by the tip {tip[:7]} (AT.49)")
    clean, line = merge_commit_authors(root, repo, str(done.get("sha", "")))
    print(line)
    return 0 if clean else 6


def merge_commit_authors(root: Path, repo: str, sha: str) -> tuple[bool, str]:
    """(clean, line): GitHub authors a pull request's merge commit with the merging account's commit
    email, which no pre-commit check here sees, so the merge commit's author and committer are read
    through the API and hashed against the banned list (AP-review-0002, A3; A1's check; AP-all-0008/A2). A match is
    reported at once, as the commit and the fingerprint's first 8 characters, never the address; the
    merge has happened, so `merge` exits 6. A list or a commit it cannot read is UNMEASURED, said."""
    sys.path.insert(0, str(HERE))
    import guards  # noqa: E402  (house/guards.py, beside this file)
    try:
        own = os.environ.get("HOUSE_BANNED")
        text, _ = guards.read_banned(root, ["--file", own] if own else [])
        _, fps = guards.parse_banned(text)
    except (RuntimeError, ValueError) as e:
        return True, f"unmerged: the merge commit's author and committer: UNMEASURED: the banned list could not be read ({e})"
    data, why = gh_api(f"repos/{repo}/commits/{sha}")
    commit = (data or {}).get("commit") if isinstance(data, dict) else None
    if why or not isinstance(commit, dict):
        return True, (f"unmerged: the merge commit {sha[:7]}'s author and committer: UNMEASURED: "
                      f"{why or 'no commit in the answer'}; read it again with house/guards.py banned once main is fetched")
    hits = []
    for role in ("author", "committer"):
        addr = str((commit.get(role) or {}).get("email") or "")
        h = guards.fingerprint(addr) if addr.strip() else ""
        if h in fps:
            hits.append(f"{role} matches fingerprint {h[:8]} ({fps[h]})")
    if hits:
        return False, (f"unmerged: BANNED: the merge commit {sha[:7]} on {repo}: " + "; ".join(hits)
                       + ": report it to the operator now; no override exists (his banned-address rule)")
    return True, f"unmerged: the merge commit {sha[:7]}'s author and committer are clean against {len(fps)} fingerprint(s)"


def session_identity(explicit: str | None = None) -> tuple[str, str | None]:
    """('claude', session) inside a Claude session; ('not-claude', None) otherwise."""
    if explicit:
        return "claude", explicit
    if os.environ.get("CLAUDECODE") == "1":
        rid = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
        if rid.startswith("cse_"):
            return "claude", "https://claude.ai/code/session_" + rid[4:]
        sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        return "claude", (f"claude-code:{sid}" if sid else "claude-code")
    return "not-claude", None


def append_log(root: Path, events: list[dict]) -> None:
    p = root / LOG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def commit_log(root: Path, message: str, session: str | None) -> None:
    body = message + ("\n\nClaude-Session: " + session if session and session.startswith("http") else "")
    git(root, "add", LOG_PATH)
    git(root, "commit", "-q", "-m", body, "--", LOG_PATH)


def cmd_log_created(root: Path, branch: str, explicit: str | None) -> int:
    by, session = session_identity(explicit)
    append_log(root, [{"event": "created", "branch": branch, "by": by, "session": session,
                       "at": now_utc(), "base": git(root, "rev-parse", "HEAD")}])
    commit_log(root, f"branch: log {branch} at creation (the pruning rule)", session)
    print(f"branch: logged {branch} as created by {by}")
    return 0


def cmd_ready(root: Path, explicit: str | None) -> int:
    """IR-16: the owning session's last act at its close: mark the branch's tip as finished work."""
    branch = git(root, "branch", "--show-current", check=False)
    if not branch or branch == "main":
        print("unmerged: ready marks a session branch, never main or a detached HEAD")
        return 1
    dirty = blocking_changes(root)
    if dirty:
        print("unmerged: uncommitted work; commit and push it first, then mark the branch ready: " + ", ".join(dirty[:8]))
        return 1
    by, session = session_identity(explicit)
    work = git(root, "rev-parse", "HEAD")
    append_log(root, [{"event": "ready", "branch": branch, "work": work, "by": by, "session": session, "at": now_utc()}])
    commit_log(root, f"branch: mark {branch} ready at {work[:7]} (IR-16, the ready gate)", session)
    push = subprocess.run(["git", "-C", str(root), "push", "-q", "origin", branch], capture_output=True, text=True)
    if push.returncode != 0:
        print(f"unmerged: {branch} marked ready at {work[:7]} locally, but the push failed; push it, or the mark "
              "does not count: " + ((push.stderr or "").strip().splitlines() or ["refused"])[-1])
        return 1
    print(f"unmerged: {branch} marked ready at {work[:7]} and pushed; any later commit returns it to in progress")
    return 0


def git_path(root: Path, name: str) -> Path:
    p = Path(git(root, "rev-parse", "--git-path", name, check=False) or ".git/" + name)
    return p if p.is_absolute() else root / p


def read_reviews(root: Path) -> dict:
    try:
        return json.loads(git_path(root, REVIEWS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def review(root: Path, branch: str, policy: dict, use_cache: bool = True) -> tuple[str, str]:
    """('closable' | 'needs work', reason) at the branch's fetched tip: a throwaway worktree merges
    main (this house has no resolution policy, so any conflict needs work) and runs the policy's
    review command; nothing is committed or pushed, and the worktree is removed whatever happens."""
    tip = git(root, "rev-parse", "-q", "--verify", f"refs/remotes/origin/{branch}", check=False)
    if not tip:
        return "needs work", f"{branch} is not on origin"
    cache = read_reviews(root)
    hit = cache.get(branch) or {}
    if use_cache and hit.get("tip") == tip and hit.get("review") == policy["review"]:
        return hit["verdict"], hit["reason"]
    wt = Path(tempfile.mkdtemp(prefix="house-review-")) / "tree"
    ident = ["-c", "user.name=house review", "-c", "user.email=review@invalid", "-c", "commit.gpgsign=false"]
    try:
        git(root, "worktree", "add", "-q", "--detach", str(wt), tip)
        p = subprocess.run(["git", "-C", str(wt), *ident, "merge", "--no-commit", "--no-ff", "refs/remotes/origin/main"],
                           capture_output=True, text=True)
        if p.returncode != 0:
            hard = git(wt, "diff", "--name-only", "--diff-filter=U", check=False).splitlines()
            verdict, reason = "needs work", "it conflicts with main: " + ", ".join(hard or [(p.stderr or p.stdout).strip()[:120]])
        else:
            cmd = policy["review"]
            r = subprocess.run(cmd, shell=True, cwd=str(wt), capture_output=True, text=True, timeout=1800)
            last = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()][-1:]
            verdict, reason = (("closable", f"merges with main and `{cmd}` passes") if r.returncode == 0 else
                               ("needs work", f"`{cmd}` fails: " + (last[0] if last else f"exit {r.returncode}")))
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        verdict, reason = "needs work", f"the review could not run: {e}"
    finally:
        git(root, "worktree", "remove", "--force", str(wt), check=False)
        git(root, "worktree", "prune", check=False)
        shutil.rmtree(wt.parent, ignore_errors=True)
    cache[branch] = {"tip": tip, "review": policy["review"], "verdict": verdict, "reason": reason, "at": now_utc()}
    try:
        git_path(root, REVIEWS).write_text(json.dumps(cache, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass
    return verdict, reason


def cmd_review(root: Path, branch: str) -> int:
    fetch_all(root)
    verdict, reason = review(root, branch, read_policy(root), use_cache=False)
    print(f"unmerged: review of {branch}: {verdict} ({reason}); nothing was committed or pushed")
    return 0 if verdict == "closable" else 1


def cmd_brief(root: Path, branch: str) -> int:
    tip = git(root, "rev-parse", "-q", "--verify", f"refs/remotes/origin/{branch}", check=False)
    if not tip:
        print(f"unmerged: {branch} is not on origin")
        return 1
    g = gate(root, branch, tip, read_policy(root))
    hit = read_reviews(root).get(branch) or {}
    verdict = f"{hit['verdict']} ({hit['reason']})" if hit.get("tip") == tip else "not reviewed at this tip (house/unmerged.py review)"
    print(f"Resume brief: {branch}\n"
          f"- Owner: {g['owner'] or 'not recorded'}; tip {tip[:7]}, quiet {g['quiet']} days, state {g['kind']}.\n"
          f"- Review: {verdict}.\n"
          "- What finishing means: check out the branch, read its last commits and its handoff, finish the work it set "
          "out to do or say it cannot, run the house's checks green, push, then mark it ready with "
          "`python3 -I -B house/unmerged.py ready` as the last act. Nothing merges until DU's word on a ready branch.")
    return 0


# ------------------------------------------------------------------ pruning

def refs(root: Path, prefix: str) -> dict[str, str]:
    out = {}
    for line in git(root, "for-each-ref", "--format=%(refname)\t%(objectname)", prefix).splitlines():
        ref, sha = line.split("\t")
        out[ref[len(prefix):]] = sha
    return out


def prune_plan(root: Path):
    """(kept, to_prune, local_only), over the remote's Claude-logged branches merged into main."""
    main = git(root, "rev-parse", "-q", "--verify", "origin/main", check=False)
    if not main:
        return [], [], []
    current = git(root, "branch", "--show-current", check=False)
    logged = claude_logged(root)
    remote = {k: v for k, v in refs(root, "refs/remotes/origin/").items() if k not in ("main", "HEAD")}
    local = {k: v for k, v in refs(root, "refs/heads/").items() if k != "main"}
    rows = []
    for name, sha in sorted(remote.items()):
        if name == current or name not in logged or not ok(root, "merge-base", "--is-ancestor", sha, main):
            continue
        ts = int(git(root, "log", "-1", "--format=%ct", sha))
        rows.append({"branch": name, "sha": sha, "ts": ts, "remote": sha, "local": local.get(name),
                     "last": dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    rows.sort(key=lambda r: (-r["ts"], r["branch"]))
    local_only = [n for n, sha in sorted(local.items())
                  if n not in remote and n != current and n in logged and ok(root, "merge-base", "--is-ancestor", sha, main)]
    return rows[:KEEP], rows[KEEP:], local_only


def web_url(root: Path) -> str:
    url = git(root, "remote", "get-url", "origin", check=False)
    url = url[:-4] if url.endswith(".git") else url
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    return url


def present(root: Path, branch: str) -> list[str]:
    url = web_url(root)
    lines = [f"  {branch}", f"      path: refs/heads/{branch}"]
    if url.startswith("http"):
        lines.append(f"      link: {url}/tree/{branch}")
    return lines


def log_due(root: Path, doomed: list[dict], session: str | None) -> list[dict]:
    have = {(e.get("branch"), e.get("tip")) for e in read_log(root) if e.get("event") in ("due", "pruned")}
    return [{"event": "due", "branch": r["branch"], "tip": r["remote"], "last_commit": r["last"], "at": now_utc(),
             "session": session, "kept": KEEP, "reason": "the remote denied the delete"}
            for r in doomed if (r["branch"], r["remote"]) not in have]


def cmd_prune(root: Path, dry_run: bool, fetch: bool) -> int:
    if fetch:
        try:
            fetch_all(root)
        except RuntimeError as e:
            print(f"prune: fetch failed ({e}); nothing pruned")
            return 0
    kept, doomed, local_only = prune_plan(root)
    current = git(root, "branch", "--show-current", check=False)
    by, session = session_identity()
    if by != "claude" and not dry_run:
        print(f"prune: not a Claude session; nothing pruned ({len(doomed)} due; a Claude session prunes them at its next house/branch.sh)")
        return 0
    if local_only and not dry_run:
        for n in local_only:
            git(root, "branch", "-q", "-D", n)
        print(f"prune: cleared {len(local_only)} merged Claude branch(es) that existed only in this workspace: " + ", ".join(local_only))
    if not doomed:
        print(f"prune: {len(kept)} of Claude's merged branches on the remote, all within the newest {KEEP}; nothing to prune")
        return 0
    if dry_run or current in ("", "main"):
        print(f"prune: {len(doomed)} of Claude's merged branches are past the newest {KEEP}:")
        for r in doomed:
            print(f"  {r['branch']:<44} last commit {r['last']}  tip {r['sha'][:7]}")
        if not dry_run:
            print("prune: on main; the record must be committed on a session branch, so pruning runs at the next house/branch.sh")
        return 0
    denied = root / ".git" / "prune-denied"
    events, done = [], []
    if denied.exists():
        print(f"prune: this workspace's git access refuses branch deletion (recorded {denied.read_text().strip()}); not retried.")
        print(f"prune: {len(doomed)} could not be deleted here; present each to DU by its full name and path:")
        for r in doomed:
            print("\n".join(present(root, r["branch"])))
        events = log_due(root, doomed, session)
        doomed = []
    for r in doomed:
        p = subprocess.run(["git", "-C", str(root), "push", "-q", f"--force-with-lease=refs/heads/{r['branch']}:{r['remote']}",
                            "origin", f":refs/heads/{r['branch']}"], capture_output=True, text=True)
        if p.returncode != 0:
            why = (p.stderr or p.stdout or "").strip()
            if re.search(r"\b40[37]\b", why):
                # a policy denial: reported, never retried or routed around; remembered for this workspace
                denied.write_text(f"{now_utc()}: {next((l for l in why.splitlines() if '40' in l), why.splitlines()[-1])}\n")
                print("prune: this workspace's git access refuses branch deletion (HTTP 403); stopped, not retried.")
                rest = doomed[len(done):]
                print(f"prune: {len(rest)} could not be deleted here; present each to DU by its full name and path:")
                for x in rest:
                    print("\n".join(present(root, x["branch"])))
                events += log_due(root, rest, session)
                break
            print(f"prune: kept {r['branch']}: the remote refused the delete ({why.splitlines()[-1] if why else 'no reason given'}); present it to DU:")
            print("\n".join(present(root, r["branch"])))
            continue
        events.append({"event": "pruned", "branch": r["branch"], "tip": r["remote"], "last_commit": r["last"],
                       "at": now_utc(), "session": session, "kept": KEEP})
        if r["local"] and ok(root, "merge-base", "--is-ancestor", r["local"], git(root, "rev-parse", "origin/main")):
            git(root, "branch", "-q", "-D", r["branch"])
        done.append(r["branch"])
    if events:
        append_log(root, events)
        n_pruned = sum(1 for e in events if e["event"] == "pruned")
        n_due = len(events) - n_pruned
        commit_log(root, f"branch: prune {n_pruned} merged Claude branch(es) past the newest {KEEP}"
                   + (f"; {n_due} due, the remote denied the delete" if n_due else "") + " (the pruning rule)", session)
        if git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False):
            git(root, "push", "-q", check=False)
    if not done:
        return 0
    print(f"prune: pruned {len(done)} of Claude's merged branches past the newest {KEEP} (kept {len(kept)}):")
    for b in done:
        print(f"  {b}")
    print("prune: restore any with house/unmerged.py restore <branch>")
    return 0


def cmd_restore(root: Path, branch: str) -> int:
    ev = [e for e in read_log(root) if e.get("event") in ("pruned", "due") and e.get("branch") == branch]
    if not ev:
        print(f"restore: no pruned record for {branch} in {LOG_PATH}")
        return 1
    tip = ev[-1]["tip"]
    p = subprocess.run(["git", "-C", str(root), "push", "-q", f"--force-with-lease=refs/heads/{branch}:", "origin",
                        f"{tip}:refs/heads/{branch}"], capture_output=True, text=True)
    if p.returncode != 0:
        print(f"restore: the remote refused {branch} at {tip[:7]} ({(p.stderr or 'exists').strip().splitlines()[-1]})")
        return 1
    print(f"restore: {branch} pushed back at {tip[:7]}")
    return 0


def prune_line(root: Path):
    _, doomed, _ = prune_plan(root)
    if not doomed:
        return None
    return (f"pruning: {len(doomed)} of Claude's merged branches are past the newest {KEEP} ("
            + ", ".join(r["branch"] for r in doomed) + "); pruned at the next house/branch.sh")


# ------------------------------------------------------------------ check, snooze, merge

def cmd_check(root: Path, as_json: bool, fetch: bool) -> int:
    rows = unmerged(root, fetch=fetch)
    due = [r for r in rows if not r["snoozed"]]
    if as_json:
        print(json.dumps(rows, indent=1))
        return 0
    pl, hb = prune_line(root), head_branch_line(root)
    if not rows:
        print("unmerged: every remote branch is merged into main")
        for line in (pl, hb):
            if line:
                print(line)
        return 0
    policy = read_policy(root)
    for r in due:
        if r["kind"] == "stalled":                        # IR-16: reviewed, never merged
            hit = read_reviews(root).get(r["branch"]) or {}
            r["review"], r["reason"] = (review(root, r["branch"], policy) if fetch else
                                        (hit["verdict"], hit["reason"]) if hit.get("tip") == r["tip"] else
                                        ("not reviewed", "run house/unmerged.py review " + r["branch"]))
    kinds = ", ".join(f"{n} {k}" for k in ("ready", "in progress", "stalled", "yours")
                      if (n := sum(1 for r in due if r["kind"] == k)))
    print(f"unmerged: {len(due)} branch(es) not merged into main" + (f" ({kinds})" if kinds else "")
          + (f", {len(rows) - len(due)} snoozed" if len(rows) > len(due) else ""))
    print("  branch                                    ahead behind  last        tip      author      gate         state")
    for r in rows:
        st = r["state"] + (f" until {r['until']}" if r["state"] == "snoozed" else "")
        print(f"  {r['branch']:<42}{r['ahead']:>5} {r['behind']:>6}  {r['date']}  {r['sha']:<7}  {r['author'][:10]:<10}  "
              f"{r['kind']:<11}  {st}")
    if any(r["kind"] in ("ready", "yours") for r in due):
        print("put each ready branch, and each of DU's, to DU in his question widget, its tip shown: merge now, keep "
              "reminding, snooze a week, snooze a month (a branch of Claude's merges with `--tip` the tip he was shown)")
    if any(r["kind"] == "in progress" for r in due):
        print(f"in progress: listed, never offered, until its session marks it ready; stalled at {policy['quiet_days']} days quiet")
    for r in (x for x in due if x["kind"] == "stalled"):
        print(f"stalled: {r['branch']} quiet {r['quiet']} days (owner {r['owner'] or 'not recorded'}); review at "
              f"{r['sha']}: {r['review']} ({r['reason']})")
        print("  put to DU: " + ("close it out as it stands (merge --as-is), hand it back to its session, snooze, keep reminding"
                                 if r["review"] == "closable" else
                                 f"hand it to its module's agent (house/unmerged.py brief {r['branch']}), a developer checks it, snooze, keep reminding"))
    for line in (pl, hb):
        if line:
            print(line)
    return 0


def cmd_snooze(root: Path, branch: str, days: int, by: str) -> int:
    today = dt.date.today()
    until = (today + dt.timedelta(days=days)).isoformat()
    write_snooze(root, branch, {"state": "snoozed", "until": until, "on": today.isoformat(), "by": by})
    print(f"unmerged: {branch} snoozed {days} days, until {until} (commit {SNOOZE_PATH})")
    return 0


def cmd_watch(root: Path, branch: str, by: str) -> int:
    write_snooze(root, branch, {"state": "watch", "on": dt.date.today().isoformat(), "by": by})
    print(f"unmerged: {branch} kept on watch; it is reported at every branch creation and boot (commit {SNOOZE_PATH})")
    return 0


def guards_green(root: Path) -> tuple[bool, str]:
    tool = root / "house" / "guards.py"
    if not tool.exists():
        return True, ""
    p = subprocess.run([sys.executable, "-I", "-B", str(tool), str(root), "check", "--base", "origin/main"],
                       capture_output=True, text=True)
    return p.returncode == 0, p.stdout


def blocking_changes(root: Path) -> list:
    """Every uncommitted change. (The soul house exempts its live act gate's ledger here;
    this house runs no act gate, so nothing is exempt.)"""
    p = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1", "-z"], capture_output=True, text=True)
    out = []
    for entry in (p.stdout or "").split("\0"):
        if len(entry) < 4:
            continue
        st, path = entry[:2], entry[3:]
        out.append(f"{st.strip() or '?'} {path}")
    return out


def cmd_merge(root: Path, branch: str, by: str, shown: str | None = None, as_is: bool = False) -> int:
    dirty = blocking_changes(root)
    if dirty:
        print("unmerged: the working tree is not clean; commit or stash first: " + ", ".join(dirty[:8])
              + (f" (+{len(dirty) - 8} more)" if len(dirty) > 8 else ""))
        return 1
    fetch_all(root)
    claude = is_claude(root, branch)                      # AT.49: by the log, never by the commits
    if claude:
        now = git(root, "rev-parse", "-q", "--verify", f"origin/{branch}", check=False)
        if not shown:
            print(f"unmerged: {branch} is Claude's by the creation log, so it lands only by a pull request "
                  "guarded by the tip DU was shown: pass --tip <sha> from the check's table")
            return 1
        if not now.startswith(shown):
            print(f"unmerged: {branch} moved since DU was shown {shown} (it is at {now[:7]}); nothing merged, "
                  "show him the new tip")
            return 1
        g = gate(root, branch, now, read_policy(root))     # IR-16: the ready gate, before anything is merged
        if g["kind"] != "ready" and not as_is:
            why = "it was never marked ready" if g["mark"] == "none" else "commits came after its ready mark"
            print(f"unmerged: {branch} is {g['kind']} at {now[:7]} ({why}); only a ready branch is merged. Nothing "
                  "changed. Its session marks it ready at its close (house/unmerged.py ready), or DU closes it out "
                  f"as it stands (merge {branch} --tip {now[:7]} --as-is).")
            return 4
    # the merge works in a temporary worktree, detached at the branch's tip, so the
    # checkout is never checked out over or written
    wt = Path(tempfile.mkdtemp(prefix="house-merge-")) / "tree"
    git(root, "worktree", "add", "-q", "--detach", str(wt), f"origin/{branch}")
    try:
        return _merge_in(root, wt, branch, by + (", as it stands" if as_is else ""), claude)
    finally:
        git(root, "worktree", "remove", "--force", str(wt), check=False)
        git(root, "worktree", "prune", check=False)
        shutil.rmtree(wt.parent, ignore_errors=True)


def _merge_in(root: Path, wt: Path, branch: str, by: str, claude: bool) -> int:
    p = subprocess.run(["git", "-C", str(wt), "merge", "--no-commit", "--no-ff", "origin/main"], capture_output=True, text=True)
    conflicted = git(wt, "diff", "--name-only", "--diff-filter=U").splitlines() if p.returncode != 0 else []
    if p.returncode != 0:
        git(wt, "merge", "--abort", check=False)
        print("unmerged: the merge of main into the branch conflicts; nothing was committed and the operator resolves these:")
        for f in conflicted or [(p.stderr or p.stdout).strip()]:
            print(f"  {f}")
        return 2
    green, report = guards_green(wt)
    if not green:
        git(wt, "merge", "--abort", check=False)
        print("unmerged: the merged tree fails the house guards; the merge was not committed:")
        print(report.rstrip())
        return 2
    by_line, session = session_identity()
    msg = (f"Merge main into {branch} (the unmerged rule, on {by}'s word)\n\nBy house/unmerged.py; the merged tree passed house/guards.py."
           + (f"\n\nClaude-Session: {session}" if session and session.startswith("http") else ""))
    if ok(wt, "rev-parse", "-q", "--verify", "MERGE_HEAD"):
        git(wt, "commit", "-q", "-m", msg)
    git(wt, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    if claude:                                            # AT.49: by pull request, never a push to main
        tip = git(wt, "rev-parse", "HEAD")
        rc = land_by_pull_request(root, branch, tip, by)
        if rc == 0:
            try:
                fetch_all(root)
            except RuntimeError:
                pass
        return rc
    ff = subprocess.run(["git", "-C", str(wt), "push", "-q", "origin", "HEAD:refs/heads/main"], capture_output=True, text=True)
    if ff.returncode == 0:
        print(f"unmerged: {branch} merged into main (fast-forward) and pushed")
        return 0
    why = (ff.stderr or "").strip().splitlines()
    print(f"unmerged: {branch} is clean against main and pushed, but main refused the push ({why[-1] if why else 'protected'}).")
    print(f"  merge it in the remote's web interface: {web_url(root)}/pull/new/{branch}")
    return 3


def main(argv) -> int:
    args = list(argv[1:])
    root_arg = args.pop(0) if args and args[0] not in COMMANDS and Path(args[0]).is_dir() else None
    if root_arg:
        root = Path(root_arg).resolve()
    elif ok(Path.cwd(), "rev-parse", "--show-toplevel"):
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()
    else:
        root = Path.cwd().resolve()
    if not args or args[0] not in COMMANDS:
        print(__doc__)
        return 2
    # an unpacked archive carries no .git; a check that cannot run says so (NOT RUN,
    # the guards' own words) and is never a traceback or a verdict
    if not (ok(root, "rev-parse", "--git-dir") and (root / ".git").exists()):
        print(f"unmerged: NOT RUN: no repository at {root} (an unpacked archive carries no .git); "
              "a check that cannot run is not a pass")
        return 0
    cmd = args.pop(0)
    by = args[args.index("--by") + 1] if "--by" in args else "DU"
    if cmd == "check":
        return cmd_check(root, "--json" in args, "--no-fetch" not in args)
    if cmd == "snooze":
        return cmd_snooze(root, args[0], int(args[args.index("--days") + 1]) if "--days" in args else 7, by)
    if cmd == "watch":
        return cmd_watch(root, args[0], by)
    if cmd == "merge":
        return cmd_merge(root, args[0], by, args[args.index("--tip") + 1] if "--tip" in args else None, "--as-is" in args)
    if cmd == "ready":
        return cmd_ready(root, args[args.index("--claude-session") + 1] if "--claude-session" in args else None)
    if cmd in ("review", "brief"):
        return (cmd_review if cmd == "review" else cmd_brief)(root, args[0]) if args else (print(__doc__) or 2)
    if cmd == "log-created":
        explicit = args[args.index("--claude-session") + 1] if "--claude-session" in args else None
        return cmd_log_created(root, args[0], explicit)
    if cmd == "prune":
        return cmd_prune(root, "--dry-run" in args, "--no-fetch" not in args)
    return cmd_restore(root, args[0])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
