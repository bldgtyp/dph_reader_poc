# designPH Data Model — How and Where It Stores Data

Investigation record, 2026-08-19. Sources of evidence are named throughout so every claim can be
re-checked. Where something is **inferred** rather than observed, it says so.

**Scope:** designPH 2.1.10 / 2.1.15 / 2.2.24 / 2.2.29 / 2.4.0 BETA, across 14 corpus models
(Phase 0 baseline). Upstream is now 3.0 — re-verify before relying on any of this for 3.0.

> ⚠ **§6 is CONTESTED.** The `*Auto` vs `*ID` reading rule was refuted by the Phase 0 corpus
> baseline. Do not implement it; read §6.2 and §6.3 first.

---

## 1. The one-sentence version

designPH stores **everything** in standard SketchUp `AttributeDictionary` objects, all under a
single dictionary name — **`DesignPH_dict`** — attached at exactly two levels: **the model** (project
settings and lookup tables) and **individual faces** (per-surface assignments).

There is no sidecar file, no database, no hidden layer. The data lives in the `.skp`.

---

## 2. Evidence base

| Model | designPH version stamp | What it gave us |
|---|---|---|
| `~/Dropbox/bldgtyp/2523 Wellington/08_DesignPH/2523 Wellington.skp` | `2.1.10` **and** `2.2.29` | Full model-level table set; 103 classified faces; both key generations |
| `~/Desktop/dph_plus_testing/designph_test~.skp` | `2.2.29` | 6 faces, clean auto-classified state |
| `~/Desktop/dph_plus_testing/designph_test.skp` | `2.4.0 BETA` | Model-level keys only (saved before face assignment) |
| Live JSON dumps from BT Attribute Inspector | 2.4.0 BETA session | Confirms in-memory values match on-disk values |
| `_adephi_st_example_files/adelphi-designph.skp` | `2.1.15` | Primary corpus model; 1441 tagged faces; type instability (§6.4) |
| **Phase 0 baseline — all 14 corpus models** | `2.1.10` … `2.4.0 BETA` | §5.3.1 `tempZone` decode · §6.2 rename hypothesis refuted · `descName` (§5.2) |
| `_adephi_st_example_files/adelphi-phpp.xlsm` | *(PHPP 10)* | PHI's own group labels — resolved groups 12–14 and 18 (§5.3) |

Plus the shipped data libraries under
`~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/designPH/data/`.

The Phase 0 baseline covers all 14 `.skp` files in the corpus — the primary Adelphi model, the two
`_misc_test_files` samples, and the 11 files under `~/Dropbox/bldgtyp/*/08_DesignPH/`. Full per-model
key and value inventory: `planning/RESULTS/PHASE-0_corpus-baseline.md`; regenerate with
`uv run planning/spikes/phase0/corpus_baseline.py`.

**Full key inventory** for the Wellington model — 29 distinct keys under `DesignPH_dict`,
reproducible with `uv run tools/skp_attr_dump.py "<model>.skp" -d DesignPH_dict`:

```
tempZoneAuto 343 · descNameAuto 160 · descNameFreeze 116 · BackMaterial 103 · Material 103
areaGroupID 103 · tempZoneID 103 · assemblyID 59 · faceTypeAuto 59 · assemblyIDAuto 44
TFA_rf 10 · designPH_version 2 · frames_ud 2 · ihg_ud 2 · klima_ID 2 · tracker_data 2
vent_ud 2 · Klima_Standort 1 · connections_ud 1 · glazing_ud 1 · tfa_calc 1 · tfa_calc_ud 1
assemblies_calc 1 · layer_table_01ud…05ud 1 each · Dashboard 1
```

---

## 3. Storage mechanism

SketchUp gives every entity — and the model itself — an unlimited set of named attribute
dictionaries, each a string-keyed bag of values. This is core SketchUp model data, not plugin data.

```ruby
face.set_attribute("DesignPH_dict", "areaGroupAuto", 8)
face.get_attribute("DesignPH_dict", "areaGroupAuto")   # => 8
face.attribute_dictionary("DesignPH_dict")             # => AttributeDictionary or nil
```

Consequences we care about:

- **Portable.** Readable by anything that can open a `.skp`, with designPH absent or never installed.
- **Persistent.** Survives save/load, copy, Dropbox sync, and version-control round-trips.
- **Typed.** SketchUp preserves Ruby primitives — String, Integer, Float, true/false, nil, Length, Array.
- **Not namespaced by SketchUp.** Any other plugin can read *or overwrite* `DesignPH_dict`.
  Nothing protects it.

---

## 4. Model-level keys

Attached to `Sketchup::Model`. Project-wide settings plus designPH's whole working dataset.

| Key | Type | Example | Meaning |
|---|---|---|---|
| `designPH_version` | String | `"2.2.29"`, `"2.4.0 BETA"` | Version that last wrote the model |
| `klima_ID` | String | `"HU0001b"`, `"US0058a"`, `"DE-9999"` | Selected climate dataset ID |
| `Klima_Standort` | String | `"Budapest"` | Climate location display name |
| `Dashboard` | Boolean | `true` | UI state — dashboard open |
| `assemblies_calc` | Marshal | 85 rows | The assembly table (see §7) |
| `layer_table_<id>` | Marshal | `layer_table_01ud` | Build-up layers for **one** assembly |
| `connections_ud` | Marshal | 13 rows | Thermal bridge / connection library |
| `frames_ud` | Marshal | | User-defined window frames |
| `glazing_ud` | Marshal | | User-defined glazings |
| `vent_ud` | Marshal | | Ventilation system settings |
| `ihg_ud` | Marshal | | Internal heat gains / occupancy |
| `tfa_calc`, `tfa_calc_ud` | Marshal | | Treated floor area calculation inputs |
| `tracker_data` | Marshal | large | Internal bookkeeping — purpose not established |

**Note the `layer_table_*` pattern.** These are *not* SketchUp layers/tags. Each assembly gets its
own model-level key holding its material build-up: `layer_table_01ud` = the layers of assembly `01ud`.
An assembly is therefore split across two places — its header row in `assemblies_calc`, its layers in
a separate key. A model with 80 assemblies would carry 80 `layer_table_*` keys.

---

## 5. Face-level keys

Attached to individual `Sketchup::Face` entities.

⚠ **`Sketchup::Edge` entities carry a `DesignPH_dict` too** — thermal bridges, which PHPP measures
as lengths. They use the same `areaGroupID` / `tempZoneID` / `assemblyID` keys but resolve
`assemblyID` against a different table, and they never carry the cached `Material`/`BackMaterial`
that marks a face record. See §7.1. **Walking only faces loses them.**

| Key | Type | Observed values | Meaning |
|---|---|---|---|
| `areaGroupAuto` | Integer | `8`, `10`, `11` | PHPP area group — **auto-classification cache, see §6** |
| `areaGroupID` | Integer **or String** | `1`, `8`, `9`, `10`, `11`, `14`, `18`, `'n'` | PHPP area group — the authoritative assignment (§6.3). **Type-check every read** (§6.4) |
| `assemblyIDAuto` | String / nil | `"83ud"`, `"85ud"`, nil | Assembly assignment, designPH-derived |
| `assemblyID` | String | `"01ud"`–`"05ud"` | Assembly assignment (older key generation) |
| `tempZoneAuto` | String / nil | `"A"`, `"B"`, `"i"`, `"split A/B"`, nil | Temperature zone — **derivable from the area group, see §5.3.1** |
| `tempZoneID` | String | `"TFA"`, `"A"`, `"B"`, `"P"`, `"I"`, `"i"`, `"X"` | Temperature zone (see §5.3.1 for the full decode) |
| `faceTypeAuto` | String / nil | `"xo"`, `"xi"`, `"i"`, nil | Face type — `"xo"` exterior opaque, `"i"` interior (both **observed** by area-group co-occurrence, §6.4); `"xi"` still undecoded. **Not written by every designPH run** |
| `descNameAuto` | String | `"Wall_004_S"`, `"TFA_face_012"` | Auto-generated surface name |
| `descName` | String | `"104C HALL"`, `"S_00"` | **User-typed** surface name — the override |
| `descNameFreeze` | Boolean | `true` | Lock — "stop regenerating this name". **Independent of `descName`**: Wellington sets it `true` on 116 faces that carry no `descName` at all, so it can lock a *generated* name |
| `TFA_rf` | Float / Integer | `0.5`, `0` | TFA reduction factor |
| `Material` | String | `"Default"` | **Cached** original front material |
| `BackMaterial` | String | `"Default"` | **Cached** original back material |

### 5.0 ⚠ `face.area` is NET of glued window openings — and `face.loops` does not show them

*(Established 2026-08-21 by a 16-of-16 exact match on Adelphi. Evidence:
`poc/_private/fixtures/adelphi-designph_COPY.extraction.json` plus the translation report's own
area cross-check.)*

designPH windows are **glued** Dynamic Components. Where one is glued to a face, SketchUp's
`face.area` returns the area **less the opening**, while `face.loops` reports **no inner loop** for
it.

The confirmation is exact, not circumstantial:

| | |
|---|---|
| distinct window host faces on Adelphi | **16** |
| faces where SketchUp's area disagreed with the area of the same transformed boundary | **16** |
| intersection | **16** (both differences empty) |
| of those hosts, how many report `loops.size > 1` | **2** |

So a translator reading `face.area` gets **net** area, and one building a polygon from
`outer_loop` + `inner_loops` gets **gross** area. Both are correct and they answer different
questions. Which one is wanted depends on the consumer: PHPP wants gross wall area with windows
subtracted separately, which is the honeybee/HBJSON convention too (apertures are children of their
face). **Ship the loops and let the consumer subtract**; use `face.area` only as a cross-check, and
expect it to differ on precisely the window hosts.

⚠ This also kills `loops.size > 1` as a way to find window hosts. It is a fact about *modelled*
holes, not about glued openings — the complement of the `cuts_opening?` trap (§9), and the two
together mean **neither loop count nor definition capability identifies a host**. Only `glued_to`
does.

### 5.1 `Material` / `BackMaterial` are a stash, not an assignment

designPH repaints faces with its own area-group colours for the coloured display mode. Before doing
so it caches your original front and back material names in its own dictionary, so it can restore
them when you leave that mode. **Do not read these as "the material of this surface."** They record
what the surface looked like before designPH touched it.

This is why the shipped `.skm` files are numbered by area group
(`designPH_reverse_material_8.skm`, `_9`, `_10`, `_11`, `_14`, …) — they are the display palette.
`reverse_material_*` are the striped back-face textures that flag reversed normals.

### 5.2 `descNameAuto` naming convention

Decoded from the test model, which has exactly six faces:

```
Floor_001_D    Wall_002_N    Wall_003_E    Wall_004_S    Wall_005_W    Roof_006_H
└─┬──┘ └┬┘ ┬    
  │     │  └─ orientation: N / E / S / W / H(orizontal) / D(own)
  │     └──── sequence number — a single global counter across all types
  └────────── element type: Wall / Roof / Floor
```

TFA faces use a **separate** counter and a different shape: `TFA_face_001` … `TFA_face_160`.

The global counter means **inserting a face renumbers nothing, but deleting and re-running
classification can renumber everything.** Names are not stable identifiers. Use `entityID` or
`persistent_id` if you need identity.

**`descNameAuto` is only half the name.** The user's own name lives in a separate key, `descName`
(added 2026-08-19, Phase 0). The triple is a derived/override/lock set, the same pattern as §6's
revised reading of the `*ID` / `*Auto` pairs:

| Key | Role |
|---|---|
| `descNameAuto` | designPH's generated name — `Wall_004_S`, `TFA_face_012` |
| `descName` | what the user typed — `104C HALL`, `109 PANTRY`, `S_00`, `N_EXT` |
| `descNameFreeze` | the lock: user renamed it, stop regenerating |

Observed on 6 of the 14 corpus models (Bluff Reach n=70, Holmes, MacDonough n=34, plus backups). Its
population matches the classified-face count in each model — MacDonough carries `descName` on exactly
the 34 faces that carry `areaGroupID`.

**A reader must prefer `descName` and fall back to `descNameAuto`.** Exporting `Wall_004_S` while
`104C HALL` sits unread in the model is visible data loss on exactly the models real consultants
produce.

### 5.3 PHPP area group numbers

`areaGroupID` / `areaGroupAuto` hold the **raw PHPP Areas-worksheet group number**, not a designPH
enum. Confirmed directly: the `connections_ud` table in the Wellington model carries both the number
and PHI's own label in the same row.

| # | Group | Confirmed how |
|---|---|---|
| 1 | Treated Floor Area | observed on 44 faces w/ `TFA_face_*` names |
| 2–6 | North / East / South / West / Horizontal Windows | PHPP standard, not observed on faces |
| 7 | External Door | material file `_7.skm` |
| 8 | External Wall — Ambient | observed |
| 9 | External Wall — Ground | observed |
| 10 | Roof/Ceiling — Ambient | observed |
| 11 | Floor slab / Basement ceiling | observed |
| 12–14 | **User-defined surfaces** | PHPP `Areas` summary rows 19–21; group 14 observed on 5 faces (Linde 250703) |
| 15 | Thermal Bridges Ambient | `connections_ud` row, labelled by designPH |
| 16 | Perimeter Thermal Bridges | localisation strings; observed (Bluff Reach, Holmes) |
| 17 | Thermal Bridges Floor Slab / Basement Ceiling | `connections_ud` row, labelled by designPH; observed |
| 18 | **Building element towards neighbour** | PHI's own label, `Areas!M27` of the Adelphi PHPP; observed on 15 Adelphi faces |

**Resolved 2026-08-19 (Phase 0), from the Adelphi PHPP's own summary table:**

- **Group 18 is "Building element towards neighbour."** Adelphi carries 446.5 m² of it (`Areas!L27`),
  consistent with an urban townhouse with party walls. Previously listed as unaccounted-for in §6.
- **Groups 12–14 are user-defined surface slots**, not fixed PHI categories. This is why
  `designPH_reverse_material_14.skm` ships with no data ever observed against it — designPH supplies
  a display colour for the user-defined slots. The earlier "**Open:** what group 14 is" is closed.

The full group list, its temperature zones and the per-surface areas are extracted to
`planning/RESULTS/phpp/phpp_areas_summary.csv`.

### 5.3.1 `tempZoneID` is derived from the area group — not independent data

**Established 2026-08-19 (Phase 0).** `tempZoneID` / `tempZoneAuto` are **not a designPH enum**. They
hold the PHPP `Areas`-worksheet *temperature zone*, assigned deterministically from the area group by
PHPP's own summary table (`Areas!K8:N27`):

| `areaGroup` | `tempZone` | Meaning |
|---|---|---|
| `1` | `TFA` | treated floor area marker |
| `2`–`6` (windows), `7` (door), `8`, `10`, `15` | `A` | ambient |
| `9`, `11`, `17` | `B` | ground / basement — routes through PHPP `Ground` |
| `12`–`14` (user-defined) | `X` | observed for group 14 |
| `16` | `P` | perimeter |
| `18` | `I` | towards a neighbouring building |
| `'n'` *(untagged)* | `'i'` | designPH's own "not classified" marker — **not a PHPP zone** |

Independently corroborated by the `phi-rules` PHPP 10 `Areas` teardown: *"`A` rows default to
ambient, `B`/`P` rows route through `Ground`, `I` is the neighbouring-building condition."*

✅ **Refined 2026-08-19, against `Areas!K8:N29` of `PHPP_EN_V10.6_Empty.xlsx` directly.** The table
above is right, but it is not *all* PHPP. **14 of the 18 rows come straight from the workbook;
three values are designPH's own fill for cells PHPP leaves blank or user-set:**

| Value | Group | Source |
|---|---|---|
| `A`, `B`, `P`, `I` | 8/10/15, 9/11/17, 16, 18 | **PHPP's** — `Areas!K9:K27` |
| `TFA` | 1 | **designPH's.** `Areas!K8` is blank — TFA is the normalisation area, not a thermal zone |
| `X` | 12–14 | **designPH's** default for a user-defined slot PHPP expects the *user* to zone |
| `i` | *(untagged)* | **designPH's** "not classified" marker. Not a PHPP zone at all |

So do not map `TFA`, `X` or `i` onto PHPP temperature zones. The coalesce and the integrity check
below are unaffected. Full table with PHI's own labels: `phi-rules`
`rulesets/designph-2x-r1/tool/D04-area-groups.md`.

**Evidence:** exact population arithmetic in five models — e.g. Bluff Reach `8`+`10`+`15` = 31+8+55 =
94 = `A`:94, and `9`+`11`+`17` = 14+1+28 = 43 = `B`:43. Every model balances to the unit across 14
distinct group values. See `planning/RESULTS/PHASE-0_results.md` Finding 1 for the full table.

⚠ **Inferred from counts, not observed per-face.** The offline reader extracts attribute records
without associating them to entities. Confirm per-face with the BT Attribute Inspector before relying
on it — it is cheap to check, and a wrong mapping puts a wrong temperature zone on every surface.

✅ **Partially confirmed live, 2026-08-21.** A per-face read of all 1441 tagged Adelphi faces found
**zero** area-group/temp-zone contradictions against this table (the POC translator runs the check on
every face and reports mismatches; the Adelphi report has none). That is a real per-face
confirmation for the groups Adelphi uses — 1, 8, 9, 10, 11, 18 — and says nothing about 12–17.

**Consequences:**

- A reader needs **only** `areaGroup`. `tempZone` carries no independent information.
- Reading both gives a **free integrity check**. A pair that contradicts this table means the model
  is inconsistent and must be *reported*, never silently resolved.
- `'i'` and `'I'` differ and the difference matters: `'I'` is a real envelope surface facing a
  neighbour; `'i'` is unclassified clutter. A case-insensitive read conflates them.

### 5.4 Not every face carries every key

Key subsets are **role-dependent**. In Wellington:

- **TFA faces** (`areaGroupID = 1`, n=44): `tempZoneID = "TFA"`, `descNameAuto = "TFA_face_NNN"`,
  `assemblyIDAuto = nil`. No assembly — a TFA face is a floor-area marker, not an envelope surface.
- **Envelope faces** (n=59): `assemblyID` set (`02ud`…`05ud`), `faceTypeAuto` = `"xo"` or nil,
  `tempZoneID` = `"A"` / `"B"`.

Any reader must treat every key as optional. `attribute_dictionary(...)` returning `nil` and
individual keys being absent are both normal states, not corruption.

---

## 6. The `*Auto` vs `*ID` key generations — ✅ SETTLED (Phase 1, 2026-08-19)

> **The rule is a coalesce, and there is no precedence question.** Read `*ID`, fall back to
> `*Auto` — see §6.5. §6.1's version rule is refuted (§6.2) and §6.3's "prefer `*ID`" fallback is
> also insufficient (§6.5). Both earlier sections are kept because their evidence is sound and
> their failure modes are instructive.

### 6.1 The earlier conclusion — SUPERSEDED

*(Kept for the record and because its evidence is still sound as far as it goes. The three models
below do show what it says they show; the error was generalising from them.)*

**Observed:**

| Model | version stamp | `areaGroupID` | `areaGroupAuto` | `assemblyID` | `assemblyIDAuto` | `tempZoneID` | `tempZoneAuto` |
|---|---|---|---|---|---|---|---|
| **Adelphi** | **2.1.15** | **1441** | 0 | **42** (real) | 1007 (all nil) | **1441** | 0 |
| Wellington | 2.1.10 + 2.2.29 | **103** | 0 | **59** (real) | 44 (all nil) | **103** | 343 |
| test~ backup | 2.2.29 | 0 | **6** | 0 | **6** (real values) | 0 | **6** |

**Conclusion — hypothesis (a), version rename.** A clean 2.1.15 model carries *only* the `*ID`
spellings with real values, and `assemblyIDAuto` present-but-nil. A clean 2.2.29 model carries *only*
the `*Auto` spellings, with the real values now in `assemblyIDAuto`. Wellington carries both because
it was opened in both versions, confirming that **designPH never purges superseded keys**.

#### The rule it proposed — ⚠ DO NOT IMPLEMENT

```
if designPH_version >= 2.2:  read areaGroupAuto, tempZoneAuto, assemblyIDAuto
else:                        read areaGroupID,   tempZoneID,   assemblyID
```

**Still outstanding:** designPH 3.0 is untested and is what the market runs. `descNameAuto`,
`faceTypeAuto` and `assemblyIDAuto` exist in *both* generations, so those three are not part of any
rename — they appear to be genuine derived caches throughout.

### 6.2 What the full corpus shows — the rename hypothesis fails

Baselining all 14 corpus models (Phase 0 §0.3, `planning/RESULTS/PHASE-0_corpus-baseline.md`)
contradicts §6.1. Non-nil records per key:

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

**Every real project model holds its real data in the `*ID` generation, whatever the version stamp.**
`areaGroupAuto` is *entirely absent* from four of the five 2.2-stamped project models.

Applying §6.1's rule to `2414 Bluff Reach.skp` — a clean 2.2.24 model, no 2.1 history — would read
**0 area groups, 0 assemblies, and 7 of 293 temperature zones.** Total, silent loss of the envelope
on a real project.

The single model matching §6.1's description is `designph_test~.skp`: six faces, auto-classified,
never hand-assigned. §6.1 generalised from it.

### 6.3 The revised reading — derived vs user-override, reinstated

`*ID` is the **authoritative assignment** — what designPH writes when a face is actually classified.
`*Auto` is the **auto-classification cache**: sparse, mostly nil, and populated only where
auto-classification ran. §6.1 had proposed exactly this pairing and then discarded it on Adelphi's
evidence; Adelphi ruled out the *version-rename* reading only for the models it could see, and the
wider corpus rules out the rename itself.

Three key families now follow the same derived / override / lock pattern:

| Derived | Override | Lock |
|---|---|---|
| `areaGroupAuto` | `areaGroupID` | — |
| `tempZoneAuto` | `tempZoneID` | — |
| `assemblyIDAuto` | `assemblyID` | — |
| `descNameAuto` | `descName` (§5.2) | `descNameFreeze` |

**Still unanswered here, and the reason this is not simply "prefer `*ID`":** whether `*Auto` can ever
hold a value on a face where `*ID` holds none. §6.5 answers it — **it can** — which is why §6.3 is
not the final rule either.

### 6.4 ⚠ Type instability and undocumented values

*(First surfaced by Adelphi 2026-08-19; extended to the full 14-model corpus in Phase 0.)*

- **`areaGroupID` is not always an Integer.** 1359 of Adelphi's 1441 faces carry the *string* `'n'` —
  "none / unassigned". A parser that assumes Integer will crash or mis-read on the overwhelming
  majority of faces in a real model. **Type-check every read.**
- **`areaGroupID = 18` occurs** (15 Adelphi faces). ✅ *Resolved in §5.3 — "Building element towards
  neighbour."*
- **`tempZoneID` is case-sensitive**: `'i'`, `'I'`, `'TFA'`, `'A'`, `'B'`, `'P'`, `'X'` all occur.
  `'i'` and `'I'` are distinct and mean different things. ✅ *All seven decoded in §5.3.1.*
- **`faceTypeAuto` has exactly three non-nil states corpus-wide**: `'xo'`, `'i'`, `'xi'`. Phase 1
  decoded two of them from their area-group co-occurrence: **`'xo'` is the exterior opaque
  envelope** (it co-occurs with groups 8, 9, 10, 11) and **`'i'` is interior** (overwhelmingly
  beside untagged `'n'`). **`'xi'` remains undecoded** — 25 faces corpus-wide, and *always* on an
  untagged face, never once beside a classified area group. ⚠ **The key is absent entirely from
  `2414 Bluff Reach.skp` and `2605 MacDonough.skp`**, so nothing in the reader may depend on it.
- **`Material` / `BackMaterial` are not always `'Default'`** — Adelphi caches a real material named
  `"Material"`. Do not treat `'Default'` as a sentinel.
- **`TFA_rf` takes at least `0`, `0.3`, `0.5`, `0.6`.** Not a two-state flag. (`0.6`: MacDonough.)
- **`assemblies_ud`** appears as a model-level key on Adelphi where Wellington had `assemblies_calc`.
  Both spellings must be handled, and they carry **different schemas** — see §7.
- **Face-referenced assemblies may have no `layer_table_*` key in the model.** ✅ *Resolved in §7.1:
  four resolution tiers, zero genuinely unresolvable references in the corpus — but only 254 of 532
  carry a build-up.*

**Most faces in a real model are untagged.** 1359 of 1441 Adelphi faces are `areaGroupID='n'` /
`tempZoneID='i'` — interior partitions, furniture, context. The translator must filter to tagged
envelope faces rather than assuming every face is meaningful.

### 6.5 The rule — a coalesce, not a precedence ✅

*(Phase 1, `planning/RESULTS/PHASE-1_results.md` Findings 6 and 7. Evidence:
`planning/RESULTS/PHASE-1_face-attribute-matrix.md`, all 14 corpus models, grouped **per face**
rather than per record — the grouping Phase 0 lacked.)*

Two facts, both measured face by face:

**1. The two generations are never both populated on one face.** Zero cases, across all 14 models,
for all three pairs. There is therefore no precedence question to answer — `*ID` and `*Auto` are
complementary, not competing. They are not two *generations* of one field at all: one is the
assignment, the other the auto-classification, and designPH writes exactly one per face.

**2. `*Auto` regularly holds what `*ID` does not.** 301 faces across six of the seven real project
models. The worst case is total:

| Model | Stamp | Pair | Faces lost by reading `*ID` only |
|---|---|---|--:|
| Linde `250708.skp` | 2.1.15 | `assemblyID` | **92 of 92** — every assembly in the model |
| Wellington | 2.1.10 + 2.2.29 | `tempZoneID` | 169 |
| MacDonough | 2.2.29 | `tempZoneID` | 13 |
| Linde `250703` | 2.2.29 | `areaGroupID` | 8 |

**The rule:**

```
areaGroup = face["areaGroupID"]  or face["areaGroupAuto"]
tempZone  = face["tempZoneID"]   or face["tempZoneAuto"]
assembly  = face["assemblyID"]   or face["assemblyIDAuto"]
```

**Note it is version-independent, and must be.** `250708.skp` is 2.1.15 and stores assemblies in
`*Auto`; `2414 Bluff Reach.skp` is 2.2.24 and stores them in `*ID`. Any rule keyed on the version
stamp — §6.1's or its inverse — is wrong on real models. That the coalesce needs no version check is
the reason it survives where both earlier rules failed.

Two standing obligations: **type-check every read** (§6.4), and **report** any face carrying both
generations. The corpus says that is impossible; if it happens, the model is not what we think.

⚠ **One caveat, and it is why the live check is still staged.** `model.dat` retains historical
state, so this is a statement about ~7,900 dictionaries that were *written at some point*, not a
census of live entities. `planning/spikes/phase1/live_1-1_generation_check.rb` walks live faces only
and re-prints the same table.

## 7. The Marshal blob convention

Model-level tables are stored as **base64 of `Marshal.dump`**. They are recognisable because the
string starts `BAh` (base64 of `\x04\x08`, the Ruby Marshal format marker).

```ruby
Marshal.load(Base64.decode64(model.get_attribute("DesignPH_dict", "assemblies_calc")))
```

Decoded, they use a **self-describing table format** — the schema travels with the data:

```ruby
["#", :TYPE,     :TABLE]
["#", :ROW_DATA, :ARRAY]
["#", :TOKENS,   [:id, :desc, :R_in, :R_out, :surf2_percentage,
                  :surf3_percentage, :additional_U_value, :int_insul]]
["01ud", "FT-1", 0.0, 0.0, 0.0, 0.0, 0.0, false]
["02ud", "WT-1", 0.0, 0.0, 0.0, 0.0, 0.0, true]
```

Rows beginning `"#"` are metadata; everything else is data. `:TOKENS` names the columns. This is a
genuinely good pattern — an old model opened by a new version can still name its own columns — and
**the same convention appears in the shipped CSVs** (`#,COL_KEYS,...`), so it is a house style, not
an accident. See `DESIGNPH_FILE_FORMATS.md` §2.

### Known table schemas

| Key | `:TOKENS` |
|---|---|
| `assemblies_calc` | `id, desc, R_in, R_out, surf2_percentage, surf3_percentage, additional_U_value, int_insul` |
| `assemblies_ud` | `id, desc, assem_num, thk, U_value, int_insul` — **a different schema**, carrying a U-value directly and no layers |
| `layer_table_<id>` | `id, desc1, lambda1, desc2, lambda2, desc3, lambda3, thickness` |
| `layer_table_<id>` *(Linde 250703 only)* | …the eight above **plus** `R1, R2, R3, R_tot` — the schema is not fixed across models, which is what `:TOKENS` is for |
| `connections_ud` | `id, desc, areaGroupID, areaGroupName, Psi_value, F_rsi` |
| `tfa_calc_ud` | `use_tfa_direct, tfa_direct_total, num_stories, rooms_per_storey, sub_walls_ext, thk_walls_ext, sub_walls_party, thk_walls_party, sub_walls_int, thk_walls_int, sub_stairs, area_stairs` |
| `vent_ud` | `vent_sys_ID, vent_type_ID, room_height, V_n50, result_n50, coeff_e, coeff_f` |
| `ihg_ud` | `num_units, build_type` |
| `frames_ud` | `id, desc, U_FL, U_FR, U_FB, U_FT, width_L, width_R, width_B, width_T, psi_GL, psi_GR, psi_GB, psi_GT, psi_FL, psi_FR, psi_FB, psi_FT, chi_GT` — **decoded 2026-08-21**, see §7.0.1 |
| `glazing_ud` | `id, desc, g_value, U_value` — **decoded 2026-08-21**, see §7.0.1 |
| `tracker_data` | `AUTO_ID, desc, Q_to, Q_tw, Q_tb, Q_v, Q_s, Q_i, Q_n, Q_h, climate, TFA, windows, surfaces, thermal_bridges, timestamp, username, dPH_version` — ⚠ **telemetry, and it names people**. §7.0.2 |

`layer_table_*` carries **three parallel `desc`/`lambda` pairs per layer** — that is PHPP's
three-path construction on the U-values worksheet, mirrored exactly.

### 7.0 Which tables actually exist — the corpus census

*(All five live captures, 2026-08-21. Presence is what `counts.tables_found` reports; the POC ships
only the subset it consumes.)*

| Key | Models | POC ships it | Note |
|---|---|---|---|
| `ihg_ud` | **5/5** | yes | |
| `vent_ud` | **5/5** | yes | |
| `tracker_data` | **5/5** | **no — deliberately** | telemetry with usernames (§7.0.2) |
| `assemblies_calc` | 3/5 | yes | ⚠ see below |
| `frames_ud` | 3/5 | **no — a gap, not an impossibility** (§7.0.1) | |
| `connections_ud` | 2/5 | yes | thermal-bridge psi values |
| `glazing_ud` | 2/5 | **no — a gap** (§7.0.1) | |
| `assemblies_ud` | **1/5** | yes | Adelphi only |
| `tfa_calc_ud` | 1/5 | no | Linde only |
| `layer_table_<id>` | 3/5 | yes | 25 on Linde, 6 on Bluff Reach, 5 on Wellington |

⚠ **`assemblies_calc` and `assemblies_ud` are mutually exclusive across the corpus.** Adelphi
(2.1.15) carries `assemblies_ud` and no `assemblies_calc`; Bluff Reach, Linde and Wellington carry
`assemblies_calc` and no `assemblies_ud`. **`250708` (2.1.15) carries neither**, which is why its
92 faces resolve to nothing in-model at all. A reader that looks for one key and stops has a 1-in-5
to 3-in-5 chance of finding nothing, depending which it picked — read **both**, and treat absence as
normal rather than as an error (§7.1's tiers).

⚠ **Two models carry `connections_ud` but only one has tagged edges.** Linde has a 10-row
connections table and **zero** thermal-bridge edges. A populated table is not evidence that anything
uses it, and an empty edge count is not evidence the user never defined bridges.

⚠ **Row count is not entry count.** designPH pre-allocates the `NNud` id space and leaves the rest
blank — `frames_ud` and `glazing_ud` are **99 rows on every model that has them**, `connections_ud`
is 100 on Bluff Reach and 10 on Linde, `assemblies_calc` is 82. What varies is how many rows carry a
non-blank `desc`:

| | rows | named |
|---|--:|--:|
| Bluff Reach `frames_ud` | 99 | **52** |
| Bluff Reach `glazing_ud` | 99 | **10** |
| Bluff Reach `assemblies_calc` | 82 | **6** |
| Bluff Reach `connections_ud` | 100 | **19** |
| Linde `frames_ud` | 99 | **54** |
| Linde `assemblies_calc` | 82 | **25** |
| Adelphi `assemblies_ud` | 17 | **13** |

**Count non-blank values, never records.** This is the same rule as §6.4's nil `*Auto` placeholders,
one level up: designPH writes the shape first and fills it in later.

### 7.0.1 ✅ `frames_ud` and `glazing_ud` — the window libraries ARE in the model

*(Decoded 2026-08-21 from `2414_Bluff Reach_COPY.skp` with the construct-nothing Marshal reader,
`planning/spikes/phase1/ruby_marshal.py`.)*

**This corrects a standing assumption.** It had been written down that frame and glazing ids
"travel unresolved" and that only their *names* were recoverable, from the inline DC option lists
(`DESIGNPH_FILE_FORMATS.md` §2.0). That is true of what the POC *ships*, and false about what the
model *contains*. The full numeric libraries are there:

```
frames_ud   TOKENS: id, desc, U_FL, U_FR, U_FB, U_FT,
                    width_L, width_R, width_B, width_T,
                    psi_GL, psi_GR, psi_GB, psi_GT,
                    psi_FL, psi_FR, psi_FB, psi_FT, chi_GT
  ["01ud", "Ikon AluPassive", 1.342, 1.342, 1.342, 1.342,
           0.103, 0.103, 0.103, 0.103, 0.027 ×4, 0.04 ×4, 0.0]

glazing_ud  TOKENS: id, desc, g_value, U_value
  ["01ud", "PH Glazing", 0.4, 0.54]
```

That is **PHPP's Windows worksheet, column for column**: a U-value and a frame width per edge
(Left/Right/Bottom/Top), the glazing-edge psi per edge (`psi_G*`), the installation psi per edge
(`psi_F*`), and `chi_GT` for the glazing carrier. `glazing_ud` is the g-value and U-value pair.

**Consequences:**

- ✅ **A window's frame and glazing are fully resolvable from the `.skp` alone** on any model that
  carries these tables — no installed CSV library needed. The DC's `frametypeid` / `glazingtypeid`
  are `NNud` ids into exactly these tables (§9.2.1).
- ⚠ **On the 2 of 5 models that carry neither**, they are not, and the DC option lists remain the
  only way to put a *name* to an id. So this is a tier system like §7.1's, not a solved problem.
- **It is a v1 opportunity, not a POC defect.** The POC deliberately ships neither table — apertures
  translate without them — but a PHPP-bound consumer needs precisely these numbers, and PHX/WUFI
  wants them too. Shipping them is a contract change (§9 of the contract), not new research.

### 7.0.2 ⚠ `tracker_data` is telemetry, and it names people

Present on **all five** corpus models, and never shipped by the POC. Each row is one calculation
run designPH performed:

| Column | What it is |
|---|---|
| `Q_to Q_tw Q_tb Q_v Q_s Q_i Q_n Q_h` | the heat-balance terms and heating demand of that run |
| `climate TFA windows surfaces thermal_bridges` | the model's headline figures at that moment |
| `timestamp` | a Ruby `Time` object |
| **`username`** | ⚠ **the OS login of whoever ran it** |
| `dPH_version` | the designPH build that ran it |

Measured across the corpus:

| Model | Rows | Names |
|---|--:|---|
| `250703 - Linde Residence` | **188** | `greg.fisher` |
| `2414 Bluff Reach` | 37 | `john.mitchell` |
| `2523 Wellington` | 21 | — |
| `adelphi-designph` | 17 | `ed.may` |
| `250708` | 10 | `ed.may` |

⚠ **This is a second, independent identity leak, and a different one from `DESIGNPH_FILE_FORMATS.md`
§4.5.** That one is filesystem paths left behind by imported components and the save location; this
is designPH's own analytics table, keyed by username, carrying a dated history of every calculation
someone ran — 188 of them on one project. Either alone would be enough to identify the author of a
`.skp`; together they give you a name, a machine, a directory tree and a work log.

**Rules that follow:**

- **Never ship `tracker_data` in an extraction**, and say why in the code rather than just omitting
  it. A future reader adding "ship every table we can decode" would otherwise reintroduce it.
- It is a **useful forensic tool for us** — it dates a model's real working history and names the
  designPH build, which is better evidence than the `designPH_version` stamp alone.
- ⚠ **Before any corpus data leaves this repo**, this is one of the two things to strip. It is not a
  DesignPH-PLUS defect; it is a property of every designPH model in existence.

### 7.1 Resolving a face's `assemblyID` — four tiers, two namespaces ⚠

*(Phase 1, `planning/RESULTS/PHASE-1_assembly-resolution.md`. Every reference in all 14 corpus
models was checked against every table those models define.)*

**`assemblyID` does not always name an assembly, and it is not always on a face.** There are two id
namespaces, and the entity's PHPP area group decides which applies — nothing in the key name says so:

| Area group | Carried by | `assemblyID` names | Carries |
|---|---|---|---|
| 15, 16, 17 — thermal bridges (entered as *lengths* on `Areas`) | ⚠ **`Sketchup::Edge`** | a **`connections_ud`** row | Psi-value, f_Rsi |
| everything else | `Sketchup::Face` | an assembly | a build-up, or only a U-value |

Read the area group **first**. Resolving a thermal bridge against the assembly table returns either
nothing or, worse, an unrelated assembly that happens to share the id — both namespaces use `NNud`.

⚠ **Thermal bridges are attached to edges, not faces** *(Phase 1 live run, 2026-08-19)*. **A
translator that iterates `Sketchup::Face` loses every thermal bridge in the model, silently.** Three
independent lines establish it on `2414 Bluff Reach.skp`:

| Evidence | Result |
|---|---|
| Walking **live faces** | 194 carry `areaGroupID`, against **293** records offline. 54 carry `assemblyID`, against **153**. Both gaps are **99** |
| That model's thermal-bridge count | groups 15 + 16 + 17 = 55 + 16 + 28 = **99** |
| Cached materials | the 99 thermal-bridge records **never** carry `Material`/`BackMaterial`, which designPH writes only when it repaints a *face* (§5.1) |

This also explains a discrepancy the offline reader could not: record counts exceed live face counts
by exactly the thermal-bridge population, not by accumulated historical state.

Assemblies proper then resolve in three tiers of decreasing reach:

| Tier | Refs (7 real models) | Readable |
|---|--:|---|
| `layer_table_<id>` in the model | 254 | **The full build-up** |
| `assemblies_*` header row only | 42 | Name, U-value, thickness. **No layers** |
| designPH's **installed** `data/phpp_assemblies_ud.csv` | 95 | Name and defaults, from *outside the model* |
| *(thermal bridges, via `connections_ud`)* | 141 | Psi-value, f_Rsi |
| **unresolvable** | **0** | — |

Two consequences worth stating plainly:

- **Under half of all references carry a build-up.** A translator that promises layers per surface
  will be wrong more often than not.
- **The model is not self-contained.** The `83ud`–`99ud` range is designPH's shipped default library
  and lives in the plugin folder, not the file. Both 2.2.29 and the 2.4.0 BETA ship the same range.
  Adelphi is the exception that shows the mechanism: it carries an `assemblies_ud` *snapshot* of that
  library inside the model, which is why its 42 references resolve where Linde `250708.skp`'s 92
  identical-looking ones do not.

### Costs and cautions

- **Not Ruby-only** — *(corrected by Phase 1; the earlier claim was that every non-Ruby reader is
  blocked)*. `planning/spikes/phase1/ruby_marshal.py` reads Marshal 4.8 in pure Python. The shipping
  extension is Ruby and decodes these natively, so this changes no architecture — it removes a
  stated portability constraint, and it is what let the corpus-wide analysis run offline.
- **`Marshal.load` executes.** It can instantiate arbitrary classes. Fine on your own models;
  do not run it over files from strangers. The Python reader above constructs nothing — an unknown
  class becomes an inert record of its name — so it is the safer tool for a file of unknown origin.
- **Marshal is version-sensitive.** Plain Arrays/Strings/Symbols/Floats round-trip fine across Ruby
  versions, which is all these tables use. Do not assume that holds if designPH ever dumps a custom class.
- Not all blobs are tables — `vent_ud` and `ihg_ud` decode to a flat array with the `:TOKENS` row
  at the *end*, not the start. Do not assume row 3 is the header.

---

### 7.2 ⚠ Multi-section assemblies — three parallel paths, and ISO 6946's mean of limits

*(Settled 2026-08-21 against designPH 2.4.0 BETA's own U-/R-value calculator, on Linde `06ud`.)*

designPH mirrors PHPP's **three parallel construction paths**: `layer_table_*` carries
`desc1/lambda1`, `desc2/lambda2`, `desc3/lambda3` per layer, and the path **areas** live on the
*assembly* header in `assemblies_calc` as `surf2_percentage` / `surf3_percentage`.

| | |
|---|---|
| **The stored values are PERCENTAGES** | `06ud` stores `21.875`; the dialog reads **Surface percentage 2: 21.88** |
| **Section 1 is the unstored remainder** | the dialog reads **78.12** = 100 − 21.88 |
| ⚠ **Small values are small percentages, not fractions** | the same column holds `0.0625` and `0.09375` — 0.06 % and 0.09 %, essentially unframed |

That last row is the trap. `0.0625` is exactly `1.5/24` and `0.09375` exactly `1.5/16`, so they read
convincingly as *fractions* at standard US stud spacings — a pattern that fits three numbers and is
wrong. Reading them that way applies a hundredfold framing correction to assemblies that have almost
none.

**The U-value method is ISO 6946 §6.7, not an area-weighted lambda.** The answer is bracketed and
the mean taken:

* **upper limit** — each section is a complete path, its layer resistances summed, the paths
  combined in parallel by area. No lateral heat flow.
* **lower limit** — each *layer* gets an area-weighted conductivity, then the layers are summed.
  Free lateral heat flow.
* `R = (R_upper + R_lower) / 2`, and `(R_upper − R_lower) / 2R` is the **Error %** designPH prints
  next to the U-value — 2.75 % on `06ud`, reproduced exactly.

Films (`R_in`, `R_out`) are **inside** designPH's assembly U-value. honeybee's `u_value` is
material-only, so the two differ even on an unframed assembly — 0.004–0.005 W/m²K on Linde's, which
is enough on its own to fail a ±0.005 comparison.

**How common:** only **4 of 82** `assemblies_calc` rows on Linde carry a non-zero section
percentage; Wellington and Bluff Reach carry none. 49 % of Linde's *layers* have a `lambda2`, but a
`lambda2` with no area is not a framed layer — counting those overstates the population fivefold.

## 8. Rules and edge cases

### 8.1 Attributes attach to entity *identity*, not geometry

This is the big one.

- **Split a face** → the new face has no dictionary. The assignment is gone.
- **Explode a group** → the group's own dictionary is gone.
- **Erase and redraw** → gone.
- **Push/pull creating new faces** → the new faces are unclassified.

This is why `designPH/rbe/designPH_observers.rbe` and the two
`designPH_notification_observers_*` libraries exist: the plugin watches for edits and repairs
assignments. **With designPH uninstalled the data stays put but stops self-maintaining** — the model
is readable but will silently drift out of sync with the geometry if anyone edits it.

### 8.2 Component definitions vs instances

Window components are Dynamic Components (see §9). Attributes on a **definition** are inherited by
every instance; attributes on an **instance** are per-placement. Reading only one of the two will
give wrong answers. designPH puts geometry-driving DC values on instances (`lenx`, `leny` vary per
window) and the shared template on the definition.

### 8.3 Version keys are not cleaned up

Wellington carries two `designPH_version` values (`2.1.10` and `2.2.29`) and two generations of face
keys simultaneously. **designPH does not purge superseded data.** A `.skp` is an accumulation, not a
snapshot. Any parser must tolerate contradictory keys on the same face.

### 8.4 The dictionary is unprotected

`DesignPH_dict` is an ordinary dictionary name. Anything — including our own tools — can overwrite
it. If we ever write into it, we must be certain we are not corrupting the plugin's state. **Strong
default: read `DesignPH_dict`, write only to our own namespace.**

### 8.5 Units

SketchUp's internal length unit is **always inches**, regardless of display units. `face.area`
returns square inches. designPH's stored values are a mix: DC values are inches
(`framewidth: 4.330708661417323` = 110 mm), while its own table values are **SI/PHPP units**
(`lambda`, `R_in`, `Psi_value`, thickness in mm). Do not assume consistency — check per field.

### 8.6 Transformations

A face inside a group is stored in that group's *local* coordinates. `face.area` gives the local
area; `face.area(transformation)` gives the true one. Any recursive walk must accumulate
transformations or every scaled group will silently lie.

### 8.6.1 ⚠ A recursive walk costs *placements* × faces, and on a real model that is a million

*(Measured 2026-08-21: Adelphi, live, `Dph.here` → 3656 ms.)*

Phase 0 estimated Adelphi at "~8037 live faces". A correct recursive walk — descending into every
group and component instance, per placement, as the id scheme requires (§8.2) — visits
**1,023,558**. Of those, **1,022,117** are untagged faces on `Layer0`: 3D Warehouse content
(furniture, trees, cars) placed many times over.

The multiplication is not a bug; each placement genuinely *is* a distinct surface, which is why the
POC's ids are path-qualified. But two things follow:

- **A "faces walked" census reads like the model has a million faces.** It does not; it has ~8000
  unique faces placed many times. Report both if the number is shown to a user.
- **~3.7 s of the export is the walk.** Tolerable, and the obvious v1 optimisation is to memoise per
  *definition*: a definition whose subtree contains no `DesignPH_dict` anywhere can be skipped on
  every subsequent placement, with the untagged census multiplied rather than re-walked. On Adelphi
  that would remove essentially all of the million.

### 8.6.2 ⚠ Real designPH models contain degenerate geometry, and it comes through faithfully

Adelphi, from the POC's first live export, all confirmed against honeybee's own `ValidateModel`:

| What | Example |
|---|---|
| A **sliver triangle** | `TFA_face_012` — 3 points, **1.7 cm²**, two vertices 0.42 mm apart |
| A **zero-width spur** | `face_3281_1710` — 7 points where vertices 2 and 4 are the *same point* and vertex 3 runs 0.8 m out and straight back |
| **Sub-micron non-flatness** | two group-1 faces with a **12 µm** z-spread — invisible at any modelling tolerance, and enough to fail a downstream horizontality test set at 1e-7 m |

None of these is a translator defect; they are what the model contains. But a translator has to
*decide* about them rather than discover them at the far end of the pipeline, and "report, don't
guess" means naming them rather than silently repairing. The 12 µm case is the sharp one: it is
noise by any reasonable standard, and it cost 368 m² of TFA in the first run
(`HONEYBEE_STACK.md` §4, `is_horizontal`).

**⚠ And there is more of it than the first pass found — the examples above are examples, not a
census.** With a degeneracy scan on every classified face (2026-08-21), Adelphi's 82 report:

| | count |
|---|---|
| faces with a boundary edge shorter than 1 mm | **8** |
| faces whose boundary **revisits a point** (spur or self-touch) | **7** |
| faces under 10 cm² | 1 |

The revisit count is the one to notice: **every edge of a spur is long**, so a short-edge test does
not find it, and `face_3281_216` alone revisits 21 points. Finding one example by hand and writing it
down reads like a census afterwards; it is not one.

**The decision, taken 2026-08-21: report and carry, repair nothing.** A classified face that
vanished would break *82 of 82* — the first number any reader checks — and 1.7 cm² moves no area
total, so dropping costs more than it saves. Each degenerate face is named in the report with what is
wrong with it. The single exception is the TFA extrusion, which genuinely cannot proceed on some of
them; `spaces` drops only the face honeybee itself names, and names it back.

### 8.7 `.skp` keeps prior state

`model.dat` inside a `.skp` contains more than the current model state — Wellington yields key
counts (343 `tempZoneAuto` for 103 classified faces) that exceed the live entity count. Treat raw
binary scans as an *upper bound* / historical union, not as the current model. **For current state,
read through the Ruby API.**

---

## 9. Windows are Dynamic Components, not designPH data

Window geometry does **not** live in `DesignPH_dict`. It lives in SketchUp's own
`dynamic_attributes` dictionary on the component instance. From a live dump:

```json
"dynamic_attributes": {
  "frametypeid":   "01ud",
  "glazingtypeid": "01ud",
  "framewidth":    4.330708661417323,
  "framewidthbot": 4.330708661417323,
  "lenx": "225.18749999999997",
  "leny": "390.1875",
  "d_reveal": "12.5",
  "o_reveal": "11",
  "area": 56.687207693906245
}
```

`frametypeid` / `glazingtypeid` are the **join keys** into the frame and glazing libraries — the same
`NNud` / `NNNNwi03` ID space used everywhere else (see `DESIGNPH_FILE_FORMATS.md` §3). The presence
of `frametypeid` is also the **only reliable predicate for "this instance is a designPH window"** —
definition-name matching fails because users rename.

### 9.1 ✅ The definition's structure — settled live, 2026-08-21

*(`DphWin.inspect_one("403U")` on `adelphi-designph_COPY`, definition
`designPH_Window_Simple 1.2`. Raw dump in `planning/POC/RESULTS/POC-2_results.md`.)*

```
definition "designPH_Window_Simple 1.2"
  4 Edge, 1 ComponentInstance, 4 Group          <- NO faces at this level
  COMPONENT "WinFrameSimple#2"
    9 Group
      GROUP 223062 -> 1 Face  0.5226 m²  normal [0,0,-1]   <- THE GLAZING
      GROUP 223063..223070 -> frame members, 4-6 faces each, 0.005-0.089 m²
  GROUP 222871 -> 1 Face 0.0867 m²      (reveal/jamb)
  GROUP 222872 -> 1 Face 0.0867 m²
  GROUP 222873 -> 1 Face 0.1028 m²
  GROUP 222874 -> 7 Faces 0.004-0.150 m² (sill assembly)
```

Three things follow, and the second is the one that matters:

**1. `definition.entities.grep(Sketchup::Face)` returns `[]`.** The faces are two and three levels
down. A flat read finds nothing — which is exactly what the POC's first live export did, reporting
all 46 apertures as "could not identify a panel face". **Walk definitions recursively.**

**2. ⚠ The largest face is the GLAZING, not the rough opening.** 0.5226 m² is
`(lenx − 2·framewidth) × (leny − 2·framewidth) × 0.00064516` to four decimals — the glass, net of
frame on all four sides. The rough opening is `lenx × leny` = **0.891 m²**.

> A "take the definition's largest face" heuristic therefore produces a window **41 % too small**,
> and it does so *plausibly* — the geometry is real, in the right place, the right shape. Nothing
> downstream would flag it. For a honeybee `Aperture`, which represents the whole window with frame
> and glazing carried as PH properties, the **rough opening** is the correct rectangle.

**3. The local frame is XY with normal ±Z.** The glazing face's normal is `[0, 0, −1]` in definition
space, so the rough opening is the local rectangle
`(0,0,0) → (lenx,0,0) → (lenx,leny,0) → (0,leny,0)`, taken through the **world** transform (§9.3).
Verified against the host: the world origin of `403U` lands on its host plane at parameter 0.871
along the wall, and within its z-extent.

⚠ **That the origin is on the plane does not say it is a *corner*.** A rectangle centred on the
origin also puts its centre on the plane, and the two differ by half a window — a plausible-looking
error of exactly the kind this section keeps collecting. **Measured, 2026-08-21**
(`planning/spikes/poc/solve_window_parent.py`): the parent transform is recoverable from the first
capture alone, because every window's local +Z must map onto its host's world normal (Kabsch over all
46) and every local origin must land on that host's world plane (least squares). The solve reproduces
§9.3's independently measured parent translation and 403U's world origin to four decimals, and then
answers the question directly:

| convention | windows inside their host polygon |
|---|---|
| **corner at the origin, `+x`/`+y`** | **46 / 46** |
| centred on the origin | 23 / 46 |
| corner at the origin, `+x`/`−y` | 15 / 46 |
| corner at the origin, `−x`/`−y` | 12 / 46 |

Two by-products worth keeping: every window origin lies **0.000 m** from its host plane (so a
non-trivial off-plane distance downstream is a coordinate-space bug, not a reveal), and the whole
answer came off a capture that was already on disk — **no SketchUp session, no re-run**. A recorded
capture holds more than the run that produced it asked of it.

### 9.2 ⚠ `lenx` × `leny` is NOT the stored `area` — and `area` is probably stale

The dump at the top of this section satisfies `lenx × leny × 0.00064516 == area`, and that single
sample was previously taken as confirming a per-field unit table. **Across Adelphi's 46 windows it
holds on only 20.** Ratios of `lenx·leny·0.00064516` to `area` run **0.44 to 1.66** — `area` is
sometimes larger than the product and sometimes smaller.

Ruled out by measurement:

- **Instance scaling.** All 46 transforms are unscaled — one distinct axis-length triple, exactly
  `(1.0, 1.0, 1.0)`.
- **Frame deduction.** `(lenx−2·fw)(leny−2·fw)` is the *glazing* (0.5226 m² here); `area` is
  0.8203 m², between glazing and gross and matching neither. No combination of `framewidth`,
  `framedepth` or `revealdepth` reproduces it.

**The likely explanation is staleness, and it follows from something already documented in this
section:** `area` is a **DC formula output**, and designPH's custom formula functions
(`designphget*`) only evaluate while the plugin is loaded and recomputing. Adelphi was last written
by **2.1.15** and is being opened under **2.2.29 BETA**. A window resized since its last recompute
keeps an `area` from the old size — which produces ratios on both sides of 1.0, exactly as observed.

⚠ **Treat every formula-driven DC value as potentially stale.** `lenx`/`leny` are the component's
actual size and stay current; `area` is derived and does not. **Do not use `area` for anything**;
compute from `lenx`/`leny` and say so.

Its *type* is unstable too: `String` on Adelphi, `Float` in the earlier dump.

### 9.2.1 The full DC key set, with types (Adelphi, 2026-08-21)

| Key | Type | Note |
|---|---|---|
| `frametypeid`, `glazingtypeid` | String | The join keys. `frametypeid`'s presence is the window predicate |
| `frametype`, `glazingtype` | String | Duplicates of the ids on this model |
| `lenx`, `leny` | **String** | Inches. The rough opening. **The only dimensions to trust** |
| `framewidth`, `framewidthbot`, `framewidthl`, `framewidthr`, `framewidthtop` | **Float** | Inches. Per-edge frame widths — PHPP takes all four |
| `framedepth`, `revealdepth` | String | Inches |
| `d_reveal`, `o_reveal` | String | Inches. The PHPP reveal shading pair |
| `instcill`, `insthead`, `instleft`, `instright` | String `"0"`/`"1"` | Per-edge install flags — these are PHPP's Psi-install conditions |
| `area` | String **or** Float | ⚠ Derived, stale, unusable — see §9.2 |
| `_frametype_options`, `_glazingtype_options` | String | ★ see below |

★ **`_frametype_options` and `_glazingtype_options` carry the library inline**, as SketchUp DC
option lists. ⚠ **Measured 2026-08-21: they are 39,685 and 5,230 characters, and every one of
Adelphi's 46 windows carries a byte-identical copy** — 2.07 MB if shipped per window, 45 KB
deduplicated. They are library data stored on a window, and the extraction contract treats them as
model-level for exactly that reason (`CONTRACT_extraction-json.md` §5.1). The frame list runs to some
500 entries, down to real products:

```
"&PH-FRAMES: average thermal quality=01ud…"
"&PH Glazing=01ud&Single glazing=92ud&Do…"
```

That is a **name-for-id mapping stored in the model itself**, for the frame and glazing libraries
that `DESIGNPH_FILE_FORMATS.md` §3 otherwise says live only in the installed CSV library. It will not
give U-values or g-values, but it names the ids — enough to make a report say
*"PH Glazing (01ud)"* rather than *"01ud"*, with no library on disk. The POC does exactly that.

⚠ **designPH also writes a placeholder list, `&Launch designPH to edit=01ud&`, on some definitions**,
and it claims `01ud` just as the real library does. Merging the two by "longest name wins" picks the
**placeholder** — *Launch designPH to edit* is 23 characters against *PH Glazing*'s 10 — and
silently un-names the whole library while looking like it resolved. Merge by how many ids the *list*
names, not by the length of the *name*.

### 9.3 ⚠ `instance.transformation` is relative to the PARENT, not the world

The instance transform is the component's placement **within its enclosing group**, and on a real
model the parent is neither identity nor a pure translation. Measured on `403U`:

| | translation (m) |
|---|---|
| `instance.transformation` — the local one | `[0.9163, 0.0000, 14.2746]` |
| parent accumulated | `[-3.2414, 8.1321, -2.9972]` |
| **world = parent × instance** | `[-2.9319, 7.2696, 11.2774]` |

Note the world translation is **not** the sum: the parent group is rotated in plan, so only `z` adds
(11.2774 = 14.2746 − 2.9972) while `x` and `y` do not. Anyone tempted to "just add the offsets" gets
a window metres away from its wall.

The world origin is correct: it lands on host `2375`'s plane at parameter **0.871** along the wall
and inside its z-extent. The local one sits **1.2 m** off that plane, and across Adelphi's 46
windows the local origins miss their hosts by **1.2 m to 3.3 m**.

**Ship the accumulated transform, or ship the parent alongside.** This is a trap specifically
because the two are the same object type and differ only by where they were read.

---

---

## 10. Reading designPH data without designPH

Two supported routes and one unsupported one.

1. **SketchUp Ruby API** (best — reflects true current state):
   ```ruby
   model.attribute_dictionary("DesignPH_dict").keys
   face.get_attribute("DesignPH_dict", "areaGroupAuto")
   ```
   This is what `bt_inspector` does. No designPH needed, only SketchUp.

2. **SketchUp C SDK** — headless, no SketchUp install. The right answer for a batch pipeline.

3. **Direct binary parse** — no SketchUp at all. Works, and is how much of this record was produced,
   but it is reverse-engineered and unsupported. See `DESIGNPH_FILE_FORMATS.md` §4 and
   `tools/skp_attr_dump.py`. Use it for reconnaissance, not production.

---

## 11. Assessment — what is worth copying

**Good:**
- One dictionary name, two attachment levels. Easy to find, easy to strip, easy to reason about.
- Self-describing tables (`:TOKENS`) in both Marshal and CSV. Schema travels with data.
- Caching the user's original materials before repainting.
- The `descNameAuto` / `descName` / `descNameFreeze` derived / override / lock triple (§5.2).
- Storing raw PHPP area-group numbers rather than a private enum — no translation layer at export.
  This pays off twice: it also makes `tempZone` derivable rather than stored data (§5.3.1), and gives
  any reader a free consistency check.

**Bad / would not copy:**
- `Marshal` for persistence. Ruby-only, executes on load, and version-fragile. JSON would have cost
  nothing here given the data is all primitives.
- Never purging superseded keys, so models accumulate contradictory generations with no migration marker.
- Splitting one assembly across `assemblies_calc` + `layer_table_<id>` instead of nesting it.
- Depending on registered DC functions for geometry, which breaks when the plugin is absent.

---

## 12. Open questions

*(Re-ranked after the Phase 1 per-face analysis, 2026-08-19.)*

1. **`faceTypeAuto = 'xi'`** — the last undecoded face-level value. 25 faces corpus-wide, *always* on
   an untagged face, never beside a classified area group. `'xo'` and `'i'` are decoded (§6.4).
2. **`tempZoneAuto = "split A/B"`** — what does designPH do at export with a face marked as split
   between two temperature zones? *(The rest of the `tempZone` value space is decoded in §5.3.1.)*
3. **The `101ud`+ id range** — Bluff Reach and Holmes use it for `connections_ud` (§7.1), but nothing
   on disk explains where the numbering starts. Cosmetic unless a model ever uses it for an assembly.
4. **3.0 schema** — everything here is 2.x. Unknown whether 3.0 migrates, renames, or breaks.
   Phase 4.
5. **Export path** — we never examined what `designPH_data_pppwrite_*` actually emits. If we ever want
   to write PHPP directly, that is the thing to characterise next.

**Closed by Phase 1's live runs (2026-08-19):**

- ~~Window hosting~~ — **`glued_to` resolves 46 of 46** on Adelphi, so host lookup is solved and
  geometric projection is only a fallback. But `definition.behavior.cuts_opening?` turned out to be a
  **capability of the component definition, not a fact about the host**: it is `true` on all 46
  windows while only **1 of 16** host faces actually has an inner loop.
  ⚠ **Superseded 2026-08-21:** `face.loops.size > 1` is not the replacement either — it is true on
  only **2 of the 16** hosts, because a glued opening reduces `face.area` without creating a loop
  (§5.0). Use `glued_to`, which resolved 46 of 46 twice.
- ~~The untagged-face shading filter~~ — **refuted, and shading geometry left v1 scope.** Both
  remaining candidate rules failed live: `faceTypeAuto` splits untagged faces roughly 60/40 against
  the envelope bounding box, the two signals disagree with each other, and `faceTypeAuto` is absent
  entirely from two of the seven real models. v1 will **ask the user which SketchUp tags are
  shading** rather than guess (PRD §7.2).
- ~~`*Auto` vs `*ID` precedence~~ — the two are **mutually exclusive per face**, so the rule is a
  coalesce and there is no precedence (§6.5). Live confirmation still staged.
- ~~Whether `*Auto` can hold a value where `*ID` holds none~~ — **yes**, on 301 faces in six of seven
  real models, which is why "prefer `*ID`" was also wrong (§6.5).
- ~~Where assembly build-ups live~~ — four tiers, two id namespaces, **zero unresolvable references**
  corpus-wide, but only 254 of 532 carry a build-up (§7.1).
- ~~`tracker_data`~~ — a per-calculation run log: `Q_*` demands, climate, TFA, window/surface counts,
  timestamp, username, designPH version. Bookkeeping; nothing the translator needs.
- ~~`areaGroup` → `tempZone` is inference~~ — now observed per-face: 7931 pairs, 0 disagreements.

**Closed by Phase 0:**

- ~~Area group 14~~ — a user-defined surface slot, not a fixed PHI category (§5.3).
- ~~Area group 18~~ — "Building element towards neighbour" (§5.3).
- ~~`tempZoneAuto`/`tempZoneID` `'i'` vs `'I'`~~ — `'I'` is the neighbour condition, `'i'` is
  designPH's untagged marker. Whole value space decoded (§5.3.1).
- ~~`TFA_rf` full value set~~ — at least `0`, `0.3`, `0.5`, `0.6`; confirmed not a two-state flag.
  *(That it is the PHPP TFA reduction factor is still inference, not observation.)*
