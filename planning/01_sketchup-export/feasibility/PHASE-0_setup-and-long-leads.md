# Phase 0 — Setup and Long-Lead Starts

> ✅ **CLOSED 2026-08-19.** [`RESULTS/PHASE-0_results.md`](RESULTS/PHASE-0_results.md). This file is the plan as written; open-looking items in it were settled there or in later phases.

**Box:** ~2 h of work, plus two items that then run in the background for weeks
**Gate:** none — this phase enables the others
**Prerequisite:** none

> ✅ **Complete 2026-08-19** — [`RESULTS/PHASE-0_results.md`](RESULTS/PHASE-0_results.md).
> §0.2–§0.5 done. §0.1's two **[Ed]** long leads are **deferred to Phases 4 and 5** by Ed's
> decision — staged and ready in
> [`RESULTS/PHASE-0_long-lead-staging.md`](RESULTS/PHASE-0_long-lead-staging.md).
>
> ⚠ Phase 0 did not come back empty. It **refuted the `*ID`/`*Auto` version rule** in
> `00_Context/DESIGNPH_DATA_MODEL.md` §6, which now blocks Phase 1 §1.1. Read the results file
> before starting Phase 1.

---

## Objective

Get a repeatable test harness in place, and **start the two things with multi-week latency** so they
are ready when Phases 4 and 5 need them.

## Tasks

### 0.1 — Start the long leads ⏸ **DEFERRED by Ed, 2026-08-19**

> **Ed's decision:** the designPH 3.0 purchase moves to the **start of Phase 4**, and the PHI
> conversation to the **start of Phase 5**. Neither is a Phase 0 action any more. Work continues up
> to those two boundaries.
>
> **Consequence, recorded so nobody rediscovers it as a surprise:** the 1–3 week procurement latency
> and the open-ended PHI reply latency were the whole reason these sat in Phase 0. Deferring them
> moves that wait out of the background and onto the critical path — Phase 4 cannot start work until
> the licence arrives, and Phase 5's gate cannot close until PHI replies. Budget for it at those
> phases rather than at Phase 0.
>
> Both remain **fully staged and ready to fire** —
> [`RESULTS/PHASE-0_long-lead-staging.md`](RESULTS/PHASE-0_long-lead-staging.md) holds the purchase
> checklist and the drafted opener. Phases 4 and 5 each open by executing their half of it.

Both items are Ed's to execute; the agent's job was to stage them (draft the PHI opener for Ed's
review, list what the licence purchase needs) and then get out of the way. That staging is done.

**A. Procure a designPH 3.0 licence.** Phase 4 cannot run without it, and 3.0 is what the market
actually runs. Purchasing plus install is realistically 1–3 weeks. Note the existing install here is
2.2.29 + a 2.4.0 BETA overlay; keep them, as version-spread is exactly what we need for testing.

**B. Open the PHI conversation.** Phase 5's gate. Frame per PRD §9: complementary, open-source, we do
not touch envelope→PHPP. Two asks: (1) is PHI comfortable with us reading `DesignPH_dict` through the
public SketchUp API; (2) would they consider authorising `.ppp` access in writing under §2.4(d), for
shading in v2. **Do not begin by asking for anything — begin by showing what it unlocks for designPH.**

### 0.2 — Set up the results folder  *(done — `RESULTS/` exists with `.gitkeep`)*

```
planning/01_sketchup-export/feasibility/RESULTS/          # phase results land here, one file per phase
```

Every phase writes `PHASE-N_results.md` here, negative results included.

### 0.3 — Baseline the corpus

Run the existing offline reader across every corpus model and commit the output as a baseline, so any
later change in our reading is visible as a diff:

```bash
cd /Users/em/Desktop/dph_plus_testing/00_Context
for f in ../corpus/adelphi/adelphi-designph.skp \
         ~/Dropbox/bldgtyp/*/08_DesignPH/*.skp ; do
  uv run tools/skp_attr_dump.py "$f" -d DesignPH_dict > "../planning/01_sketchup-export/feasibility/RESULTS/baseline_$(basename "$f" .skp).txt" 2>&1
done
```

The glob resolves to the five verified projects in `00_OVERVIEW.md` (Wellington, Linde, Bluff Reach,
MacDonough, Holmes — stamps 2.1.10 through 2.2.29) plus their `~.skp` backups. Include the backups —
a backup stamped differently from its main file is evidence, not noise. Also baseline the two
`corpus/synthetic/designph_test*.skp` models (2.4.0 BETA / 2.2.29), the only 2.4-generation samples
we have.

*(As run: 14 models. The glob yields **11** files, not 10 — the Linde folder holds a third, separate
model, `250703 - Linde Residence.skp` (2.2.29). Baselines landed in `RESULTS/baselines/` rather than
flat in `RESULTS/`, which by then held five other deliverables. The structured analysis —
per-model version, key generation, full value inventory, undocumented-key flags — is
`planning/spikes/phase0/corpus_baseline.py`, output `RESULTS/PHASE-0_corpus-baseline.md`.)*

Record for each model: designPH version, face count by `areaGroup`, distinct values of every
face-level key. Flag any key or value **not** already documented in
`00_Context/DESIGNPH_DATA_MODEL.md` §5.

### 0.4 — Characterise the reference HBJSON  *(source file now supplied — gap closed)*

`corpus/adelphi/adelphi-honeybee-json.hbjson` exists: honeybee schema **1.53.1**, Meters,
tol 0.001 — 6 rooms, 52 faces, 44 apertures, 38 `Space`s, 56 constructions, 66 materials,
**1287 orphaned shades**.

Tasks:

1. Validate it against `honeybee-schema` 1.53.1 and `honeybee-ph-schema`. If the *reference* does not
   validate, our acceptance criteria (PRD §11) need rethinking before anything else.
2. Dump its structure to `RESULTS/reference_hbjson_shape.md` — the exact key paths where PH data
   lives (`rooms[].properties.ph.spaces[]`, `properties.ph.bldg_segments`, `space.wufi_type`,
   `space.volumes`, `space.quantity`) — as the target shape for the translator.
3. **Investigate the 1287 orphaned shades.** The Adelphi designPH model has 1359 *untagged* faces
   (`areaGroupID='n'`). If these are the same context geometry, then untagged designPH faces have a
   natural home in HBJSON as orphaned shades — see PRD §7.2 note. Confirm or refute by comparing
   counts and a sample of coordinates.

**Do not expect equality with our output.** The reference has 6 solid rooms with solved adjacency;
v1 emits one non-solid room. It is a shape reference.

### 0.5 — Confirm the PHPP ground truth

Open `adelphi-phpp.xlsm` read-only (`openpyxl(data_only=True)`; it will not recalculate) and extract
the Areas and U-Values worksheets to CSV in `RESULTS/`. These become the numerical reference for
assembly translation later. Use the `phi-rules` skill for the cell map rather than exploring the
workbook by hand.

## Deliverables

- ✅ Baselines for all **14** corpus models — `RESULTS/baselines/` + `RESULTS/PHASE-0_corpus-baseline.md`
- ✅ Undocumented keys/values found and `00_Context/DESIGNPH_DATA_MODEL.md` updated
      (`descName`; groups 12–14 and 18; the `tempZone` decode; §6 marked contested)
- ✅ Reference HBJSON validated; shape dumped to `RESULTS/reference_hbjson_shape.md`; the
      shades-vs-untagged-faces question answered (half confirmed — see results §0.4)
- ✅ PHPP Areas + U-Values extracted to `RESULTS/phpp/` (4 CSVs)
- ⏸ designPH 3.0 ordered **[Ed]** — *deferred to Phase 4 start; staged in*
      `RESULTS/PHASE-0_long-lead-staging.md` §A
- ⏸ PHI conversation opened **[Ed]** — *deferred to Phase 5 start; staged in*
      `RESULTS/PHASE-0_long-lead-staging.md` §B

## Notes

- Do not modify any corpus file. Copy before experimenting.
- `adelphi-designph.skp` is designPH **2.1.15** — *below* the PRD's stated 2.2+ support floor. This is
  useful (it exercises the old key generation) but means the primary reference model would be
  **refused by v1's own version gate**. Worth raising with Ed: either the floor drops to 2.1, or the
  primary corpus model needs re-saving in a newer designPH.
  *(Phase 0 update: cheaper than it looked. If §6.3's revised reading holds per-face, the 2.1/2.2
  distinction largely stops mattering for reading and the floor can drop to 2.1 at no cost. Phase 1
  §1.1 decides.)*
