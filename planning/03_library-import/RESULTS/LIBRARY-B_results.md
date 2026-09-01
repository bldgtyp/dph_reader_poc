# Spike L-B — results

```
DATE:    2026-08-31 (agent prep + all three Ed sessions, one evening — same day as the L-A PASS)
STATUS:  ✅ COMPLETE
GATE:    ⭐ PASS — all five contract questions answered (§3); CONTRACT_phn-library.md FROZEN v1
```

**What L-B asks:** the PHN → designPH mapping contract — do **real PH-Navigator assemblies and
window types**, mapped by a stated contract, reproduce their intended U-values in designPH's
own calculator (framed/multi-section included, the leg L-A deferred), and reach the PPP export?
Deliverable: [`../CONTRACT_phn-library.md`](../CONTRACT_phn-library.md), frozen on a pass.

## 1. Agent-side prep (2026-08-31) — done, rehearsed, nothing designPH-graded yet

### 1.1 The source is real production PHN data

**Linde Home (BT 2524)**, version "Round 2 Update", pulled read-only over the production `phn`
MCP (etag recorded in the payload provenance): **8 assemblies** — 6 framed/multi-section, 2
unframed controls — with materials, plus the per-edge frame data of five sampled aperture types
(**9 distinct frame tuples**) and **2 glazings**. Deliberately the same building as the corpus's
`250703 - Linde Residence.skp`, so the PHN library lands beside the designPH library its author
built by hand. Source snapshot: `../../spikes/library-import/_private/phn/linde_phn_library.json`
(client data, gitignored), with transcription self-checks (segment sums, thickness totals)
enforced by the mapper.

### 1.2 The mapping contract exists and is executable

[`CONTRACT_phn-library.md`](../CONTRACT_phn-library.md) v0 DRAFT; `map_phn.py` implements it:
films from (type, exterior_condition); per-layer segments packed into PHPP's assembly-level
3-path model (§2.4 — the |F| ≤ 2 packing, refusal beyond); names sanitized against the DC
option-list delimiters (`&`, `=`); frames as per-edge tuples; ISO 6946 mean-of-limits intended
U per assembly **with the expected Error %**, using the POC-1 function verified against
designPH's own calculator (7/7).

Mapped: **8/8 assemblies, 0 refusals** — F-GR and R-VT need all three PHPP paths (two distinct
framing fractions each). Intended values, the grading sheet:
`_private/payload/lb_expectations.md`. The packing's absorbed alignment delta is printed per
assembly (0.0000–0.0042 W/m²K; worst on triple-framed W-EC) — a stated loss, not a silent one.

### 1.3 The write path is rehearsed on real tables — 4/4 scenarios clean

`write_library_b.rb` (data-driven successor to L-A's paste-in, same guards) +
`rehearse_b.py`/`offline_rehearsal_b.rb`:

| scenario | exercised |
|---|---|
| `lb_bluffreach` | fill 8 assembly slots (`07ud…14ud`) + 8 created layer tables + 9 frames + 2 glazings, strict style |
| `lb_linde` | fill around the named-row gaps (`08ud…10ud, 29ud…33ud`); **wrapped** base64 style preserved on `frames_ud`/`glazing_ud` |
| `lb_adelphi_create` | all three tables + layer tables **created** on a model that never carried them |
| `lb_bluffreach_probe` | `:probe` — foreign `phn_id` token + column appended to `assemblies_calc`, everything else byte-identical |

Verified per scenario: metadata untouched, every non-marker row byte-identical, styles
preserved, marker rows exact — and ⭐ **the closing arithmetic loop**: assemblies and layer
tables are decoded back out of the written bytes and re-run through ISO 6946 — recovered U ==
intended U on 8/8 in every scenario. What designPH will read provably computes what we predict.
⚠ A rehearsal is not a capture: designPH has graded nothing yet.

### 1.4 Copies staged, baselines captured

`_private/copies/`: `2414_BluffReach_LIBIMPORT-lb.skp` (gate session),
`250703_Linde_LIBIMPORT-lb.skp` (n>1 + wrapped style), `2414_BluffReach_LIBIMPORT-xc.skp`
(extra-column probe). Baselines in `_private/baseline/` — live-state table dumps + contract-v2
captures; capture counts match the corpus numbers exactly (194/99/40 · 74/0/47).

## 2. ⭐ Session 1 — Bluff Reach, the gate session (Ed + agent, 2026-08-31 evening)

designPH **2.2.29 stable**, SketchUp 22.0.353. Write clean (dry-run ids exactly as rehearsed:
assemblies `07ud…14ud`, frames `03ud,04ud,06ud…12ud`, glazings `02ud,03ud`), re-initialise,
grade, assign, save, export. Screenshots + files: `_private/post/Spike L-B/Sesson 1/`.

### 2.1 ⭐ The calculator leg: 8/8 EXACT — U, R, and Error %

Graded off Ed's eight calculator screenshots against `lb_expectations.md`:

| assembly | designPH shows U / R / Error % | intended U / Error % | |
|---|---|---|---|
| ZZ F-CS (Crawlspace) | 0.111 / 9.00 / **0.00** | 0.1112 / 0.00 | ✅ |
| ZZ F-GR (Garage) | 0.073 / 13.71 / **2.59** | 0.0730 / 2.59 | ✅ |
| ZZ R-AT (Attic) | 0.073 / 13.62 / **1.96** | 0.0734 / 1.96 | ✅ |
| ZZ R-FL (Flat) | 0.083 / 12.11 / **2.97** | 0.0826 / 2.97 | ✅ |
| ZZ R-VT (Vaulted) | 0.062 / 16.07 / **3.96** | 0.0622 / 3.96 | ✅ |
| ZZ W-CS (Crawlspace) | 0.261 / 3.84 / **0.00** | 0.2607 / 0.00 | ✅ |
| ZZ W-EC (Ext. Conditioned) | 0.121 / 8.29 / **2.30** | 0.1206 / 2.30 | ✅ |
| ZZ W-GR (Conc. Above Grade) | 0.159 / 6.28 / **3.24** | 0.1593 / 3.24 | ✅ |

Error % (2 decimals, designPH's own spread figure) matches **exactly on all eight** — the
sharpest available display check — and every shown R equals 1/intended-U to 2 decimals. The
three-path packing renders exactly as designed: F-GR shows Surface percentages **78.12 / 9.38 /
12.50** with the 21.875 %-framed layers carrying wood in sections 2 *and* 3, the 9.375 % layer
in section 2 only. Dropdowns carry all 9 frames + 2 glazings with per-edge asymmetry intact
(mullR: L 0.74 / R 0.94; mullL mirrored). Quirk: g = 0.0 renders as a *blank* cell (ThermaTru).

### 2.2 The diffs: the write set, designPH's stamp, and two named analysis effects

Model-level (`dump_model_tables.py --diff`, baseline → post): exactly our 19 rows + 8 created
layer tables, every field payload-exact after designPH's own save (no normalisation), plus
`designPH_version 2.2.24 → 2.2.29` and **one appended `tracker_data` row** — the analysis run
Ed performed for the export, logging itself (§7.0.2). *Refines* L-A's O-6: designPH's **save**
touches one field; running an **analysis** additionally appends telemetry.

Entity-level (capture diff, `entity_id` excluded): the assigned face `assembly_ref 03ud → 13ud`
(ZZ W-EC on `Wall_033_S`) and window H1's DC `frametype`/`frametypeid` **both** → `03ud` (frame
pair coherent; widths propagated into the DC in inches — §8.5 again). Ed's trivial edit shows as
one roof reassignment. Edges: 0 changed. Window transforms: the known ~1-ULP DC-refresh noise.
⚠ One designPH analysis behaviour worth knowing: the run wrote `desc_name` auto-names onto **54
classified faces** (`Wall_043_N`…) — designPH's own doing, not a write-side obligation.

### 2.3 ⭐ The export: everything arrived — and the needle-read answers B-3

`2414_BluffReach_LIBIMPORT-lb-post.ppp` (156,308 bytes, produced by 2.2.29; ⚠ the `.ppp` is
**UTF-16LE** text — UTF-8 needles return a clean false zero; the wrong-container lesson, again).
Verbatim needles, amended hard rule 1: **all 8 assemblies, all 9 frames, both glazings present**,
plus the id-prefixed *reference* forms for exactly what Ed assigned: `13ud-ZZ W-EC (Ext.
Conditioned)`, `03ud-ZZ smartwin compact Tilt-Turn`, and `02ud-ZZ smartwin | 6SKN-18AR-4-18AR-4XN`.
PHPP by eye (Ed): present and assigned.

⭐ **B-3 answered.** designPH's UI split the glazing pair again on assignment (H1:
`glazingtype = 02ud`, `glazingtypeid = 01ud` — frame pair stayed coherent), so the export was
produced from a split state — and the window reference in the `.ppp` is `02ud-…` (the other 36
windows all read `01ud-PH Glazing`). **The PPP export consumes `glazingtype`, not
`glazingtypeid`.** Same verdict as L-A's observation, now n=2, both under 2.2.29.

## 2b. ✅ Session 2 — Linde: second model, wrapped style (Ed + agent, same evening)

designPH 2.2.29, `250703_Linde_LIBIMPORT-lb.skp`. Write clean — 11 keys, ids exactly as
rehearsed, filling **around** the named-row gaps (`08ud…10ud, 29ud…33ud`), layer tables cloned
from `layer_table_01ud`'s 8-col schema. Console + screenshot: `_private/post/Spike L-B/Session 2/`.

- **Listed and computed on n=2**: the user-calculated list shows our rows seated between
  Linde's own 25 assemblies with designPH-computed U matching (visible rows: ZZ F-CS 0.111,
  ZZ F-GR 0.073, ZZ R-AT 0.073). The below-the-fold five are closed by arithmetic instead:
  **U recomputed from the saved post-file's bytes is EXACT on 8/8** (same closing loop as the
  rehearsal, now on designPH-saved data).
- ⭐ **B-5 PASS: the wrapped base64 style survived** — post-save `frames_ud` and `glazing_ud`
  are still `[wrapped]`, rows field-exact, beside strict siblings.
- **The diff census is fully accounted**: 19 row-diffs + 8 ADDED layer tables (ours) +
  **189 `tracker_data` diffs (designPH's own)** — 2 appended rows (designPH logs calc events at
  launch/re-initialise, not only full analyses) and 187 rows whose Ruby `Time` payloads were
  **re-serialised representation-only** (same instants, richer zone encoding). Two O-6
  refinements worth keeping: designPH's save re-dumps `tracker_data` even untouched, and a
  change-detecting watcher (pholio) must canonicalise or exclude `tracker_data` before hashing —
  alongside the already-known `entity_id`.

## 2c. ⭐ Session 3 — the update-key probe (Ed + agent, same evening)

designPH 2.2.29, `2414_BluffReach_LIBIMPORT-xc.skp`, `DPHLB.write!(:probe)` — the full payload
PLUS a foreign `:phn_id` token + one extra cell on **every** `assemblies_calc` row (8 carrying
real PHN ids, 74 empty). Ed then ran a calculation and a PPP export, both error-free. Files:
`_private/post/Spike L-B/Session 3/`.

**B-2 answered on all three counts — the foreign column is:**

1. **Read-tolerated**: designPH lists all 8 ZZ rows with correct U-values, calculates, and
   exports, with the widened schema in place (screenshot + Ed: "calculation ran without any
   error").
2. **Save-preserved, byte-intact**: the saved file's `:TOKENS` still ends `phn_id` (9 tokens),
   every row is 9 cells, and the 8 PHN ids read back verbatim (`asm_b6cs79yqdjrz`…).
3. **Export-inert**: the probe `.ppp` carries every ZZ row normally and **zero** occurrences of
   any `asm_*` id or the string `phn_id` — the column leaks nowhere.

Diff census (post-fix tool): 82 `assemblies_calc` row-widenings + the TOKENS change (the probe
itself), our 9 frames + 2 glazings + 8 layer tables, the version restamp, one tracker row.
Nothing unexplained.

**Consequence for the contract (§5): the update key is the `phn_id` column** — a re-importer
matches rows on `phn_id` where present (rename-in-PHN safe), falling back to `desc` match for
rows imported before the column existed. designPH's own tolerance of the extra column is now
measured, not assumed.

⚠ One tool lesson, same shape as always: the **probe crashed the diff tool** —
`dump_model_tables.py --diff` indexed row cells by the baseline's shorter token list
(`IndexError`), on exactly the first input whose rows differ in width. Fixed (guarded both
accesses); the case the tool was built to grade is the case it had never met.

## 3. The contract's open questions

| # | Question | Answer |
|---|---|---|
| B-1 | Calculator reproduces intended U and Error %; PPP carries them | ⭐ **PASS** — 8/8 exact incl. Error %; export needle-validated + PHPP by eye (§2.1, §2.3) |
| B-2 | Foreign `phn_id` column: read-tolerated? survives save? | ⭐ **YES, all three counts** — tolerated (lists/computes/calculates/exports), save-preserved byte-intact, export-inert. The `phn_id` column becomes the contract's update key (§2c) |
| B-3 | Which of the split `glazingtype`/`glazingtypeid` pair does the export consume? | ✅ **`glazingtype`** — discriminated by the split pair on the assigned window (§2.3); n=2 with L-A, both 2.2.29 |
| B-4 | Which end of the layer list does the dialog show as outside? | ✅ Row 1 = our first-emitted (outside) layer, and R_in/R_out are explicit separate fields — order is display-only; outside-first confirmed compatible (Ed 1.5 + screenshots) |
| B-5 | Wrapped-style writes survive Linde's save byte-stable? | ⭐ **PASS** — post-save `frames_ud`/`glazing_ud` still wrapped, rows field-exact; 8/8 U recomputed from saved bytes exact (§2b) |

## 4. Gate — ⭐ PASS (Ed + agent, 2026-08-31)

| # | Criterion | Verdict |
|---|---|---|
| 1 | ≥ 5 real PHN assemblies, framed/multi-section included, reproduce intended U in designPH's calculator on stable 2.2.29 | ⭐ **PASS — 8/8, Error % exact on every one** (§2.1), reconfirmed on a second model by list-U + saved-bytes recompute (§2b) |
| 2 | PPP export carries them (needle-validated; placement by eye in PHPP) | ⭐ **PASS** (§2.3), plus the probe export (§2c) |
| 3 | Contract doc complete: value mapping, serialisation discipline, id/update policy, split-pair answer, user-facing rule | ✅ **[`CONTRACT_phn-library.md`](../CONTRACT_phn-library.md) FROZEN v1** — B-1…B-5 all folded in |

**Evidence limits, stated:** one machine (macOS arm64, SketchUp 22.0.353), designPH stable
2.2.29 throughout (the BETA's analysis path is unusable on SU2022); source data from one PHN
project (8 assemblies, 9 frame tuples, 2 glazings — but two models, two base64 styles, and the
full 3-path packing exercised). The B-3 verdict (export reads `glazingtype`) is n=2 but both
observations are 2.2.29 with the split in the same direction.

**▶ What L-B hands L-C:** the frozen contract + `map_phn.py`/`write_library_b.rb` as the working
seed; the `phn_id` update key measured viable; per-model slot allocation composing around named
gaps; the user rule unchanged ("re-initialise designPH after import"); and two watcher-relevant
byte-stability facts (`tracker_data` re-dumps on save; analysis writes `desc_name` auto-names).
