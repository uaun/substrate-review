#!/usr/bin/env bash
# house/branch.sh: create a session branch named by DU's branch naming rule,
#   session/<YYYY-MM-DD>/<NN>-<slug>
# and claim it on the remote the moment it exists (IR-13; AP-review-0002, A1 and A2; ported from Jetsam's house/ at f97c6f7 for Review's house (AP-review-0002), which re-derived the soul house's tools;
# ported from the soul house's house/branch.sh at f6468fe, by way of Grade's port at
# 26c4a9d, the reference read at 7c339e8, and re-derived for this house).
#
# The day is UTC. NN is the day's count, two digits, the highest found on the remote,
# locally and in the creation log for the day, plus one; a number the log holds is never
# reused, even after its branch is pruned. Branches pushed under the older
# session/<day>-<slug> shape count one each. If the remote cannot be listed, local
# branches and the log are counted and the script says so.
#
# The claim: the branch's first commit is its creation line in house/branches.jsonl
# (by claude inside a Claude session, not-claude otherwise; A2), then it is pushed with a
# lease that requires the ref not to exist on the remote. A refused push means another
# session claimed that count first: the local branch is dropped, the count recomputed
# from the remote, and the claim retried (three attempts). After the claim, Claude's
# merged branches past the newest 10 are pruned and the unmerged check runs (A3), whose
# ready branches, and DU's, the session puts to DU.
#
# Usage: house/branch.sh <slug> [--print] [--no-push] [--claude-session URL]
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="house/branches.jsonl"
slug="${1:-}"
usage="usage: house/branch.sh <slug> [--print] [--no-push] [--claude-session URL]"
[ -n "$slug" ] || { echo "$usage"; exit 2; }
case "$slug" in
  *[!a-z0-9-]*|-*|*-) echo "branch: slug must be lowercase-with-dashes: $slug"; exit 2;;
esac
shift
mode=""; claude_session=""
while [ $# -gt 0 ]; do
  case "$1" in
    --print|--no-push) mode="$1";;
    --claude-session) claude_session="${2:-}"; shift;;
    *) echo "$usage"; exit 2;;
  esac
  shift
done
day="$(date -u +%Y-%m-%d)"
cd "$ROOT" || exit 1

next_name() {
  remote_ok=1
  remote_list="$(git ls-remote --heads origin "refs/heads/session/$day/*" "refs/heads/session/$day-*" 2>/dev/null)" || remote_ok=0
  local_list="$(git for-each-ref --format='%(refname:short)' "refs/heads/session/$day/" "refs/heads/session/$day-*" 2>/dev/null)"
  logged_list="$( { cat "$ROOT/$LOG" 2>/dev/null; git show "origin/main:$LOG" 2>/dev/null; } \
    | grep -oE "\"branch\": *\"session/$day/[0-9]{2}-[a-z0-9-]+\"" | sed -E 's/.*"(session[^"]+)"$/\1/')"
  max=0; old=0
  for ref in $(printf '%s\n%s\n%s\n' "$remote_list" "$local_list" "$logged_list" | sed -E 's#^.*refs/heads/##' | awk 'NF{print $NF}' | sort -u); do
    n="$(printf '%s' "$ref" | sed -nE "s#^session/$day/([0-9]{2})-.*#\1#p")"
    if [ -n "$n" ]; then
      [ "$((10#$n))" -gt "$max" ] && max=$((10#$n))
    elif printf '%s' "$ref" | grep -qE "^session/$day-[a-z0-9-]+$"; then
      old=$((old + 1))
    fi
  done
  [ "$old" -gt "$max" ] && max=$old
  next=$((max + 1))
  [ "$next" -le 99 ] || { echo "branch: the day already has 99 branches"; exit 1; }
  name="$(printf 'session/%s/%02d-%s' "$day" "$next" "$slug")"
}

log_created() {
  python3 -I -B "$ROOT/house/unmerged.py" "$ROOT" log-created "$name" ${claude_session:+--claude-session "$claude_session"} >/dev/null \
    || { echo "branch: could not log $name in $LOG"; exit 1; }
}

next_name
[ "$remote_ok" -eq 1 ] || echo "branch: remote unreachable; counted local branches and the log only"
if [ "$mode" = "--print" ]; then echo "$name"; exit 0; fi

if [ "$mode" = "--no-push" ] || [ "$remote_ok" -eq 0 ]; then
  git checkout -q -b "$name" && log_created && echo "branch: $name (local only; not claimed on the remote)"
  exit 0
fi
claimed=0
for attempt in 1 2 3; do
  git checkout -q -b "$name" || exit 1
  log_created
  # an empty expected value in the lease: the ref must not exist on origin yet, so a
  # same-commit branch another session already pushed is refused, never silently shared
  if git push -q -u --force-with-lease="refs/heads/$name:" origin "$name" 2>/dev/null; then
    claimed=1; echo "branch: $name (claimed on origin)"; break
  fi
  echo "branch: $name was claimed by another session; recounting"
  git checkout -q - && git branch -q -D "$name"
  git fetch -q origin 2>/dev/null
  next_name
done
[ "$claimed" -eq 1 ] || { echo "branch: could not claim a name after 3 attempts"; exit 1; }
python3 -I -B "$ROOT/house/unmerged.py" "$ROOT" prune
python3 -I -B "$ROOT/house/unmerged.py" "$ROOT" check --no-fetch
