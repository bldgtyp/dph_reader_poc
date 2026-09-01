# Contract — PH-Navigator → designPH library import (Spike L-B)

**Version: 1 — ✅ FROZEN 2026-08-31.** The L-B gate passed the same evening the draft was
written: designPH 2.2.29's own calculator reproduced the intended U **and Error % exactly on
8/8 real PHN assemblies** (6 framed/multi-section, both 3-path cases), on two models and both
base64 styles, and the PPP export carries every row (`RESULTS/LIBRARY-B_results.md`). Every
§9 question is answered below in place. `../spikes/library-import/map_phn.py` +
`write_library_b.rb` are the reference implementation. Changes go through §10.

This is the only seam between PH-Navigator's library data and a designPH model. An importer
programs against this document; `map_phn.py` and `write_library_b.rb` are its reference
implementation, and the rules they encode are the rules stated here — a divergence between the
two is a bug in one of them.

**Design rules, inherited and binding:**

- **The write recipe is L-A's, verbatim** (`00_Context/DESIGNPH_DATA_MODEL.md` §14.2): designPH's
  own serialisation (`Marshal.dump` + base64), matching each key's existing base64 style, emitting
  the `:TOKENS` schema the model's own table carries, filling pre-allocated blank slots, never
  touching a DC option list or any entity-level dictionary. Model-level keys only.
- **The route is the USER-CALCULATED library** — `assemblies_calc` + `layer_table_<id>` — never
  `assemblies_ud` (that is the CSV-seeded user-defined library, a separate product surface with a
  separate id namespace; §14.5). PHN assemblies carry layers; they belong on the layered route.
- **Report, don't guess** (hard rule 4): an assembly the mapping cannot represent is refused by
  name with a reason, never skipped, never silently approximated.
- **A lossy step states what it absorbed**: the one approximation in this contract (§2.4's
  framing-alignment packing) is quantified per assembly in the emitted expectations table.
- **Version gate**: the writer refuses a designPH 3.x version stamp by name, and records the
  stamp it wrote under.

---

## 1. Source of truth on the PHN side

| designPH target | PHN source | Read via |
|---|---|---|
| `assemblies_calc` + `layer_table_*` | Assembly Builder assemblies (layers → segments → project materials) | `list_envelope_assemblies` + `list_project_materials` |
| `frames_ud` | the distinct **frame-component tuples** (top/right/bottom/left) that aperture-type elements use | `get_aperture_u_value_report` (per-edge width, U, ψ-g, ψ-install, names) |
| `glazing_ud` | project glazings | same report (glazing g, U, name) |

PHN frames are **per-edge components** (Head / Jamb / Sill each its own record); designPH's
`frames_ud` row is a **window type** with per-edge values. The mapping unit is therefore the
*tuple*: each distinct (top, right, bottom, left) combination an element uses becomes one
`frames_ud` row (§3). Element grids, installs, and operation are placement data, not library
data — out of scope here.

## 2. Assemblies → `assemblies_calc` + `layer_table_<id>`

### 2.1 Header row (`id, desc, R_in, R_out, surf2_percentage, surf3_percentage, additional_U_value, int_insul`)

| Column | Rule |
|---|---|
| `id` | allocated by the writer — first blank slot, §5 |
| `desc` | the PHN assembly name, **sanitized** (§6). *(Spike payloads prefix `ZZ ` for UI findability; the contract name is verbatim-sanitized.)* |
| `R_in`, `R_out` | film resistances from **(type, exterior_condition)**, table below |
| `surf2_percentage`, `surf3_percentage` | **PERCENTAGES** (§7.2's trap — `9.375` means 9.375 %), from the §2.4 packing |
| `additional_U_value` | `0.0` |
| `int_insul` | `false` (PHN has no equivalent flag; revisit if designPH is shown to consume it) |

**Films (ISO 6946), by PHN `type` × `exterior_condition`** — a well-ventilated exterior layer
takes R_se = the R_si value for that heat-flow direction:

| | `outdoor_air` | `ventilated` |
|---|---|---|
| `wall` | 0.13 / 0.04 | 0.13 / 0.13 |
| `roof` | 0.10 / 0.04 | 0.10 / 0.10 |
| `floor` | 0.17 / 0.04 | 0.17 / 0.17 |

Any other combination (e.g. ground contact) is a **refusal** until a rule is stated here.
*(Corroboration: Linde's own designPH model stores 0.13/0.13 on its ventilated wall — the
convention above is what its author used.)*

### 2.2 Layer rows

- One `layer_table_<id>` per assembly, `<id>` = the header row's slot.
- **Emit the schema the model's own layer tables carry** (8-col or 12-col; both exist within one
  model — §7). A created table clones the model's first existing layer table, blanked; if none
  exists, the canonical 8-col 8-row shape. Row ids are integers 1…8 (measured).
- **Layers are emitted OUTSIDE-first.** PHN's `orientation` says which end of its list is
  outside (`last_layer_outside` ⇒ reverse). ✅ Verified compatible: the dialog shows row 1 (our
  outside layer) at the top, and R_in/R_out are separate explicit fields — ordering is
  display-only; U is direction-independent (B-4).
- `desc1`/`lambda1` = the layer's **primary** (largest-area) material, name sanitized, λ in W/mK;
  `thickness` in **mm**. `desc2/lambda2` (`desc3/lambda3`) only where the packing (§2.4) puts a
  secondary material in that path; **blank otherwise** — a blank path falls back to `lambda1`,
  which is designPH's own idiom (observed in real Linde tables, and the verified semantics of
  the POC's regression implementation).
- 12-col donors additionally get `R1/R2/R3` = thickness/λ(path, with blank-falls-back-to-1) and
  `R_tot` = `R1` — matching the observed uniform-row pattern. ⚠ Untested leg: no 12-col donor is
  first-sorted in any staged model.
- **> 8 layers is a refusal** (every corpus layer table is 8-row pre-allocated).

### 2.3 What "correct" means — the intended U

The intended U-value is **ISO 6946 §6.7's mean of limits, films included**, computed on the
packed 3-path model — the same method designPH's own U-/R-value calculator uses, verified in
POC-1 on seven independent assemblies to ±0.0005 W/m²K with Error % exact
(`00_Context/DESIGNPH_DATA_MODEL.md` §7.2). `map_phn.py` ports that exact function and emits,
per assembly, the intended U **and** the expected Error % designPH must print beside it.
Regression bar (the L-B gate): designPH's calculator shows the intended U within
**±0.0005 W/m²K** and the expected Error % within ±0.01.

### 2.4 Packing PHN's per-layer segments into PHPP's three paths

PHN models framing per layer (segments with widths); PHPP/designPH models it as **assembly-level
section percentages** with per-layer materials per section. The packing:

1. Per layer, group segments by material → (material, fraction) pairs, primary = largest.
   **A layer with 3+ materials is a refusal** (representable only approximately).
2. Let F = the distinct secondary fractions across all layers.
   - |F| = 0 → single path, `surf2 = surf3 = 0`.
   - |F| = 1 → `surf2 = F₀`; framed layers put their secondary material in path 2.
   - |F| = 2 → `surf2 = F_small`, `surf3 = F_big − F_small`; a layer framed at `F_small` fills
     path 2 only; one framed at `F_big` fills paths 2 **and** 3 (their areas sum to `F_big`).
   - |F| ≥ 3 → **refusal**.
3. ⚠ **The stated loss**: the packing assumes framing in different layers is *aligned* (nested
   columns). ISO 6946's upper limit moves when real framing is staggered. The expectations table
   prints the U under the fully-independent (staggered product) reading beside the packed one —
   on the Linde set the absorbed Δ is 0.0000–0.0042 W/m²K, worst on the triple-framed W-EC.
   The intended U (what designPH computes from the written rows) is the **packed** one; the Δ
   column is the mapping being honest about representation, not an error in the write.

## 3. Frame tuples → `frames_ud`

One row per distinct (top, right, bottom, left) frame-component tuple
(`id, desc, U_FL…U_FT, width_L…width_T, psi_GL…psi_GT, psi_FL…psi_FT, chi_GT`):

| Column | Rule |
|---|---|
| `desc` | derived tuple name (shared family prefix; mixed tuples — e.g. a mullion edge — get a suffix like `mullR`), sanitized §6 |
| `U_F{L,R,B,T}` | the edge component's frame U (W/m²K) |
| `width_{L,R,B,T}` | the edge component's width **in metres** (designPH stores SI here — 0.103 on real rows; the DC copy designPH derives is inches, its own doing — §8.5) |
| `psi_G{L,R,B,T}` | the edge's glazing-edge ψ (W/mK) |
| `psi_F{L,R,B,T}` | the edge component's **perimeter install ψ** (PHN's report zeroes ψ-install contextually on mullion-adjacent edges — that context is placement data; the *type* carries the perimeter value; mullion components themselves carry 0) |
| `chi_GT` | `0.0` — PHN has no glazing-carrier χ |

## 4. Glazings → `glazing_ud`

`id, desc, g_value, U_value` — name sanitized, g and U verbatim from PHN. An opaque door leaf
(g = 0) is a legal row (Linde's ThermaTru writes g 0.0 / U 0.574).

## 5. Id allocation, re-import, and the update key

- **Allocation**: first blank slot (blank `desc`) in the user range — `01ud…82ud` for
  `assemblies_calc`, `01ud…91ud` for `frames_ud`/`glazing_ud` (92ud+ hold shipped presets on
  observed models). Insufficient slots ⇒ **refusal of the whole write**, never a partial import.
  Measured (L-A): fill-next-blank composes across repeated runs — which also means naive
  re-import **duplicates**.
- **Creation**: a table the model never carried is created with designPH's own pre-allocation
  (82 rows / 99 rows / 8 layer rows) — accepted, measured (L-A on a 2.1.15-era model).
- ✅ **The update key is the `phn_id` column** *(decided by the Session 3 probe, 2026-08-31)*:
  the importer appends a `:phn_id` token to `assemblies_calc`'s `:TOKENS` and one cell per row
  (the PHN id on imported rows, `""` elsewhere). Measured on 2.2.29: designPH **tolerates** the
  widened schema (lists, computes, calculates, exports normally), **preserves it byte-intact
  through its save** (token + all 82 cells + the 8 ids verbatim), and the column is
  **export-inert** (zero leakage into the `.ppp`). Re-import matches on `phn_id` where present
  (rename-in-PHN safe) and falls back to exact-`desc` match for rows that predate the column.
  ⚠ This is the contract's one sanctioned deviation from "emit the schema the model carries" —
  it *extends* the schema, never rewrites existing cells, and the same rule may be applied to
  `frames_ud`/`glazing_ud` (untested there; same designPH code path is likely but not measured).

## 6. Name sanitization

designPH's regenerated DC option lists delimit on `&` and `=` (`&name=id&…`) — either character
in a `desc` would corrupt every window's dropdown. Rule: `&` → `+`, `=` → `-`, applied to every
desc this contract writes (assembly, layer, frame, glazing). Pipes, slashes, parens pass
through (all observed in real designPH descs). Length: no designPH limit has been measured;
the longest written name (44 chars) is a de-facto tested bound — treat longer names as untested.

## 7. Serialisation discipline (the L-A recipe, restated as contract)

1. Base64 style **per key, matched to what the key already carries** (Linde live: `frames_ud`/
   `glazing_ud`/`layer_table_11ud+` wrapped beside strict siblings). New keys: strict.
2. `:TOKENS` cloned from the model's own table; never a canonical schema over a donor's.
3. **Never write**: DC option lists (they regenerate — §14.4), any face/edge/window dictionary,
   any key not named in §§2–4. Provenance (`spike`, `written_at`, `wrote_keys`,
   `phn_version_etag`) goes in **`DesignPHPlus_dict`**, our namespace, only.
4. One undoable operation; dry-run first; `LIBIMPORT`-title guard on spike copies.

## 8. User-facing rule (measured, L-A)

Imports may happen at any timing — before open, mid-session, dialog open — but **an open
designPH dialog is a stale view**: the user rule shipped with any importer is
*"after import, run Extensions → designPH → Launch designPH or re-initialise model (or reopen
the model)"*. designPH's save does not clobber foreign rows (it touches exactly
`designPH_version`).

## 9. The five contract questions — ✅ all answered 2026-08-31 (`RESULTS/LIBRARY-B_results.md`)

| # | Question | Answer |
|---|---|---|
| B-1 | Calculator reproduces intended U ± 0.0005 and Error % on framed assemblies? | ⭐ **8/8 exact incl. Error %** (F-GR 0.073/2.59 %, R-VT 0.062/3.96 %…); export carries all rows + the assigned references |
| B-2 | `phn_id` extra column survives read + save? | ⭐ **Yes, all three counts** — tolerated, save-preserved, export-inert. Now §5's update key |
| B-3 | Which of the split `glazingtype`/`glazingtypeid` pair does the export consume? | ✅ **`glazingtype`** — discriminated by a naturally split pair on the assigned window (`02ud-…` in the `.ppp` vs 36× `01ud-PH Glazing`); n=2 with L-A, both 2.2.29. An importer still never *writes* either key |
| B-4 | Which end of the layer list is "outside"? | ✅ Dialog row 1 = our first-emitted (outside) layer; R_in/R_out are separate explicit fields, so ordering is display-only — outside-first stands |
| B-5 | Wrapped-style writes survive the save? | ✅ Linde post-save `frames_ud`/`glazing_ud` still wrapped, rows field-exact; U from saved bytes exact 8/8 |

## 10. Change control

FROZEN at v1 (2026-08-31). Changes follow the same rule as the extraction contract: a version
bump with the evidence named, and `map_phn.py` + this doc move together — a divergence between
them is a bug in one of them.
