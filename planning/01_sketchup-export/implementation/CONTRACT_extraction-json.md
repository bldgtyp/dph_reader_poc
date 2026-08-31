# Contract — the extraction JSON (Ruby → Python seam)

**Version: 2 — ✅ FROZEN 2026-08-21.** v1 froze earlier the same day with §8.1–8.3's corrections
applied; **v2 followed within the hour**, off the first live capture on the fixed collector, and
moved the frame/glazing option lists out of every window and into a model-level `libraries` block
(§5.1). E-1 remains open and does not block: it asks whether tagged edges appear inside
groups/components, which is about what the collector will *find*, not about the document's shape —
the walk already visits edges at every nesting level. Any further change goes through §9.

> **Why v2 exists, in one line.** The v1 capture was **2,249,369 bytes** against a bridge verified to
> 4 MB, and **2.07 MB of it was the same 44,915-character library repeated byte-identically on all 46
> windows.** Deduplicated to model level it is 45 KB. The bump cost nothing because it landed between
> the fix and the corpus capture — §9's "an Ed cost, which is the incentive to settle before
> freezing" was, for exactly one hour, not true.

Extends the face-record schema proven in Phase 3 (`00_Context/DATA_CONTRACTS.md` §2.4) to the full
POC scope. This is the **only** seam between the Ruby collector (POC-2) and the Python translator
(POC-3); both sides program against this document, and fixtures of this shape are what POC-3's tests
consume.

**Design rules, inherited and binding:**

- **Ruby stays dumb.** The collector coalesces key generations, accumulates transforms, converts
  lengths to metres, and decodes Marshal tables to plain arrays. It does **no** type normalisation,
  no geometry math beyond transforms, and no classification logic — with **one sanctioned
  exception**: the classified-face filter (§2), which is the evidenced Phase 3 rule
  (`DATA_CONTRACTS.md` §2.5) and decides only *whether a face record ships*, never how it is read.
  Python owns every other judgement call — one place to get it wrong, not two.
- **Raw values pass through raw.** `area_group` may be `"8"`, `8`, `"n"`, or `null`. The contract
  promises presence, not type. Python type-checks every field (hard rule 5).
- **One JSON string per bridge hop.** Verified to 4 MB; Adelphi's face payload is 19.4 KB. If a
  payload ever approaches 1 MB, log it — do not silently chunk. ⚠ That rule earned its keep on the
  first capture it applied to: v1's Adelphi payload came in at **2,249,369 bytes**, and the warning
  is what surfaced §5.1's 2.07 MB of duplicated library.
- **Versioned.** `contract_version` is checked by the translator; mismatch is a hard, reported error.

---

## 1. Envelope

```jsonc
{
  "contract_version": 2,
  "generated_by": "dph_plus_poc collector <git-sha or dev>",
  "model": {
    "file_name": "adelphi-designph_COPY",
    "designph_versions": ["2.1.15"],        // ALL version stamps found — Wellington has two
    "klima_id": "US0058a",                  // raw, or null
    "klima_standort": null,                 // raw, or null (Adelphi has none)
    "units_note": "geometry in metres; raw designPH table and DC values untouched (mixed units, see §4/§5)"
  },
  "counts": {                               // the collector's own census — the baseline cross-check
    "faces_walked": 8037,                   // every live face visited (§6.1 census rules)
    "faces_tagged": 1441,                   // carrying DesignPH_dict at all
    "faces_classified": 82,                 // area_group coalesces to a positive integer
    "edges_tagged": 0,                      // edges carrying DesignPH_dict
    "windows_found": 46,
    "tables_found": ["assemblies_ud", "vent_ud", "ihg_ud", "tracker_data"]
  },                                        // (Adelphi-shaped example: it carries NO layer_table_* —
                                            //  only Wellington/Linde-class models do)
  "faces":   [ …§2… ],                      // classified faces only
  "edges":   [ …§3… ],                      // tagged edges (thermal bridges)
  "windows": [ …§4… ],
  "libraries": { …§5.1… },                  // designPH's frame + glazing libraries, model-level
  "tables":  { …§5… },
  "unclassified": { …§6… }
}
```

## 2. Face records — classified faces only

A face is **classified** iff its coalesced area group parses as a positive integer
(`Integer(s.to_s, 10) > 0 rescue false` — the Phase 3 rule). Unclassified faces go to §6, never
shipped as geometry.

```jsonc
{
  "id": "face_a1b2..._c3d4...",       // ★ PATH-QUALIFIED persistent identifier — see §2.1
  "entity_id": 9153,                  // entity.entityID — session-scoped, debugging aid ONLY
  "area_group": "8",                  // coalesced areaGroupID‖areaGroupAuto — RAW (String|Integer)
  "temp_zone": "A",                   // coalesced tempZoneID‖tempZoneAuto — RAW; Python runs the
                                      // areaGroup→tempZone integrity check (DESIGNPH_DATA_MODEL §5.3.1)
  "assembly_ref": "01ud",             // coalesced assemblyID‖assemblyIDAuto — RAW, or null.
                                      // NOT resolved here; namespace depends on area group
  "desc_name": "104C HALL",           // descName ‖ descNameAuto — the user's name wins; or null
  "tfa_rf": 0.5,                      // raw, or null (only meaningful on group-1 faces; Python
                                      // treats absence as weighting factor 1.0, NOT exclusion)
  "outer_loop": [[x, y, z], "…"],     // metres, world coords, accumulated transform applied,
                                      // SketchUp loop order preserved (defines orientation — §2.2)
  "inner_loops": [[[x, y, z], "…"]],  // [] when none — holes are carried, not just flagged
  "area_m2": 12.34,                   // face.area(accumulated_transform) × 0.00064516 — cross-check
  "both_generations": []              // names of pairs where *ID AND *Auto are both non-nil, e.g.
                                      // ["assembly"] — corpus says always []; non-empty → Python
                                      // must REPORT it (§6.5 obligation)
}
```

### 2.1 Identity — path-qualified, persistent

`entityID` is session-scoped, and **both** `entityID` and `persistent_id` identify the *entity
inside its definition*, not the placement — a component placed twice yields the same face entity
under two transforms. Therefore:

```
id = "face_" + <persistent_id of each ComponentInstance/Group on the path, joined by "_"> 
             + "_" + <persistent_id of the face>
```

Top-level entities have an empty path. This makes ids **unique under component instancing** (each
placement is a distinct envelope surface — ship one record per placement, each with its own world
geometry) and **stable across sessions** for an unedited model — which is what makes POC-4's
cross-session reproducibility claim and POC-5's re-run diffs possible. Same scheme for edges
(`edge_…`) and windows (`window_…`).

### 2.2 Orientation

**No `normal` field is shipped.** Transforming a normal by the accumulated matrix is wrong under
non-uniform scale or mirroring (normals need the inverse-transpose); rather than carry that trap,
the contract ships the transformed loop in SketchUp's winding order and Python derives orientation
from `Face3D.normal`. A mirrored transform flips the winding together with the geometry, so the
derived normal stays consistent. POC-3 must include a scaled-group and a mirrored-group synthetic
fixture; POC-2's collector preserves loop order verbatim.

## 3. Edge records — thermal bridges (area groups 15/16/17)

```jsonc
{
  "id": "edge_…",                     // §2.1 scheme
  "entity_id": 4412,
  "area_group": "15",                 // raw coalesced
  "connection_ref": "101ud",          // raw coalesced assemblyID‖assemblyIDAuto — resolves against
                                      // connections_ud (NOT the assembly table). Named differently
                                      // here so no one ever joins it to assemblies by accident
  "desc_name": null,
  "length_m": 4.27,                   // derived from the TRANSFORMED endpoints (do not assume
                                      // Edge#length takes a transform argument)
  "start": [x, y, z],                 // metres, world
  "end": [x, y, z]
}
```

Any tagged edge whose area group is *not* 15/16/17 is still emitted, with the anomaly left to Python
to report. Downstream note: `PhThermalBridge.length` is derived from geometry — `start`/`end` are
the authoritative values; `length_m` is a cross-check.

## 4. Window records

Windows are Dynamic Component instances; their data lives in SketchUp's `dynamic_attributes`, not
`DesignPH_dict` (`DESIGNPH_DATA_MODEL.md` §9).

```jsonc
{
  "id": "window_…",                       // §2.1 scheme
  "entity_id": 7201,
  "designph_name": "Window_012_S",        // ★ the reporting name, resolved by the collector:
                                          // instance name ‖ designPH-generated name if present ‖
                                          // definition name + "#" + id suffix. NEVER null — every
                                          // report line must be able to name its window
  "definition_name": "designPH_Window_Simple_1-1",
  "instance_name": null,                  // raw, may be blank/renamed
  "dynamic_attributes": {                 // RAW passthrough of the designPH-relevant subset —
    "frametypeid": "01ud",                // an ALLOW-LIST (§4.1), never the whole DC dictionary.
    "glazingtypeid": "01ud",              // ⚠ units are PER-FIELD, not uniform: lenx/leny/d_reveal/
    "lenx": "225.18749999999997",         //   o_reveal/framedepth/revealdepth are inches-as-Strings;
    "leny": "390.1875",                   //   framewidth* are inches-as-Floats; instcill/insthead/
    "d_reveal": "12.5",                   //   instleft/instright are "0"/"1" flags.
    "o_reveal": "11",                     // ⚠ "area" is a STALE DC output — DO NOT COMPUTE FROM IT.
    "framewidth": 4.330708661417323,      //   It equals lenx×leny×0.00064516 on only 20 of 46 real
    "area": 56.687207693906245,           //   windows (§8.1); it ships so a report can say what the
    "_frametype_options": "&PH-FRAMES…"   //   model claims. Full key table: DATA_MODEL §9.2.1
  },
  "transformation": [16 floats],          // the ACCUMULATED WORLD transform:
                                          //   parent_transform * instance.transformation, .to_a,
                                          // column-major, translation at 12–14, INCHES.
                                          // ⚠ NOT `instance.transformation` on its own — that is
                                          // PARENT-relative while every other geometry field here
                                          // is world, and mixing them put Adelphi's 46 windows
                                          // 1.2–3.3 m off their hosts (§8.2)
  "panel_outer_loop": [[x, y, z], "…"],   // the ROUGH OPENING in world metres: definition-local
                                          // (0,0,0)-(lenx,0,0)-(lenx,leny,0)-(0,leny,0) through the
                                          // world transform. ⚠ NOT a face from the definition —
                                          // there are none at its top level, and the largest at any
                                          // depth is the GLAZING, 41 % small (§8.1).
                                          // null means a genuine read failure: no usable lenx/leny
  "host_face_id": "face_…",               // glued_to → the §2.1 id, or null. Same path as the
                                          // window's own: a glued instance glues within its context
  "host_resolution": "glued_to",          // "glued_to" | "unresolved"  (no Ruby-side geometric
                                          // fallback — recovery, if ever needed, is Python's, in
                                          // POC-3, from transformation + panel_outer_loop)
  "host_has_inner_loops": false           // face.loops.size > 1 on the host — never cuts_opening?,
                                          // and NOT a host test either: a glued opening makes no
                                          // loop, so this is true on only 2 of 16 real hosts. It
                                          // reports whether the hole was MODELLED, which is why
                                          // face.area is net while the loop polygon is gross
}
```

⚠ **Referential integrity is deliberately loose:** `host_face_id` may name a face that is not in
`faces` (an unclassified host — a real PRD §8.2 edge case). That is legal contract data; the
translator reports such windows rather than crashing on the missing join.

### 4.1 The `dynamic_attributes` allow-list

The DC dictionary also holds `_<name>_formulaunits`, `_<name>_label` and a dozen other editor
artefacts, so the collector ships a **named list** rather than the dictionary:

```
frametypeid glazingtypeid frametype glazingtype
lenx leny area
framewidth framewidthl framewidthr framewidthtop framewidthbot
framedepth revealdepth d_reveal o_reveal
instcill insthead instleft instright
```

⚠ **No underscore key ships on a window.** `_frametype_options` / `_glazingtype_options` are wanted
— they are the only way to name a `frametypeid` with no CSV library on disk — but they are *library*
data and go to §5.1. v1 shipped them here and paid **2.07 MB** for it.

Per-window values live on the **instance**; the definition holds the shared template and fills in
where the instance is silent. `lenx`/`leny` are the only values Ruby coerces to a number, and only
because the rectangle cannot be built without one — the raw String still ships here, so Python's
type check runs on the authoritative copy.

## 5. Tables — decoded Marshal blobs, raw rows

Model-level `DesignPH_dict` keys holding Marshal blobs (recognised by the `BAh` base64 prefix) are
decoded **in Ruby** (`Marshal.load(Base64.decode64(v))` — the user's own model; acceptable for the
POC, noted in POC-2 §7) and shipped as tokens + rows. The self-describing `:TOKENS` row travels with
the data; **its position varies** (`vent_ud`/`ihg_ud` put it at the *end* — `DESIGNPH_DATA_MODEL.md`
§7), so the collector normalises to `{tokens, rows}`.

**Shipped:** `assemblies_calc`, `assemblies_ud`, `connections_ud`, `vent_ud`, `ihg_ud`, and
**every `layer_table_*` key present** (a family, not one key — Linde `250703` carries 25).
**A table absent from the model is omitted from `tables` entirely** — never `null`, never `{}`.
The translator treats absence as tier-unresolvable and reports. (Adelphi, the primary fixture, has
no `assemblies_calc`, no `connections_ud`, and no `layer_table_*` — absence is the *normal* case.)

```jsonc
"tables": {
  "assemblies_ud":   { "tokens": ["id", "desc", "assem_num", "thk", "U_value", "int_insul"],
                       "rows": [["83ud", "…", 1, 0.35, 0.15, false], "…"] },
  "connections_ud":  { "tokens": ["id", "desc", "areaGroupID", "areaGroupName", "Psi_value", "F_rsi"], "rows": ["…"] },
  "layer_table_01ud": { "tokens": ["id", "desc1", "lambda1", "desc2", "lambda2", "desc3", "lambda3",
                                   "thickness"], "rows": ["…"] },   // 12-column variant exists
                                                                    // (adds R1,R2,R3,R_tot) — read by NAME
  "assemblies_calc": { "tokens": ["id", "desc", "R_in", "R_out", "surf2_percentage",
                                  "surf3_percentage", "additional_U_value", "int_insul"], "rows": ["…"] },
                                          // ⚠ NO U-value column — a calc header alone cannot make
                                          //   even a no-mass construction (POC-3 §5)
  "vent_ud":         { "tokens": ["vent_sys_ID", "vent_type_ID", "room_height", "V_n50",
                                  "result_n50", "coeff_e", "coeff_f"], "rows": ["…"] },
                                          // room_height in metres (SI, designPH's own tables);
                                          // multiple rows possible → POC-3 §7 rule
  "ihg_ud":          { "tokens": ["num_units", "build_type"], "rows": ["…"] }
}
```

- Metadata rows (`["#", …]`) are stripped after `tokens` is captured; symbols become strings; values
  are otherwise untouched — **designPH table values are SI/PHPP units** (lambda, Psi, mm) and stay
  that way. Only *SketchUp geometry* is converted to metres.
- Marshal blobs the POC does not consume (`tracker_data`, `tfa_calc`, `tfa_calc_ud`, `frames_ud`,
  `glazing_ud`) are **listed in `counts.tables_found` but not shipped**. Non-blob model keys
  (`Dashboard`, `designPH_version`, `klima_ID`, …) are not tables at all; the relevant ones ship in
  `model`.
- A blob that fails to decode ships as `{"error": "<message>"}` under its key — reported, not dropped.

### 5.1 `libraries` — designPH's frame and glazing lists, carried inline

```jsonc
"libraries": {
  "frame_types":   ["&PH-FRAMES: average thermal quality=01ud&…&Alumil S.A. - SD95=1806ed04&"],
  "glazing_types": ["&PH Glazing=01ud&Single glazing=92ud&…", "&Launch designPH to edit=01ud&"]
}
```

SketchUp Dynamic-Component **option lists**, raw: `&<name>=<id>&<name>=<id>&`. designPH writes them
onto window instances *and* definitions, and `DESIGNPH_FILE_FORMATS.md` §3 otherwise has these
libraries living only in designPH's installed CSVs — so this is a large part of one travelling inside
the `.skp`. No U-values, no g-values; it **names the ids**, which is the difference between a report
line reading `01ud` and one reading `PH Glazing (01ud)`.

- **Distinct values, first-seen order.** Ruby deduplicates and does **not** choose between them —
  deduplicating is not a judgement call, picking a winner is (`Library.from_raw` does that).
- Both keys are **always present**, `[]` when the model has no windows. Unlike §5's tables, absence
  is not meaningful here.
- ⚠ **The tiebreak is list size, not name length.** designPH writes a placeholder
  (`&Launch designPH to edit=01ud&`) on some definitions, and it claims `01ud` too. *Launch designPH
  to edit* is a **longer** string than *PH Glazing*, so the obvious "longest name wins" rule picks
  the placeholder and silently un-names the whole library. A placeholder names one id; a real library
  names hundreds.

#### Why this is model-level — the v1 measurement

| | |
|---|---|
| `_frametype_options` on Adelphi | **39,685 chars**, ~500 entries down to real manufacturer products |
| `_glazingtype_options` | 5,230 chars |
| distinct values across all 46 windows | **2** (the library, and designPH's placeholder) |
| cost of shipping them per window | 44,915 × 46 = **2.07 MB** of a 2,249,369-byte payload |
| cost at model level | **45 KB** |

The bridge is verified to 4 MB and the contract says to log anything approaching 1 MB. It logged —
`WARNING: extraction payload is 2249369 bytes (>1 MB)` — which is the warning doing its job on the
very first capture it applied to.


## 6. Unclassified — per-entity for tagged, aggregate for untagged

The 82/1441/8037 gap is the design problem; the POC reports it rather than solving it — and the
report must be able to **name** every designPH-tagged entity it omits (hard rule 4), so
tagged-unclassified faces ship as compact records, not just counts:

```jsonc
"unclassified": {
  "tagged_faces": [                       // one compact record per DesignPH_dict-carrying,
    { "id": "face_…",                     // unclassified face. ~100 B each; Adelphi's 1359 ≈ 140 KB
      "area_group": "n",                  // — well inside the bridge budget. RAW value as found
      "tag": "Layer0" }                   // the face's SketchUp tag name
  ],
  "untagged_by_tag": {                    // no DesignPH_dict at all → aggregate only
    "04_SHADING_TREES": 392, "Layer0": 5100
  }                                       // classified faces excluded — the v1 shading-UI evidence
}
```

### 6.1 Census rules

- `faces_walked` counts every live face the walk visits, **excluding the internals of recognised
  designPH window components** (the walk emits the window record and does not descend — §4; window
  internals are neither walked nor counted, and the reconciliation harness must expect that).
- `unclassified.tagged_faces` + `faces` + (faces inside emitted windows: none) account for every
  `DesignPH_dict`-carrying face — `len(tagged_faces) + len(faces) == counts.faces_tagged`, an
  invariant the translator asserts.

## 7. Fixtures

- **Synthetic fixtures** (`pocs/01_sketchup-export/py/tests/fixtures/synthetic/`) are hand-written JSONs of this shape,
  one per translator case (each face type + boundary condition, each assembly tier, a thermal
  bridge, a window with/without holes, scaled and mirrored group geometry, the type-instability
  cases: `area_group` as `"8"`/`8`/`"n"`/`null`). They are unit-test scaffolding **only** — the
  house lesson stands: *a synthetic model is not evidence about real models*. No conclusion about
  designPH may rest on them.
- **Real fixtures** (`pocs/01_sketchup-export/_private/fixtures/`, POC-2 deliverable) are collector output captured from
  corpus-model copies inside SketchUp: **Adelphi, Bluff Reach, `250708.skp`, Wellington, and
  `250703 - Linde Residence.skp`** (the only model known to carry `layer_table_*` — the tier-1
  evidence). They contain client data — `pocs/01_sketchup-export/_private/` is gitignored, manifest-tracked.

  ⚠ **The Adelphi capture on disk predates the §8.1/§8.2 corrections** and carries the parent-relative
  transform and a `null` panel loop on all 46 windows. It stays as the *evidence* those defects
  existed; it is **not** a fixture for the fixed collector, and the next Ed session re-captures it.
  A rehearsal of what the fixed collector should produce —
  `planning/spikes/poc/patch_and_translate.py`, which reconstructs the two fields from the recovered
  parent transform — is a **rehearsal, not a capture**, marked as such in its `generated_by`, and may
  not be used as a fixture or quoted as evidence about a live model.

## 8. What §4 used to say, and why it changed

*Kept after the freeze because the two refuted candidates both look right, and the record of
*why* they are wrong is the only thing standing between a future reader and re-adopting them.*

| # | Question | Answer |
|---|---|---|
| **W-1** | Window rectangle derivation, and the `dynamic_attributes` unit table | ✅ **Both original candidates were wrong.** See §8.1 |
| **T-1** | Do Marshal blobs come back as base64 Strings live? | ✅ **Yes.** `assemblies_ud`, `vent_ud`, `ihg_ud` and `tracker_data` all read as `String` starting `BAh` and decoded cleanly on the live model. The offline evidence held |
| **E-1** | Do tagged edges appear inside groups/components? | ✅ **YES, and only nested.** All **99** of `2414_Bluff Reach`'s tagged edges sit **two levels deep** in groups — **zero at the top level** — in area groups 15/16/17, every `connection_ref` resolvable. A walk that visited only the top level would have found none of them and reported success. Answered 2026-08-21 by POC-2's capture |

### 8.1 W-1, settled — and it changes §4

Evidence: `DphWin.inspect_one("403U")` plus the full 46-window capture
(`pocs/01_sketchup-export/_private/fixtures/adelphi-designph_COPY.extraction.json`). Detail in
`00_Context/DESIGNPH_DATA_MODEL.md` §9.1–9.3.

**Candidate 1 — "the definition's largest face" — is refused, twice over:**

1. `definition.entities.grep(Sketchup::Face)` returns `[]` on **all 46** windows. The geometry is two
   and three levels down inside sub-groups; the walk must recurse.
2. Even recursing, the largest face is the **GLAZING** — 0.5226 m² =
   `(lenx − 2·framewidth)(leny − 2·framewidth)`, exact to four decimals — not the rough opening
   (0.891 m²). It would make every window **41 % too small**, plausibly, with nothing downstream to
   catch it.

**Candidate 2 — `transform × lenx/leny` — is the survivor, with a correction:** the rectangle is the
local `(0,0,0)→(lenx,0,0)→(lenx,leny,0)→(0,leny,0)` in the definition's **XY plane** (the glazing
face's normal is `[0,0,−1]` in definition space), taken through the **world** transform.

✅ **The corner convention is measured, not inferred** *(2026-08-21,
`planning/spikes/poc/solve_window_parent.py`)*. That the origin lies *on* the host plane does not say
it is a **corner** of the opening rather than its centre, and the two differ by half a window. The
parent transform is recoverable from the first capture alone — every window's local +Z must map onto
its host's world normal (Kabsch) and every local origin must land on that host's plane (least
squares) — and the recovered parent reproduces `DESIGNPH_DATA_MODEL.md` §9.3's independently measured
`[-3.2414, 8.1321, -2.9972]` and 403U's world origin to four decimals. Against the real host
polygons:

| convention | windows landing inside their host |
|---|---|
| **corner at the origin, `+x`/`+y`** | **46 / 46** |
| centred on the origin | 23 / 46 |
| corner at the origin, `+x`/`−y` | 15 / 46 |
| corner at the origin, `−x`/`−y` | 12 / 46 |

Measured on the same solve: every window origin sits **0.000 m** from its host plane, which is what
makes `apertures.OFF_PLANE_LIMIT_M` a usable early warning rather than a formality.

**⚠ And the unit table in §4 was wrong.** `lenx × leny × 0.00064516 == area` holds on only **20 of
46** windows, ratios 0.44–1.66; instance scaling is ruled out (all 46 unscaled). `area` is a stale
DC formula output. **`area` is now unusable and must not be read.** `lenx`/`leny` (inches-as-String)
and `framewidth*` (inches-as-Float) are confirmed across all 46.

### 8.2 ⚠ A contract defect found by the same run — §4's `transformation`

§4 used to specify `instance.transformation.to_a` **VERBATIM**. That is the instance's transform
**relative to its parent**, while every other geometry field in this contract is **world** space.
Mixing the two put Adelphi's windows **1.2–3.3 m** off their own host planes.

**Applied:** §4 now ships the **accumulated world transform**
(`parent_transform * instance.transformation`), still `to_a`, still column-major, still inches. Same
field, same shape, correct space.

⚠ The trap is that the two are **the same object type** and differ only in where they were read, so
nothing type-checks and nothing raises. `apertures.OFF_PLANE_LIMIT_M` exists as the tripwire: a
rectangle that far off its host's plane is a coordinate-space error rather than a deep reveal, and
projection would otherwise absorb it in perfect silence.

### 8.3 Other §4 corrections from the same capture — applied

- `panel_outer_loop` is **no longer optional-because-hard**: it is the rough opening, and it is
  always derivable from `lenx`/`leny` + the world transform. `null` now means a genuine read failure.
- The DC key set is larger than §4 showed. The full allow-list is now §4.1, including
  `_frametype_options` / `_glazingtype_options`, which carry the **id → name mapping inline in the
  model**. Full table with types: `DESIGNPH_DATA_MODEL.md` §9.2.1.

## 9. Changing the contract after freeze

One change, atomically: bump `contract_version`; update the collector, `contract.py`, and **every**
fixture (synthetic by hand, real by re-capture — an Ed cost, which is the incentive to settle §8
before freezing); re-run POC-2's reconciliation; record the bump and its cause in
`RESULTS/`. The translator hard-fails on any version it does not know — no compatibility shims in
a POC.
