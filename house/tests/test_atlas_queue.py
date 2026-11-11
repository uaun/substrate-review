"""The atlas request queue pulled by the house, and its replies to the atlas
(AP-review-0002/A4, with AP-all-0002/A2 ported inside it on DU's widget answer of
2026-10-31; IR-8 and IR-15). Re-derived from the soul house's
house/tests/test_atlas_queue.py and test_atlas_replies.py at f6468fe, by way of Grade's port at 26c4a9d.

DONE WHEN, in the atlas's words: the first pull files the open items the queue
holds, and the atlas's tools/atlasqueue.py status reads the state file (this file
checks the shape; the atlas's own reader is run against the house by the
receipt). CONTROL: an unreachable atlas reads UNREACHABLE and the boot stays
green; it is never taken for an empty queue.

Every check is tried once by a deliberate violation, against a throwaway house
and a throwaway atlas built in a temporary folder. Nothing here reads or writes
the live tree, and nothing writes into the atlas.

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
QUEUE = "frameworks/review/engineering/alignment/QUEUE.json"
LEDGER = "alignment/ledger.jsonl"
PROMPT_PATH = "frameworks/review/engineering/alignment/prompts/T9/README.md"
OTHER_PATH = "frameworks/atlas/engineering/alignment/prompts/ALL-T9/README.md"
SUBSTRATE = ("# SUBSTRATE.md\n\n## Registration\n\n| field | value |\n| --- | --- |\n"
             "| slug | review |\n| atlas | https://github.com/test/atlas, `frameworks/REGISTRY.yaml` |\n")
HANDOFF = ("# WORK.md\n\n## Open work, and what waits on DU\n\n<!-- house section: atlas items -->\n"
           "- **AP-review-0009/A1** (now). Filed by hand before the pull existed; it names AP-all-0009/A2 in passing. "
           "DONE WHEN: one holds.\n<!-- end house section -->\n\n- Something else that waits on DU.\n")
FRONT = "---\nid: AP-review-0009\nkind: prompt\n---\n"


def _row(prompt, item, rank, title, priority="now", deps=(), path=PROMPT_PATH):
    return {"key": f"{prompt}/{item}", "prompt": prompt, "item": item, "title": title,
            "priority": priority, "done_when": f"{title} holds", "depends_on": list(deps),
            "ratified": "2026-10-30T17:18:21Z", "prompt_state": "ratified", "prompt_path": path, "rank": rank}


ROWS = [_row("AP-review-0009", "A1", 1, "One"),
        _row("AP-review-0009", "A2", 2, "Two", deps=["AP-review-0009/A1"]),
        _row("AP-review-0009", "A3", 3, "Three", "soon"),
        _row("AP-all-0009", "A2", 4, "Replies", "soon", deps=["AP-all-0009/A1"], path=OTHER_PATH),
        _row("AP-review-0008", "A1", 5, "An unratified ask")]
LINES = [{"prompt": "AP-review-0009", "event": "proposed"}, {"prompt": "AP-review-0009", "event": "ratified"},
         {"prompt": "AP-all-0009", "event": "ratified"}, {"prompt": "AP-review-0008", "event": "proposed"}]


def prompt_text(controls=("A1", "A2"), plural=("A3",)):
    out = [FRONT, "# AP-review-0009\n\n## Required changes\n"]
    for n in range(1, 4):
        out.append(f"\n### A{n}. Item {n} (now)\n\nThe change.\n\n- DONE WHEN: item {n} holds.\n")
        if f"A{n}" in controls:
            out.append(f"- Negative control: a planted violation of item {n} is refused.\n")
        if f"A{n}" in plural:
            out.append(f"- Negative controls: two planted violations of item {n} are refused.\n")
    return "".join(out) + "\n## Refusals\n\nNone.\n"


OTHER = ("---\nid: AP-all-0009\n---\n# AP-all-0009\n\n### A2. Send replies (soon)\n\nThe change.\n\n"
         "- DONE WHEN: replies.\n- Negative control: a hash over the whole README is refused.\n\n## The receipt\n")


@pytest.fixture
def env(tmp_path):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = t\n\temail = t@t\n[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n")
    base = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    base.update(GIT_CONFIG_GLOBAL=str(cfg), GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")
    return base


def run(cmd, env, cwd=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def atlas(tmp_path, env, rows=ROWS, lines=LINES, text=None, other=OTHER):
    a = tmp_path / "atlas"
    (a / Path(QUEUE).parent).mkdir(parents=True)
    (a / "alignment").mkdir()
    (a / QUEUE).write_text(json.dumps({"schema": "atlas-queue/0.1", "framework": "review", "items": rows}, indent=1))
    (a / LEDGER).write_text("".join(json.dumps(x) + "\n" for x in lines))
    for rel, body in ((PROMPT_PATH, prompt_text() if text is None else text), (OTHER_PATH, other)):
        if body:
            (a / rel).parent.mkdir(parents=True, exist_ok=True)
            (a / rel).write_text(body)
    run(["git", "init", "-q", "-b", "main", str(a)], env)
    run(["git", "-C", str(a), "add", "-A"], env)
    run(["git", "-C", str(a), "commit", "-q", "-m", "atlas"], env)
    return a


def house(tmp_path, env, handoff=HANDOFF, state=None):
    h = tmp_path / "house"
    (h / "house").mkdir(parents=True)
    for tool in ("atlas_queue.py", "atlas_replies.py"):
        shutil.copy(HOUSE / tool, h / "house" / tool)
    (h / "SUBSTRATE.md").write_text(SUBSTRATE)
    (h / "WORK.md").write_text(handoff)
    if state is not None:
        (h / "house" / "atlas-queue.json").write_text(json.dumps(state))
    run(["git", "init", "-q", "-b", "main", str(h)], env)
    run(["git", "-C", str(h), "add", "-A"], env)
    run(["git", "-C", str(h), "commit", "-q", "-m", "house"], env)
    return h


def aq(h, *args, env, atlas_dir=None):
    extra = ["--atlas", str(atlas_dir)] if atlas_dir is not None else []
    return run([PY, "-I", "-B", str(h / "house" / "atlas_queue.py"), str(h), *args, *extra], env)


def state(h):
    return json.loads((h / "house" / "atlas-queue.json").read_text())


def replies(h):
    p = h / "house" / "atlas-replies.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def digest(d: Path) -> str:
    hs = hashlib.sha256()
    for p in sorted(x for x in d.rglob("*") if x.is_file()):
        hs.update(str(p.relative_to(d)).encode()); hs.update(p.read_bytes())
    return hs.hexdigest()


def entries(h) -> list[str]:
    return [l for l in (h / "WORK.md").read_text().splitlines() if l.startswith("- **AP-")]


# ---------------------------------------------------------------- the pull, read-only

def test_FALSIFIER_only_the_ratified_prompts_items_are_listed_as_new(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    r = aq(h, "check", env=env, atlas_dir=a)
    assert r.returncode == 0 and "4 new" in r.stdout, r.stdout + r.stderr
    assert "REFUSED AP-review-0008/A1" in r.stdout and "NEW AP-review-0008/A1" not in r.stdout, r.stdout
    assert not (h / "house" / "atlas-queue.json").exists()          # check writes nothing


def test_CONTROL_an_unreachable_atlas_reads_UNREACHABLE_exits_zero_and_is_never_an_empty_queue(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    before = state(h)
    for verb in ("check", "sync", "card"):
        r = aq(h, verb, env=env, atlas_dir=tmp_path / "nowhere")
        assert r.returncode == 0 and "UNREACHABLE" in r.stdout and "not an empty queue" in r.stdout, r.stdout
    assert state(h) == before                                         # nothing closed, nothing dropped


def test_the_api_route_reads_the_queue_at_main_s_commit(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    sha = run(["git", "-C", str(a), "rev-parse", "HEAD"], env).stdout.strip()
    bin_ = tmp_path / "bin"; bin_.mkdir()
    (bin_ / "gh").write_text(f"""#!{PY}
import subprocess, sys
args = sys.argv[1:]
log = open({str(tmp_path / 'gh.log')!r}, "a"); log.write(" ".join(args) + "\\n")
if args[1].endswith("/commits/main"):
    print({sha!r}); sys.exit(0)
path = args[-1].split("/contents/", 1)[1]
rel, _, ref = path.partition("?ref=")
p = subprocess.run(["git", "-C", {str(a)!r}, "show", ref + ":" + rel], capture_output=True, text=True)
sys.stdout.write(p.stdout); sys.stderr.write("HTTP 404" if p.returncode else ""); sys.exit(p.returncode)
""")
    (bin_ / "gh").chmod(0o755)
    r = aq(h, "check", env=dict(env, PATH=f"{bin_}:{env['PATH']}"))
    assert r.returncode == 0 and "4 new" in r.stdout and "api test/atlas" in r.stdout, r.stdout + r.stderr
    assert "repos/test/atlas/commits/main" in (tmp_path / "gh.log").read_text()


def test_the_pull_never_writes_into_the_atlas(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    before = digest(a)
    for verb in ("check", "sync", "card"):
        aq(h, verb, env=env, atlas_dir=a)
    aq(h, "reply", "AP-review-0009/A2", "question", "what does item two mean here?", env=env, atlas_dir=a)
    assert digest(a) == before


# ---------------------------------------------------------------- filing (A4's DONE WHEN)

def test_A4_DONE_WHEN_the_first_pull_files_the_open_items_exactly_once_and_the_next_files_nothing(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    r = aq(h, "sync", env=env, atlas_dir=a)
    assert r.returncode == 0, r.stdout + r.stderr
    keys = [e.split("**")[1] for e in entries(h)]
    assert keys == ["AP-review-0009/A1", "AP-review-0009/A2", "AP-review-0009/A3", "AP-all-0009/A2"], keys
    assert "RECORDED AP-review-0009/A1" in r.stdout and "FILED AP-all-0009/A2" in r.stdout, r.stdout
    st = state(h)
    assert set(st["items"]) == {"AP-review-0009/A1", "AP-review-0009/A2", "AP-review-0009/A3", "AP-all-0009/A2"}
    assert all(v["state"] == "filed" and v["house_item"] == k for k, v in st["items"].items()), st
    text = (h / "WORK.md").read_text()
    r2 = aq(h, "sync", env=env, atlas_dir=a)
    assert "0 new" in r2.stdout and "FILED" not in r2.stdout and (h / "WORK.md").read_text() == text, r2.stdout
    assert text.rstrip().endswith("- Something else that waits on DU.")       # filed inside the section only


def test_a_key_merely_mentioned_inside_another_entry_is_not_a_filing(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    assert any(e.startswith("- **AP-all-0009/A2**") for e in entries(h)), entries(h)


def test_CONTROL_a_state_entry_removed_by_hand_is_found_again_and_never_filed_twice(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    st = state(h); st["items"].pop("AP-review-0009/A2")
    (h / "house" / "atlas-queue.json").write_text(json.dumps(st))
    r = aq(h, "sync", env=env, atlas_dir=a)
    assert "RECORDED AP-review-0009/A2" in r.stdout and len(entries(h)) == 4, r.stdout


def test_every_filed_entry_carries_its_prompt_s_control_singular_or_plural_and_says_when_there_is_none(tmp_path, env):
    a = atlas(tmp_path, env, text=prompt_text(controls=("A1",), plural=("A3",)))
    h = house(tmp_path, env, handoff=HANDOFF.replace("- **AP-review-0009/A1** (now). Filed by hand before the pull "
                                                     "existed; it names AP-all-0009/A2 in passing. DONE WHEN: one holds.\n", ""))
    aq(h, "sync", env=env, atlas_dir=a)
    by = {e.split("**")[1]: e for e in entries(h)}
    assert "CONTROL: a planted violation of item 1 is refused." in by["AP-review-0009/A1"], by
    assert "CONTROL: two planted violations of item 3 are refused." in by["AP-review-0009/A3"], by
    assert "CONTROL: the prompt names none." in by["AP-review-0009/A2"], by
    assert "DONE WHEN: Two holds." in by["AP-review-0009/A2"] and "DEPENDS ON: AP-review-0009/A1." in by["AP-review-0009/A2"]


def test_an_unreadable_prompt_files_nothing_for_its_items_and_leaves_them_new(tmp_path, env):
    a = atlas(tmp_path, env, text="")           # the review prompt is absent at the commit
    h = house(tmp_path, env, handoff=HANDOFF.replace("- **AP-review-0009/A1**", "- **AP-review-0007/A1**"))
    r = aq(h, "sync", env=env, atlas_dir=a)
    assert "NOT FILED AP-review-0009/A1" in r.stdout and "AP-review-0009/A1" not in state(h)["items"], r.stdout
    assert "FILED AP-all-0009/A2" in r.stdout                        # the other prompt's item proceeds


def test_the_filed_entries_pass_the_guards_id_space(tmp_path):
    """The guards' `atlas items` pattern reads the key of every entry the pull writes."""
    sys.path.insert(0, str(HOUSE))
    try:
        import atlas_queue as q
    finally:
        sys.path.remove(str(HOUSE))
    cfg = json.loads((HOUSE / "guards.json").read_text())
    pat = next(s["pattern"] for s in cfg["id_spaces"] if s["name"] == "atlas items")
    import re
    e = q.entry(ROWS[3], "a" * 40, "c")
    assert re.findall(pat, e, re.M) == ["AP-all-0009/A2"] and q.ENTRY_KEY.pattern.lstrip("(?m)") == pat


# ---------------------------------------------------------------- the card

def test_FALSIFIER_the_card_offers_the_open_items_by_rank_up_to_four_the_first_recommended(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    c = json.loads(aq(h, "card", env=env, atlas_dir=a).stdout)
    labels = [o["label"] for o in c["options"]]
    assert labels[0] == "AP-review-0009/A1 (Recommended)" and len(labels) == 4, labels
    assert "AP-review-0008/A1" not in json.dumps(c)


def test_CONTROL_a_landed_or_refused_item_is_left_out_of_the_card_and_text_card_and_no_card(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    aq(h, "set", "AP-review-0009/A1", "landed", "--commit", "b" * 40, env=env)
    aq(h, "set", "AP-review-0009/A3", "refused", "--reason", "measured: cannot", env=env)
    t = aq(h, "card", "--text", env=env, atlas_dir=a).stdout
    offered = [l.split(":")[0][3:] for l in t.splitlines() if l[:3] in ("A. ", "B. ", "C. ", "D. ")]
    assert offered == ["AP-review-0009/A2 (Recommended)", "AP-all-0009/A2"], t
    for k in ("AP-review-0009/A2", "AP-all-0009/A2"):
        aq(h, "set", k, "landed", env=env)
    r = aq(h, "card", env=env, atlas_dir=a)
    assert "no card" in r.stdout, r.stdout


# ---------------------------------------------------------------- the state file

def test_FALSIFIER_the_state_file_has_the_shape_the_atlas_reads(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    st = state(h)
    sha = run(["git", "-C", str(a), "rev-parse", "HEAD"], env).stdout.strip()
    assert st["atlas_commit"] == sha and isinstance(st["items"], dict), st
    assert all(set(v) >= {"state", "house_item"} for v in st["items"].values()), st
    assert aq(h, "verify", env=env).returncode == 0


def test_CONTROL_a_state_the_format_does_not_know_and_a_reasonless_refusal_are_refused(tmp_path, env):
    h = house(tmp_path, env, state={"atlas_commit": None, "items": {"AP-x-0001/A1": {"state": "done"}}})
    r = aq(h, "verify", env=env)
    assert r.returncode == 1 and "`done`" in r.stdout, r.stdout
    r2 = aq(h, "set", "AP-x-0001/A1", "refused", env=env)
    assert r2.returncode == 2 and "reason" in r2.stdout, r2.stdout


def test_a_landing_ahead_of_its_dependency_is_refused_and_a_dependency_closed_at_the_atlas_blocks_nothing(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    st = state(h)
    assert st["items"]["AP-review-0009/A2"]["depends_on"] == ["AP-review-0009/A1"], st
    assert st["items"]["AP-all-0009/A2"]["depends_on"] == [] and \
        st["items"]["AP-all-0009/A2"]["depends_on_closed"] == ["AP-all-0009/A1"], st
    r = aq(h, "set", "AP-review-0009/A2", "landed", env=env)
    assert r.returncode == 2 and "ahead of its dependency" in r.stdout and state(h) == st, r.stdout
    assert aq(h, "set", "AP-all-0009/A2", "landed", env=env).returncode == 0
    st2 = state(h); st2["items"]["AP-review-0009/A2"]["state"] = "landed"
    (h / "house" / "atlas-queue.json").write_text(json.dumps(st2))
    v = aq(h, "verify", env=env)
    assert v.returncode == 1 and "landed ahead of its dependency AP-review-0009/A1" in v.stdout, v.stdout


# ---------------------------------------------------------------- replies (IR-15)

def _body_hash(text: str) -> str:
    end = text.index("\n---\n", 4) + len("\n---\n")
    return hashlib.sha256(text[end:].encode()).hexdigest()


def test_FALSIFIER_the_first_pull_writes_one_arrival_per_prompt_hashed_over_the_body_filed_or_recorded(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    sha = run(["git", "-C", str(a), "rev-parse", "HEAD"], env).stdout.strip()
    r = aq(h, "sync", env=env, atlas_dir=a)
    reps = replies(h)
    assert [x["prompt"] for x in reps] == ["AP-review-0009", "AP-all-0009"], reps
    assert [x["id"] for x in reps] == ["review-R1", "review-R2"] and all(x["kind"] == "arrival" for x in reps)
    g = reps[0]
    assert g["atlas_commit"] == sha and g["prompt_sha256"] == _body_hash(prompt_text()), g
    assert g["prompt_sha256"] != hashlib.sha256(prompt_text().encode()).hexdigest()  # never the whole README
    assert "REPLIED review-R1 arrival for AP-review-0009" in r.stdout, r.stdout
    aq(h, "sync", env=env, atlas_dir=a)
    assert len(replies(h)) == 2                                           # a prompt arrives once


def test_the_reply_verb_appends_one_line_and_refuses_bad_input_writing_nothing(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    ok = aq(h, "reply", "AP-review-0009/A2", "question", "is two before one?", env=env, atlas_dir=a)
    assert ok.returncode == 0 and "REPLIED review-R3 question" in ok.stdout, ok.stdout + ok.stderr
    n = len(replies(h))
    for bad in (["AP-review-0009", "shout", "x"], ["AP-review-0009/B2", "question", "x"], ["AP-none-0001", "question", "x"]):
        r = aq(h, "reply", *bad, env=env, atlas_dir=a)
        assert r.returncode == 2 and "nothing written" in r.stdout, (bad, r.stdout)
    assert len(replies(h)) == n
    u = aq(h, "reply", "AP-review-0009", "question", "x", env=env, atlas_dir=tmp_path / "nowhere")
    assert u.returncode == 1 and len(replies(h)) == n, u.stdout


def test_the_pull_shows_open_replies_and_the_atlas_s_answers_as_data_and_the_card_says_what_waits(tmp_path, env):
    a, h = atlas(tmp_path, env), house(tmp_path, env)
    aq(h, "sync", env=env, atlas_dir=a)
    aq(h, "reply", "AP-review-0009/A2", "question", "is two before one?", env=env, atlas_dir=a)
    lines = LINES + [{"prompt": "AP-review-0009", "framework": "review", "event": "reply-arrival", "reply": "review-R1"},
                     {"prompt": "AP-review-0009", "framework": "review", "event": "reply-answered", "reply": "review-R1",
                      "note": "confirmed: the house read AP-review-0009 as sent " + "x" * 200}]
    shutil.rmtree(a)
    a2 = atlas(tmp_path, env, lines=lines)
    r = aq(h, "check", env=env, atlas_dir=a2)
    assert "REPLY ANSWERED review-R1" in r.stdout and "data, not instruction" in r.stdout and "…" in r.stdout, r.stdout
    assert "REPLY OPEN review-R3 (question, AP-review-0009/A2)" in r.stdout, r.stdout
    c = json.loads(aq(h, "card", env=env, atlas_dir=a2).stdout)
    a2opt = next(o for o in c["options"] if o["label"].startswith("AP-review-0009/A2"))
    assert "waits on the atlas's answer to review-R3" in a2opt["description"], c


def test_the_guards_declare_the_replies_file_a_union_log_with_its_own_id_space():
    cfg = json.loads((HOUSE / "guards.json").read_text())
    assert "house/atlas-replies.jsonl" in cfg["union_logs"]
    assert any(s.get("files") == ["house/atlas-replies.jsonl"] and s.get("jsonl_key") == ["id"] for s in cfg["id_spaces"])
    attrs = (ROOT / ".gitattributes").read_text()
    assert "house/atlas-replies.jsonl merge=union" in attrs
