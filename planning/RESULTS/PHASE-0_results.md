# Phase 0 — Results

**Run:** 2026-08-19 · **Box:** ~2 h · **Gate:** none (enabling phase)
**Plan:** [`../PHASE-0_setup-and-long-leads.md`](../PHASE-0_setup-and-long-leads.md)

---

## Summary

All agent-runnable Phase 0 tasks are complete.

The two **[Ed]** long leads were staged and then **deferred out of Phase 0 by Ed (2026-08-19)**: the
designPH 3.0 purchase now fires at the start of Phase 4, the PHI opener at the start of Phase 5. Both
are drafted and ready in [`PHASE-0_long-lead-staging.md`](PHASE-0_long-lead-staging.md). The
tradeoff, recorded so it is not rediscovered later: their latency — 1–3 weeks for procurement,
open-ended for a PHI reply — is now on the critical path at those phases rather than running in the
background from here. Phases 1–3 are unaffected.

Phase 0 has no gate, but it did not come back empty. It produced **four findings that change the
record**, two of which change the plan:

| # | Finding | Effect |
|---|---|---|
| 1 | **`tempZoneID` is fully derivable from `areaGroupID`** — decoded and arithmetically verified across five models | Closes three open questions in the data-model record; gives the translator a free integrity check |
| 2 | **The `*ID` vs `*Auto` version rule (§6) is refuted by the wider corpus** | ⚠ **Blocks Phase 1's first task.** Following the documented rule would silently lose all envelope data on real 2.2 models |
| 3 | **PHPP area groups 14 and 18 identified** from PHI's own labels | Closes two `§5.3` "unknown" rows |
| 4 | **The orphaned-shades hypothesis is half right** — right destination, wrong source rule | PRD §7.2 promoted to v1 *with a filter*, which Phase 1 must define |
| 5 | **`descName`, an undocumented key** — the user's own surface names | v1 must prefer it over `descNameAuto` or lose them |

Plus three new enum values, a newly-flagged risk to assembly resolution, and a scoping correction to
the PRD §11 acceptance criteria.

## Deliverables

| Task | Deliverable | Status |
|---|---|---|
| 0.1 Long leads **[Ed]** | [`PHASE-0_long-lead-staging.md`](PHASE-0_long-lead-staging.md) — drafted PHI opener, licence checklist | staged; **deferred to Phases 4 and 5** |
| 0.2 Results folder | `planning/RESULTS/` | done (pre-existing) |
| 0.3 Corpus baseline | [`PHASE-0_corpus-baseline.md`](PHASE-0_corpus-baseline.md) · [`baselines/`](baselines/) (14 raw dumps + JSON) | done |
| 0.4 Reference HBJSON | [`reference_hbjson_shape.md`](reference_hbjson_shape.md) · [`validation/`](validation/) | done |
| 0.5 PHPP ground truth | [`phpp/`](phpp/) — 4 CSVs | done |

Spike code: [`../spikes/phase0/`](../spikes/phase0/) — four scripts, all PEP 723 + `uv run`.
No corpus file was modified. No SketchUp was involved.

---

## 0.3 — Corpus baseline

14 models baselined: the primary Adelphi model, the two `_misc_test_files` samples, and all 11
`.skp` files under `~/Dropbox/bldgtyp/*/08_DesignPH/` (five projects plus backups).

**Correction to `00_OVERVIEW.md`:** the glob resolves to **11 files across five projects**, not the
six implied. The Linde folder holds a *third* model, `250703 - Linde Residence.skp` (2.2.29) — a
different, later model from `250708.skp` (2.1.15), not a backup of it. It is the corpus's richest
model-level sample (25 `layer_table_*` keys, 47 distinct keys) and is now included.

Wellington's backup is on disk as `2523 Weiilington~.skp` — a typo in the filename, not a different
model.

### Finding 1 — `tempZoneID` decoded (and shown to be redundant)

`tempZoneID` is **not a designPH enum**. It is the PHPP `Areas`-worksheet *temperature zone*, and it
is assigned deterministically from the area group. The mapping comes straight from PHI's own summary
table in the Adelphi PHPP (`Areas!K8:N27`, extracted in [`phpp/phpp_areas_summary.csv`](phpp/phpp_areas_summary.csv)):

| `areaGroupID` | PHPP group | `tempZoneID` | Meaning |
|---|---|---|---|
| `1` | Treated floor area | `TFA` | floor-area marker |
| `2`–`6` | Windows N/E/S/W/Horiz | `A` | ambient |
| `7` | Exterior door | `A` | ambient |
| `8` | External wall — ambient | `A` | ambient |
| `9` | External wall — ground/basement | `B` | routes through `Ground` |
| `10` | Roof / ceiling — ambient | `A` | ambient |
| `11` | Floor slab / basement ceiling | `B` | routes through `Ground` |
| `12`–`14` | User-defined surfaces | `X` | observed for 14 |
| `15` | Thermal bridges — ambient | `A` | ambient |
| `16` | Perimeter thermal bridges | `P` | perimeter |
| `17` | Thermal bridges FS/BC | `B` | routes through `Ground` |
| `18` | Building element towards neighbour | `I` | neighbouring-building condition |
| `'n'` | *(untagged)* | `'i'` | designPH's own "not classified" marker |

**Evidence — the counts balance exactly in every model,** across 14 distinct group values:

| Model | Arithmetic |
|---|---|
| Adelphi | `n`:1359 = `i`:1359 · `1`:40 = `TFA`:40 · `8`+`10` = 19+3 = `A`:22 · `9`+`11` = 4+1 = `B`:5 · `18`:15 = `I`:15 |
| Bluff Reach | `1`:140 = `TFA`:140 · `8`+`10`+`15` = 31+8+55 = `A`:94 · `9`+`11`+`17` = 14+1+28 = `B`:43 · `16`:16 = `P`:16 |
| Holmes | `1`:26 = `TFA`:26 · `8`+`10`+`15` = 47+4+13 = `A`:64 · `9`+`11`+`17` = 26+2+13 = `B`:41 · `16`:16 = `P`:16 |
| Wellington | `1`:44 = `TFA`:44 · `8`+`10` = 29+15 = `A`:44 · `9`+`11` = 14+1 = `B`:15 |
| Linde 250703 | `n`:1708 = `i`:1708 · `8`+`10` = 41+13 = `A`:54 · `9`:7 = `B`:7 · `14`:5 = `X`:5 |

Cross-checked against the `phi-rules` PHPP 10 `Areas` teardown, which states independently that
*"`A` rows default to ambient, `B`/`P` rows route through `Ground`, `I` is the neighbouring-building
condition"*.

**Caveat — this is a count-level match, not a per-face match.** The offline reader extracts
attribute records without associating them to entities, so the pairing is inferred from exact
population arithmetic rather than observed face by face. Five independent models balancing to the
unit across 14 group values is strong, but **Phase 1 should confirm it per-face** with the BT
Attribute Inspector. It is cheap to check and the consequence of being wrong is a wrong temperature
zone on every surface.

**Consequences:**

- The translator needs **only** `areaGroupID`. `tempZoneID` carries no independent information.
- Reading both gives a **free integrity check**: a pair that disagrees with the table above means the
  model is inconsistent, and should be *reported* (hard rule 4), not silently resolved.
- Resolves `§6`'s "`'i'` and `'I'` are distinct values, meaning distinct things" — `'I'` is the
  neighbour condition (group 18); `'i'` is designPH's untagged marker (group `'n'`). Case matters,
  and a case-insensitive read would conflate a real envelope surface with unclassified clutter.

### Finding 2 — the `*ID` / `*Auto` version rule does not survive the wider corpus ⚠

`00_Context/DESIGNPH_DATA_MODEL.md` §6 concludes hypothesis (a), a **version rename** at designPH
2.2, and states the rule:

```
if designPH_version >= 2.2:  read areaGroupAuto, tempZoneAuto, assemblyIDAuto
else:                        read areaGroupID,   tempZoneID,   assemblyID
```

The full corpus refutes it. Non-nil record counts:

| Model | Stamp | `areaGroupID` | `areaGroupAuto` | `tempZoneID` | `tempZoneAuto` | `assemblyID` | `assemblyIDAuto` |
|---|---|---:|---:|---:|---:|---:|---:|
| Adelphi | 2.1.15 | **1441** | — | **1441** | — | **42** | 0 / 1007 |
| Linde 250708 | 2.1.15 | **1781** | — | **1781** | 0 / 1350 | — | 92 / 431 |
| Bluff Reach | **2.2.24** | **293** | — | **293** | 7 / 382 | **153** | 0 / 70 |
| Holmes | **2.2.29** | **147** | — | **147** | 1 / 37 | **98** | 0 / 27 |
| MacDonough | **2.2.29** | **34** | — | **34** | 13 / 170 | **13** | 0 / 22 |
| Linde 250703 | **2.2.29** | **1774** | 8 / 8 | **1774** | 9 / 1367 | **73** | 2 / 368 |
| Wellington | 2.1.10 + 2.2.29 | **103** | — | **103** | 169 / 343 | **59** | 0 / 44 |
| `designph_test~` | 2.2.29 | — | **6** | — | **6** | — | **6** |

**Every real project model stores its real data in the `*ID` generation, whatever the version
stamp.** `areaGroupAuto` is *entirely absent* from four of the five 2.2-stamped project models.
Applying the documented rule to `2414 Bluff Reach.skp` — a clean 2.2.24 model — would read **0 area
groups, 0 assemblies, and 7 of 293 temperature zones.** That is total, silent loss of the envelope
on a real project, and the exact failure mode hard rule 4 exists to prevent.

The one model matching §6's description is `designph_test~.skp`: six faces, auto-classified, never
hand-assigned. §6 generalised from it.

**Revised reading — the superseded hypothesis is reinstated.** `*ID` is the **authoritative
assignment** (what designPH writes when a face is actually classified); `*Auto` is the
**auto-classification cache**, sparse and mostly nil. §6 had proposed exactly this "derived vs
user-override" pairing and then discarded it on the strength of Adelphi. Adelphi ruled out the
*version-rename* reading only for models it could see; the wider corpus rules out the rename itself.

The same pattern now has a third instance: `descNameAuto` (generated) / `descName` (user override) /
`descNameFreeze` (lock) — see Finding 5.

⚠ **This blocks Phase 1's first task.** Do not implement §6's rule. `00_Context/DESIGNPH_DATA_MODEL.md`
§6 has been updated to mark the conclusion contested and record this evidence. Phase 1 must settle
the correct precedence per-face, live, before any read-layer work.

**What is *not* yet answered:** whether `*Auto` may ever hold a value `*ID` does not, on the same
face. The offline reader cannot tell — it reads records, not entities, and `model.dat` retains
historical state. If that case exists, a naive "prefer `*ID`" rule loses data too. Phase 1, with the
Inspector, is the place to decide.

### Finding 3 — PHPP area groups 14 and 18 identified

Both were "unknown" in `§5.3`. The Adelphi PHPP names them in PHI's own labels:

- **Group 18 = "Building element towards neighbour."** Adelphi carries 446.5 m² of it (`Areas!L27`),
  consistent with an urban townhouse with party walls, and exactly 15 faces carry `areaGroupID=18`.
  Its temperature zone is `I`.
- **Groups 12–14 = user-defined surface slots**, not fixed PHI categories (`Areas` summary rows
  19–21). This explains why `designPH_reverse_material_14.skm` ships with no data ever observed
  against it: designPH ships a display colour for the user-defined slots. Linde 250703 uses group 14
  on 5 faces.

### Finding 5 — `descName`, an undocumented key

Present on 6 of 14 models (Bluff Reach, Holmes, MacDonough and their backups) and absent from `§5`.

```
Bluff Reach (n=70):   '104C HALL'  '104A BAR'  '100 FOYER'  '109 PANTRY'  '113 BATHROOM'
MacDonough  (n=34):   'S_00'  'N_EXT'  'N_00'  'W_EXT'  'W_01'  'E_01'
```

These are **user-typed** surface and room names — the override that `descNameFreeze` locks, paired
with the generated `descNameAuto`. Its population matches the classified-face count in each model
(MacDonough: `descName` 34 = `areaGroupID` 34).

**Consequence for v1:** HBJSON `display_name` must prefer `descName` and fall back to
`descNameAuto`. Exporting `Wall_004_S` while the user's own `104C HALL` sits unread in the model
would be a visible, embarrassing data loss on exactly the models real consultants produce.

### Other new values

| Key | New value | Where | Status |
|---|---|---|---|
| `tempZoneID` | `'P'` | Bluff Reach, Holmes | **explained** — perimeter (group 16) |
| `tempZoneID` | `'X'` | Linde ×3 | **explained** — user-defined group (pairs 5↔5 with group 14) |
| `TFA_rf` | `0.6` | MacDonough | new reduction factor; `TFA_rf` takes at least `0`, `0.3`, `0.5`, `0.6` |

### Assembly build-ups may not be resolvable from the model alone ⚠

Flagged for Phase 1, not chased here. Faces reference assemblies that have **no `layer_table_*` key
in the same model**:

- Adelphi: `assemblyID` values `83ud`–`95ud`; **zero** `layer_table_*` keys.
- Bluff Reach: `assemblyID` values up to `114ud`; `layer_table_01ud`–`06ud` only.

Either the build-ups live inside the `assemblies_calc` / `assemblies_ud` Marshal blob, or they
resolve against the shipped library CSVs, or they are unresolvable. PRD §8.3 assumes
`layer_table_<id>` is the source, and calls assemblies *"the easiest place to be quietly wrong"* —
so this needs answering before the assembly translator is designed. Decoding the Marshal blobs is
Phase 1 (S3) work.

---

## 0.4 — Reference HBJSON

Full report: [`reference_hbjson_shape.md`](reference_hbjson_shape.md).

### Validation

**Core (`honeybee-schema==1.53.1`) — INVALID, but harmlessly so.** 5587 raw pydantic errors reduce
to **147 failing objects, every one inside `properties.energy`**. Zero errors touch geometry,
boundary conditions, apertures, or `properties.ph`. The inflation is pydantic-1 union expansion:
each non-conforming material reports once per union branch. `honeybee-schema==1.57.2` produces the
identical failure set, so this is not a simple version bump away.

**Consequence for PRD §11 (criterion 1):** the criterion **survives, scoped**. What fails here are
honeybee-energy payloads v1 does not write. Do not weaken the acceptance criterion on the strength of
this result — state that it covers the core geometry and PH payloads.

**PH extensions (`honeybee-ph-schema`) — passes, but proves almost nothing.** All 102 payloads
validate. The package is at **v0.1.0**, is **not on PyPI** (imported from
`~/Dropbox/bldgtyp-00/00_PH_Tools/honeybee-ph-schema`), and every model declares `extra="allow"`
with **zero required fields** — a payload of `{}` validates.

`AGENTS.md` states *"Schema contracts are published in `honeybee-ph-schema`"*, which overstates the
current position on both counts. **PRD §11 criterion 1 cannot lean on it as an acceptance gate until
it tightens.** Either tighten the schema, or replace that half of the criterion with an explicit
per-field expectation list. Recorded as an open question, not silently patched.

### Finding 4 — the 1287 orphaned shades, half confirmed

PRD §7.2 asked Phase 0 to confirm that untagged designPH faces have a natural home as orphaned
shades, and to promote it into v1 scope if so.

**Destination: confirmed.** Exterior context geometry has a well-formed home as `orphaned_shades`
with `is_detached: true` and a `ShadePhPropertiesAbridged` block. Costs nothing; lets Ladybug compute
shading downstream. **Promote to v1 scope.**

**Blanket source rule: refuted.** All 1287 shades are detached exterior site context, spanning
~50 m × 50 m around a 15 m × 9 m building; **0 of 1287** fall inside the building's bounding box. The
untagged designPH faces are a mixed bag — `§6` calls them *"interior partitions, furniture, context"*.
Mapping every untagged face to a shade would inject partitions and furniture into the shading model
and quietly corrupt any downstream shading calculation.

**The count similarity is not evidence.** 1287 vs 1359 is suggestive and nothing more: the HBJSON came
from the Rhino route, not from `adelphi-designph.skp`. A coordinate comparison needs geometry, which
the offline reader cannot read.

**Carried to Phase 1:** define the filter separating shading-relevant exterior geometry from interior
clutter, and confirm it against live geometry. Until it exists, untagged faces are *reported*, not
exported.

---

## 0.5 — PHPP ground truth

Extracted read-only (`data_only=True`; openpyxl does not recalculate) using the cell maps from the
`phi-rules` corpus teardowns rather than by exploring the workbook. Both teardowns matched this file
exactly.

| File | Rows | Contents |
|---|---|---|
| [`phpp/phpp_areas_summary.csv`](phpp/phpp_areas_summary.csv) | 19 | group summary — areas, avg U-values, temperature zones |
| [`phpp/phpp_areas_surfaces.csv`](phpp/phpp_areas_surfaces.csv) | 109 | per-surface areas, assembly links, U-values |
| [`phpp/phpp_u-values_assemblies.csv`](phpp/phpp_u-values_assemblies.csv) | 12 | assembly ID, name, Rsi/Rse, thickness, U-value |
| [`phpp/phpp_u-values_layers.csv`](phpp/phpp_u-values_layers.csv) | 56 | per-layer material, lambda, thickness |

**Integrity check passed.** Summing `phpp_areas_surfaces.csv` by group reproduces the summary
figures to the last decimal for all nine populated surface groups (1, 2–6, 8, 9, 10, 11, 18). Groups
15–17 are thermal bridges, entered in a separate block (`Areas!K143:AE246`) that is deliberately not
extracted — they are lengths, not areas.

Assembly links cross-check: `Areas!AA44 = '15ud-Wall_2E'` with `AC44 = 0.19240` matches
`U-values` block 12, `15ud / Wall_2E`, U = 0.19240.

**Note on provenance.** The Adelphi surface descriptions are `Face_006a677e`-style hashes — this
PHPP came from the **Rhino/PHX** route, not from designPH. It is sound as *numerical* ground truth
for U-values, areas and TFA; it is **not** a reference for what designPH's own PHPP export looks like.

⚠ **A note for the `phi-rules` feedback loop.** The `phpp-areas` teardown says *"Rows `34:40` are
fixed/import rows"*. Row **33** (`Projected building footprint`, group 0) is also fixed and
non-user-entered. A one-row correction; proposed to Ed rather than committed, per the skill's rule
that checklist and rule content is CPHC judgment.

---

## Documents updated

Per the evaluation protocol, the record was corrected before Phase 1 starts:

| Document | Change |
|---|---|
| `00_Context/DESIGNPH_DATA_MODEL.md` | §2 evidence base extended to 14 models · §5 `descName` added and the enum columns corrected · §5.2 the name derived/override/lock triple · §5.3 groups 12–14 and 18 identified · **§5.3.1 new** — the `tempZone` decode · §6 restructured and marked **CONTESTED**, with §6.2 the corpus evidence and §6.3 the revised reading · §6.4 extended · §12 open questions re-ranked, four closed |
| `DESIGNPH-PLUS_PRD.md` | §7.2 shading geometry promoted to v1 with a filter · §7.4 version-floor note · §8.3 assembly-resolution risk · §11 acceptance criteria scoped and `honeybee-ph-schema` dropped from the gate |
| `AGENTS.md` | Current-phase pointer · the "1441 tagged faces" figure corrected to 82 classified of 1441 · secondary corpus corrected to 11 files · `planning/spikes/phase0/` listed under existing tools |
| `CLAUDE.md` | Three new entries under "Things that have bitten us" — generalising from the six-face model, nil placeholders, pydantic-1 union inflation |
| `planning/00_OVERVIEW.md` | Status banner · secondary corpus corrected to 11 files / five projects; Linde 250703 added |
| `planning/PHASE-0_setup-and-long-leads.md` | Completion banner; deliverables ticked; as-run notes on §0.3 |
| `planning/PHASE-1_read-side-facts.md` | §1.1 rewritten around the refuted rule and marked blocking · §1.3 pruned to what is still open · **§1.4 and §1.5 new** (assembly resolution, the shading filter) · gate and deliverables updated · box 3 h → 4 h |
| `planning/.index.md`, `planning/RESULTS/.index.md`, `planning/spikes/.index.md` | Status table; new folder indexes |

## Handover to Phase 1

Ordered by what would waste the most work if got wrong:

1. **Settle the `*ID` / `*Auto` precedence per-face, live.** Blocking. Nothing in the read layer can
   be built on §6's rule as written.
2. **Confirm the `areaGroup` → `tempZone` mapping per-face** with the Inspector. Cheap; the mapping
   is a load-bearing integrity check.
3. **Resolve where assembly build-ups actually live** when `layer_table_<id>` is absent. Decode
   `assemblies_calc` / `assemblies_ud`.
4. **Define the untagged-face filter** for shading geometry.
5. **Decide the version floor** (PRD §7.4). The primary corpus model is 2.1.15, below the stated 2.2
   floor. Finding 2 makes this cheaper than it looked — if `*ID` is authoritative regardless of
   version, the 2.1/2.2 distinction largely stops mattering for reading.
