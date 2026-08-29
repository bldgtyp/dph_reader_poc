# Data Contracts — designPH to HBJSON, end to end

The shapes data actually takes at each hop, and the rules that govern each conversion. This is the
translation spine: [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) says what designPH stores,
[`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) says what honeybee wants, and this says how one becomes the
other.

Everything below was exercised end to end in SketchUp — first on 2026-08-19 against
`adelphi-designph.skp`, and on **2026-08-21 across the whole five-model corpus**: 545 of 545
classified faces, 239 of 239 windows, 99 of 99 thermal bridges, TFA on the three models that carry
it. Where a claim here comes from one model, it says so.

⚠ **Everything in §2's schema is contract v2** (`planning/POC/CONTRACT_extraction-json.md`, frozen
2026-08-21). v1 differed in three places and each one was a real bug: the window transform, the
aperture rectangle, and the frame/glazing libraries shipping per-window.

---

## 1. The pipeline

```
Sketchup::Face + DesignPH_dict          Ruby, in-process
        │  read, coalesce, convert units
        ▼
face-record JSON                        Ruby → JS, via execute_script
        │  JSON string across the bridge
        ▼
Python dict                             JS → Python, via a JSON string
        │  Face3D → Face → Room → Model
        ▼
HBJSON                                  Python → JS → Ruby → disk
```

**One serialisation format spans all three languages: a JSON string.** Not Ruby objects, not
Pyodide proxies. Proxies leak (`.destroy()`), and a string is the only thing all three hops agree on.

## 2. Hop 1 — reading a face

### 2.1 Hard rules that govern the read

1. **Coalesce the key generations; never version-key them.** Read `face[*ID] or face[*Auto]`. The
   two are **mutually exclusive per face** across all 14 corpus models, and both generations hold
   real data on real models regardless of the version stamp. A rule keyed on the version stamp loses
   envelope data silently. (`DESIGNPH_DATA_MODEL.md` §6.5)
2. **Type-check every read.** `areaGroupID` is a `String` on 1359 of 1441 faces in the primary
   corpus model — most often `'n'`, meaning unassigned. Nothing about value types is guaranteed.
3. **Read-only.** Never write to `DesignPH_dict`. v2 authoring writes to `DesignPHPlus_dict`.
4. **Report, don't guess.** Any face, window, edge, or assembly that cannot be translated is named
   in a report. Silent loss is the failure mode that would most damage a free tool.

⚠ **The fallback key names are asymmetric, and the obvious guess is wrong.** `areaGroupID` and
`tempZoneID` fall back to `areaGroupAuto` / `tempZoneAuto` — **no `ID`** — while `assemblyID` falls
back to `assemblyIDAuto`, which keeps it. `areaGroupIDAuto` does not exist; reading it finds nothing
and loses `250708`'s 92 assemblies in silence. Adelphi masks it, because every one of its classified
faces carries `areaGroupID`. The Phase 3 spike shipped exactly this typo
(`planning/POC/RESULTS/POC-2_results.md` finding 50), **and this document carried it too until
2026-08-28**, when the HEADLESS Spike-A expected-value derivation hit it again from the offline
baseline (Linde is the model that needs both keys: 66 + 8 = its 74 classified faces).

```ruby
group     = dict["areaGroupID"] || dict["areaGroupAuto"]     # no "ID" on the fallback
zone      = dict["tempZoneID"]  || dict["tempZoneAuto"]      # likewise
assembly  = dict["assemblyID"]  || dict["assemblyIDAuto"]    # ...but this one keeps it
```

### 2.2 Units

**SketchUp's internal unit is always inches**, whatever the model displays.

| | |
|---|---|
| length | `× 0.0254` → metres |
| area | `× 0.00064516` → m² |

`Length#to_f` returns inches. `face.area(transform)` returns in².

### 2.3 Geometry

Recurse into groups and components carrying the accumulated transformation, or nested faces land in
the wrong place:

```ruby
point = vertex.position.transform(accumulated_transform)
```

`face.outer_loop.vertices` gives the outer boundary. **Inner loops are a separate matter** — record
them and handle holes deliberately.

### 2.3.1 ⚠ Gross vs net area — the two numbers, and which one to ship

*(Settled 2026-08-21 by a 16-of-16 exact match on Adelphi. `DESIGNPH_DATA_MODEL.md` §5.0.)*

| Source | What it measures |
|---|---|
| a polygon built from `outer_loop` + `inner_loops` | **gross** — modelled holes subtracted, glued window openings **not** |
| `face.area(transform)` | **net** — modelled holes *and* glued window openings both subtracted |

Both are correct. They differ on exactly the window host faces, and by exactly the window areas.

**Ship the loops; carry `face.area` only as a cross-check.** That is what honeybee and PHPP both
want: an `Aperture` is a *child* of its `Face`, so the consumer subtracts. Shipping the net area as
if it were the wall would double-subtract every window.

⚠ **The cross-check will therefore fire on every window host, and that is correct behaviour** — do
not "fix" it by switching to `face.area`. On Adelphi it fires on 16 of 82 faces, by 0.3–3.9 m² each.

### 2.3.2 ⚠ World space is the contract's space — including transforms

Every geometry field crossing the seam is **world** coordinates, in metres. The trap is that
`ComponentInstance#transformation` is **parent-relative**, so shipping it "verbatim" alongside
world-space face loops mixes two coordinate systems in one document. On Adelphi that put every
window 1.2–3.3 m from its own host plane. Ship `accumulated_parent * instance.transformation`.
(`DESIGNPH_DATA_MODEL.md` §9.3.)

### 2.4 The face-record schema

⚠ **Superseded as a schema.** The shape below is the Phase 3 *spike*'s, kept because it is the
minimum that proved the seam works. The real one is
[`planning/POC/CONTRACT_extraction-json.md`](../planning/POC/CONTRACT_extraction-json.md), frozen at
**v2**, and it differs in ways that matter — ids are **path-qualified** (`face_<parents…>_<pid>`,
not `face_<entityID>`, because an entityID names an entity *inside its definition* and a component
placed twice is two envelope surfaces); inner loops are **carried**, not flagged; and edges,
windows, tables and the model's libraries all travel too.

```jsonc
{
  "model_name": "adelphi-designph_COPY",
  "units": "Meters",
  "faces": [
    {
      "id": "face_9153",              // ⚠ v2: path-qualified — see contract §2.1
      "area_group": "8",              // ⚠ String OR Integer OR null. Coalesced, never normalised here
      "vertices": [[x, y, z], ...],   // metres, world coordinates, outer loop only
      "has_inner_loops": false        // ⚠ v2: `inner_loops` carries the geometry
    }
  ],
  "tagged_total": 1441,               // faces carrying DesignPH_dict at all
  "classified_only": true             // whether faces with no real area group were filtered out
}
```

**Payload sizes, measured on the real corpus (contract v2):** 334 KB (Adelphi) to 501 KB (Linde) for
the *whole* document — faces, edges, windows, tables, libraries and the named unclassified faces.
The verified bridge capacity is 4 MB, so chunking is still not needed.

⚠ **It was 2.25 MB before v2**, because the frame and glazing option lists shipped on every window —
44,915 characters repeated byte-identically on all 46 of Adelphi's. The contract's *"log anything
approaching 1 MB"* rule is what caught it, on the first capture it ever applied to. **Before shipping
a field per entity, ask whether its values are per entity**; `distinct` is a one-line check and the
answer was 2 out of 46.

⚠ **`area_group` is deliberately left un-normalised at this hop.** Ruby coalesces the two key
generations and nothing more; Python does the type check. One place to get it wrong instead of two.

### 2.5 What "classified" means

```ruby
Integer(group.to_s, 10) > 0   rescue false
```

Adelphi: **82 classified of 1441 tagged of ~8037 live faces.** The gap is the whole design problem —
see [`CONSTRAINTS.md`](CONSTRAINTS.md) §4.

## 3. Hop 2 — the bridge

```
Ruby → JS   dialog.execute_script("startSpike(#{JSON.generate(context)})")
JS   → Ruby sketchup.spike_result(JSON.stringify(report))
```

Verified to **4 MB per hop, both directions, checksum-exact** (djb2 → signed 32-bit; identical
implementations in `main.rb` and `spike.js`, agreeing on empty, ASCII and 100 KB inputs). No ceiling
was found at 4 MB.

⚠ Checksums agree only for the Basic Multilingual Plane — JS iterates UTF-16 code units, Ruby
iterates codepoints.

⚠ **Do not echo geometry back.** An early build reflected the whole face payload into the result
file and doubled its size for nothing. Summarise: strategy, model name, face count.

## 4. Hop 3 — building the honeybee model

### 4.1 designPH area group → honeybee face type

The area group is the **only** classification designPH stores, so it is the entire basis for face
typing.

| Group | PHPP meaning | honeybee `face_types.*` |
|---|---|---|
| 1 | Treated Floor Area | `floor` — ⚠ and **no boundary condition**, so honeybee defaults it to `Ground` (§5.1) |
| 2–6 | N/E/S/W/Horizontal windows | *not faces* — apertures |
| 7 | External Door | *(unmapped, auto-assigned by tilt)* · `Outdoors` |
| 8 | External Wall — Ambient | `wall` · `Outdoors` |
| 9 | External Wall — Ground | `wall` · **`Ground`** |
| 10 | Roof/Ceiling — Ambient | `roof_ceiling` · `Outdoors` |
| 11 | Floor slab / Basement ceiling | `floor` · **`Ground`** |
| 12–14 | User-defined surfaces | *(unmapped)* · `Outdoors`, and the report says it is a guess |
| 15–17 | Thermal bridges | **`Sketchup::Edge`, not faces** — lengths, not areas |
| 18 | Building element towards neighbour | *(unmapped)* · **`Adiabatic`** — an equal-temperature party wall carries zero heat flow. Adelphi has 446.5 m² of it |

Anything unmapped falls through to honeybee's own tilt-based auto-assignment. **Pass the object, not
the string** — `face_types.wall`, never `"Wall"`.

**Boundary conditions are mapped explicitly, never defaulted** (PRD §6). A model where every face
falls through to `Outdoors` is schema-valid and wrong about every ground-coupled surface in the
building — which is exactly the set PHPP treats differently.

Observed on Adelphi's 82 faces: **41 `Floor`, 38 `Wall`, 3 `RoofCeiling`.**

⚠ **The winding has to be flipped to match the type the area group assigned.** honeybee's convention
is a `Floor` normal pointing **down**; designPH winds its TFA and slab faces **up**, so
`ValidateModel` rejected **40 of Adelphi's 41 Floors** as *"an upward-pointing Floor, which should be
changed to a RoofCeiling"*. The direction of the fix is the decision: the **area group is
authoritative** about what the surface is — it is PHPP's own classification — while honeybee is
*inferring* type from geometry. Letting honeybee win would quietly re-file a TFA marker as roof.
⚠ Never flip an **untyped** face: with `face_type=None` honeybee assigns from the tilt, so flipping
first changes the answer it gives.

⚠ **Groups 15–17 must never arrive as faces, and groups 2–6 must never arrive as faces either.** Both
are refused and reported rather than translated around — a bridge or an aperture in the face list
means the collector filed a record in the wrong place, which is worth seeing.

⚠ **Groups 15–17 are on edges.** A face-only reader loses every thermal bridge silently — 99 of 293
tagged entities on a real project. Their `assemblyID` also resolves against `connections_ud`, a
different table from the assemblies, and both use `NNud` ids, so getting it backwards is silent too.
**Read the area group first**; 15/16/17 means edge + connection.

### 4.2 Construction

```python
geometry = Face3D([Point3D(*p) for p in vertices])
face     = Face(identifier, geometry, face_types.wall)   # or None to auto-assign
room     = Room("Room_id", faces)                        # non-solid is fine and expected
model    = Model(model_id, rooms=[room], units="Meters")
```

Cost for 82 faces: `Face3D`+`Face` 6.1 ms, `Room()` ~0, `to_dict` 9.6 ms, `json.dumps` 2.3 ms.

## 5. Hop 4 — the HBJSON that comes out

Measured output from Adelphi, 87,248 bytes at the Phase 3 spike. ⚠ The real translator's Adelphi
output is **324 KB** — the difference is the 46 apertures, the TFA `Space`, the constructions and the
per-face PH properties that the spike did not emit. Bluff Reach, with 99 thermal bridges, is 686 KB.

```jsonc
{
  "identifier": "adelphi-designph_COPY",
  "units": "Meters",
  "version": "1.53.1",                  // ⚠ stamped by us, not honeybee — see §5.3
  "rooms": [{
    "faces": [ /* 82 */ ],
    "properties": {
      "energy": { /* ... */ },
      "ph": {
        "type": "RoomPhProperties",
        "spaces": [ /* 1, 368.476 m² */ ],   // ⚠ was EMPTY on the first run — see §5.1
        "ph_bldg_segment_id": "...",
        "ph_foundations": [],
        "specific_heat_capacity": "...",
        "specific_heat_capacity_wh_m2k": "..."
      }
    }
  }],
  "properties": {
    "energy": { "global_construction_set": { /* ... */ } },   // ⚠ does not validate — §5.2
    "ph": { "type": "ModelPhProperties", "id_num": 0, "bldg_segments": [...], "team": {...} }
  },
  "user_data": {
    "dph_plus": { "shading": "not-computed", "translator_version": "...", "report": "..." }
  }
}
```

⚠ **The shading disclosure lives in `user_data`, inside the HBJSON**, verified to survive `to_dict`
*and* `from_dict` (decision D-3). A marker that travelled beside the file could be separated from it;
this one cannot. The model must not be passable on without the disclosure.

⚠ **Thermal bridges do not serialise under the Room.** They land on the **model's** PH properties —
`properties.ph.bldg_segments[0].thermal_bridges` — and the Room keeps only a segment id. Looking for
them under `rooms[].properties.ph` finds nothing and proves nothing.

### 5.0.1 ✅ Confirmed as interchange, by a different honeybee

The POC's Adelphi output **loads in Rhino/Grasshopper** (2026-08-21) — a Ladybug Tools install at
different versions from the vendored payload. Geometry renders, face types colour correctly,
boundary conditions separate. Details and the version table: `HONEYBEE_STACK.md` §6.2–6.3.

That is the first evidence that the file is genuinely *interchange* rather than merely
self-consistent, which is the project's entire premise (PRD §1).

### 5.1 ✅ `spaces` — was empty on the real model, now solved

`Space.from_room` raised `ValueError: Floor face 'face_9153' must be horizontal for World-Z
extrusion`, so no PH `Space` was created. **TFA is a headline Passive House number**; an absent
`Space` is precisely the silent loss hard rule 4 exists to prevent.

Two distinct failure modes, both real:

| Condition | Message |
|---|---|
| no face maps to group 1 or 11 | `Honeybee Room '…' has no Floor faces.` |
| a Floor face is not horizontal | `Floor face '…' must be horizontal for World-Z extrusion.` |

**Root cause found 2026-08-21, and it is narrower than it looked.** The predicate is
`Face3D.is_horizontal(1e-7)` — it tests **`max.z − min.z`**, i.e. flatness in Z, *not* the normal —
and honeybee-ph calls it at **a tenth of a micron**. On Adelphi exactly **2 of 40** TFA faces fail
it, with a **12 µm** z-spread. Because `Space.from_room` raises for the whole room, those 2 cost all
40 and **368 m² of TFA**.

The fix is three things, not one, and all three are implemented and measured (`dph_translator.spaces`):

1. **Pre-filter with honeybee's own predicate**, not an approximation of it. A guard written against
   `normal.z` measures a different quantity and lets these through — see `HONEYBEE_STACK.md` §4.
2. **Flatten below a stated, reported tolerance** (1 mm). Snapping 12 µm of coordinate noise is not
   the "projection" that would be fabrication; a genuinely sloped face still gets reported. The
   *exported envelope face is left alone* — only the throwaway extrusion copy is flattened.
3. **Never let one face cost the room.** `Space.from_room` names the offending face in every one of
   its error messages, so a refusal is narrowed: drop the named candidate, retry, report it.

✅ **Result on the corpus, 2026-08-21:** Adelphi **368.476 m², 0 lost** (the two 12 µm faces named as
flattened); Bluff Reach **1491.9 m²**; Wellington **448.2 m²**. Linde and `250708` derive no Space at
all, correctly — they carry no area-group-1 faces.

⚠ **Still a v1 question, and it is not the extrusion.** TFA marker faces are *inside the envelope
Room*, where honeybee defaults a `Floor` to a `Ground` boundary condition — so a floor-area marker
reads downstream as a ground-coupled envelope surface. Harmless in the POC (nothing consumes it) and
wrong in principle.

### 5.2 ⚠ `global_construction_set` does not validate

27 failing objects under `honeybee-schema` 1.53.1 and the same region under 2.2.0 — all
honeybee-energy's *defaults*, none touching geometry or PH. Upstream drift.
**Open v1 decision: emit a global construction set at all?**

### 5.3 ✅ The schema version is stamped

`version` came out `null` because `honeybee-schema` is deliberately not installed. Decision D-2
stamps `dph_translator.HBJSON_SCHEMA_VERSION` (`"1.53.1"`), with a test asserting it equals the pin
the validator checks against — a stamp naming a version nothing validates against would be worse
than none.

### 5.4 What v1 must additionally carry

- `shading: not-computed` — an **explicit** marker. Emitting zeros or omitting silently would let a
  consumer mistake an incomplete model for a complete one (PRD §7.2).
- A translation report naming every entity that could not be converted — §5.5.

### 5.5 The report artefact — the second output, and its shape

**Three files are written, not one**, and the report is a first-class output rather than a log. It
is what makes hard rule 4 ("report, don't guess") checkable: **every entity is either an object in
the HBJSON or a row in this file, and the two sets are disjoint.** That disjointness is asserted as
a unit test, not hoped for.

```
<name>.hbjson         the model
<name>.report.json    ← this
<name>.extraction.json  only when Diagnostics ▸ Save extraction JSON is on
```

Real example, Bluff Reach (2026-08-21):

```jsonc
{
  "summary": {
    "translator_version": "0.2.0",
    "hbjson_schema_version": "1.53.1",       // what we STAMP, not what a Ladybug user runs (§5.3)
    "generated_by": "dph_plus_poc collector <sha> (built <iso8601>)",
    "model": "2414_Bluff Reach_COPY",
    "designph_versions": ["2.2.24"],
    "faces":           { "in": 194, "translated": 194, "reported": 0 },
    "apertures":       { "in":  40, "translated":  40, "reported": 0 },
    "thermal_bridges": { "in":  99, "translated":  99, "reported": 0 },
    "spaces": { "derived": 1, "ceiling_height_m": 2.5 },
    "tfa_m2_covered": 1491.862, "tfa_m2_lost": 0.0,
    "assembly_tiers": { "none": 140, "1-layered": 54 },   // §6's four tiers, tallied
    "libraries": { "frame_types": {…}, "glazing_types": {…} },
    "tables_present": [ … ], "tables_undecodable": [ … ]
  },
  "shading": "not-computed",                  // the explicit marker of §5.4
  "shading_note": "…reveal dimensions ARE present…",
  "notes": [ "⚠ the HBJSON carries honeybee-ph's DEFAULT site (New York)…" ],
  "unclassified": {                           // §2.5 — the majority of a real model
    "tagged_faces": [ { "id": …, "area_group": null, "tag": "*Vn50" } ],
    "tagged_face_count": 382,
    "untagged_by_tag": { "Layer0": 2555527, "*Vn50": 52, "Shading_Tree": 28 }
  },
  "entries": {                                // per KIND, not per failure class
    "face":           { "count": 194, "outcomes": {…}, "listed": [ … ], "truncated": false },
    "aperture":       { "count":  40, … },
    "assembly":       { "count": 194, … },
    "thermal_bridge": { "count":  99, … }
  },
  "runtime": { "timings": {…}, "payload": {…}, "wasm_heap_mb": 34.6, "js_heap_mb": 82.4 },
  "host_notes": []                            // what only Ruby saw — see below
}
```

**Rules the shape encodes, each of which was paid for:**

- **Three outcomes, not two**: `translated`, `translated-with-notes`, `reported-not-translated`.
  A face can arrive intact *and* have something worth saying about it, and collapsing that into
  pass/fail is how a real caveat disappears.
- **Entries are keyed by `kind`, meaning the entity class — not the failure class.** One face can
  appear under both `face` and `assembly` with different outcomes, because "the geometry translated"
  and "its construction resolved" are different questions.
- **Keyed by the contract's path-qualified `id`**, never `entity_id`. The session-scoped one is a
  debugging aid; re-run diffs depend on the stable one (`SKETCHUP_RUNTIME.md` §7).
- **`listed` is capped at 200 per kind and `truncated` says so.** A short list and a truncated list
  must not look alike.
- ⚠ **`runtime` and `host_notes` are merged in by Ruby, not produced by the translator.** The
  timings are measurements only the JS side can see; `host_notes` is what only the Ruby side saw —
  a missing version stamp, a payload over the notice threshold. **A note nobody kept is a note
  nobody read**, so they travel in the artefact rather than only in the console.
- **`unclassified.untagged_by_tag` counts *placements*.** `Layer0: 2555527` on a model with ~8000
  unique faces is correct and will look absurd; say which it is wherever it is shown
  (`DESIGNPH_DATA_MODEL.md` §8.6.1).

⚠ **`PASSED WITH OMISSIONS` is the ordinary outcome on a real model, and that is the design.** All
five corpus models report it. A translator that said `PASSED` on a model where 140 of 194 faces had
no resolvable assembly would be the worse tool by a wide margin.

## 6. Assemblies — the constraint the PRD had to be rewritten around

⚠ **An assembly reference does not always resolve inside the model.** Only **254 of 532** corpus
assembly references carry a build-up; the rest resolve only against designPH's *installed* CSV
library, outside the `.skp`.

So a reader must handle four tiers, and cannot assume it can produce a layered
`OpaqueConstruction` for every face. PRD §8.3 is written around this. Detail:
`planning/RESULTS/PHASE-1_assembly-resolution.md`.

Tier distribution across the whole captured corpus, 2026-08-21 — the measurement the PRD was
rewritten on the *expectation* of:

| model | tier 1 (layered) | tier 2 (U-value) | tier 3 (library, unresolvable) | none |
|---|---|---|---|---|
| Adelphi | 0 | 42 | 0 | 40 |
| Bluff Reach | 54 | 0 | 0 | 140 |
| Wellington | 59 | 0 | 0 | 44 |
| Linde `250703` | 71 | 0 | 3 | 0 |
| `250708` | 0 | 0 | **92** | 0 |

⚠ **`250708` resolves nothing inside the model at all**, and it is not a broken file — it is the
normal case for a model whose assemblies come from designPH's installed library. A translator that
promised a layer stack per surface would be empty-handed on an entire real project.

### 6.1 ⚠ Multi-section assemblies — the U-value is NOT a series sum

designPH mirrors PHPP's **three parallel construction paths** per layer (`lambda1/2/3`), with the
path areas on the *assembly* header (`surf2_percentage` / `surf3_percentage`, as **percentages**;
section 1 is the unstored remainder). The U-value is **ISO 6946 §6.7 — the mean of an upper and a
lower resistance limit** — and the spread between them is the *Error %* designPH prints beside its
own answer. Full derivation and the evidence: `DESIGNPH_DATA_MODEL.md` §7.2.

Two things this costs a translator that does not know it:

- **honeybee cannot represent it.** A layer's conductivity is one number, so an `OpaqueConstruction`
  built from these layers reports the **section-1** value — 0.0698 against designPH's 0.0750 on
  Linde's `06ud`, **8 % low, in the direction that flatters the building**. And
  `EnergyMaterialPhProperties.divisions.get_equivalent_conductivity` does not rescue it: that is an
  area-weighted lambda, which is ISO 6946's *lower* limit.
- **designPH's U includes the films**; honeybee's `u_value` is material-only (`HONEYBEE_STACK.md`
  §4). On Linde's unframed assemblies that difference alone is 0.004–0.005 W/m²K — enough on its own
  to fail a ±0.005 comparison that paired the wrong two numbers.

So the real figure travels on the **report** (`u_value_iso6946`, with the section areas and the
spread), and how honeybee-ph should represent a framed layer is a **v1 question** — arguably an
upstream one, since `divisions` exists precisely for this and computes the optimistic bound.

## 7. Windows

- Windows are **SketchUp Dynamic Components**, not designPH dictionary data
  (`DESIGNPH_DATA_MODEL.md` §9). They carry `frametypeid`, `glazingtypeid`, `lenx`, `leny`.
- **`glued_to` resolves the host face reliably** — 46 of 46 on Adelphi, confirmed twice (Phase 1,
  and the POC's live capture 2026-08-21).
- ⚠ **Neither `cuts_opening?` nor `loops.size > 1` identifies a host.** `cuts_opening?` is a
  capability of the *definition* — `true` on all 46. And `loops.size > 1` is a fact about *modelled*
  holes — true on only 2 of the 16 real hosts, because a glued opening reduces `face.area` **without
  creating a loop** (§2.3.1). **`glued_to` is the only thing that identifies a host.**

### 7.0 ⚠ The window transform is the ACCUMULATED one

`ComponentInstance#transformation` is the placement **within its enclosing group**, while every
other geometry field in the contract is world. They are the same object type and differ only in
where they were read, so nothing type-checks and nothing raises — it put Adelphi's 46 windows
**1.2–3.3 m off their own hosts**, and *projection onto the host plane absorbed the error in
silence*. Ship `parent_transform * instance.transformation`.

**Any lossy step needs a stated limit on how much it was allowed to absorb.** `apertures.
OFF_PLANE_LIMIT_M` refuses a rectangle more than 0.5 m off its host and reports the distance on
every window that passes; measured on the corrected capture, all 46 are **0.000 m**.

### 7.1 The aperture rectangle — settled

**Use the rough opening: `lenx × leny` in the definition's local XY plane, through the *world*
transform.** Full derivation and evidence in `DESIGNPH_DATA_MODEL.md` §9.1.

Two attractive alternatives, both wrong:

| Tempting | Why it fails |
|---|---|
| the definition's **largest face** | it is the **glazing**, `(lenx−2·fw)(leny−2·fw)` — every window comes out **41 % too small**, and plausibly so: right place, right shape, nothing downstream complains |
| the stored `dynamic_attributes["area"]` | it is a **stale DC formula output**. Matches `lenx·leny` on only 20 of 46 Adelphi windows, ratios 0.44–1.66 |

⚠ And the faces are **not at the top level of the definition** — `definition.entities.grep(Face)`
returns `[]` on all 46. Walk definitions recursively or find nothing at all.

✅ **The corner convention is measured, not inferred.** That the definition origin lies *on* the host
plane does not say it is a **corner** of the opening rather than its centre — half a window apart.
Scored against the real host polygons: `+x`/`+y` from the origin lands **46/46** inside, against
23/46 centred and 15/46 and 12/46 for the flipped pair
(`planning/spikes/poc/solve_window_parent.py`).

### 7.1.1 ⚠ Two ways honeybee calls a legitimate aperture invalid

Both fire on real designPH data, neither is repairable without fabricating an area, and both are
predicted in the report rather than discovered downstream:

| | |
|---|---|
| **Flush with the host edge** | `Face3D.is_sub_face` takes **no tolerance**, so a corner 1 µm past the boundary — which is the collector's own coordinate rounding — reads as *not fully bounded*. 2 of Adelphi's 46 windows sit this way |
| **The opening is modelled as an inner loop** | honeybee expects an aperture on the *gross* face and subtracts the opening itself, so a host that already carries the hole subtracts it twice. Only **2 of 16** Adelphi hosts model the hole at all |

⚠ The same tolerance-free trap sat on *our* side: `Polygon2D.is_point_inside_bound_rect`, used as a
fast path in front of the tolerant `point_relationship`, refused every flush window outright. Two
tests of one property that disagree at the boundary — the local-approximation rule again.

### 7.2 Where the frame data goes

`lenx`/`leny` → the aperture rectangle. `d_reveal`/`o_reveal` (inches → m) → the PH
`ShadingDimensions` reveal fields, horizon and overhang left null. `framewidth{,l,r,top,bot}` are
per-edge and PHPP takes all four. `instcill`/`insthead`/`instleft`/`instright` are the per-edge
Psi-install conditions. `frametypeid`/`glazingtypeid` are the library join keys, and there are **two** in-model routes to
resolve them — corrected 2026-08-21:

1. ✅ **`frames_ud` / `glazing_ud`, the Marshal tables** — the full PHPP numbers: per-edge U-values
   and frame widths, glazing-edge and installation psi, `chi_GT`, g-value and U-value. Present on
   **3 of 5** corpus models. `DESIGNPH_DATA_MODEL.md` §7.0.1. ⚠ **The POC ships neither table**, so
   frame constructions do not reach the HBJSON today — a scope choice, and the shortest real item on
   v1's list.
2. `_frametype_options` / `_glazingtype_options` — the DC option lists, **names only**, but present
   more often. Enough to *name* a type in a report with no CSV library on disk
   (`DESIGNPH_DATA_MODEL.md` §9.2.1).

## 8. Reference outputs

| File | Use |
|---|---|
| `poc/_private/fixtures/*.extraction.json` | ★ **The five real captures**, contract v2, gitignored (client data). `MANIFEST.md` says which model each came from |
| `poc/_private/fixtures/adelphi-designph_COPY.hbjson` | ★ What we actually produce today — 1 room, 82 faces, 46 apertures, 1 TFA space |
| `planning/RESULTS/validation/phase3_sketchup_output.hbjson` | The Phase 3 *spike*'s output — 1 room, 82 faces, no apertures, no spaces. Superseded; kept as the baseline the POC is measured against |
| `planning/RESULTS/validation/phase3_sketchup_hbjson_core.json` | Its schema verdict |
| `_adephi_st_example_files/adelphi-honeybee-json.hbjson` | **Shape** reference only. 6 solid rooms from the Rhino route, solved adjacency. **Never an equality target**, and no longer loadable (`tfa_override`) |
| `_adephi_st_example_files/adelphi-phpp.xlsm` | Numerical ground truth — areas, U-values, TFA |
| `planning/RESULTS/phpp/*.csv` | That ground truth, extracted |

⚠ The corpus formats are **only approximately aligned**. A mismatch between them is not by itself
evidence of a bug.

⚠ **And "approximately aligned" is measurable, now that it has been measured.** Joining Adelphi's
in-model `assemblies_ud` to the PHPP export **by name** matches only **3 of 14** assemblies, and the
ids differ on all three (`83ud`/`84ud`/`85ud` against `01ud`/`07ud`/`13ud`) — two different id
spaces, which is why the join is by name. Two of the three agree within 0.003 W/m²K; the third
disagrees by 0.031, and hand-checking put the difference on the **PHPP side** (its header includes a
framing fraction its layer list only hints at). The `.skp` is designPH **2.1.15** and the `.ppp` that
made the PHPP is **2.4.0 BETA**: not two views of one tool.

**So the PHPP is ground truth for arithmetic, not for identity.** Use it to check a *method*
(§6.1's ISO 6946 derivation was validated this way); do not expect a row-for-row correspondence.
