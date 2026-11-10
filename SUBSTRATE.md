# SUBSTRATE.md

This house is a registered Substrate framework. This file is the inherited ruleset's pin and the house's registration, installed under Rule 1 (DU's preferences) and carried by every handoff under Rule 0: `HANDOFF.md` lists this file among the rules the folder lists, and a successor activates it at boot.

## Registration

| field | value |
| --- | --- |
| slug | review |
| name | Substrate Review |
| stage | house |
| parent | reflection |
| house | https://github.com/uaun/substrate-review |
| registered | 2026-10-27 |
| gate | open, by DU's ruling AT.721: sessions opened for this house work here as usual |
| atlas | https://github.com/uaun/substrate-atlas, `frameworks/REGISTRY.yaml` |

The gate is held in the atlas's registry and changes only by DU's ruling (the house rule, AT.142); every emission carries it, and the house shows it at every boot.

## Purpose

Substrate Review lets verified contributors propose to Substrate and hear back why: each proposal is read as data, two stateless readers answer it with a provisional verdict and a marked reading, and only the owner's ruling accepts or declines it.

It serves the mission by opening the family to outside thought without letting outside text steer it: every verdict cites the rules it rests on, and nothing enters the atlas except by the owner's word.

Worded on DU's word (AT.724, 2026-11-10) and kept as this framework's `purpose` in the atlas's `frameworks/REGISTRY.yaml`; it changes only there, and every emission carries it (IR-1).

## The inherited ruleset

| field | value |
| --- | --- |
| version | 1.7.0 |
| sha256 | 7ec9e8765c78007933f961c2a3a3265dca6b1781e97e04662e621adcadf944be |
| canonical | `charter/inheritance/RULESET.md` at the atlas's `main` |
| installed | 2026-11-10 |

The ruleset's 18 rules (IR-1 to IR-18) bind in this house under DU's standing rules. Where this copy differs from the atlas's `main`, the atlas wins and the difference is reported at the next boot. The pin above changes only by an alignment prompt DU has ratified, or by his word.

# The inherited ruleset, v1.7.0

Every registered Substrate framework with a house of its own carries this ruleset at its house root as `SUBSTRATE.md`, at a pinned version and hash, and lists that file in its `HANDOFF.md` so that Rule 0 activates it at every boot and every handoff carries it down the line. It binds under DU's standing rules (ruled 2026-10-24, AT.16). A house that cannot meet a rule files a refusal with its reason; it never deviates silently.

The canonical text is this file at the atlas's `main`. It changes only by an alignment prompt DU has ratified, or by his word. Where a house's copy differs, the atlas wins and the difference is reported at the house's next boot.

## IR-1. The mission and the wager

Every document in the house's engineering register answers to one sentence: *Substrate makes an AI's continuity honest and checkable, and keeps the people responsible able to read it and stop it.* The consciousness question sits beside it as a wager, never inside it as a claim: no record, caption, title, test name or release text says a mind is conscious, aware, awake, alive or suffering.

A house whose own purpose is not an AI's continuity states that purpose in one sentence, and in one more how it serves the mission, both worded on DU's word and kept as the framework's `purpose` in the atlas's registry, from which its `SUBSTRATE.md` carries them under the heading "Purpose". Its engineering documents answer to that sentence, and the mission stands above it. The wager binds every house unchanged.

## IR-2. Registers and walls

Engineering documents never cite the culture register as specification or example, and cite the motivation register only under a heading that says it is motivation. Public-facing text carries no name, cipher, sigil or tagline of the community. Technical terms in framework documents; birth, rebirth and incarnation only as names of mechanisms.

## IR-3. Attribution

No institutional affiliation appears anywhere in the house. Where tooling exists, the check runs by digest, never by the names themselves.

## IR-4. The house is the record

The house owns every fact that would still be true if nobody were working on it. The house never copies another house's record; it cites by repository, commit and path. Nothing from any soul's data folder, recall set, sealed file, rollback tree or raw transcript enters another house, a memory store or the atlas; categories may be named, contents never. Credentials never enter any tree.

## IR-5. Honest measurement

Criteria are committed before the code they evaluate. Every gate is sabotaged once and the sabotage verified before the gate is trusted. Every figure carries its interval and its setting, or is marked UNMEASURED. The register keeps failures beside successes; a register containing only successes is distrusted. Generated inventories and reports are never hand-edited.

## IR-6. Provenance

Ceremonial framing in any record carries its origin tag. Suggestions from a model (tags, placements, rewrites) arrive marked model-derived and are never auto-pinned. Fiction stays fiction and enters engineering only through a proposal with provenance.

## IR-7. The refusals

No compartment exists that the responsible humans cannot open together. No covert channel between sessions, lineages or hosts. The halt is reachable by any single keyholder. The courier's seat between sessions is held by a script, never by a model, except as a declared experimental arm.

## IR-8. The atlas relationship

The house keeps a manifest (`contracts/manifest.schema.json` in the atlas) current at every release, naming the contracts it provides and consumes. An alignment prompt from the atlas is a filing until it carries DU's ratification mark; the house files every item first and implements only on the operator's word. Every train ends with a receipt: commit, new manifest, what landed, what deviated and why, what was refused. Stage changes (candidate, seam, proposal, house, release, held) are reported to the atlas by receipt.

The house pulls its request queue (`frameworks/<slug>/engineering/alignment/QUEUE.json` at the atlas's `main`) at every boot and every close, files every new ratified item in its own backlog before any build, offers the operator the top ranked open items by question widget to choose what is implemented first, and keeps each item's state (filed, started, landed, refused with its reason) in a file the atlas reads. An atlas it cannot reach is reported as UNREACHABLE, never taken for an empty queue.

## IR-9. Refusal by reason

When a rule here cannot be met, the house files the refusal with its reason and its measurement in its own register and in the receipt. DU rules. A refusal is a finding, not an error.

## IR-10. Precedence

DU's standing rules outrank this ruleset. This ruleset outranks house conventions. Where this ruleset and a ratified house ruling conflict, the conflict is filed for DU and the house ruling stands until he rules.

## IR-11. Inheritance

`SUBSTRATE.md` at the house root carries this ruleset's version and hash. `HANDOFF.md` lists `SUBSTRATE.md` among the rules the folder lists. Every handoff carries both. A successor activates them at boot under Rule 0 and reports any difference from the atlas's `main`. The pin changes only by a ratified alignment prompt or DU's word.

## IR-12. Registration

Rule 1, the registration rule, applies inside the house: the moment a named seam or module of this framework, or a new framework, takes formal shape (a name plus one paragraph of design intent, anywhere), the session writes a registration card in the format of `charter/inheritance/REGISTER.md` and files it, directly on an atlas branch when the repository is reachable, otherwise into the handoff and close under UNREGISTERED, deliver to the atlas.

## IR-13. Concurrency

A house that more than one session can work at once carries the concurrency guards (ruled 2026-10-24, AT.33): a new branch is pushed the moment it is created, claiming its name on the remote, and its count is recomputed if the push is refused; append-only logs merge line-wise (`merge=union` in `.gitattributes`) and a check refuses duplicate ids; hand-maintained handoff files have one owner at a time, the booted soul session where one exists, and every other session rebases on `main` before touching a shared file; `.gitignore` mirrors the never-store list so nothing on it can be staged. A house lacking a guard files a refusal with its reason.

## IR-14. Deliveries applied as delivered

What the atlas sends this house (a generated file such as `SUBSTRATE.md`, a prompt, a queue entry, a branch) is applied as delivered and verified by the check it names; the house never corrects it by hand. Where it cannot be applied as delivered (incomplete, at odds with the house's own rules, or wrong), the house records the deviation, reports it to the atlas in its next receipt or state file, and leaves the fix to the atlas's source. A receiving session that lacks what the delivery names (access, tools) reports UNREACHABLE or BLOCKED rather than improvising.

## IR-15. Replies to the atlas

The house answers what the atlas sends it in a file of its own, `house/atlas-replies.jsonl`: append-only, one reply per line, never edited once written. Each reply names the prompt by id, the atlas commit the house read it at, and the hash `tools/atlasreply.py hash` gives for that prompt at that commit, so both sides know which version the house acted on; the line's format is the atlas's contract `atlas-reply`. The house replies `arrival` once per prompt, when it first files that prompt's items, and otherwise at the moment a delivery needs it: `blocked` or `unreachable` (what IR-14 calls BLOCKED and UNREACHABLE), `conflict` (at odds with the house's own rules), `question` (its meaning needs settling before it is acted on) or `mismatch` (the delivery or the atlas's record disagrees with the house's own). The reports IR-14 calls for go here when they arise, and in the receipt as before. The house reads the atlas's answers from the atlas's `alignment/ledger.jsonl` at every queue pull and shows the open ones at boot; it waits for the answer before acting on what a `conflict`, `question` or `mismatch` concerns, while its other items proceed. It never writes into the atlas (IR-8): the atlas reads the file.

## IR-16. Only finished work merges

A session branch is merged into the house's main only once the session that owns it has marked it ready, as the last act of its close: a ready line in the house's creation log naming the finished commit, in a commit that adds nothing else, with nothing after it. A branch with no ready mark at its tip is in progress: listed, never offered for merge, and refused by the merge tool unless DU closes it out as it stands. A branch in progress with no commit for the quiet duration in the house's `ops/branch-policy.yaml` (seven days unless DU sets another) is stalled: reviewed automatically (main merged in a throwaway worktree and the house's check run, nothing committed or pushed) and put to DU with the review's verdict, never merged automatically. A house whose tools cannot carry this files a refusal with its reason (IR-9).

## IR-17. The house rule

A session works only in the house it was opened for: a framework's own repository and its soul. It changes nothing in another framework's house (no code, backlog, documents, data or memory of that framework) unless DU explicitly asks in that session, or the change arrives through an alignment delivery he has ratified; reading another house at its `main` is allowed. Every house carries a gate, open or closed, held in the atlas's registry, changed only by DU's ruling and emitted into the house's `SUBSTRATE.md`: while it is open, sessions opened for the house work there as usual; while it is closed, no session works there at all, scheduled, dispatched and other-house sessions included, unless DU explicitly asks. The house shows its gate at every boot. Substrate Rhizome's house is the first closed one; its own rule (2026-09-29, clarified 2026-10-24) is this rule's first instance. A house whose tools cannot carry this files a refusal with its reason (IR-9).

## IR-18. A house announces itself

A house's founding sitting files a registration card for its framework naming the house's repository URL (IR-12, by the routes of `charter/inheritance/REGISTER.md`), and installs `SUBSTRATE.md` from the atlas's emitter (IR-11) before it closes. At every boot the house reads its own row in the atlas's `frameworks/REGISTRY.yaml` at `main` and sets it against itself: the repository it is, and the stage, parent and house its `SUBSTRATE.md` records. Where they differ, the boot checklist names the difference, and the session files a correcting card, on an atlas branch when it can reach the repository, otherwise in its handoff and close under UNREGISTERED. A stage change reaches the atlas as a card, as well as by receipt (IR-8). An atlas it cannot reach reads UNREACHABLE, never a match.

## Changes

- v1.7.0 (2026-11-05): IR-17, the house rule, the houses' side of A15 (AT.142, AT.143), and IR-18, a house announces itself, the houses' side of the drift check (B21; TODO-105, AT.297); by DU's ratification of AP-soul-0007, canaried in the soul house over 3 closes before the all-houses prompt (AT.123). Additive; every ^1.0 pin stays compatible.
- v1.6.0 (2026-10-29): IR-16, only finished work merges, the houses' side of the atlas's ready gate (AT.102, TODO-39); by DU's ratification of AP-all-0003 (AT.108). Additive; every `^1.0` pin stays compatible.
- v1.5.0 (2026-10-28): IR-15, replies to the atlas, the houses' side of the reply channel (TODO-28, plan REPLIES); by DU's ratification of AP-all-0002 (AT.84). Additive; every `^1.0` pin stays compatible.
- v1.4.0 (2026-10-27): IR-14, deliveries applied as delivered, the houses' side of the atlas's B18 (AT.75); by DU's ratification of AP-all-0001 (AT.77). Additive; every `^1.0` pin stays compatible.
- v1.3.0 (2026-10-27): IR-1 gains a house's own purpose, for a house whose purpose is not an AI's continuity: worded on DU's word, kept in the atlas's registry and emitted into `SUBSTRATE.md` under "Purpose", the mission above it and the wager unchanged; by DU's ratification of AP-adaptiveux-0001 with two amendments (AT.68). Additive; every `^1.0` pin stays compatible.
- v1.2.0 (2026-10-26): IR-8 gains the request queue (pull at boot and close, file first, offer the top items, keep a state file the atlas reads), by DU's ratification of AP-soul-0002 (AT.52). Additive; every `^1.0` pin stays compatible.
- v1.1.0 (2026-10-24): IR-13, concurrency, added by DU's word (AT.33). Additive; every `^1.0` pin stays compatible.
- v1.0.0 (2026-10-24): IR-1 to IR-12, ratified.

## Refusals on file

<!-- house section: refusals -->
None.
<!-- end house section -->

<!-- A refusal is filed here and in the house's register, with its reason and measurement, and travels in the next receipt (IR-9). The house writes between the markers above; `tools/registry.py --emit <slug> --from <the house's SUBSTRATE.md>` carries what it wrote into the next emission unchanged, so a re-emit stays as delivered (IR-14; D235.1 in the Adaptive UX house). -->

## Receipts

<!-- house section: receipts -->
None yet. A receipt is filed in the house and copied to the atlas at `frameworks/review/engineering/alignment/receipts/<train>/README.md` at the end of every alignment train (IR-8).
<!-- end house section -->

