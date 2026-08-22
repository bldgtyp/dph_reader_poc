# The honeybee / honeybee-ph / PHX Stack

What the downstream Python stack requires, what it costs, and where it bites. Everything here is
observed — Phase 2 (`planning/RESULTS/PHASE-2_results.md`) audited it, Phase 3
(`planning/RESULTS/PHASE-3_results.md`) ran it inside SketchUp.

Source repos: `~/Dropbox/bldgtyp-00/00_PH_Tools/` and *github.com/PH-Tools*.

---

## 1. The payload — exactly eight wheels

Pinned as of 2026-08-19. All `py3-none-any`; **nothing in the reachable closure imports a C or Rust
extension.**

| Wheel | Version | Bytes |
|---|---|--:|
| `honeybee_energy` | 1.123.23 | 586,381 |
| `ladybug_core` | 0.44.56 | 275,103 |
| `honeybee_ph` | 1.33.48 | 214,204 |
| `ladybug_geometry` | 1.35.3 | 204,922 |
| `honeybee_core` | 1.64.65 | 196,266 |
| `ladybug_geometry_polyskel` | 1.7.52 | 38,765 |
| `ph_units` | 1.5.38 | 32,177 |
| `honeybee_standards` | 2.0.7 | 11,109 |

≈1.5 MB. Order does not matter — nothing resolves dependencies and nothing imports until all eight
are on the path.

**Why it is pure at all:** these packages must stay **IronPython 2.7 compatible** so they load in
Rhino/Grasshopper. That constraint is what keeps them free of native extensions, and therefore what
makes the whole Pyodide route possible. It is a load-bearing accident — see the
`ironpython-27-compatibility` skill before editing any of them.

## 2. ⚠ Declared dependencies are not imported dependencies

`honeybee-core` **hard-declares** `honeybee-schema==2.2.0`, which pulls `pydantic-openapi-helper` →
`pydantic` → Rust `pydantic-core`. On packaging metadata alone the subtree looks impure and the whole
approach looks dead.

It is not. **The only imports of `honeybee_schema` in the reachable closure are three *inside a
function* in `honeybee_energy/cli/validate.py`.** Every top-level `click` import is in a `cli/`
module. Nothing on the model-building path touches either.

Resolve the closure, then ask what actually *imports* it, then prove it by installing `--no-deps` and
running the thing. `pip download` answers a question about your laptop, not about the package —
use `uv pip compile --universal` and read purity off PyPI's file list.

## 3. Import order and the `_extend_` hooks

```python
import ladybug_geometry.geometry3d.pointvector
import ladybug.location
import honeybee.room
import honeybee.model
import honeybee_energy.lib.constructionsets
import honeybee_ph.space
import honeybee_ph                 # ← must be last
```

**`honeybee_ph` last is not cosmetic.** Importing it runs `_extend_honeybee_ph`, which grafts
`.properties.ph` onto honeybee's own classes. Without it, `Room.properties.ph` does not exist and
HBJSON round-tripping loses every PH payload silently.

Cost is concentrated in `honeybee.room` (588 ms of a 2.6 s cold start); the rest are ~0 because
they are already pulled in transitively.

⚠ **These packages define no `__version__` attribute.** Use `importlib.metadata.version("honeybee-core")`.

## 4. API traps

### `honeybee.face.Face` wants a face-type *object*

```python
from honeybee.facetype import face_types
Face(identifier, geometry, face_types.wall)     # ✅
Face(identifier, geometry, "Wall")              # ✗ AssertionError: Wall is not a valid face type
```

Attribute names on `face_types`: `wall`, `floor`, `roof_ceiling`, `air_boundary`. Passing `None`
lets honeybee auto-assign by tilt.

### ⚠ `Face3D.is_horizontal(tolerance)` measures Z-EXTENT, not orientation — and honeybee-ph calls it at 1e-7

*(Measured 2026-08-21. This one cost 368 m² of TFA on the first real export.)*

```python
def is_horizontal(self, tolerance):
    return self.max.z - self.min.z <= tolerance      # ← flatness in Z, NOT the normal
```

`honeybee_ph.space.Space.from_room` calls it with **`1e-7`** — a tenth of a micron. **No CAD model is
flat to a tenth of a micron.** Two of Adelphi's 40 TFA faces have a **12 µm** z-spread with
`normal.z = 0.999999999998`, and they fail.

Two separate lessons, and the first is the sharper one:

1. **A pre-filter must use the same predicate as the thing it is protecting.** A guard written as
   `abs(normal.z − 1) < tol` measures a *different quantity* and lets these through — so the
   exception fires anyway, and because `Space.from_room` raises for the whole room, **all 40** TFA
   faces are lost rather than the 2 that are actually at fault. Getting the tolerance wrong is
   recoverable; measuring the wrong thing is not.
2. **1e-7 m is not a modelling tolerance.** Flattening a face to its mean Z below a stated,
   *reported* threshold (1 mm, say) is noise removal, not repair. Projecting a genuinely sloped face
   would be fabrication. Draw the line explicitly and name every face on either side of it.

✅ **Resolved 2026-08-21** (`dph_translator.spaces`): pre-filter with `Face3D.is_horizontal` at
honeybee's own `1e-7`, flatten to mean z below a stated 1 mm and report each one, refuse and name
anything above it — and, because `Space.from_room` raises for the *whole room*, drop the single face
honeybee **names in its own error message** and retry rather than losing every candidate. On Adelphi
that recovers **368.476 m² across 40 faces, 0 lost**, with the two 12 µm faces named as flattened.

### ⚠ `Face3D.is_sub_face` takes NO tolerance, so a flush window is "not fully bounded"

`Face.check_apertures` — and therefore `ValidateModel` — asks `Face3D.is_sub_face`, whose
polygon-inside test has no tolerance at all. A window sitting flush with its host's edge fails it.
**Two** of Adelphi's 46 do, one exactly on the boundary and one **0.3 µm** past it — the extraction
contract's own coordinate rounding, not an overhang.

⚠ That 0.3 µm is worth dwelling on: an offline rehearsal of the same fix put the second window
*exactly* on zero and predicted one flush note; the live run put it a third of a micron over and
produced two. **A tolerance-free predicate turns float noise into a classification**, which is
precisely why the response is a warning rather than a refusal.

⚠ It fails a second way that matters more: a host whose opening is **modelled as an inner loop**
already subtracts the hole, and honeybee expects an aperture to be a sub-face of the *gross* face —
so the opening comes off twice. Only 2 of Adelphi's 16 hosts are modelled that way (a glued opening
usually creates no loop), which is exactly what makes it easy to miss.

Neither is repairable without fabricating an area, so the POC emits the aperture and puts honeybee's
own verdict in the report *in advance*, saying which of the two cases it is. Note the shape of the
answer: **one threshold decides whether to emit, a different one predicts what a validator will
say**, and they are allowed to differ as long as both are stated.

⚠ And the same trap has a mirror image on our side: `Polygon2D.is_point_inside_bound_rect` was used
as a fast pre-filter in front of the tolerant `point_relationship`, and being tolerance-free it
refused flush windows outright. Two tests of one property that disagree at the boundary is the
local-approximation rule again — the library's tolerant predicate is the whole test, and `0` (on the
edge) is a pass.

### ⚠ honeybee rejects an upward-pointing `Floor`

`ValidateModel` on real output: *"Face … is an upward-pointing Floor, which should be changed to a
RoofCeiling"* — **40 of Adelphi's 41 Floor faces**. honeybee's convention is that a Floor's normal
points **down**.

This is a genuine convention clash rather than a bug. designPH's TFA faces are wound normal-up, and
its **area group is authoritative about what the surface is** (`DATA_CONTRACTS.md` §4.1) — honeybee
is inferring type from geometry, we are assigning it from PHPP's own classification. The resolution
is to flip the geometry to match the type we assigned, and report it; the alternative — letting
honeybee re-type the surface — would silently move a TFA marker into the roof.

✅ **Done 2026-08-21** (`build._orient`), symmetrically for `RoofCeiling`, reported per face, and
**never on an untyped face** — with `face_type=None` honeybee assigns from the tilt, so flipping
first would change the answer it gives. All 40 upward-Floor errors are gone from Adelphi's
`check_all`. Safe for TFA: `Space.from_room` re-normalises the winding for its own extrusion anyway.

### ⚠ `honeybee-schema` requires a `Room` to have at least 4 faces

`ensure this value has at least 4 items`. A three-face model produces schema-invalid HBJSON on a rule
with nothing to do with translation quality. Irrelevant for real models (Adelphi has 82) and a live
trap for small test fixtures — build validation fixtures with **six or more**.

### ⚠ `Space.from_room` has two distinct failure modes, and both fire on real data

`honeybee_ph.space.Space.from_room(hb_room, avg_ceiling_height)` derives a PH `Space` (the TFA/iCFA
carrier) from a Room's **horizontal Floor faces**. It raises `ValueError` when:

1. **`Room has no Floor faces`** — normal whenever no face maps to designPH area group 1 or 11. A
   wall-and-roof selection legitimately has no Space.
2. **`Floor face '<id>' must be horizontal for World-Z extrusion`** — and **this one fired on the
   real Adelphi model**, so the run produced *no PH Space at all* despite 82 faces translating
   cleanly.

Both must be caught and **reported, not raised** (hard rule 4). ✅ Failure mode 2 is **solved** —
see the `is_horizontal` note above. It was an open problem for a whole phase, and the reason is worth
keeping: TFA is a headline number, and a silently absent `Space` is exactly the kind of quiet loss
that would damage the tool's reputation.

`Space.from_room` deliberately does *not* attach itself. The caller does:

```python
space = Space.from_room(hb_room, height)
hb_room.properties.ph.add_new_space(space)
```

### ⚠ honeybee-ph fabricates a default site, and it serialises like real data

Every `BldgSegment` arrives with a populated site — **New York, 40.6 / −73.8, climate zone 1** — that
nobody set. It goes into the HBJSON looking exactly like project data, and a downstream consumer has
no way to tell it is a placeholder.

designPH stores only a climate **dataset id** (`klima_ID`), so there is nothing to overwrite it
with. ⚠ And Adelphi's is `"DE-9999"` — designPH's own German default, never set, on a Brooklyn
townhouse. So the file can carry a *fabricated* New York site next to a *defaulted* German id, and
neither is the building's climate.

Say so in the report. Making the site settable is a v1 job.

### `Room` does not require solid geometry

`Room(identifier, faces)` accepts an arbitrary face list. `room.geometry.is_solid` is `False` and
that is fine — v1 emits **one non-solid Room** by design (PRD §8.1). Do not attempt watertight
repair.

### ⚠ `Room` takes *ownership* of the faces it is given

`Room.__init__` sets `face._parent = self` on every face. So a second `Room` built from the same
face objects — even a throwaway one, built only to read `geometry.is_solid` or to hand to
`Space.from_room` — silently re-parents them and corrupts the real Room. **Build one Room per set
of faces**; if a temporary Room is genuinely needed (POC-3 §7's TFA extrusion is the case), build it
from *copies*, or from a disjoint face set. Caught in POC-1 review, before it shipped.

### ⚠ Identifiers are truncated at 100 characters, silently

`honeybee.typing.clean_string` strips characters outside `[.A-Za-z0-9_-]`, maps spaces to `_`,
hashes an input that leaves nothing valid — and **truncates at 100 characters without warning**.
Every identifier setter asserts `valid_string`, so this is honeybee's rule and not one to
re-implement locally: a hand-rolled sanitiser matching only the character class lets a long name
raise `AssertionError` from inside `Room()`, outside any per-face guard, and the whole run dies with
no entity named.

Truncation matters for this project specifically. The extraction contract's ids are
**path-qualified** (`CONTRACT_extraction-json.md` §2.1): `face_` plus one ~19-digit persistent id
per group/component on the path. Five levels of nesting overflows 100 characters, and two faces
under the same deep parent then differ only in a tail that is cut off — **two envelope surfaces
merging into one identifier**. Check for duplicate identifiers after cleaning and report them;
`dph_translator.translate` does.

### ⚠ Two exports of the same model are not the same file — and it is NOT a round-trip problem

Measured 2026-08-21 across all five corpus fixtures (`poc/tools/byte_identity.py`, POC-4). **Three
consecutive runs of the same translation on one CPython 3.11 produce three different SHA-256s.**
Two causes, and they are different in kind:

| Cause | Scale |
|---|---|
| `honeybee_ph/_base.py` — `_Base.__init__` does `self._identifier = uuid.uuid4()`, so every **newly constructed** PH object gets a fresh identifier | **152 distinct** uuids in Adelphi's export, appearing **301** times (`_Base` also seeds `display_name` from the identifier); 901 occurrences in Bluff Reach's |
| `honeybee_energy/properties/model.py` — `materials` and `constructions` return `list(set(...))`, ordered by `PYTHONHASHSEED`, which CPython randomises per process | 4 lists: `properties.energy.materials`, `.constructions`, and the same two under `.global_construction_set` |

⚠ **The second is invisible to a size check.** Reordering a list changes no bytes of length, so two
runs produce files that are the *same size to the byte* with different hashes. When a whole-file
comparison fails and the sizes match exactly, look for ordering before looking at arithmetic.

#### ✅ Serialisation round-trips ARE stable — this is not an upstream defect

Measured, because the opposite was asserted first and it was wrong. `Model.from_dict` →
`to_dict` on Adelphi's export preserves **152 of 152** identifiers, and again on a second round:

```
original uuids : 152
after 1 round  : 152   kept from source: 152
after 2 rounds : 152   kept from round1: 152
```

Every honeybee-ph `from_dict` reads the stored `identifier` back. So `uuid4` is a **constructor
default for objects that have no identity of their own yet**, which is the correct design — the
churn comes entirely from *us building fresh objects on every export*, out of a designPH source that
carries no persistent id for a site, a climate, or a floor segment.

#### What it actually affects — narrower than it looks

- **Nothing about correctness.** Each file is valid and internally consistent.
- **Almost nothing is a reference.** On Adelphi, 148 of the 152 uuids appear exactly twice — as an
  object's own `identifier` and the `display_name` seeded from it. Only **one** (`ph_bldg_segment_id`)
  is a genuine cross-reference, and it resolves within its own file.
- **Diffing two exports of the same model** shows ~301 changed strings on top of the real change.
  Noise, not breakage — but it is the reason a re-export comparison has to canonicalise.
- **The extraction JSON is unaffected** — its ids are path-qualified and persistent
  (`CONTRACT_extraction-json.md` §2.1) and it carries no uuids at all. So *collector* stability is a
  separate, cleaner question.

⚠ A cross-host or cross-run comparison must therefore canonicalise. `poc/tools/byte_identity.py`
numbers UUID-shaped strings by first appearance (preserving aliasing, so a reference pointing at the
wrong object still shows) and sorts **only** those four named lists. It must not sort more:
`boundary` vertex order defines a face's orientation, and a blanket sort would report a wall and its
mirror image as identical.

## 5. ⚠ Reading HBJSON is 100× more expensive than writing it

1441 faces, one Room:

| | Pyodide 0.24.1 / Chromium 88 | Pyodide / modern Chrome | CPython 3.14 |
|---|--:|--:|--:|
| `Model.to_dict` | 115 ms | 58 ms | 44 ms |
| `json.dumps` | 24 ms | 38 ms | 21 ms |
| **write total** | **139 ms** | 96 ms | 65 ms |
| `Model.from_dict` | **36.3 s** | 18.2 s | **9.0 s** |

**9 s on native CPython** makes this an upstream honeybee-ph characteristic, not a Pyodide one — the
old engine merely amplifies it. v1 writes HBJSON and never reads it back, so it sits off the product
path. Only call `from_dict` as a correctness assertion, and never on a UI thread.

## 6. HBJSON schema validation — what actually validates

The model produced from Adelphi inside SketchUp (1 room, 82 faces, 87,248 bytes):

| Validator | Raw errors | Failing objects | Touching geometry or PH |
|---|--:|--:|--:|
| `honeybee-schema` 1.53.1 (pydantic 1.x) | 433 | 27 | **0** |
| `honeybee-schema` 2.2.0 (pydantic 2.x) | 432 | ~92 paths | **0** |

Every failure under both is inside `properties.energy.global_construction_set` (materials,
constructions) plus `electric_load_center`. **honeybee-energy's own defaults do not validate against
either published `honeybee-schema`.** That is upstream drift, not our output.

**Open v1 decision:** whether to emit a global construction set at all.

### 6.0 `ValidateModel` across the whole corpus — 2026-08-21

honeybee's own `Model.check_all` on all five translated models. **Three classes of finding, and every
one is either designPH's data or a deliberate design decision — none is a translation defect:**

| Finding | Where | What it is |
|---|---|---|
| *"not closed to within 0.01 tolerance"*, naked edges (5–265) | **all five** | PRD §8.1's deliberately **non-solid Room**. Expected, and not a defect |
| *"Aperture … is not coplanar or fully bounded"* | 7 apertures: Adelphi 2, Wellington 4, Bluff Reach 1 | flush with the host edge, or a host that models its own opening — §4 above |
| self-intersecting / degenerate geometry | Adelphi only | the model's own sliver and zero-width spur (`DESIGNPH_DATA_MODEL.md` §8.6.2) |

✅ **Zero upward-pointing `Floor` errors on any model** — the winding flip holds corpus-wide, against
40 on Adelphi alone before it.

✅ **And the report predicted all 7 flagged apertures, exactly** — 1/1, 4/4, 2/2, with no
false positives and none missed. That is the "emit ours, predict honeybee's verdict" design working
as intended (PRD decision 15): a downstream validator finds nothing the report did not already name.

⚠ **Non-manifold edges are the one thing worth watching**: 38 on `250708`, 15 on Bluff Reach, 0
elsewhere. Not investigated. It is consistent with designPH surfaces meeting at shared edges in a
non-solid assembly, and it is *not* something the POC set out to fix — but nobody has confirmed that
reading, and "consistent with" is not "explained".

### 6.1 ⚠ It is worse than "the defaults": `honeybee_ph` makes **every** material fail

*(2026-08-21, on a model carrying spaces, a thermal bridge, an aperture with PH reveal properties,
boundary conditions and constructions — the payload Phase 3's clean verdict never contained.)*

`honeybee_ph`'s `_extend_` hook adds a `properties` key to every `EnergyMaterial` /
`EnergyMaterialNoMass`, and published `honeybee-schema` 1.53.1 rejects it outright:

```
properties.energy.materials.0.properties  →  extra fields not permitted
properties.energy.materials.0.type        →  string does not match regex "^EnergyMaterialNoMass$"
```

So the constructions **we** emit fail too, not just honeybee-energy's defaults. **No HBJSON produced
with `honeybee_ph` loaded can validate 100 % against published `honeybee-schema`** — which is every
HBJSON this project will ever write.

What still holds, and is what the gate is scoped to: **zero errors touching geometry or the PH
segment**, confirmed on the full-payload model. `honeybee-ph-schema` (§9) is where a v1 answer lives.

### 6.2 ⚠ Version skew with what a real Ladybug user runs

Measured against Ed's own Rhino install, 2026-08-21:

| | Vendored payload | Grasshopper (Ladybug Tools 1.10.0) |
|---|---|---|
| `honeybee-core` | 1.64.65 | **1.64.55** |
| `honeybee-schema` | not installed; we validate against **1.53.1** | **2.1.2** |
| `honeybee-ph` | 1.33.48 | **1.29.0** |

Three different schema versions are in play — the one we stamp (1.53.1), the one the ecosystem
validates with (2.1.2), and none installed in the payload at all. **Stamping `1.53.1` may be
stamping a version the ecosystem has moved past**; that is a live v1 question, not a settled
decision.

### 6.3 ✅ Interoperability is proven, and by a *different* install

The POC's Adelphi output **loads in Rhino/Grasshopper** — `HB Load HBJSON` in 418–445 ms,
`ValidateModel` runs, geometry renders, face types colour correctly, `VizByBC` separates the
boundary conditions.

This matters more than it looks. Every pytest run and every Chromium run uses **the same eight
vendored wheels**, so they can only prove self-consistency. Grasshopper's honeybee is an independent
install at different versions, and `Model.from_dict` accepted our file. That is the first real
evidence that the output is *interchange*, which is the whole point of the project (PRD §1).

⚠ `ValidateModel` also reports **234 naked edges and 1 non-manifold edge**. That is **not** a defect:
v1 emits one deliberately non-solid `Room` (PRD §8.1). Expect it, and do not let a future reader
mistake it for one.

⚠ **pydantic 1 inflates error counts by expanding every union branch** — 433 raw errors for 27
actually-failing objects, a 16× multiplier (the reference HBJSON hits 38×). Collapse by failing
*object* before drawing any conclusion, and never quote the raw count as severity.

⚠ **`adelphi-honeybee-json.hbjson` no longer loads.** `Model.from_dict` raises
`Failed to apply ph properties to the Model: 'tfa_override'` from `PHPPSettings10.from_dict` — it was
written by an older `honeybee-ph`. It remains a **shape** reference; it is not usable as a load
fixture. Build fixtures with `Room.from_box`.

### 6.4 ph-navigator as a consumer — measured on a real upload, and read from its source
*(POC-5, 2026-08-21 — `planning/POC/RESULTS/POC-5_results.md` §3; source = `ph-navigator-v2`)*

- ⚠ **A face whose construction uses `EnergyMaterialNoMass` is invisible in the Model-tab viewer.**
  Its `ConstructionMaterialSchema` requires `thickness`/`conductivity`/`density`, so a no-mass
  layer fails validation and the face is skipped and **miscounted as an "air boundary"**
  (`model_viewer/extraction.py:238-256`). Apertures vanish with their host face. Measured: Adelphi
  (tier-2, no-mass) renders 40 of 82 faces — the TFA markers only; Bluff Reach (tier-1, real
  layers) renders 194 of 194 with all 40 apertures on their hosts. **The HBJSON is right — the
  same file renders whole in Rhino/GH**; the limit is the viewer's.
- ✅ **Nothing keys on `properties.ph.*.identifier`, and nothing matches entities across uploads.**
  Each HBJSON file is an independent immutable artifact (deduped by content hash); `diff_versions`
  diffs the project *document* on PHN-minted ids. The per-export uuid churn (§4) is therefore
  harmless to this consumer.
- **`global_construction_set` is discarded by honeybee-energy itself on load** —
  `ModelEnergyProperties.global_construction_set` is a read-only property returning the generic
  set; the key is written on export and ignored by `apply_properties_from_dict`. Emitting it is
  inert bytes to any `from_dict` consumer. (This resolves POC-3 D-1's "revisit with ph-navigator
  evidence".)
- **`user_data` is dropped by ph-navigator's DTOs** on model/faces/apertures (shades excepted).
  A disclosure marker there is write-only for this consumer; the channel it *reads back* is a
  top-level `ph_nav` block (its own envelope-export convention).
- **Thermal bridges load (honeybee-ph parses them) and are then discarded** — no display anywhere.
- **A non-solid Room loads fine** — nothing checks solidity; only the file row's `volume_m3`
  (currently unconsumed) is garbage.

## 7. PHX — the write path is reachable, the read path is not

`PHX` converts HBJSON to the certification tools. Phase 2 audited it per subpackage:

| PHX subpackage | Impure top-level imports |
|---|---|
| `from_HBJSON` — HBJSON → `PhxProject` | ✅ none |
| `model` — the PHX object model | ✅ none |
| `to_WUFI_XML` — WUFI-Passive export | ✅ none |
| `to_METr_JSON` — METr export | ✅ none |
| `to_PPP` | ✅ none |
| `xl` — the Excel adapter | ✅ none — Protocol-typed, framework injected by the caller |
| `from_WUFI_XML` — the WUFI **reader** | ❌ `lxml`, `pydantic`, `pydantic_core`, `rich` |
| `PHPP` | ❌ `pydantic` |
| `hbjson_to_phpp.py` | `xlwings` — guarded by `if __name__ == "__main__"` |

Verified empirically, not by reading imports: with `lxml`, `xlwings`, `pydantic` and `rich` **not
installed at all**, `from_HBJSON` → `model` → `to_WUFI_XML` / `to_METr_JSON` produced ~29,000 chars
of WUFI XML and ~51,600 chars of METr JSON.

`PHX.xl` reading clean is not an accident: `xl_typing.py` defines `xl_app_Protocol` and friends, and
`xl_app.py` takes the framework as a constructor argument. PHX never imports `xlwings` — the caller
passes it in.

**So WUFI-Passive and METr export are reachable in the browser.** Adding `phx` costs ~0.4 MB. Never
import `PHX.from_WUFI_XML`, `PHX.PHPP`, or `PHX.hbjson_to_phpp`.

⚠ **PHPP writing is permanently blocked**, and not by packaging: `xlwings` publishes a pure wheel and
imports fine. It fails only when it reaches for a **live Excel**, which an `HtmlDialog` will never
have. This is a runtime blocker, not an install blocker, and it is the one export format Pyodide
cannot deliver. v1 excludes PHPP writing anyway — designPH keeps that job.

## 8. Licences of what gets vendored

Read from each wheel's own `METADATA`, 2026-08-19:

| Package | Licence | Holder |
|---|---|---|
| `honeybee-core`, `honeybee-energy`, `ladybug-core`, `ladybug-geometry`, `ladybug-geometry-polyskel` | **AGPL-3.0** | Ladybug Tools LLC |
| `honeybee-standards` | GPL-3.0 (classifier only) | Ladybug Tools LLC |
| `honeybee-ph` | GPL-3.0-or-later | **BLDGTYP** |
| `ph-units` | *none declared* | **BLDGTYP** |

**The AGPL exposure is entirely Ladybug Tools' code.** The two BLDGTYP packages are our own
copyright. Full briefing: `planning/RESULTS/PHASE-3_licence-question.md` — unresolved, and it must
be answered before v1 code is written.

⚠ Housekeeping regardless of the legal answer: **`ph-units` publishes no licence metadata.**

## 9. Schema contracts

`honeybee-ph-schema` (`~/Dropbox/bldgtyp-00/00_PH_Tools/honeybee-ph-schema`, **not on PyPI**)
publishes the PH extension contracts and has CI built for schema drift. It is what the PRD §7.1
fallback — Ruby writing HBJSON directly — would validate against.

When adding or changing a field on any model class, or touching `to_dict`/`from_dict`, use the
`hbjson-serialization-contract` skill. For PHX model classes, `phx-model`.
