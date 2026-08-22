# Phase 4 — designPH 3.0 Compatibility (S4)

> ⏸ **TABLED (Ed, 2026-08-19), and ⛔ blocked on procurement**: the designPH 3.0 licence cannot be bought yet (Ed, 2026-08-21) — no agent work unblocks this phase, do not propose starting it. The POC completed on the recorded working assumption that a 2.x reader translates to 3.0 later; the unwind check (`POC/RESULTS/POC-5_results.md` §6) confirms the collector is still the blast radius.

**Box:** 1 day of work — **plus 1–3 weeks of procurement latency, now inside this phase**
**Gate:** can v1 serve the market it is aimed at?
**Prerequisite:** Phase 1 findings recorded

---

## 4.0 — Order the designPH 3.0 licence **[Ed]** — do this the day Phase 4 opens

Originally a Phase 0 background item; **deferred here by Ed on 2026-08-19.** The consequence is that
its 1–3 week latency now sits on this phase's critical path rather than running in the background,
so ordering is the *first* action of Phase 4, not a prerequisite met beforehand.

Nothing needs drafting — the purchase checklist is already written:
[`RESULTS/PHASE-0_long-lead-staging.md`](RESULTS/PHASE-0_long-lead-staging.md) §A. It covers keeping
2.2.29 and the 2.4.0 BETA installed (version spread is the asset here), the SketchUp-version
compatibility check, and the first baseline diff to run on arrival.

**While waiting**, §4.1's diff harness can be written and dry-run against the existing Phase 0
baselines — that work does not need 3.0 in hand.

## Objective

Everything known about designPH's data model comes from versions **2.1.10 – 2.4.0 BETA**. Upstream is
**3.0** (released 2026-07-28), and that is what the target market will increasingly be running. Its
attribute schema has never been seen.

This phase answers: does the Phase 1 read layer work against 3.0, or does 3.0 move the goalposts?

## Why this is a real risk

designPH already renamed its face keys once between 2.1 and 2.2 (`00_Context/DESIGNPH_DATA_MODEL.md`
§6), without migration and without purging the old spellings. `DesignPH_dict` is not a published
interface and carries no compatibility guarantee. A second rename at a major version boundary is
entirely plausible.

## Method

**4.1 — Re-run the key inventory.** Open the corpus models in 3.0, save copies, and diff against the
Phase 0 baselines:

```bash
cd /Users/em/Desktop/dph_plus_testing/00_Context
uv run tools/skp_attr_dump.py "<model saved from 3.0>.skp" -d DesignPH_dict \
  > ../planning/RESULTS/dph3_<model>.txt
diff ../planning/RESULTS/baseline_<model>.txt ../planning/RESULTS/dph3_<model>.txt
```

Record: new keys, removed keys, renamed keys, changed value types, changed enum values.

**4.2 — Re-run the Phase 1 §1.1 experiment against 3.0.** Change one face's area group in the 3.0 UI
and observe which key updates. This extends the version rule to a third generation, or confirms 3.0
kept 2.2's spellings.

**4.3 — Round-trip an old model.** Open `adelphi-designph.skp` (2.1.15) in 3.0, save, re-inventory.
Does 3.0 migrate old keys, add new ones alongside, or ignore them? This is exactly the situation a
real user will be in, and it determines whether our reader must handle three generations at once.

**4.4 — Check the `.ppp` header.** Read (by eye — no parser) the version banner of a 3.0 export.
Relevant to the Phase 5 conversation about whether a documented format is even stable enough to ask
for.

**4.5 — Re-check windows.** Repeat Phase 1 §1.2 against a 3.0 model. Did window components change —
different definition names, different glue or opening behaviour?

## Gate

**PASS — 3.0 uses the 2.2 key generation unchanged.** Raise the version gate ceiling to include 3.0
and proceed. Best case.

**PASS WITH CHANGES — 3.0 introduces a third generation.** Extend the version rule to three branches,
update `00_Context/` §6, widen the test matrix. Costly but tractable; it is the same shape of problem
already solved once.

**FAIL — 3.0 fundamentally changes storage** (moves off `DesignPH_dict`, encrypts values, drops
attributes in favour of an internal store). The read-side thesis is broken for the market's current
version. Stop v1. This escalates directly into Phase 5: the only remaining route is a supported
interface agreed with PHI, which changes the project from "sidecar" to "partnership."

## Deliverables

- `planning/RESULTS/PHASE-4_results.md` with the baseline diffs
- `00_Context/DESIGNPH_DATA_MODEL.md` scope line and §6 updated to cover 3.0
- PRD §7.4 version support matrix updated
- A recommendation on the 2.1 floor question raised in Phase 0 notes — whether v1 supports 2.1
  (which the primary corpus model needs) or holds the line at 2.2+

## Note — the escape hatch, now more load-bearing than before

If the licence has not arrived, **do not block on this phase.** Phases 1–3 gate v1's architecture;
Phase 4 gates its *market coverage*. Build against 2.2+ and treat 3.0 support as a fast-follow, with
the version gate refusing 3.0 politely in the interim rather than guessing (PRD §7.4).

This mattered less when the licence was ordered back in Phase 0 and would plausibly have arrived by
now. With §4.0 deferred to this phase's first day, a wait here is the *expected* case rather than the
unlucky one — so plan on shipping v1 against 2.2+ and folding 3.0 in when the licence lands.
