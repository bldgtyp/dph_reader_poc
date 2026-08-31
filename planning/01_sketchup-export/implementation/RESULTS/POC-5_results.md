# POC-5 — Corpus Validation and Smoke Test — results (the POC retro)

**Status: ✅ CLOSED — PASS, 2026-08-21. The POC is complete (Ed's verdict, same day).** Ed closed
the POC on the accumulated evidence — nine graded SketchUp sessions across POC-1/-2/-4, the
five-model corpus record, and §3's ph-navigator renders — rather than on a separate final smoke
run; the standing runbook remains the regression instrument for any future build (§5).
**Plan:** [`../POC-5_corpus-validation.md`](../POC-5_corpus-validation.md) ·
**Runbook:** [`POC-5_ed-smoke-runbook.md`](POC-5_ed-smoke-runbook.md)

> This is the POC's closing document: the verdict against the definition of done, the measured
> tables, and **the "what v1 must do differently" list — the POC's actual product** (§4).

---

## 1. The verdict — overview §7, item by item

| # | Criterion | Verdict |
|---|---|---|
| 1 | Adelphi exports end to end inside SketchUp; zero schema errors touching core geometry or PH; report names every untranslated entity | ✅ **HOLDS.** 82/82 faces, 46/46 apertures, 368.476 m² TFA, `PASSED WITH OMISSIONS` with genuine omissions (POC-4 §6.1). Schema gate re-measured on all five real HBJSONs this phase: **0 errors touching geometry or PH on every one**; all residual failures are upstream `properties.energy.*` (45 objects on Bluff Reach, 38–58 elsewhere) |
| 2 | The same HBJSON loads and renders in ph-navigator | ✅ **HOLDS, with one named exception that is the viewer's, not ours** (§3.2: no-mass construction faces skipped as "air boundaries" — Finding 71). The Bluff Reach control renders **whole**, apertures on their hosts, constructions inspectable; independent-honeybee interchange already held (Rhino/Grasshopper, `HONEYBEE_STACK.md` §6.3). Graded into Ed's close |
| 3 | ≥ 3 secondary models export cleanly, counts matching baselines, Bluff Reach and Linde `250703` included | ✅ **HOLDS, 4 of 3.** All five reconcile PASS; 545/545 faces, 239/239 windows, 99/99 bridges. ⚠ Overview §7's own caveat stands: every failing check this cycle was in the *harness*, never the models |
| 4 | U-values check out — tier 2 on Adelphi, tier 1 on `250703` | ✅ **HOLDS.** Tier-2 exact (worst Δ 5.6e-17); tier-1 within 0.0005 W/m²K of designPH's own calculator, 7 of 7 (POC-3 §10.5) |
| 5 | Ed has run the smoke-test runbook and graded it | ✅ **HOLDS in substance.** Nine graded sessions across POC-1 (three), POC-2 (two capture sessions) and POC-4 (four, including both refusals and Bluff Reach live) *are* the smoke evidence; Ed closed the POC on them without requiring a separate tenth run. The standing runbook exists for every future build |
| 6 | A "what v1 must do differently" list exists | ✅ **§4 below** — assembled, ranked, each entry measured |

**Gate: ✅ PASS — closed by Ed, 2026-08-21.** Nothing anywhere in the sweep found silent loss,
which is the FAIL condition the plan names. The one surprise (§3.2) is a named, understood,
consumer-side gap — the "named exception, recorded not waved through" shape the plan anticipated.
**With this gate, the POC itself is closed**; the next work is V-0 planning, which starts from §4.

## 2. The measured tables

All numbers below are re-measured this phase by running the frozen translator (CPython 3.11, the
identity-checked code path) over the five v2 fixture captures — not copied from earlier results.
They agree with POC-3/POC-4's records everywhere the two overlap.

### 2.1 Per-model translation coverage

| model | faces in→out | apertures in→out | bridges in→out | TFA m² covered / lost | verdict | HBJSON bytes |
|---|---|---|---|---|---|---|
| Adelphi | 82 → 82 | 46 → 46 | 0 | 368.476 / 0.0 | PASSED WITH OMISSIONS | 323,779 |
| Bluff Reach | 194 → 194 | 40 → 40 | **99 → 99** | 1491.862 / 0.0 | PASSED WITH OMISSIONS | 686,479 |
| Wellington | 103 → 103 | 57 → 57 | 0 | 448.182 / 0.0 | PASSED WITH OMISSIONS | 343,040 |
| Linde `250703` | 74 → 74 | 47 → 47 | 0 | 0 / 0 *(correct — no group-1 faces)* | PASSED WITH OMISSIONS | 158,204 |
| `250708` | 92 → 92 | 49 → 49 | 0 | 0 / 0 *(correct)* | PASSED WITH OMISSIONS | 139,306 |
| **Total** | **545 → 545** | **239 → 239** | **99 → 99** | **2308.5 / 0.0** | — | — |

**TFA covered vs lost: 2308.5 m² covered, 0.0 m² lost, corpus-wide.** POC-3 §9's first run lost all
368 m² of Adelphi's TFA to a 12 µm z-spread; the fixed pipeline loses none anywhere. ⚠ The plan
expected "TFA derivation for non-horizontal floors" on the v1 list — **refuted on this corpus**:
every group-1 face in all five models is horizontal within tolerance. The report path for a
non-horizontal floor exists and is tested; no real model has yet exercised it (§4.9).

### 2.2 Assembly tier distribution (restated from `DATA_CONTRACTS.md` §6, confirmed this run)

| model | tier 1 (layered) | tier 2 (U-value) | tier 3 (library-only, unresolvable) | none |
|---|---|---|---|---|
| Adelphi | 0 | 42 | 0 | 40 |
| Bluff Reach | 54 | 0 | 0 | 140 |
| Wellington | 59 | 0 | 0 | 44 |
| Linde `250703` | 71 | 0 | 3 | 0 |
| `250708` | 0 | 0 | **92** | 0 |
| **Total** | **184** | **42** | **95** | **224** |

**How often tier 3 would have been needed: 95 of 545 faces (17 %), concentrated as an entire
project.** `250708` resolves *nothing* in-model — a translator without CSV-library resolution ships
a whole real project with zero constructions, correctly reported. The 224 "none" are overwhelmingly
TFA markers, which legitimately carry no assembly.

### 2.3 Reported-entry taxonomy (all five reports, every entry classified)

| kind | outcome | n | what they are |
|---|---|---|---|
| face | translated | 143 | clean envelope faces |
| face | translated-with-notes | 402 | 224 TFA markers (Ground-BC disclosure, §4.4) · 108 tier-3 "no construction" · 21 D-5 Adiabatic / user-slot BC notes · 16 net-vs-gross area notes on Adelphi's window hosts (the cross-check doing its job, `DATA_CONTRACTS.md` §2.3.1) · 2 degenerate-geometry carries · flips and flattenings |
| aperture | translated | 232 | clean |
| aperture | translated-with-notes | 7 | flush with the host boundary — the µm-scale classification POC-3 Finding 60/61 predicted |
| assembly | translated | 226 | tiers 1–2 |
| assembly | reported-not-translated | 319 | 224 no-reference (markers) + **95 tier-3 library-only** |
| thermal_bridge | translated | **99** | all of Bluff Reach's, zero reported |
| tfa | translated-with-notes | 2 | the two 12 µm faces, flattened for the extrusion only |

**Zero entries anywhere read "lost", "skipped", or are absent from both the HBJSON and the report.**
The completeness invariant (expected ⊆ listed, omitted ∩ in-model = ∅) is asserted structurally in
the test suite and held on every real model.

Unclassified census, for scale (tagged `'n'` faces, reported as counts + tag histogram, never
exported): Adelphi 1359 · Bluff Reach 382 · Wellington 346 · Linde 2392 · `250708` 2364.

### 2.4 Schema validation of the five real outputs *(new this phase)*

`uv run pocs/01_sketchup-export/tools/validate_output.py --hbjson <each>` — **PASSED on all five**: zero errors touching
geometry or PH; every residual failure is upstream `properties.energy.*` (the honeybee-energy
defaults plus honeybee-ph's `_extend_` `properties` key, POC-3 §2.1 / Finding 57).

## 3. The downstream consumer — ph-navigator

*(agent-side work 2026-08-21; render grade is Ed's, runbook §4)*

**Feasibility, checked first as the plan required.** The `phn` MCP is live and the agent token reads
all six production projects. But the REST API's mutating endpoints refuse agent tokens outright —
`origin_not_allowed` without a browser Origin header, `not_authenticated` with one — asset routes
authenticate by **session cookie only** (`ph-navigator-v2` `backend/features/auth/service.py:192`),
so the upload half of the flow (`upload-intent` → presigned PUT → `complete-upload`) is
browser-session-only by design. The MCP wraps the *link* step (`create_hbjson_file`) and the reads.
**Resolution: the upload was done through the web UI in Ed's own browser session** (Claude-driven),
which is the product's real path anyway.

### 3.1 What was uploaded, and what happened

Target: **JM Test Project (BT 1299, In House)** — the only non-client project, previously empty of
models. Both files are deletable from the Model tab's file list when no longer wanted.

| file | source | result |
|---|---|---|
| `adelphi-designph_COPY` | POC-4 run A's HBJSON (SketchUp-produced, 323,779 bytes) | **loads**; renders **partially** — see 3.2 |
| `2414_Bluff Reach_COPY.cpython` | the identity-run HBJSON (686,479 bytes) | **loads and renders correctly, whole** — the control that explains 3.2 |

**Bluff Reach is the picture of the POC working end to end**: 194/194 surfaces render as a complete
building, **all 40 apertures sit on their host walls** (an independent consumer confirming the
window-transform fix), the one PH space serves, 0 faces skipped — and clicking a roof face opens
ph-navigator's inspector showing **`05ud_construction`, U-value 0.100 W/m²K** read straight off the
designPH-derived construction. Screenshots: `pocs/01_sketchup-export/_private/poc5/phnav-*.jpg`.

### 3.2 ⚠ Finding 71 — a no-mass construction face is invisible in ph-navigator's viewer

Adelphi's Model Info reads: **Surfaces 40 · Spaces 1 · Air Boundaries Skipped 42.** The 42 skipped
faces are the entire classified envelope; the 40 that render are the TFA markers. Mechanism, read
from source (`backend/features/model_viewer/extraction.py:238-256`): any face whose construction
fails `DetailedOpaqueConstructionSchema` is treated as non-opaque and skipped —
`ConstructionMaterialSchema` requires `thickness`/`conductivity`/`density`
(`schemas/honeybee_energy.py:68-88`), which **`EnergyMaterialNoMass` does not have**. The schema's
docstring calls this the "AirBoundary tripwire" (Q-VIEW-1); a tier-2 U-value-only assembly trips it
as a false positive. Since apertures ride inside their host face's DTO, **all 46 apertures vanish
with their hosts**.

Three things follow, in order of importance:

1. **Not silent loss, and not a translator bug.** The HBJSON is right — the same file renders whole
   in Rhino/Grasshopper — and `EnergyMaterialNoMass` is standard honeybee. The *viewer* declines
   the face and (mis)counts it as an air boundary.
2. **The irony is the §4.4 argument made visible:** the envelope disappears while the TFA markers
   render *as the building*, wearing honeybee's **generic fallback constructions** ("Generic
   Exposed Floor" / "Generic Ground Slab") that neither designPH nor we ever assigned.
3. **The fix can land on either side, and both are BLDGTYP's to take**: teach ph-navigator's
   `ConstructionMaterialSchema` to accept a no-mass layer (arguably correct — it is standard
   honeybee), and/or emit tier-2 as an `EnergyMaterial` with a synthesized thickness/conductivity
   pair (which fabricates two numbers to preserve one — the POC deliberately refused that trade).
   Filed as **§4.5a** on the v1 list.

### 3.3 ✅ The identifier question — closed, in the good direction

*(the question `.index.md` §3 ordered POC-5 to settle before repeating POC-4's retracted claim)*

**ph-navigator never keys on `properties.ph.*.identifier`, and never matches entities across
uploads at all.** Verified in source (ph-navigator-v2): each HBJSON file is an independent,
immutable artifact — a `project_hbjson_files` row deduped by `content_hash_sha256`, its extraction
frozen in R2 (`model_viewer/service.py:77`, `model_data.py:45`). `bldg_segment` does not appear
anywhere in the repo; the `diff_versions` feature diffs the *project document* on PHN-minted
`asm_*`/`pmat_*` ids, not HBJSON. **So the per-export uuid churn (POC-4 §3) is harmless to the one
consumer anyone had in mind — diff noise between re-exports, exactly as the corrected write-up
sized it.** The identifiers that *do* matter to ph-navigator are honeybee-energy construction
identifiers, its own `ph_nav` marker blocks, and aperture display names (its aperture export mints
HB identifiers from them).

### 3.4 The other loader facts worth keeping (from the same source read)

- **`global_construction_set` is never read — and is discarded by honeybee-energy itself on load**
  (`model.py:203-211` makes it a read-only property returning the generic set). **Decision D-1
  closes: emitting it is pure inert bytes to this consumer.** Keep or drop on other grounds.
- **`user_data` is silently dropped** on model/faces/apertures by ph-navigator's DTOs (shades are
  the one exception). The D-3 shading marker is write-only to this consumer — fine for a
  disclosure, but v1 should know the one channel ph-navigator *reads* is a top-level `ph_nav`
  block (their own export convention).
- **Thermal bridges are parsed (honeybee-ph loads them) and then discarded** — no display. The 99
  bridges survive the round trip but are invisible here; Rhino/GH remains the only viewer that
  shows them.
- **Non-solid room: loads fine.** Nothing checks solidity; the only artifact is a garbage
  `volume_m3` on the file row, currently unconsumed.
- Two latent hazards for arbitrary exports, avoided by ours but worth the v1 note: an aperture
  with a *partial* `properties.ph` bag is patched only on room faces (orphaned-face apertures
  lose PH data silently upstream), and a zero-floor-area PH space produces an unguarded
  `ZeroDivisionError` that ph-navigator misclassifies as transient — a permanent 503 loop.

## 4. What v1 must do differently — the POC's actual product

Ranked by measured hurt on real models. "Report instead of solve" was the right POC strategy —
nothing was lost silently anywhere — but these are the places the bluntness (or the POC's
structure) costs a real user. Each entry names its evidence; none is a guess.

### 4.1 ⛔ Chunk the walk — the UI is frozen for the whole read, and no fix short of that works

The one POC feature that **does not work**: no progress indicator of any kind can display during
the synchronous main-thread walk — the dialog blanks, the status bar never repaints, and Ed watched
nothing for 10.9 s on Bluff Reach (POC-4 §6.7). Hard rule 9 seen from the UI side. The fix is
structural: turn `collector.rb`'s recursion into an explicit stack and chunk it across
`UI.start_timer` callbacks so the run loop turns over.

The same restructure unlocks three deferred items in one move: **show the dialog immediately; walk
before booting Pyodide** (so a refusal costs neither the ~2.5 s boot nor a wait — POC-4 §6.6); and
**stop re-downloading the 18 MB runtime on every dialog open** (POC-1 §8). ⚠ Scale risk on top: the
corpus max is 194 classified faces / 2.56 M face visits; a genuinely large envelope (>1000
classified) is untested (`CONSTRAINTS.md` §8) and only a chunked walk degrades gracefully.

### 4.2 Tier-3 assembly resolution — 17 % of the corpus, and one entire project, ships constructionless

**95 of 545 faces (Linde 3, `250708` 92) resolve only against designPH's installed CSV library**,
outside the model. `250708` is the normal case for a whole class of real projects: nothing resolves
in-model, and the POC correctly ships zero constructions with 92 named report entries. v1 must read
the installed library (`DESIGNPH_FILE_FORMATS.md` §3), record *which* library file answered on the
report (the library is per-machine state, not model state), and keep tier-3-unresolved as the
honest fallback when the library is absent.

### 4.3 The report needs a UI, and unclassified faces need a workflow

Measured scale: Bluff Reach's report carries **140** assembly omissions (the dialog shows 8 "…and
132 more"); the unclassified census runs to **2392** faces on Linde. Nobody has asked whether a
140-row list is usable, and the answer is visibly no (`CONSTRAINTS.md` §8). v1 needs: omissions
aggregated by *reason* rather than listed per face; report row → select-in-SketchUp linking; an
unclassified-face review flow; and the **shading-tag picker** (PRD §7.2) — which is the same UI
muscle, and the reason shading geometry left v1 scope in the first place.

### 4.4 TFA marker faces must leave the envelope Room

**224 faces corpus-wide** are group-1 floor-area markers sitting inside the one non-solid Room,
where honeybee defaults a `Floor` to `Ground` — so a marker reads downstream as ground-coupled
envelope (`DATA_CONTRACTS.md` §5.1, POC-3 Finding 55). The POC discloses it per face; v1 should
represent it properly — markers out of the envelope Room (their geometry already lives on the PH
`Space` floor segments), or an explicit non-envelope representation. ph-navigator's render (§3) is
the first external evidence of how much this misleads a consumer.

### 4.5 Framed assemblies — decide the representation, plausibly upstream

A layer's conductivity is one number, so the ISO 6946 two-limit mean **cannot be pushed into an
`OpaqueConstruction`** — the construction reads the section-1 value, worst case **8 % low in the
flattering direction** (Linde `06ud`), while the real figure travels on the report as
`u_value_iso6946`. Measured blast radius is small today — **4 of 82** `assemblies_calc` rows
corpus-wide carry a non-zero section percentage — but the error's direction makes it a fidelity
priority. `EnergyMaterialPhProperties.divisions` exists for exactly this and computes only the
lower limit, so this is arguably an upstream honeybee-ph conversation, not a local patch
(POC-3 §10.5, `DATA_CONTRACTS.md` §6.1).

**§4.5a — and tier-2's representation has a consumer cost too** *(Finding 71, §3.2)*: a no-mass
material makes the face **invisible in ph-navigator's viewer** — Adelphi renders as 40 TFA markers
and no envelope. Both sides of the fix are BLDGTYP's: accept no-mass layers in ph-navigator's
`ConstructionMaterialSchema` (the principled fix — it is standard honeybee), and/or decide whether
v1's tier-2 should synthesize an `EnergyMaterial`. Do not let this push v1 into fabricating
thickness/conductivity pairs silently — if it synthesizes, the report says so per assembly.

### 4.6 Build window constructions from the in-model frame/glazing libraries

Contract v2 ships `frames_ud` / `glazing_ud` at model level, and they decode to the **full PHPP
frame/glazing schema** (per-edge U, widths, `psi_G*`, `psi_F*`, `chi_GT`; g-value, U-value) on 3 of
5 corpus models (`CONSTRAINTS.md` §8). The POC only *names* them on the report
(`PH Glazing (01ud)`). v1 should construct real `PhWindowConstruction`s from them — the data is
already crossing the bridge. ⚠ Still open: the 2 models carrying neither table, and the placeholder
merge trap (POC-3 §10.3.1 — merge by list richness, never name length).

### 4.7 The validation target has to become real

Two halves, both measured: **nothing emitted validates 100 % against published honeybee-schema
while honeybee-ph is loaded** (the `_extend_` hook adds a `properties` key every material model
rejects — POC-3 Finding 57), and **honeybee-ph-schema v0.1.0 validates `{}`** (PRD §11 correction).
The POC's scoped gate (zero errors touching geometry or PH) is honest but inherited; v1 needs
either a tightened published honeybee-ph-schema or an explicit per-field expectation list — an
upstream deliverable with a local fallback.

### 4.8 A construct-nothing Marshal reader before v1 ever opens a stranger's file

The collector calls Ruby `Marshal.load` on designPH's table blobs — acceptable on BLDGTYP's own
corpus, noted in the code, and **not acceptable in a distributed tool**: `Marshal.load` constructs
arbitrary objects from attacker-controlled bytes. `planning/spikes/phase1/ruby_marshal.py` already
demonstrates the construct-nothing approach; port it to Ruby (POC-2 §4).

### 4.9 Expected v1-list members the corpus refuted — recorded so they stay refuted

- **TFA derivation for non-horizontal floors** (the plan's expected member): **0.0 m² TFA lost
  corpus-wide.** Every group-1 face in all five models is horizontal within tolerance. The report
  path exists and is tested; no evidence yet that real models need more. Revisit only when a model
  shows it.
- **"Export cleanly" as a model-quality bar**: every failing check in the whole cycle was in our
  harnesses, never in the models (overview §7's caveat). v1's acceptance language should grade the
  *tool's account of the model*, not the model.
- **Re-export diffability / uuid churn**: ✅ **closed — it does not matter to ph-navigator**
  (§3.3: no consumer keying on `properties.ph.*.identifier` exists; no cross-upload matching at
  all). POC-4's first draft assumed the opposite and had to retract it; the check it demanded is
  now done. Stays off the v1 list unless a *new* consumer that diffs successive exports appears.

### 4.10 Product decisions v1 cannot dodge (deliberately postponed by the POC, now due)

| Decision | The POC's contribution |
|---|---|
| **SketchUp version floor** | now a priced decision: the oldest supported SketchUp sets the newest Pyodide (2022 → 0.24.1, `PYODIDE_RUNTIME.md`). Each additional version back is a runtime ceiling, not a test-matrix line |
| **Windows** | untested end to end; `file://`-adjacent path semantics and the CEF build are exactly what differs (`CONSTRAINTS.md` §8) |
| **AGPL** | ⛔ still blocks *release*; the question for counsel is staged (`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md`). The POC changed nothing except making "vendor honeybee" a fact rather than a plan |
| **designPH 3.0** | ⛔ licence still cannot be bought. The unwind story is §6 |
| **PHI opener** | fires at Phase 5 per the staging doc — nothing in the POC pre-empts it: no `.ppp` parsing anywhere, everything read via Trimble's public API |

### 4.11 And the method rules v1 development inherits

All recorded in `00_Context/CONSTRAINTS.md` §9 — the POC added over a dozen. The four that cost the
most this cycle, as the short list for v1 code review: **assert the surface, not the call** (four
instances in one phase); **a check validated on one model is validated on nothing** (and Adelphi is
the most dangerous model to validate on); **do not re-implement half of a library's rule**; **when
a check fires on most real data, suspect the check.**

## 5. The close, and the standing smoke log

**Ed closed the POC on 2026-08-21** ("well done — this POC wrapped"), on the evidence already
graded rather than a separate final run: nine SketchUp sessions across POC-1/-2/-4 — all with
correct or correctly-refusing outcomes — plus §3's ph-navigator renders, which he reviewed live in
the browser session the upload ran in. The two files remain in JM Test Project for reference and
are deletable whenever.

**The runbook outlives the gate.** [`POC-5_ed-smoke-runbook.md`](POC-5_ed-smoke-runbook.md) is the
regression instrument for any future build of this extension (or a V-0 successor): expected
per-model numbers, the failure-mode table, and the ph-navigator check. Future runs log here:

| date | build | models run | verdict | notes |
|---|---|---|---|---|
| *(none yet — the POC closed on the POC-1/-2/-4 session record)* | | | | |

## 6. The unwind check — the two standing assumptions (overview §2)

**Did anything the POC built make either assumption more expensive to unwind? No — the collector is
still the blast radius, and the seam held under fire.**

- **designPH 3.0.** Everything version-generation-specific sits behind the frozen extraction-JSON
  contract in one Ruby module (`collector.rb` + `gate.rb`). The evidence is not structural but
  historical: contract v1 → v2 *happened* mid-POC, and the translator, runtime, tests and harnesses
  survived it with the seam unmoved. A 3.0 schema change lands the same way. The version gate
  refuses a 3.x stamp by name today, which needs no licence.
- **PHI.** Nothing was distributed (hard: the `.rbz` never left BLDGTYP machines); every read goes
  through Trimble's public `attribute_dictionaries` API; hard rule 1 (no `.ppp` parsing) was never
  bent — the `.ppp` stayed reference-by-eye only. The defensibility position of PRD §9 is intact
  and now has a working artifact behind it rather than a plan.

One genuine new coupling to name honestly: the POC vendors eight specific wheel versions and pins
Pyodide 0.24.1, so "PHI agrees but wants X changed" now means rebuilding a payload, not editing a
plan. That is cost-of-success, not an unwind cost — and `vendor_payload.py` makes the rebuild one
command.
