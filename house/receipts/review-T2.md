# Receipt: train review-T2, alignment prompt AP-review-0002

The house kit, delivered by the atlas from the Jetsam setup chat (AT.44) on DU's ratification "Ratify, deliver now (Recommended)" (AT.769), as a branch and pull request in this house. The prompt is the atlas's `frameworks/review/engineering/alignment/prompts/T2/`, read at the atlas commit `41cdab3` that ratifies it. This receipt is the house's; an atlas session copies it to `frameworks/review/engineering/alignment/receipts/T2/README.md` and confirms it against `main` after DU's merge.

## Commits

On `session/2026-11-11/01-review-t2-house-kit`, from `main` at `8af23f4`:

| commit | what |
|---|---|
| `d856c8f` | the branch's creation line, by hand in the tool's format, with review-T1's branch seeded after the fact, and the filings: A1 to A7 and the eight carried family items in `WORK.md`'s atlas items, before any build (IR-8) |
| `73fc716` | A1 to A6: the kit in `house/`, `ops/branch-policy.yaml`, `.gitattributes`, `.gitignore`, the verify workflow's pytest step, `tools/check.sh` running the kit, the sabotage pass's ten kit mutations, the first queue pull's filings and arrivals, and review-T1's items marked landed |
| `2dcb716` | A7: `HANDOFF.md`, `BOOT_PROMPT.md`, the receipt lines in `SUBSTRATE.md` |
| this commit | the state file's landed marks, the vectors' not-applicable reply, and this receipt |

## Items

| item | state | measured |
|---|---|---|
| A1, the guards, the banned-address check and one house check | landed at `73fc716` | `bash tools/check.sh --atlas <atlas>` green. The guards read 0 findings: 3 union logs, 2 id spaces, 11 never-store paths, 4 content patterns, 4 owned files. The mirror is CURRENT with the atlas at `7833d57`. The banned addresses are CLEAN against the atlas's list read at `7833d57`, across 6 commits after `since`, the staged changes and every tracked text file. No file of the house holds a fingerprint. |
| A2, the creation log | landed at `73fc716` | `house/branches.jsonl` names this branch (written by hand before the tool, as its first commit) and seeds `session/2026-11-10/01-review-t1-setup` as Claude's, merged at `8af23f4`; the log check refuses a branch created twice and a line written twice (the kit's tests). |
| A3, the unmerged check, merging, pruning, the ready gate | landed at `73fc716` | the ready-gate and merge tests pass, the merge-commit tests included: a merge commit authored by a banned address exits 6 with the fingerprint's first 8 characters only, and an unreadable list reads UNMEASURED, never clean. |
| A4, the queue pull | landed at `73fc716` | the first pull at the atlas's `41cdab3` read 25 items. It recorded the 15 filed by hand (this train's seven and the eight it carries), filed the other 10 in `WORK.md` waiting on DU's rank, and filed none twice. `verify` reads the state file well-formed. |
| A5, the replies | landed at `73fc716` | 9 arrivals were written, one per prompt with an item in the first pull (AP-all-0002 to AP-all-0009 and AP-review-0002), plus one not-applicable reply for AP-all-0006/A3. |
| A6, the skeleton | landed at `73fc716` | `git check-attr filter` reads `lfs` for x.png, x.wav, x.mp4, x.pdf, x.zip and x.glb, and `unspecified` for x.md, x.json and x.svg. `git check-ignore` matches `x/__pycache__/a.pyc`, `.venv/a`, `a/.DS_Store`, `a/SubstrateSoulData/b` and `a/.env`, and not `SUBSTRATE.md` or `README.md`. |
| A7, the gap closed, the self-check, the boot prompt | landed at `2dcb716` | `HANDOFF.md` names no missing guard. `BOOT_PROMPT.md` starts with Rule 0 verbatim. The self-check reads MATCH (slug review, stage house, parent reflection, house uaun/substrate-review) and gate open (AT.721). The pin test passes all seven checks. Its negative control is a test: a registry row edited to `proposal` is named as a difference. |
| AP-all-0002/A2, AP-all-0003/A2 | landed at `73fc716` | carried by A5 and A3 |
| AP-all-0006/A1, A2 | landed at `73fc716` | carried by A6 |
| AP-all-0006/A3 | not applicable | the house has no byte-exact test vectors; the reply says so |
| AP-all-0008/A1, A2 | landed at `73fc716` | carried by A1 and A3, as AT.765 amends them for a public house |
| AP-all-0008/A3 | landed at `2dcb716` | carried by A7: the boot prints the banned-address line naming the atlas commit read |

Tests: 95 in the kit (`house/tests`, pytest) and 51 in `tests/` (unittest), all passing. The sabotage pass breaks each of 31 checks once in a throwaway copy, Review's 21 and ten of the kit's, and every one turns the tests red.

## Deviations from Jetsam's port, each with its reason

1. **One never-store copy.** Jetsam's `house/guards.json` holds the list itself. This house already keeps the atlas's list in `catalog/never-store.json` for its intake and tree guard, so `guards.json` names that file (`never_store_file`) and `house/guards.py` reads it through `load_cfg`. One copy cannot drift from a second.
2. **A fingerprint committed anywhere is refused (AT.765).** This house is public, so `banned` also reads every tracked text file for a 64-hex string that equals one of the atlas's fingerprints. The list itself is never read from the house: only from `--atlas DIR`, the API, or a test's `--file`.
3. **The `.gitignore` mirror is the atlas's globs as written.** Review-T1 mirrored the globs in git's short form (`SubstrateSoulData/`). The kit's mirror check compares the globs themselves, so the mirror is now those globs, between Jetsam's marker lines. `tools/lib.py`'s `gitignore_form` became the identity, and the tree guard reads the same block.
4. **The open work is `WORK.md`'s atlas items.** Jetsam files into `HANDOFF.md`. This house keeps its backlog in `WORK.md`, so `OPEN_WORK` and the guards' atlas-items id space read `WORK.md`, and its end marker became the pull's own (`<!-- end house section -->`).
5. **The kit's check runs inside the house check.** `tools/check.sh` stays the one command a session, CI and `ops/branch-policy.yaml` run; it runs `house/check.sh` as a step and passes `--atlas` through. Jetsam's enum-digest step and its `jetsam/local/` entries and tests are left behind.
6. **The kit's tests need pytest, and CI installs it.** Review's own tests stay unittest. The verify workflow installs pytest 9.1.1, the version these tests ran under here.
7. **The sabotage pass runs the kit's mutations against their own test files**, stopping at the first failure. A caught mutation costs seconds rather than the minute the whole kit suite takes.
8. **The emitter's comparison excludes the `installed` row**, as Jetsam's and Strata's receipts record. `tools/registry.py --emit review --from SUBSTRATE.md` equals this `SUBSTRATE.md` byte for byte except that row, which carries the day it runs (2026-11-11 against 2026-11-10).
9. **AP-all-0007/A1 and AP-all-0009/A1 are filed, not built.** Both ask that the reply writer accept a kind (`not-applicable`, `reading`). The ported `house/atlas_replies.py` may already accept both, since the not-applicable reply above was written by it. They wait on DU's rank like the other filed items, because this prompt did not carry them.

## Not done here

- `main`'s ruleset (AT.117) is DU's to apply; it may now require the verify workflow's `check` job.
- The ten items the first pull filed (AP-all-0004/A1 to A6, AP-all-0005/A1 and A2, AP-all-0007/A1, AP-all-0009/A1) wait on DU's rank.
