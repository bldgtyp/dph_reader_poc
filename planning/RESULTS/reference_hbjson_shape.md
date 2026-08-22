# Phase 0 §0.4 — Reference HBJSON: validation and shape

Source: `_adephi_st_example_files/adelphi-honeybee-json.hbjson`
Declared honeybee schema version **1.53.1**, units **Meters**, tolerance **0.001**.

> ⚠ **Shape reference, not an equality target.** This file came from the Rhino route: 6 solid Rooms with solved interior adjacency. v1 emits one non-solid Room by design (PRD §8.1). Use it to check our output is well-formed and plausibly populated — never to assert equality.

## Inventory

| Collection | n |
|---|---|
| rooms | 6 |
| faces | 52 |
| apertures | 44 |
| doors | 0 |
| ph spaces | 38 |
| orphaned shades | 1287 |
| constructions | 56 |
| materials | 66 |

## 1 — Schema validation

### Core — `honeybee-schema==1.53.1 (pydantic 1.x)`

**INVALID** — 5587 raw errors across 147 distinct failing objects.

| Failing container | Distinct objects |
|---|---|
| `properties.energy.constructions[].materials[]` | 44 |
| `properties.energy.constructions[]` | 44 |
| `properties.energy.materials[]` | 22 |
| `properties.energy.global_construction_set.materials[]` | 12 |
| `properties.energy.schedules[]` | 9 |
| `properties.energy.hvacs[]` | 6 |
| `rooms[]` | 6 |
| `properties.energy.global_construction_set.constructions[]` | 2 |
| `properties.energy.shws[]` | 1 |
| `properties.energy.program_types[]` | 1 |

The raw error count is inflated by pydantic-1 union expansion: each non-conforming material or construction reports once per candidate branch of its union. The object count is the honest figure.

**No error touches geometry, boundary conditions, apertures, shades, or `properties.ph`.** Every failure is inside an honeybee-energy payload.

**Consequence for PRD §11.** Validating v1 output against `honeybee-schema` remains a sound acceptance gate: the parts that fail here are energy payloads v1 does not write. Do not weaken the criterion on the strength of this result — scope it to the core geometry and PH payloads.

### PH extensions — `honeybee-ph-schema`

Version **0.1.0**, imported from `/Users/em/Dropbox/bldgtyp-00/00_PH_Tools/honeybee-ph-schema` (not published to PyPI).

| Payload path | Model | Checked | Failed |
|---|---|---|---|
| `rooms[].properties.ph` | `PhRoomProperties` | 6 | 0 |
| `rooms[].faces[].properties.ph` | `PhFaceProperties` | 52 | 0 |
| `rooms[].faces[].apertures[].properties.ph` | `PhApertureProperties` | 44 | 0 |

**How much does this prove?** Not much yet:

| Schema model | `extra` policy | Required fields |
|---|---|---|
| `PhRoomProperties` | `allow` | *none* |
| `PhFaceProperties` | `allow` | *none* |
| `PhApertureProperties` | `allow` | *none* |

Every field is optional and every model allows extra keys, so a payload of `{}` validates. `honeybee-ph-schema` at v0.1.0 is a **contract stub, not an acceptance gate**. PRD §11 should not lean on it until it tightens.

## 2 — Where PH data lives

The target shape for the translator. Paths verified present in this file.

| Path | Holds | Keys / value |
|---|---|---|
| `properties.ph` | model-level PH properties — `ModelPhPropertiesAbridged` | `team`, `bldg_segments`, `type`, `id_num` |
| `properties.ph.bldg_segments[]` | building segments: certification, set points, thermal bridges | `summer_hrv_bypass_mode`, `non_combustible_materials`, `user_data`, `thermal_bridges`, `num_dwelling_units`, `co2e_factors`, `set_points`, `phius_certification`, `name`, `mech_room_temp`, `identifier`, `site`, `phi_certification`, `source_energy_factors`, `num_floor_levels` |
| `properties.ph.team` | designer / customer / building / owner contact blocks | `designer`, `customer`, `building`, `owner` |
| `rooms[].properties.ph` | room-level PH properties — `RoomPhPropertiesAbridged` | `specific_heat_capacity`, `spaces`, `ph_foundations`, `ph_bldg_segment_id`, `type` |
| `rooms[].properties.ph.spaces[]` | PH `Space`s — the TFA/iCFA carrier | `volumes`, `user_data`, `number`, `wufi_type`, `properties`, `name`, `identifier`, `quantity` |
| `rooms[].properties.ph.spaces[].volumes[]` | space volumes: `avg_ceiling_height`, `floor` | `user_data`, `avg_ceiling_height`, `geometry`, `identifier`, `display_name`, `floor` |
| `rooms[].properties.ph.ph_bldg_segment_id` | link from room to its building segment | `'05a76e5a-dba7-4420-807a-2726ed006048'` |
| `rooms[].faces[].properties.ph` | face PH properties — `FacePhPropertiesAbridged` | `type`, `id_num` |
| `rooms[].faces[].apertures[].properties.ph` | aperture PH properties: shading factors, install depth | `id_num`, `default_monthly_shading_correction_factor`, `winter_shading_factor`, `summer_shading_factor`, `install_depth`, `variant_type`, `type` |
| `orphaned_shades[].properties.ph` | shade PH properties — `ShadePhPropertiesAbridged` | `type`, `id_num` |

### `Space` in detail — the TFA carrier

| Key | Example | Note |
|---|---|---|
| `volumes` | list[1] | one or more `Volume`s; each carries `floor` and `avg_ceiling_height` |
| `user_data` | `{…}` |  |
| `number` | `'000ST'` | user room number, e.g. `000ST` |
| `wufi_type` | `99` | WUFI/Phius room-use enum |
| `properties` | `{…}` |  |
| `name` | `'STAIR'` | user room name, e.g. `STAIR` |
| `identifier` | `'665598bc-fafe-46ae-ac28-8f8b8b0f590a'` |  |
| `quantity` | `1` | multiplier for repeated identical spaces |

## 3 — The 1287 orphaned shades

PRD §7.2 proposes that untagged designPH faces (`areaGroupID='n'`) have a natural home as orphaned shades, and asks Phase 0 to confirm it by comparing counts and coordinates.

| Observation | Value |
|---|---|
| Orphaned shades in the reference | 1287 |
| Untagged faces in `adelphi-designph.skp` | 1359 |
| All shades `is_detached` | True |
| Geometry types | {'Face3D': 1287} |
| Vertices per shade | {3: 711, 4: 551, 6: 11, 5: 10, 7: 3, 8: 1} |
| Shade bounding box (m) | X[24.6, 74.8] · Y[-30.7, 19.3] · Z[-1.1, 18.8] |
| Room bounding box (m) | X[36.4, 51.1] · Y[-10.8, -1.5] · Z[-3.0, 16.0] |
| Shades entirely inside the room bbox | 0 |
| Shades carrying `properties.ph` | 1287 / 1287 |

### Verdict — confirmed as a destination, refuted as a blanket rule

**The destination is right.** Exterior context geometry has a well-formed home in HBJSON as `orphaned_shades` with `is_detached: true` and a `ShadePhPropertiesAbridged` block. Emitting it costs nothing and lets Ladybug compute shading downstream. Promote to v1 scope.

**The source mapping is not.** These shades are *purely exterior site context*: all 1287 are detached, and **0** of them fall inside the building's bounding box — they span roughly 50 m × 50 m around a 15 m × 9 m building. The untagged designPH faces are a mixed bag: `00_Context/DESIGNPH_DATA_MODEL.md` §6 characterises them as *interior partitions, furniture, and context*. Mapping every untagged face to an orphaned shade would inject interior partitions and furniture into the shading model and silently corrupt any downstream shading calculation.

**The count similarity is not evidence.** 1287 vs 1359 is close, but the two sets have different provenance — this HBJSON came from the Rhino route, not from `adelphi-designph.skp`. The offline `.skp` reader reads attribute dictionaries only, not geometry, so a coordinate-level comparison is not possible without SketchUp.

**Carried to Phase 1:** define the filter that separates shading-relevant exterior geometry from interior clutter, and confirm it against live geometry in SketchUp. Until that filter exists, untagged faces must be *reported*, not exported.

