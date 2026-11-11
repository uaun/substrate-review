#!/usr/bin/env bash
# house/check.sh: the house kit's check (AP-review-0002, A1; ported from Jetsam's house/check.sh at
# f97c6f7). One command runs every guard of the kit and its tests; tools/check.sh, the house check
# HANDOFF.md names and the review command of ops/branch-policy.yaml, runs it as one of its steps.
#
#   bash house/check.sh [--atlas DIR] [--no-tests]
#
#   1. house/guards.py check: IR-13's guards on this tree (union logs, duplicate ids, the
#      creation log, the never-store mirror and tracked files, owned files)
#   2. house/guards.py mirror: this house's never-store copy against the atlas's at its main,
#      from DIR when given, else through gh; UNREACHABLE is said and stays green, DIFFERS is red
#   3. house/guards.py banned: git's user.email, the author and committer of every commit on main
#      and on the branch committed after the banned list's `since`, and the staged changes,
#      hashed against the atlas's fingerprints (the operator's banned-address rule); a match is red
#      with no override, an unreachable atlas is UNREACHABLE and stays green
#   4. house/selfcheck.py: this house's registry row at the atlas's main against SUBSTRATE.md, and
#      the gate (IR-17, IR-18); DIFFERS and a closed gate are red, UNREACHABLE stays green
#   5. house/atlas_queue.py verify: the queue's state file has the shape the atlas reads
#   6. with --atlas DIR only: the atlas's own pin test, contracts/tests/ruleset_pin.py, read-only
#   7. the kit's tests (python3 -m pytest house/tests), unless --no-tests; Review's own tests
#      (tests/, unittest) are tools/check.sh's
#
# Exit 0 only when every step that ran passed and the tests ran; a step that cannot run says
# NOT RUN, and tests that cannot run are not a pass.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
atlas=""; tests=1
while [ $# -gt 0 ]; do
  case "$1" in
    --atlas) atlas="${2:-}"; shift;;
    --no-tests) tests=0;;
    *) echo "usage: bash house/check.sh [--atlas DIR] [--no-tests]"; exit 2;;
  esac
  shift
done
slug="$(sed -nE 's/^\| *slug *\| *([a-z0-9-]+) *\| *$/\1/p' SUBSTRATE.md 2>/dev/null | head -1)"
fail=0

echo "== the guards"
python3 -I -B house/guards.py "$ROOT" check || fail=1

echo "== the never-store mirror"
python3 -I -B house/guards.py "$ROOT" mirror ${atlas:+--atlas "$atlas"} || fail=1

echo "== the banned addresses"
python3 -I -B house/guards.py "$ROOT" banned ${atlas:+--atlas "$atlas"} || fail=1

echo "== the self-check against the registry"
python3 -I -B house/selfcheck.py "$ROOT" ${atlas:+--atlas "$atlas"} || fail=1

echo "== the queue's state file"
if [ -f house/atlas_queue.py ]; then
  python3 -I -B house/atlas_queue.py "$ROOT" verify || fail=1
else
  echo "atlas queue: NOT RUN: no house/atlas_queue.py"
fi

echo "== the ruleset pin"
if [ -n "$atlas" ] && [ -f "$atlas/contracts/tests/ruleset_pin.py" ]; then
  python3 -I "$atlas/contracts/tests/ruleset_pin.py" "$ROOT" "${slug:-review}" || fail=1
else
  echo "ruleset pin: NOT RUN: no atlas checkout given (--atlas DIR); the atlas runs it on the receipt"
fi

echo "== the house's tests"
if [ "$tests" -eq 0 ]; then
  echo "tests: NOT RUN (--no-tests); this run is not a pass"
  fail=1
elif python3 -I -c "import pytest" 2>/dev/null; then
  python3 -I -B -m pytest -q -p no:cacheprovider house/tests || fail=1
else
  echo "tests: NOT RUN: pytest is not installed here; this run is not a pass"
  fail=1
fi

if [ "$fail" -eq 0 ]; then echo "house check: GREEN"; else echo "house check: RED"; fi
exit "$fail"
