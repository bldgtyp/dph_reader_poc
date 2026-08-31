# POC-3 — Python Translator (the translation core)

> ✅ **CLOSED — PASS, 2026-08-21.** [`RESULTS/POC-3_results.md`](RESULTS/POC-3_results.md). 545/545 faces, 239/239 windows, 99/99 thermal bridges across the corpus; **both U-value regressions PASS**. ⚠ Read §10.5 there: the tier-1 regression found two real defects, and the first attempt to confirm the fix was circular.

**Builds:** `pocs/01_sketchup-export/py/dph_translator/` — a pure-Python package that turns an
[extraction JSON](CONTRACT_extraction-json.md) into an HBJSON string plus a translation report.
**Depends on:** the contract frozen. Develops against synthetic fixtures immediately; picks up
POC-2's real fixtures when they land.
**Box:** ~2–3 agent sessions, no Ed runs (that is the point).
**Grounding:** `00_Context/HONEYBEE_STACK.md`, `00_Context/DATA_CONTRACTS.md` §4–6, PRD §8.

> Everything judgement-shaped lives here, on native CPython 3.11, under pytest, with no SketchUp in
> the loop. The same package then runs unmodified in Pyodide (POC-4). This is where the POC earns
> its "report, don't guess" promise — the report is a first-class output, not a log.

---

## 1. Package and environment

```
pocs/01_sketchup-export/py/
  dph_translator/
    __init__.py        # carries HBJSON_SCHEMA_VERSION = "1.53.1" (decision D-2)
    entry.py           # translate_json(str) -> str — the seam POC-1 §4.1 owns
    contract.py        # §2 — parse + type-normalise the extraction JSON
    facetypes.py       # §3 — area group → face type map
    build.py           # §3 — orchestration: records → Face3D → Face → Room → Model → HBJSON
    apertures.py       # §4
    constructions.py   # §5
    bridges.py         # §6
    spaces.py          # §7
    site.py            # §8
    report.py          # §9
  tests/               # pytest; fixtures/synthetic/ (checked in); real fixtures load from
                       # pocs/01_sketchup-export/_private/fixtures/ (gitignored — client data) and skip when absent
  .venv/               # uv venv --python 3.11 (gitignored)
  requirements.txt     # the 8 wheels ONLY, ==-pinned to HONEYBEE_STACK.md §1, installed --no-deps
```

Rules:

- **Python 3.11 exactly** — Pyodide 0.24.1's CPython. No 3.12+ syntax. Fully typed, dataclasses,
  stdlib + the 8 wheels only. (The IronPython-2.7 rules bind the *honeybee* repos, not this new
  package — it never loads in Rhino. Do not over-constrain it; do not touch the wheels' own code.)
- **The `.venv` installs exactly the 8 pinned wheels, `--no-deps`, and nothing else** — parity with
  the Pyodide payload is the point. In particular `honeybee-schema`/`pydantic` must **not** be
  present (they are declared-but-unreachable upstream; installed locally they would let tests pass
  on imports SketchUp cannot satisfy). Schema *validation* runs via the separate PEP 723 validator
  script, outside this venv.
- Import order ends with `import honeybee_ph` (the `_extend_` hooks); package versions via
  `importlib.metadata`, not `__version__` (none is defined).
- Entry points: the typed `translate(extraction_json: str) -> TranslationResult` (`hbjson: str`,
  `report: Report`, `verdict: str`), wrapped by **`dph_translator.entry.translate_json(str) -> str`**
  — the JSON-in/JSON-out seam POC-1 §4.1 owns. The dialog calls only `translate_json`.

## 2. `contract.py` — the one place types get checked

Parse the JSON into typed, frozen dataclasses. **All the type instability lands here** (hard rule 5):

- `area_group`: accept `int | str | None`; normalise via `int(str(v), 10)` with failure → the record
  is *reportable*, never an exception escaping the module.
- `contract_version != 1` → hard, reported error (verdict `FAILED`), not a guess.
- `both_generations` non-empty → report entry naming each doubled pair (`DESIGNPH_DATA_MODEL.md`
  §6.5's obligation).
- The `areaGroup → tempZone` integrity check (§5.3.1 table): a contradicting pair means the model is
  inconsistent — **report it, never silently resolve**. `TFA`/`X`/`i` are designPH's own fills, not
  PHPP zones; do not map them onto zones.
- Table rows are zipped against their `tokens` into per-table dataclasses; the two assembly-table
  schemas (`assemblies_calc` vs `assemblies_ud`) are distinct types, and `layer_table_*`'s variable
  column set (8 vs 12) is handled by name, never by position.

## 3. Faces → one non-solid Room

Per `DATA_CONTRACTS.md` §4.1's table — the area group is the entire basis for face typing:
1 → `floor`; 8, 9 → `wall`; 10 → `roof_ceiling`; 11 → `floor`; 2–6 → aperture (should not arrive as
faces — report if one does); 15–17 → must not arrive as faces (report); 7, 12–14, 18 → **pass
`None`** and let honeybee auto-assign by tilt, with a `translated-with-notes` report entry naming
the unmapped group. Pass **face-type objects** (`face_types.wall`), never strings.

**Boundary conditions — mapped explicitly, not defaulted.** PRD §6 requires faces *with boundary
conditions*; a model that is schema-valid with every face defaulting to `Outdoors` is semantically
wrong on exactly the surfaces PHPP treats differently. From the area group (temp zone as the free
integrity check, `DESIGNPH_DATA_MODEL.md` §5.3.1):

| Area group | Zone | honeybee boundary condition |
|---|---|---|
| 8, 10 (and 7 doors) | A | `Outdoors` |
| 9, 11 | B | `Ground` |
| 18 | I | `Adiabatic` — towards-neighbour assumes equal interior temperature, i.e. zero heat flow *(decision D-5; note in report per face)* |
| 12–14 | X | `Outdoors` + `translated-with-notes` (user-defined slot, zone unknowable) |
| 1 (TFA) | — | `Outdoors` is never right — TFA faces are floor-area markers; they carry no BC semantics. Keep honeybee's default and note it; their real job is §7 |

Synthetic fixtures must cover A/B/I/X and an unmapped group. Face type and BC are assigned together
in `facetypes.py` — one table, one place.

- `Face3D` from `outer_loop`; **holes** from `inner_loops` (`Face3D(boundary, holes=…)`) — Adelphi
  has exactly one holed host face; a synthetic fixture covers it either way. Orientation derives
  from the shipped winding (contract §2.2) — synthetic fixtures include a scaled and a mirrored
  group case.
- Identifier: the contract's **path-qualified `id`** (§2.1 — unique under component instancing,
  stable across sessions); display name: `desc_name` when present.
- Cross-check `Face3D.area` against the record's SketchUp-computed `area_m2` (tolerance 1%);
  disagreement → `translated-with-notes` (usually a transform bug — this check exists to catch it).
- One `Room` from all faces; `check_solid` result into the report (non-solid expected, PRD §8.1);
  one `Model(units="Meters")`.

## 4. Apertures

PRD §8.2's algorithm, implemented here from window records:

1. Host = `host_face_id` record (glued_to-resolved by the collector). `unresolved` → report by
   `designph_name` and skip; if real fixtures ever show unresolved hosts at frequency, a Python-side
   coplanar recovery from `transformation` + `panel_outer_loop` is the sanctioned extension point
   (Ruby ships the data for it; it does not attempt it). A `host_face_id` naming a face not in
   `faces` (unclassified host) → report, skip — the contract says this join may dangle.
2. Window rectangle from `panel_outer_loop` (per the settled W-1 decision); **project onto the host
   plane along the host normal** — discard the reveal offset.
3. Containment check: projected rectangle within host boundary (tolerance ~1 mm). Failure → report
   the window **by its `designph_name`** (the contract guarantees it is never null) and skip —
   never emit a floating aperture.
4. `Room`-attached: `Aperture` parented to the host `Face` (`face.add_aperture` /
   `Aperture(identifier, Face3D)` + `face.apertures` — follow honeybee's API, add a synthetic test
   asserting the parent relationship survives `to_dict`).
5. Reveal (`d_reveal`, `o_reveal` — inches-as-strings, converted here) → the aperture's PH
   **`ShadingDimensions`** reveal fields, with every horizon/overhang field left null — and note the
   interaction with the model-level shading marker (§9): the marker's wording must say reveal
   dimensions are present while shading *factors and context* are not, so the two claims cannot
   contradict. Not geometry. `frametypeid`/`glazingtypeid` → recorded on the report and stashed in
   the aperture's PH properties as identifiers (full frame/glazing library resolution is
   **stretch** — `frames_ud`/`glazing_ud` are not in the contract's shipped tables yet).
6. Host with inner loops (`host_has_inner_loops`) → handle both cases; the holed host must still
   accept its aperture or report why not.

Edge cases from the PRD, each with a synthetic fixture: straddling window, window larger than host,
host without `DesignPH_dict`, unresolved host, holed host.

## 5. Constructions — the four tiers, honestly

Resolution order per face `assembly_ref` (faces only — edge refs never come near this table):

| Tier | Source | Emit |
|---|---|---|
| 1 | `layer_table_<id>` present in `tables` | Layered `OpaqueConstruction`; designPH's three parallel `desc/lambda` paths → the 1×3 division grid on `EnergyMaterialPhProperties` (mixed-material layers) |
| 2 | `assemblies_ud` header row (carries `U_value`) | Single `EnergyMaterialNoMass` from U-value (+ `thk` where present). No fake layers |
| 2a | `assemblies_calc` header row **only** | ⚠ **No construction** — the `assemblies_calc` schema has *no U-value column* (tokens: `id, desc, R_in, R_out, …`). A calc header without its layer table cannot make even a no-mass material. Report; face falls to honeybee defaults, and the report says so |
| 3 | installed designPH CSV library | **Stretch** — not in the base POC. Report as `unresolved-in-model` with the id, so tier-3 frequency is measured on real exports |
| — | nothing | Report; face gets **no construction assigned** (falls to honeybee defaults) — and the report says so. **Never substitute a plausible default silently** |

- `R_in`/`R_out` film resistances and `additional_U_value` → PH properties, **not** folded into
  materials (a reviewer must still see the numbers).
- `int_insul` → carried onto PH properties.
- **Tier recorded per face in the report** — a U-value with no build-up is legitimate and common;
  presenting it as a full assembly is the failure.

**U-value regression — two checks, each pointed at a model that actually exercises it.**
⚠ *Adelphi has zero tier-1 assemblies* — no `layer_table_*` at all; its 42 refs resolve via the
tier-2 `assemblies_ud` snapshot (`83ud+` range). A "tier-1 on Adelphi" regression would pass
vacuously:

1. **Tier-2 pass-through (Adelphi):** `assemblies_ud.U_value` per referenced assembly vs
   `planning/01_sketchup-export/feasibility/RESULTS/phpp/phpp_u-values_assemblies.csv`, **joined by assembly name/description,
   not id** — the CSV's ids (`01ud…`) come from the PHPP/2.4.0-BETA side and are a *different id
   space* from the `.skp`'s `83ud+` refs ("not two views of one tool"). Name the CSV's key and
   value columns in the test.
2. **Tier-1 layered computation (`250703 - Linde Residence` fixture, 25 layer tables):** computed
   U from layers + films in the translator's own check function (films **included** in the check
   arithmetic, even though the emitted construction excludes them) vs designPH's own values, plus
   at least one hand-checked synthetic case.

Tolerance: **±0.005 W/m²K** (rounding in the source); a miss is a translator bug until proven a
corpus-alignment artifact — and the corpus-alignment caveat may only be invoked *after* the
arithmetic is hand-checked once.

## 6. Thermal bridges

Edge records (groups 15/16/17) join `connection_ref` against **`connections_ud` only**. The exact
API (verified against the vendored wheel, 2026-08-19 — do not rediscover it):

- Class: `honeybee_energy_ph.construction.thermal_bridge.PhThermalBridge(_identifier, _geometry)` —
  note the package: `honeybee_energy_ph`, not `honeybee_ph`.
- `_geometry` is a `LineSegment3D` (build from the contract's `start`/`end`); **`length` is a
  read-only property derived from geometry** — `length_m` is a cross-check, never an input.
- Settable: `psi_value`, `fRsi_value`, `quantity`, and `group_type`, whose allowed values are
  exactly `"15-Ambient" | "16-Perimeter" | "17-FS/BC"` — map the area group onto those strings.
- Attach point: **`hb_room.properties.ph.ph_bldg_segment.add_new_thermal_bridge(tb)`** (the
  building segment's `thermal_bridges` dict, keyed by identifier) — not the Room's PH properties
  directly.
- Unresolvable `connection_ref` → report by id. An edge whose group is not 15/16/17 → report as an
  anomaly (contract §3 ships them for exactly this).
- Synthetic fixture + the Bluff Reach real fixture (99 edges) are the tests. **The count assertion
  is the point:** 99 in, 99 out-or-reported, zero silently gone.

## 7. Spaces / TFA — report-first, the POC's honest answer

`Space.from_room` has two known failure modes and both fire on real data (`HONEYBEE_STACK.md` §4).
POC strategy — **filter, attempt, report; do not project, do not repair**:

1. Candidate faces: **group 1 only** (the TFA marker; group 11 is envelope floor — decision D-4).
   ⚠ `tfa_rf` **absent means weighting factor 1.0, not exclusion** — on Adelphi only 7 of ~40
   group-1 faces carry `TFA_rf`; filtering on its presence would silently collapse the headline
   number.
2. Horizontality test (`Face3D.normal` within tolerance of ±Z) **before** calling honeybee;
   non-horizontal TFA faces → report entry `tfa-not-derived` naming each face — the silent-loss
   guard.
3. Build a **temporary throwaway `Room`** from the horizontality-passing group-1 faces and call
   `Space.from_room` on *it* — never on the real Room, whose group-11 slab Floor faces would
   contaminate the extrusion or raise. Wrap it: both `ValueError`s → report, not raise.
   `avg_ceiling_height` from `vent_ud.room_height` (SI already; **first non-metadata row — if
   `vent_ud` has several rows, report and use the first**); `vent_ud` absent → report + skip spaces.
4. Success → attach to the **real** Room: `hb_room.properties.ph.add_new_space(space)`;
   `tfa_rf` (default 1.0) → segment weighting factors.
5. The report always states TFA coverage: *n of m TFA faces contributed; TFA not derived for k
   faces (named)*. **TFA is a headline number — its absence must be loud.**

v1 will need a real strategy (project? decompose?); the POC's contribution is measuring how much
TFA area the honest strategy loses on real models. That number goes in the results.

## 8. Site / climate

`klima_id` + `klima_standort` → model-level PH site identification (string identifiers only — no
climate-dataset resolution in the POC). Absent → report note.

## 9. The report — a first-class output

`report.py` defines the schema (JSON, written beside the HBJSON):

```jsonc
{
  "verdict": "PASSED",                       // PASSED | PASSED WITH OMISSIONS | FAILED
  "summary": { "faces": {"translated": 82, "reported": 0}, "windows": {…}, "edges": {…},
               "spaces": {…}, "tfa_m2_covered": 0.0, "tfa_m2_lost": 0.0 },
  "unclassified": { …contract §6 passthrough — the tagged_faces records land here verbatim,
                    so every DesignPH-tagged omitted face is NAMED, not just counted… },
  "shading": "not-computed",                 // the explicit marker, PRD §7.2 — precise wording:
  "shading_note": "No shading factors or context geometry. Aperture reveal dimensions ARE present
                   (ShadingDimensions, reveal fields only).",   // §4.5 — so the marker and the
                                                                // reveal data cannot contradict
  "entries": [
    { "id": "window_a1b2..._e5f6...", "kind": "window", "designph_name": "…",
      "outcome": "reported-not-translated",
      "reason": "containment check failed on host face_a1b2..._c3d4...",
      "tier": null }
  ]                                          // keyed by the contract's path-qualified `id` — the
                                             // session-scoped entity_id is a debugging aid only,
                                             // and cross-session report diffs depend on `id`
}
```

- Every non-`translated` outcome carries a human-readable reason.
- The `shading: not-computed` marker also goes **into the HBJSON itself** via `model.user_data`
  (`{"dph_plus": {"shading": "not-computed", "report_file": "<name>.report.json"}}`) so the model
  cannot travel without the disclosure. *(Open decision D-3 — confirm `user_data` survives
  `to_dict` and downstream loads; it does in honeybee core, test it.)*
- Verdict rules: `FAILED` = contract error or an exception; `PASSED WITH OMISSIONS` = anything
  reported-not-translated; `PASSED` = everything translated (rare on real models, and that is fine).

## 10. Open decisions, made explicit for review

| # | Decision | POC position |
|---|---|---|
| D-1 | Emit honeybee-energy's `global_construction_set`? (Finding 40 — it does not validate upstream) | Keep whatever `Model.to_dict` emits, exactly as Phase 3 did; validation stays core-scoped. Revisit for v1 with ph-navigator evidence from POC-5 |
| D-2 | Schema `version` stamp came out `null` in Phase 3 | Stamp the **constant `"1.53.1"`** (the schema version we validate against) from `dph_translator/__init__.py`, with a test asserting it equals the pin in `planning/spikes/phase0/validate_hbjson_core.py`. ⚠ Not `importlib.metadata` — `honeybee-schema` is deliberately **not installed** in either the venv or the Pyodide payload |
| D-3 | Where the shading marker + report pointer live | `model.user_data` (§9) — verify round-trip |
| D-4 | Group 11 (floor slab): TFA candidate or envelope-only? | Envelope floor with `Ground` BC; TFA from group 1 only, **absent `tfa_rf` = factor 1.0** — unless the Adelphi fixture shows designPH using 11 for TFA, then update and record |
| D-5 | Group 18 (towards neighbour) boundary condition | `Adiabatic` (equal-temperature assumption ⇒ zero heat flow, matching PHPP's treatment); per-face report note. Revisit if PHPP ground truth disagrees |

## 11. Testing and verification

- **pytest on CPython 3.11**, synthetic fixtures per case (contract §7's list, one per §3–§8
  behaviour + each type-instability case + scaled/mirrored groups). Synthetic fixtures are
  scaffolding, not evidence.
- **Real-fixture golden tests** once POC-2 lands: Adelphi (82/82 translated, matching Phase 3's
  observed 41 Floor / 38 Wall / 3 RoofCeiling), Bluff Reach (99 edges accounted), `250708.skp`
  (92 assemblies via `*Auto` — the coalesce regression), Wellington, `250703` (tier-1 layers).
- **Schema validation** via the existing `planning/spikes/phase0/validate_hbjson_core.py` scope:
  **zero errors touching geometry or PH**. (pydantic-1 error counts collapse by failing object —
  never quote raw counts.)
  ⚠ **Run it as an early milestone on the *first* real-fixture output that carries PH payloads** —
  Phase 3's zero came from a model with *no* spaces, bridges, or aperture PH props, so the "PH
  segment validates" claim has never been tested against what this phase adds. If PH-path errors
  appear that trace to upstream schema drift (the `global_construction_set` pattern): record them,
  scope the gate to geometry-segment errors plus a **named allowlist**, and put the
  honeybee-ph-schema question on the v1 list — do not fail the POC on upstream drift, and do not
  discover this in POC-5.
- **U-value regression** per §5 (tier-2 on Adelphi, tier-1 on `250703`).
- **Report completeness invariant**, asserted structurally — defined precisely: *every element of
  `faces`, `edges`, and `windows` appears either as an object in the HBJSON (matched by identifier)
  or as a row in `entries` (matched by `id`), and the two sets are disjoint.* `tables` and
  `unclassified` are covered by the report's `summary`/`unclassified` blocks, not by `entries`.
  This is hard rule 4 as a unit test.
- `Model.from_dict` only as a final correctness assertion, never in the product path (it is 100×
  the write cost).

## 12. Gate — split, because the real fixtures arrive on POC-2's clock

**POC-3a (independent — closes without POC-2):** synthetic-fixture suite green; contract handling,
type normalisation, report invariant, boundary conditions, schema validation on a synthetic model's
output.
**POC-3b (after POC-2's fixtures):** real-fixture goldens, both U-value regressions, the early
PH-payload validation milestone, and the two measured tables.

**PASS:** 3a and 3b green on CPython 3.11.
**PASS WITH CHANGES:** green after contract bump or documented scope trim.
**FAIL:** the completeness invariant cannot be made to hold, or U-values cannot be reconciled.

Record in `RESULTS/POC-3_results.md`, including the TFA-coverage numbers (§7) and tier distribution
(§5) measured on the real fixtures — those two tables are the POC's first real product.
