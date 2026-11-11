#!/usr/bin/env bash
# check.sh: the house check (trains review-T1 and review-T2). Runs at boot, before every commit, at close, and in
# CI on every pull request. Review's own tools are standard library Python; the house kit's tests need pytest.
#
#   bash tools/check.sh [--atlas DIR]
#
# With an atlas checkout, it also re-reads the two copies against the atlas, runs the atlas's own pin test on this
# house and reads the banned fingerprints from it (AT.765); without one those read NOT RUN or UNREACHABLE, which
# stays green and is said.
set -u
cd "$(dirname "$0")/.."
ATLAS=""
if [ "${1:-}" = "--atlas" ]; then ATLAS="${2:-}"; fi
red=0
step() {  # step NAME CMD...
  local name="$1"; shift
  if out="$("$@" 2>&1)"; then
    echo "  [ok]  $name"
  else
    echo "  [RED] $name"; echo "$out" | sed 's/^/        /' | tail -20; red=1
  fi
}
echo "review house check"
step "catalog (events, proposals, allowlist)" python3 -I -B tools/catalog.py check
if [ -n "$ATLAS" ]; then
  step "atlas copies (against the atlas)" python3 -I -B tools/atlas_copy.py check "$ATLAS"
  step "ruleset pin (the atlas's contract test)" python3 -I -B "$ATLAS/contracts/tests/ruleset_pin.py" "$ATLAS" . review
else
  step "atlas copies (shape)" python3 -I -B tools/atlas_copy.py check
  echo "  [--]  ruleset pin: NOT RUN (no atlas checkout; pass --atlas DIR)"
fi
step "intake form (generated, REVIEW's order)" python3 -I -B tools/form.py --check
step "tree guard (never-store paths and contents)" python3 -I -B tools/intake.py tree
step "union merge on the event log" grep -qx 'catalog/events.jsonl merge=union' .gitattributes
if [ -n "$ATLAS" ]; then
  step "the house kit (house/check.sh: guards, banned addresses, self-check, queue, pin, kit tests)" bash house/check.sh --atlas "$ATLAS"
else
  step "the house kit (house/check.sh: guards, banned addresses, self-check, queue, kit tests)" bash house/check.sh
fi
step "tests" python3 -I -B -m unittest discover -s tests -t . -q
step "sabotage (each check broken once goes red)" python3 -I -B tests/sabotage.py
if [ "$red" = 0 ]; then echo "check: green"; else echo "check: RED"; fi
exit "$red"
