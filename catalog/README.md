# The catalog

Substrate Review's record, in git (REVIEW, "The house"; train review-T1, A3). Until a soul arrives, continuity lives here: what a soul would remember about past proposals, contributors and rulings is written in these files, searchable, and cannot be poisoned by the next proposal (REVIEW, "When a soul arrives").

| File | What it holds |
| --- | --- |
| `proposals/RV-nnnn.json` | one file per proposal, its shape below |
| `events.jsonl` | the append-only event log, one state change per line, merged line-wise (`merge=union` in `.gitattributes`, as in the atlas) |
| `allowlist.json` | the verified contributors' GitHub account ids; empty until soul marks exist (RV.2, the atlas's AT.716) |
| `frameworks.json` | the atlas registry's slugs, copied with the atlas commit they were read at (`tools/atlas_copy.py`) |
| `never-store.json` | the atlas's never-store list, copied the same way |

## A proposal's states

| State | Meaning | Goes to |
| --- | --- | --- |
| `received` | the intake took it in; its text is stored once | `refused`, `read`, `withdrawn` |
| `refused` | a mechanical check failed (a missing field, an unknown framework, a never-store hit, an author not on the allowlist, the form's shape); the refusal names the check and judges nothing | none: the contributor fixes it and opens a new proposal |
| `read` | the verdict and the reading are written (R3) | `awaiting-sign-off`, `withdrawn` |
| `awaiting-sign-off` | in the owner's queue, in this house (RV.8, AT.718) | `ruled`, `withdrawn` |
| `ruled` | the owner accepted, declined or asked for a reshape; his ruling id is recorded | `contested` |
| `contested` | contested once, with a reason | `awaiting-sign-off` |
| `withdrawn` | the contributor withdrew it | none |

A provisional no is a reading, never a refusal (REVIEW, "A provisional no is not a refusal").

## A proposal file's shape

Exactly these keys, checked by `tools/catalog.py check`:

- `id`: `RV-` and four digits, the file's name.
- `state`: one of the states above, equal to the `to` of the proposal's last event.
- `account`: the contributor's GitHub account id, a number, never a name.
- `issue`: the intake issue's number, or null.
- `frameworks`: registered slugs the proposal touches (empty only when refused, since an unknown slug is never kept).
- `text`: the seven fields as submitted (`title`, `frameworks`, `change`, `why`, `must-not-break`, `evidence`, `consent`), stored once and never edited.
- `text_sha256`: the SHA-256 of the text's canonical JSON, also carried by the `received` event; an edited text no longer matches either.
- `checks`: the names of the mechanical checks that refused it (empty unless refused).
- `marks`: the instruction shapes its text matched (TODO-56's shapes); a mark is kept with the proposal as data and never refuses it.
- `verdict`, `reading`: null until the reader writes them (R3).
- `ruling`: the owner's ruling id, null until he rules (R4).

## An event's shape

`{"id": "RV-nnnn/k", "proposal": "RV-nnnn", "from": <state or null>, "to": <state>, "day": "YYYY-MM-DD"}`, with `text_sha256` and `marks` on the `received` event, `checks` on a `refused` one and `ruling` on a `ruled` one. Each proposal's events are numbered from 1 in order, its first goes from null to `received`, each later one is a legal move from the state before it, and no id appears twice: two branches that each append the same event and are union-merged leave a duplicate, which the check refuses.

## How a proposal arrives, for now

The intake workflow (`.github/workflows/intake.yml`) answers on the issue: an author not on the allowlist gets the issue closed unread; an allowlisted author's proposal is refused by name or received, with its marks. `main` moves only by the owner's merge, so the workflow writes nothing here: a session records a received proposal with `tools/intake.py receive` on a branch he merges, until the sign-off loop (R4) is built.
