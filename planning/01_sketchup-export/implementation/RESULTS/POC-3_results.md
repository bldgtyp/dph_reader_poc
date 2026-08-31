# POC-3 — Python Translator — results

**Status: ✅ PASS — POC-3a and POC-3b both closed 2026-08-21.** 545/545 classified faces, 239/239
windows and 99/99 thermal bridges across all five corpus models; **both U-value regressions PASS**.
§9 is the first real run's three defects, §10 is how they were fixed and what that took —
including a circular confirmation this file had to retract.
**Date:** 2026-08-20, updated **2026-08-21** · **Plan:** [`../POC-3_python-translator.md`](../POC-3_python-translator.md)

> The translation core is complete: faces with **boundary conditions**, assemblies in four tiers,
> thermal bridges from edges, apertures projected onto their hosts, TFA spaces, the site, and a
> report that accounts for every entity. 136 pytest cases on CPython 3.11, and the same package runs
> unmodified in Chromium 88. **Zero schema errors touching geometry or PH** on a synthetic model
> carrying every PH payload the POC emits — the early milestone §11 asked for, and it found two
> things worth knowing.

---

## 1. What was built

`pocs/01_sketchup-export/py/dph_translator/`, ~2000 lines across 11 modules:

| Module | §  | What it owns |
|---|---|---|
| `contract.py` | 2 | The seam. Typed `FaceRecord` / `EdgeRecord` / `WindowRecord` / `Table`, and **every** type check |
| `facetypes.py` | 3 | Area group → face type **and boundary condition**, one table, plus the temp-zone integrity check |
| `constructions.py` | 5 | Four tiers, tier recorded per face |
| `apertures.py` | 4 | Projection onto the host plane, containment, reveal → PH `ShadingDimensions` |
| `bridges.py` | 6 | Edges → `PhThermalBridge` on the building segment |
| `spaces.py` | 7 | TFA: filter, attempt, report. Never project, never repair |
| `site.py` | 8 | Climate identifiers, carried not resolved |
| `report.py` | 9 | The report schema, the three-state verdict, the shading marker |
| `build.py` | — | Orchestration |
| `entry.py` | — | `translate_json(str) -> str`, unchanged from POC-1 |

Deleted: `translate.py`, POC-1's skeleton. Its behaviour is `build.py`'s now, and the seam did not
move — which was the point of fixing it in POC-1.

## 2. Verification

`make ci`, green on 2026-08-20:

| Step | Result |
|---|---|
| `ruff` + `ruff format` (`py/` **and** `tools/`) | clean |
| `mypy` | no issues, 11 source files |
| `pytest` | **136 passed** |
| `ruby -c` (8 files) + two Ruby suites | ALL CHECKS PASSED |
| **`make validate`** — honeybee-schema 1.53.1 | **0 errors touching geometry or PH** |
| `build_rbz.py` | 6.75 MB `.rbz`, 20.83 MB installed |
| `verify_in_chrome.py` on Chromium 88 | **PASSED**, cold start 3.2 s |

The Chromium 88 run is not incidental: it is the **real translator**, not POC-1's stub, running the
same package in the engine SketchUp 2022 embeds. One code path, three hosts, still true.

Re-run green on **2026-08-21** after §10's fixes and the v2 contract bump: **154 pytest cases**,
6.77 MB `.rbz` / 20.84 MB installed, Chromium 88 cold start 4.7 s.

### 2.1 The schema milestone, run early on purpose

§11 warned that Phase 3's clean verdict came from a model with *no* spaces, bridges or aperture PH
properties — so "the PH segment validates" had never been tested against what this phase adds.
`tools/validate_output.py` translates a synthetic model carrying **all** of it (6 faces, 1 bridge,
1 aperture with reveals, 1 TFA space, all four assembly tiers) and validates it:

```
ok    zero errors touching geometry or PH  (0)
ok    all remaining failures are upstream `properties.energy.*`  (38 objects)
```

Two things came out of running it early rather than in POC-5:

1. **honeybee-schema requires a `Room` to have at least 4 faces.** A three-face model produces
   schema-invalid HBJSON on a rule that has nothing to do with translation quality. Irrelevant for
   real models (Adelphi has 82) and a trap for small test fixtures — which is why the validated
   fixture has six.
2. **honeybee-ph's `_extend_` hook makes every material fail published honeybee-schema.** It adds a
   `properties` key that the 1.53.1 `EnergyMaterialNoMass` model rejects as *extra fields not
   permitted*. This is broader than Phase 3's Finding 40: not just honeybee-energy's *defaults*, but
   **any material honeybee-ph touches, including the ones we emit**. No HBJSON produced with
   honeybee-ph loaded can validate 100% against published honeybee-schema. `honeybee-ph-schema`
   (AGENTS.md, "Schema contracts are published in honeybee-ph-schema") is the v1 answer; the gate
   stays scoped to geometry/PH per §11's own instruction.

## 3. Decisions, closed

| # | Decision | What was done |
|---|---|---|
| D-1 | Emit honeybee-energy's `global_construction_set`? | **Kept**, exactly as Phase 3. It contributes 26 of the 38 failing objects and none touch geometry or PH. Revisit for v1 with ph-navigator evidence from POC-5 |
| D-2 | The `null` schema version | **Stamped `"1.53.1"`** from `dph_translator.HBJSON_SCHEMA_VERSION`, with a test asserting it equals the pin in `validate_hbjson_core.py`. A stamp that claims a version nothing validates against would be worse than none |
| D-3 | Where the shading marker lives | **`model.user_data`**, verified to survive `to_dict` *and* `from_dict`. The model cannot travel without the disclosure |
| D-4 | Group 11: TFA or envelope? | **Envelope**, `Ground` BC. TFA is group 1 only, and **absent `tfa_rf` = 1.0** |
| D-5 | Group 18 boundary condition | **`Adiabatic`**, with a per-face note. Equal-temperature neighbour ⇒ zero heat flow |

## 4. Findings

| # | Finding | Consequence |
|---|---|---|
| 53 | ⚠ **honeybee's `u_value` and `u_factor` read the opposite way round from the obvious sense.** `u_value` is **material-only**; `u_factor` includes standard films. A no-mass material from `R = 1/0.15` reports `u_value == 0.15`, `u_factor == 0.146` | designPH's `U_value` column is material-only, so `u_value` is the comparable figure. Reaching for `u_factor` because it sounds more precise would put **every** U-value regression out by the film resistances — consistently, in the direction that still looks plausible. Caught by checking, not by reading |
| 54 | ⚠ **honeybee refuses an aperture on a `Ground` or `Adiabatic` face.** `AssertionError: Aperture cannot be added to Face … with a Ground boundary condition` | A direct collision between §3's boundary conditions and §4's apertures: designPH groups 9 and 11 map to `Ground`, so a window in a below-grade wall is refused. The refusal is *correct*; it is reported by window name rather than swallowed |
| 55 | ⚠ **honeybee's default boundary condition for a `Floor` is `Ground`, not `Outdoors`.** A group-1 TFA marker, which correctly gets no BC from us, therefore reads downstream as ground-coupled envelope | Harmless in the POC (nothing consumes a group-1 face's BC) and a real v1 question: TFA marker faces probably should not be in the envelope Room at all. Reported per face so a reader is not misled |
| 56 | ⚠ **honeybee-ph fabricates a default site — New York, 40.6/−73.8 — on every building segment**, and it serialises looking exactly like project data | designPH stores only a climate *dataset id*, which the POC carries as an identifier. A consumer reading the HBJSON has no way to tell the site is a placeholder, so the report says so explicitly and records the fabricated coordinates |
| 57 | **honeybee-ph's material extension is not representable in published honeybee-schema 1.53.1** (see §2.1) | Widens Phase 3's Finding 40 from "the defaults do not validate" to "nothing we emit validates while honeybee-ph is loaded". A v1 decision, not a POC blocker |
| 58 | **`mypy` cannot check the vendored stack at all** — `honeybee_ph/phi.py:42` places a Python-2-style `# type:` comment where mypy reports `Invalid syntax`, which halts all further checking | A direct cost of the IronPython-2.7 compatibility that makes the stack pure and Pyodide-viable. `follow_imports = "skip"` on the stack's modules keeps our own code fully checked |

## 5. What the tests actually defend

149 cases (136 at the gate, 13 added by §10's fixes), and each one is pointed at a way data
disappears quietly rather than at a happy path:

- **Face typing and boundary conditions** — every mapped group, both refusals (an aperture group or
  a bridge group arriving as a face), the unmapped fall-through, and the `'I'` vs `'i'` distinction
  that a case-insensitive compare would erase.
- **Assemblies** — all four tiers including **2a, where a `assemblies_calc` header alone produces
  nothing at all** because that schema has no U-value column; the 8- and 12-column `layer_table_*`
  variants read by name; film resistances on the report and *not* folded into the material.
- **Thermal bridges** — the count assertion (*n in, n out-or-reported, zero silently gone*), the
  three `group_type` strings, and a test that resolves `connection_ref` correctly **while a
  same-id row sits in the wrong table** — the failure that would otherwise look like success.
- **Apertures** — projection onto the host plane (the reveal is data, not geometry), containment,
  a straddling window, a window larger than its host, an unresolved host, a dangling host id, a
  holed host, and the Ground-BC refusal.
- **TFA** — the non-horizontal face named and its area counted as *lost*; **absent `tfa_rf` = 1.0**;
  group 11 excluded; multiple `vent_ud` rows reported rather than averaged; and that the throwaway
  extrusion Room does not steal the real Room's faces.
- **The report** — the completeness invariant asserted structurally (expected ⊆ listed, and omitted
  ∩ in-model = ∅), the three-state verdict, and that the shading marker and the reveal data do not
  contradict each other.
- **§10's fixes**, each written against the failure it replaces: a 12 µm z-spread that must *not*
  cost the room, the 1 mm line between flattening and fabrication, a refusal narrowed to the face
  honeybee names (injected rather than provoked — honeybee happily extrudes Adelphi's real sliver,
  and hunting for a polygon it refuses would test ladybug's robustness rather than our narrowing),
  an unattributable refusal, a rectangle off its host plane, a window flush with the host edge, a
  holed host, the Floor and RoofCeiling flips, the untyped face that must *not* be reoriented, and
  degenerate geometry that is named and carried rather than dropped.

⚠ **All of it is synthetic and none of it is evidence about designPH.** The house lesson stands. The
fixtures are hand-written *builders* rather than the hand-written JSONs contract §7 names — a
deliberate deviation, recorded in `tests/synthetic.py`: every test still parses through the same
`contract.parse` a real capture goes through, and `wall("w", 8, x0=0.0, x1=4.0)` is checkable by eye
where twelve floats are not.

## 6. Gate

**POC-3a: ✅ PASS.** Synthetic suite green; contract handling, type normalisation, the report
invariant, boundary conditions, and schema validation on a synthetic model's output — all closed
without an Ed run, which §7 said was the point.

**POC-3b: ✅ PASS**, closed 2026-08-21 once POC-2's fixtures landed:

| Clause | State |
|---|---|
| Real-fixture goldens (Adelphi 82/82, Bluff Reach 99 edges, `250708` coalesce, Wellington, `250703`) | ✅ **all five** — 545/545 faces, 239/239 windows, 99/99 bridges, 0 rejected |
| U-value regression, tier 2 on Adelphi (join by **name**, not id — different id spaces) | ✅ **exact**, worst Δ 5.6e-17 across 12 assemblies / 42 faces. ⚠ The name join matches only **3 of 14** — the `.skp` and its PHPP are different id spaces *and* different populations (§10.5) |
| U-value regression, tier 1 on `250703` (25 layer tables) | ✅ **PASS after a real fix** — 7 of 7 against designPH's own U-/R-value calculator, worst Δ **0.0005** against ±0.005. It found two defects; §10.5 |
| The two measured tables — TFA coverage, tier distribution | ✅ measured across the corpus. TFA 368.5 / 1491.9 / 448.2 m²; tiers in `DATA_CONTRACTS.md` §6 |

## 7. Out of scope, unchanged

PHPP writing; mechanical data; multi-zone; model writing. Frame/glazing library resolution stays a
stretch goal — `frames_ud` and `glazing_ud` are not in the contract's shipped tables, so the ids are
carried on the report and nothing is invented from them.

## 9. First real-fixture run — 2026-08-21, Adelphi

82 of 82 classified faces translated, 0 rejected, 96,179 bytes of HBJSON, verdict `PASSED`. The
assembly tiers came out **exactly** as Phase 1 predicted: `{2-u-value: 42, none: 40}` — 42 refs
resolving through the in-model `assemblies_ud` snapshot, and 40 faces with no assembly, which are
precisely the 40 TFA markers. And the output **loads in Rhino/Grasshopper** on an independent
honeybee install (`HONEYBEE_STACK.md` §6.3).

**Three defects, in priority order:**

| # | Defect | Cause | Fix |
|---|---|---|---|
| 1 | **0 of 46 apertures translated** | The collector's `panel_outer_loop` was `null` on all 46 — `definition.entities.grep(Face)` finds nothing, the geometry is nested | Recurse the definition; use the **rough opening** `lenx × leny` through the **world** transform. Contract §8.1 |
| 2 | **0 m² TFA derived, 368 m² reported lost** | The horizontality pre-filter measured **orientation** while honeybee measures **z-extent**, at 1e-7 m. 2 faces with a 12 µm spread slipped through and the exception cost all 40 | Use `Face3D.is_horizontal`; flatten below a stated, reported tolerance; never let one face cost the room. `HONEYBEE_STACK.md` §4 |
| 3 | **16 faces flagged by the area cross-check** | ✅ **Not a defect — the check working.** `face.area` is net of glued openings; the boundary polygon is gross. `DATA_CONTRACTS.md` §2.3.1 | Keep the check; expect it to fire on every window host |

**Three more that are not ours**, and belong on the v1 list rather than the bug list: honeybee
rejects the 40 upward-pointing TFA Floors (a winding-convention clash); the model itself contains a
1.7 cm² sliver and a zero-width spur; and `ValidateModel`'s 234 naked edges are PRD §8.1's
deliberately non-solid Room.

**Not yet done at the time:** the two U-value regressions (§5) still needed `250703`'s layer tables,
and the report's TFA and tier tables needed the remaining four models to be worth reading. ✅ **All
closed in §10.5** — and the tier-1 regression, once it finally had a model with framed assemblies,
found a real defect that every earlier check had passed over.

## 10. All three fixed — 2026-08-21, offline then live

The fixes are in; `make ci` is green (149 pytest cases, Ruby suites, schema gate, Chromium 88).
What makes this more than "the tests pass" is that the whole fixed pipeline was **run against
Adelphi's real geometry without a SketchUp session**.

### 10.1 The capture answered a question nobody had asked it

The aperture fix rested on an inference: the rough opening is the local rectangle *from the origin*,
`+x`/`+y` — but the live evidence only showed that the **origin** lands on the host plane, which a
centred rectangle would satisfy just as well, half a window away. That was going to be settled by
the containment check on re-capture, i.e. by spending an Ed session.

It did not need one. The first (defective) capture ships `instance.transformation` parent-relative
and every face in world coordinates, and those two together **determine the parent transform**:
every window's local +Z must map onto its host's world normal (Kabsch over all 46, sign-resolved by
iteration) and every local origin must land on that host's world plane (least squares).
`planning/spikes/poc/solve_window_parent.py` recovers it and reproduces
`DESIGNPH_DATA_MODEL.md` §9.3's independently measured `[-3.2414, 8.1321, -2.9972]` and 403U's world
origin **to four decimals** — then answers the question outright:

| convention | windows inside their host polygon |
|---|---|
| **corner at the origin, `+x`/`+y`** | **46 / 46** |
| centred on the origin | 23 / 46 |
| corner at the origin, `+x`/`−y` | 15 / 46 |
| corner at the origin, `−x`/`−y` | 12 / 46 |

With the parent in hand, `patch_and_translate.py` rebuilds the two broken window fields *as the fixed
collector will emit them* and runs the real translator on the result. ⚠ **A rehearsal, not a
capture** — marked in its `generated_by`, written to a scratch path, never a fixture.

### 10.2 What the rehearsal says

| | first run | after the fixes |
|---|---|---|
| Faces | 82 of 82 | 82 of 82 |
| **Apertures** | **0 of 46** | **46 of 46** — 45 clean, 1 flush-boundary note |
| **TFA** | 0 m², **368 m² lost** | **368.476 m² covered, 0 lost** |
| Upward-pointing Floors in `check_all` | 40 | **0** |
| HBJSON | 96 KB | 324 KB |
| Verdict | PASSED WITH OMISSIONS | PASSED WITH OMISSIONS *(the 40 TFA markers legitimately carry no assembly)* |

The two 12 µm faces are named as **flattened for the extrusion, envelope face unchanged**; the
remaining `check_all` findings are the model's own — the spur, the sliver, and PRD §8.1's naked
edges.

### 10.3 Live confirmation, and what it cost — 2026-08-21, SketchUp 22.0.353

Ed rebuilt (`make ed`), restarted, and exported Adelphi. **Every prediction landed:**

| | rehearsal | live |
|---|---|---|
| Apertures | 46 of 46 | **46 of 46** |
| `off_plane_m` | 0.000 | **0.0 on all 46** |
| TFA | 368.476 m², 0 lost | **368.476 m², 0 lost** |
| Faces flattened (12 µm) | `face_4374_4353`, `…4354` | the same two |
| Assembly tiers | `{2-u-value: 42, none: 40}` | the same |
| HBJSON | 323,780 bytes | **323,779 bytes** |

**One divergence, 0.3 µm wide.** The rehearsal predicted one flush-boundary note (`500`); the live
run has two. `501L`'s sill sits **0.0003 mm** past its host's bottom edge where the rehearsal's numpy
rebuild put it exactly on zero. Both windows are genuinely flush — `500`'s head is on its host's top
edge to 0.0000 mm — and a third of a micron deciding the classification is the argument for the note
being a *warning* rather than a refusal.

#### ⚠ And the live capture immediately bought contract v2

The console logged `WARNING: extraction payload is 2249369 bytes (>1 MB)` — the contract's own
"log anything approaching 1 MB" rule firing on the first capture it ever applied to. The pre-fix
capture was 264 KB, and the only thing that had changed was §4.1's widened `dynamic_attributes`
allow-list. Measured offline, straight out of the `.skp`:

```
_frametype_options:   39,685 chars   distinct values across all 46 windows: 2
_glazingtype_options:  5,230 chars   distinct values across all 46 windows: 2
44,915 × 46 = 2.07 MB of a 2.25 MB payload
```

Every window carried a **byte-identical** copy of the same library, against a bridge verified to
4 MB. It is *library* data — designPH's installed frame list, ~500 entries down to
`Alumil S.A. - SD95 - SWISSPACER ULTIMATE=1806ed04`, which `DESIGNPH_FILE_FORMATS.md` §3 otherwise has
living only in the CSVs on disk. **Contract v2** hoists it to a model-level `libraries` block: 45 KB
once, and the translator now writes `PH Glazing (01ud)` where the report said `01ud`.

The bump was free only because it landed **between the fix and the corpus capture**. §9's warning
that a contract change costs an Ed re-capture was, for about an hour, not true — and that hour was
the whole window.

### 10.3.1 ⚠ The tiebreak that is not name length

designPH writes a placeholder, `&Launch designPH to edit=01ud&`, on some window definitions, and it
claims `01ud` just as the real library does. The obvious merge rule — *the longer name wins* —
**picks the placeholder**: "Launch designPH to edit" is 23 characters against "PH Glazing"'s 10, so
the whole library would be silently un-named while looking like it had resolved. The rule that works
is the size of the *list*: a placeholder names one id, a real library names hundreds. Caught by a
test written before the merge rule was, which is the only reason it was caught at all.

### 10.5 The two U-value regressions — 2026-08-21

All five models captured and reconciled (POC-2 gate closed), and the translator ran on all five:
**545 of 545 classified faces, 239 of 239 windows, and Bluff Reach's 99 thermal bridges** — the
first time the bridge path has run on real data. Tier 1 is finally exercised: 71 layered assemblies
on Linde, 59 on Wellington, 54 on Bluff Reach, against Adelphi's zero.

**Tier-2 pass-through (Adelphi): ✅ PASS, exact.** The `assemblies_ud` U-value reaches the HBJSON
unchanged on all 12 referenced assemblies / 42 faces, worst Δ **5.6e-17 W/m²K**. Compared against
honeybee's `u_value` (material-only), never `u_factor` (Finding 53).

**Tier-1 layered (Linde): ✅ PASS after a real fix — worst Δ 0.0005 W/m²K on 7 of 7 assemblies**,
against designPH 2.4.0 BETA's own U-/R-value calculator. Tolerance is ±0.005, so ten times the
margin. It got there by finding two genuine defects.

#### The defects

designPH mirrors PHPP's **three parallel construction paths** per layer (`lambda1/2/3` in
`layer_table_*`), with the path *areas* on the assembly header (`assemblies_calc.surf2_percentage`).

1. ⚠ **The emitted U-value ignored the framing.** `lambda2`/`lambda3` went onto
   `EnergyMaterialPhProperties.divisions`, but the material's conductivity is `lambda1` alone. On
   Linde's `06ud` that is **0.0698 against designPH's 0.0750 — 8 % low, in the direction that
   flatters the building.**
2. ⚠ **The divisions were set to equal column widths**, which describes a stud bay as half timber.
   They now carry the real areas.

And the ISO 6946 figure is reported for *every* tier-1 assembly, not only framed ones, because it
also folds in the films that honeybee's `u_value` omits — worth 0.004–0.005 W/m²K on Linde's three
unframed assemblies, which is on its own enough to fail a ±0.005 regression comparing the wrong pair.

#### What settled it, and what I got wrong first

Ed opened Linde in designPH and read `06ud` off the U-/R-value calculator. Two things came out of
one screenshot:

- **`surf2_percentage` is a percentage.** Stored `21.875`, the dialog shows **Surface percentage 2:
  21.88**, and section 1 is the unstored remainder, **78.12**. So the same column's `0.0625` and
  `0.09375` are 0.06 % and 0.09 % — *negligible* framing, not 6 % and 9 %. The earlier reading here
  ("all three land on exact sixteenths, so the column is mixed-scale") was a plausible pattern
  fitted to three numbers, and it was wrong.
- **The method is ISO 6946 §6.7, the mean of two limits** — upper (whole paths in parallel by area)
  and lower (area-weighted λ per layer) — not an area-weighted lambda. The dialog's **Error % :
  2.75** is the spread between them, and the implementation reproduces that figure exactly.

⚠ **An earlier claim in this file — "the blend formula is confirmed, not assumed" — was circular.**
It solved for the framing fraction that made a simple lambda blend match one PHPP number, then
reported the match as confirmation. A fitted parameter cannot confirm the model it was fitted to.
What replaced it is a published method checked against seven independent assemblies plus the
dialog's own error figure, and a hand-checked synthetic case in `test_constructions.py`.

| ref | designPH | reported | Δ | honeybee's `u_value` | spread |
|---|---|---|---|---|---|
| `01ud` | 0.104 | 0.1038 | −0.0002 | 0.1065 | 0.02 % |
| `02ud` | 0.128 | 0.1275 | −0.0005 | 0.1319 | — |
| `03ud` | 0.058 | 0.0583 | +0.0003 | 0.0595 | 0.01 % |
| `04ud` | 0.158 | 0.1582 | +0.0002 | 0.1626 | — |
| `05ud` | 0.062 | 0.0624 | +0.0004 | 0.0633 | 0.02 % |
| **`06ud`** | **0.075** | **0.0750** | **+0.0000** | 0.0698 | **2.75 %** |
| `07ud` | 0.165 | 0.1654 | +0.0004 | 0.1702 | — |

#### What is still not right, and is reported rather than hidden

The ISO 6946 U-value **cannot be pushed into the honeybee construction** without inventing a
conductivity, so `OpaqueConstruction.u_value` still reads the section-1, film-free number. Nor does
the division grid fix it: `Divisions.get_equivalent_conductivity` is an area-weighted average, which
is ISO 6946's *lower* limit. So a downstream consumer reading either still gets the optimistic
figure. designPH's own value travels on the report as `u_value_iso6946`, with the section areas and
the spread beside it — a v1 question, not a POC one.

Blast radius, measured rather than assumed: **4 of 82** `assemblies_calc` rows carry a non-zero
section percentage, and Wellington and Bluff Reach have **none**. 49 % of Linde's layers have a
`lambda2`, but a `lambda2` with no area is correctly ignored — counting those would have overstated
the problem fivefold.

### 10.4 Findings from fixing them

| # | Finding | Consequence |
|---|---|---|
| 59 | ⚠ **A projection hides the bug it is meant to survive.** Flattening a window onto its host plane works exactly as well from 3 m as from 3 mm, so shipping a parent-relative transform produced *no symptom at all* — 46 silent misplacements | `apertures.OFF_PLANE_LIMIT_M` refuses a rectangle more than 0.5 m off its host and reports the distance on every window that passes. Measured on the corrected data the offsets are **0.000 m**, so the number is a live early warning rather than a formality. Any lossy step needs a limit on how much it was allowed to absorb |
| 60 | ⚠ **`Polygon2D.is_point_inside_bound_rect` takes no tolerance**, and it sat as a fast path in front of the tolerant `point_relationship` — refusing any window flush with its host's edge. Adelphi has one, and it was the single aperture to fail the first rehearsal | The local-approximation rule again, in miniature: two tests of one property that disagree at the boundary. The library's tolerant predicate is the whole test, and `0` — on the edge — is a pass. **The cross-check that fires is doing its job**: it found a bug in our code, not in the data |
| 61 | ⚠ **`Face3D.is_sub_face` also takes no tolerance**, so `ValidateModel` calls that same flush window *not coplanar or fully bounded*. And it fails a second way: a host that models its opening as an **inner loop** subtracts it twice, because honeybee expects an aperture on the *gross* face. Only 2 of 16 Adelphi hosts model the hole at all | Unrepairable without fabricating an area, so the aperture is emitted and the report **predicts honeybee's verdict in advance**, saying which of the two cases it is. Note the shape: one threshold decides whether to emit, a different one predicts what a validator will say — legitimate, as long as both are stated |
| 62 | **One example is not a census.** "a 1.7 cm² sliver and a zero-width spur" became, once counted, **8** faces with a sub-mm edge and **7** whose boundary revisits a point — `face_3281_216` revisits 21 | ⚠ And the spur is invisible to the obvious test: **every edge of a spur is long**. Detection needs a non-adjacent coincident-vertex check, not just short edges. Decision recorded: **report and carry, repair nothing** — a classified face that vanished would break *82 of 82*, and 1.7 cm² moves no total |
| 64 | ⚠ **A DC option list is library data wearing a window's clothes.** 44,915 characters, byte-identical on all 46 windows, 2.07 MB of a 2.25 MB payload | Contract v2. And the general form: **before shipping a field per entity, ask whether its values are per entity.** The `distinct` count is a one-line check and it was 2 out of 46. The payload warning is what surfaced it, on the first capture it ever applied to |
| 65 | ⚠ **"The longer name wins" picks designPH's placeholder over its library.** *Launch designPH to edit* is 23 characters; *PH Glazing* is 10 | Merge by the richness of the *list*, not the length of the *name*. A plausible tiebreak that silently un-names a 500-entry library is exactly the class of error this project keeps finding: right-looking, wrong, and invisible downstream |
| 63 | **`Space.from_room` names the face it refuses**, in every one of its error messages | That is what makes "one face must never cost the room" implementable: drop the named candidate, retry, report it. Bounded by construction — one candidate per pass. A refusal that names nobody is reported wholesale rather than guessed at |
