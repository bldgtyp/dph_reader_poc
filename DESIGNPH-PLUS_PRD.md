# DesignPH-PLUS — Product Requirements

**Status:** Draft v1 · 2026-08-19 · BLDGTYP (Ed May, John Mitchell)
✅ **POC-validated 2026-08-21** — a proof of concept built to this PRD ran end to end on five real
models and closed PASS (`planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md`). Its retro **§4 is the ranked list
of what a v1 must do differently**; where the POC contradicted this document, the section carries a
dated correction in place. Read the retro before treating any uncorrected section as settled.
⚠ **Superseded as a product thesis, same day** — the strategy retrospective concluded the right
product is not a standalone extension but a web record above all the tools (folder watcher + readers;
"version control for Passive House"). That PRD is
[`pholio/context/PRD.md`](/Users/em/Dropbox/bldgtyp-00/00_PH_Tools/pholio/context/PRD.md). The
designPH read described here survives as server-side ingest and a fallback exporter; §7.2 (shading),
§8 (translation rules) and §9 (legal posture) remain the reference.
**Grounding:** [`00_Context/DESIGNPH_DATA_MODEL.md`](00_Context/DESIGNPH_DATA_MODEL.md) · [`00_Context/DESIGNPH_FILE_FORMATS.md`](00_Context/DESIGNPH_FILE_FORMATS.md) · [`00_Context/DESIGNPH.md`](00_Context/DESIGNPH.md)

> A SketchUp extension that reads a designPH model and writes a valid, standard **HBJSON** — opening
> Passive House envelope data to viewers, QA tools, reporting, certifiers, and downstream automation.

---

## 1. Problem

designPH is where essentially every CPHC does Passive House geometry, and for certification work it is
effectively mandatory — certifiers in practice refuse projects that do not use its shading calculation.
But the model it produces is a dead end:

- **The data is trapped.** It lives in a `.skp` on one person's laptop. No viewer, no API, no diff, no
  automated QA, no way for a contractor, owner, certifier, or municipality to read it.
- **The model is only half a building.** designPH covers envelope. Mechanical (heat pumps, DHW, PV),
  distribution (ducts, pipes), non-residential and multifamily program, zoning, and multiple ventilators
  are all absent — so a large share of every project is still hand-typed into PHPP.
- **That split causes errors.** Some data in SketchUp, some in PHPP, no single source of truth,
  no way to validate one against the other.

The existing alternative — Rhino → Grasshopper → Honeybee → Honeybee-PH → PHX → PHPP — works well
and is unusable for ~99% of the market. The learning curve is prohibitive, and on small projects you
*still* need a parallel designPH model for certification, so it buys almost nothing.

**There is no bridge from where the industry actually works to the open building-data ecosystem.**

## 2. Proposal

A free, open-source SketchUp extension that converts a designPH model into a standard Honeybee model
and serializes it to **HBJSON** — the same format the Ladybug Tools ecosystem, PHX, and ph-navigator
already consume.

```
designPH (envelope)  ──┐
                       ├──►  Honeybee Model  ──►  HBJSON  ──┬──► viewers / QA / reporting
DesignPH-PLUS v2       │                                    └──► PHX ──► PHPP / WUFI-Passive / METr
(program, mech)      ──┘
```

v1 delivers the top-left path only. That is deliberate — see Non-Goals.

## 3. Why this is viable now

Three findings from the August 2026 investigation, all documented in `00_Context/`:

1. **designPH's data is readable without designPH.** Everything lives in one standard SketchUp
   `AttributeDictionary` (`DesignPH_dict`), reachable through Trimble's public, documented Ruby API.
   No reverse engineering required.
2. **Room-level data does not require watertight geometry.** `honeybee-ph` models rooms as
   `Space` → `SpaceFloor` → `SpaceFloorSegment` with a weighting factor — built from tagged floor
   faces, not closed solids. designPH already tags TFA faces and stores `TFA_rf`. This removes the
   obstacle most likely to have killed the project.
3. **The whole honeybee stack is pure Python** (`py3-none-any` wheels, guaranteed by Ladybug's
   IronPython 2.7 compatibility). That makes running real honeybee inside SketchUp's Chromium
   `HtmlDialog` via Pyodide a live option — no server, no bundled interpreter.

## 4. Users

| User | What they get |
|---|---|
| **CPHC / PH consultant** (primary) | One button in SketchUp → a standard model file they can share, archive, diff, and hand to anyone |
| **Certifier** | A machine-readable model to review alongside the PHPP, instead of a proprietary `.skp` |
| **Contractor / owner** | A web-viewable model (ph-navigator) without SketchUp or a licence |
| **Municipality / program administrator** | A standard format for compliance reporting and portfolio analysis |
| **Tooling & agents** | An open input for QA/QC, checklists, automated review |

## 5. Goals and non-goals

### v1 goals

1. Produce a schema-valid HBJSON from any supported designPH model, read-only, with one action.
2. Carry envelope geometry, assemblies, apertures, and PH `Space`s (TFA) faithfully.
3. Never silently lose or misrepresent data — report, don't guess.
4. Install as a single `.rbz` with no other dependencies.

### Explicit non-goals for v1

These are not deferred by oversight. Each one is load-bearing.

- **No mechanical, DHW, PV, or distribution data.** designPH cannot author it and v1 has no UI.
- **No writing to the model.** v1 is strictly read-only. It cannot corrupt a designPH project.
- **No writing to PHPP.** designPH keeps that job. We are complementary, not a replacement.
- **No shading.** Omitted and explicitly marked — see §7.2.
- **No `.ppp` parsing.** Prohibited by licence — see §9.
- **No non-residential or multi-zone program.** Single residential program only.
- **No watertight-geometry repair.** Non-solid models are accepted and reported.

## 6. Scope — what v1 converts

| designPH source | → Honeybee target |
|---|---|
| Faces + `areaGroupID`/`areaGroupAuto` | `Face` with boundary condition and face type |
| `assemblyID` / `assemblyIDAuto` + `assemblies_calc` + `layer_table_<id>` | `OpaqueConstruction` (see §8.3) |
| Window DC instances (`frametypeid`, `glazingtypeid`, `lenx`, `leny`) | `Aperture` + PH window construction |
| TFA faces + `TFA_rf` | `Space` / `SpaceFloor` / `SpaceFloorSegment` |
| `vent_ud` (`room_height`, `V_n50`) | Space volume, infiltration |
| `ihg_ud` (`num_units`) | Occupancy for the residential program |
| `klima_ID`, `Klima_Standort` | Site / climate identification |
| All faces | A single non-solid `Room` |

## 7. Architecture

### 7.1 Runtime — **decided** (Phase 3, 2026-08-19)

**Pyodide inside the extension's `HtmlDialog`.** Ruby collects the model → hands JSON to the dialog →
real, unmodified honeybee + honeybee-ph runs in WebAssembly → HBJSON returns → Ruby writes it. Zero
install, offline, no server exposed off the machine, and it uses the actual tested library rather than
a reimplementation.

**This is no longer a preference between options.** It was built, run inside SketchUp 2022 on real
designPH models, and measured — first at the Phase 3 spike (82 of 82 classified Adelphi faces, 87 KB
of HBJSON, boot in 2.6 s), then across the whole five-model corpus: **545 of 545 classified faces,
239 of 239 windows, 99 of 99 thermal bridges, none rejected.** Full evidence and the gates:
[`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_results.md`](planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_results.md) and
[`planning/01_sketchup-export/implementation/RESULTS/`](planning/01_sketchup-export/implementation/RESULTS/.index.md).

Four constraints came with it, and each is load-bearing:

**(a) Pyodide 0.24.1, pinned by the dialog's engine.** SketchUp 2022 embeds **CEF 88.2.4 = Chromium
88** (January 2021). Modern Pyodide will not run there — 0.28+ fails to *parse* (ES2022 static blocks,
Chromium 94) and 0.25–0.27 fail to instantiate their wasm (reference types, Chromium 96). 0.24.1
(CPython 3.11) is the newest that works, verified end to end against a real Chromium 88. See §7.4:
**the oldest SketchUp we support sets the newest Pyodide we can use.**

**(b) Served over `http://127.0.0.1`, never `file://`.** A `file://` page cannot fetch its own
assets — `fetch`, `XMLHttpRequest` *and* the dynamic `import()` Pyodide uses are all refused, and the
third cannot be polyfilled. Confirmed inside SketchUp, not merely in stock Chromium. The extension
therefore runs a `TCPServer` on loopback: OS-assigned port, random path token, shut down with the
dialog. It is also the only way to set the COOP/COEP headers `SharedArrayBuffer` would need.

**(c) The server is a worker thread pumped by a sleeping `UI.start_timer`.** Both halves are
required and each omission hangs SketchUp silently — see the CLAUDE.md lessons. This is the single
most fragile part of the design and needs a comment in the code saying why.

**(d) Wheels are installed by unpacking, and `micropip` is not shipped.** `micropip` is coupled to
the Pyodide release and cannot run on 0.24.1; every wheel in the payload is `py3-none-any`, so
unpacking *is* installing. Phase 2 planned the reverse and kept the unpack in reserve — the reserve
became the mechanism.

**Measured cost:** **6.66 MB `.rbz`**, 20.7 MB installed, 2.6 s cold start, 28.8 MB WASM heap,
4 MB verified across the Ruby↔JS bridge in both directions. Exporting a worst-case 1441-face model
costs **139 ms**; the HBJSON is byte-identical to what CPython produces.

**The Python side is settled (Phase 2).** Eight `py3-none-any` wheels — `honeybee-core`,
`honeybee-energy`, `honeybee-ph`, `honeybee-standards`, `ladybug-core`, `ladybug-geometry`,
`ladybug-geometry-polyskel`, `ph-units` — 1.5 MB, no C or Rust extension anywhere in the reachable
closure.

⚠ **The licence question is now live**, because vendoring honeybee (AGPL-3.0) is a decision rather
than a possibility. Written up for counsel:
[`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md`](planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md).
**Resolve it before v1 code is written** (§9).

**Retained as a genuine alternative, not a fallback in waiting:** *Ruby writes HBJSON directly* —
reimplementing honeybee's *serialization* only, validated in CI against published `honeybee-schema`
and `honeybee-ph-schema`. It ships no third-party code and links nothing, so it is the answer if
counsel finds real AGPL entanglement risk for the hosted products. It costs schema-drift maintenance
forever; that is the price of the freedom, and it should be paid deliberately rather than by default.

**Rejected:** bundled Python interpreter (corporate-IT hostile, the thing Ladybug Tools most regret);
server-side `.skp` parsing (no Linux build of the SketchUp C SDK); user-installed Python (support
burden on a free tool).

### 7.2 Shading

**Omitted from v1.** Because PLUS does not write the envelope to PHPP, shading is only needed for a
path we are not building. Certifiers continue to receive designPH's shading through designPH's own
`.ppp` import, exactly as today.

The output **must** carry an explicit `shading: not-computed` marker. Emitting zeros, or omitting
silently, would let a downstream consumer mistake an incomplete model for a complete one.

**Carry the shading *geometry* even without the factors — ⚠ OUT of v1 scope again, pending a UI.**
*(Promoted by Phase 0 §0.4 on the strength of the destination; withdrawn by Phase 1 §1.5 on the
failure of the source rule. See `planning/01_sketchup-export/feasibility/RESULTS/PHASE-1_results.md`.)*

**The destination still stands.** Exterior context geometry has a well-formed home in HBJSON as
`orphaned_shades` with `is_detached: true` and a `ShadePhPropertiesAbridged` block. That was never
the problem.

**The source rule has now failed twice.** Phase 0 refuted "untagged face → shade". Phase 1 tested the
two remaining candidates live and refuted both:

| `faceTypeAuto` | outside envelope bbox | inside |
|---|--:|--:|
| `'xo'` | 252 | 168 |
| `'i'` | 167 | 238 |
| nil | 7050 | 61 |

A 60/40 split is not a discriminator, and the two signals disagree with each other. `faceTypeAuto` is
also **absent entirely** from two of the seven real project models. The bounding-box test is weaker
than it looks: the bbox is the *tagged* faces' extent, so "inside" means "within the building volume",
which contains interior partitions and the envelope's own faces alike.

The scale makes a wrong rule expensive. Adelphi has **8037 live faces**, only **82** tagged. Bluff
Reach: 7467 live, 194 tagged. Exporting untagged-and-outside would emit ~6700 shades where the
reference HBJSON has 1287.

**The signal that does work is the user's own.** Both models carry SketchUp tags naming the intent:
`04_SHADING_TREES` (Adelphi, 392 faces), `Shading_Tree` and `*Vn50` (Bluff Reach). The modeller
already said which geometry is shading — but the tag *names* are user-authored and differ per model,
so no fixed rule can read them either.

**Therefore: v1 asks rather than guesses.** Present the model's tag list, let the user tick which tags
are shading geometry, default to none. Small UI, no heuristic, works on every model including those
with no `faceTypeAuto`. Until that exists, untagged faces are **reported, not exported** (hard rule 4)
— which is where Phase 0 left them, and the position the evidence still supports.

### 7.3 Packaging

One extension, feature-flagged, so v2 adds surface without a second install. Loader stub +
`SketchupExtension` per SketchUp convention. When v2 does write, it writes to its **own**
`DesignPHPlus_dict` — never into `DesignPH_dict`.

### 7.4 Supported versions

**SketchUp 2021+** (VFF container era), **designPH 2.2+**. Read `designPH_version` from the model and
**refuse politely on anything unrecognised** rather than guessing. A wrong-but-plausible HBJSON would
do more damage to a free tool's reputation than a clear refusal.

⚠ **The SketchUp floor is now a technical constraint, not just a compatibility preference.**
SketchUp 2022 = Chromium 88 caps the vendored runtime at Pyodide 0.24.1 / CPython 3.11 (§7.1). Every
SketchUp release ships a newer CEF, so raising the floor raises the ceiling. **Unresolved: which
SketchUp versions the market actually runs**, and whether dropping 2022 buys enough to be worth the
users it costs. Decide before v1 pins a runtime.

⚠ **Open question on the 2.2 floor.** The primary corpus model `adelphi-designph.skp` is designPH
**2.1.15** — below the stated floor, so v1's own version gate would refuse it. Decide in Phase 1
whether the floor drops to 2.1 or the corpus model gets re-saved from a newer designPH.

*(Phase 0 update: this is cheaper than it looked. The version-keyed read rule in §6 of the data-model
record **did not survive the full corpus** — every real project model stores its data in the `*ID`
keys whatever its version stamp. If that holds per-face in Phase 1, the 2.1/2.2 distinction largely
stops mattering for reading, and the floor can drop to 2.1 at no cost. The version gate still earns
its keep as a **refuse-on-unrecognised** guard for versions above what we have tested.)*

## 8. Translation rules

### 8.1 Rooms and geometry

One `Room` per model, built from the face list. **Non-solid is accepted** — designPH models are
surface models and most real ones will not be solid; requiring solidity would reject the majority of
the market. Run `check_solid()` and surface the result in a validation report.

Volume comes from designPH's `vent_ud` (`room_height`, `V_n50`), not from geometry — so non-solid
geometry does **not** make the PH results wrong. It only limits downstream uses needing a sealed
volume (daylight, CFD), which are not v1's consumers.

### 8.2 Apertures

Windows are Dynamic Components offset from the wall plane by their reveal depth, so naive extraction
produces non-coplanar apertures that honeybee rejects.

1. Find the host face — **`ComponentInstance#glued_to`**; fall back to nearest coplanar face.
2. Project the window rectangle onto the host plane, **discarding the reveal offset**.
3. Carry reveal depth into PH aperture properties, not geometry.
4. Validate containment. **On failure, report the window by its designPH name — never drop silently.**

✅ **Host lookup is solved** *(Phase 1 live run, 2026-08-19)*. `glued_to` resolves on **46 of 46**
windows in the Adelphi model. Geometric nearest-coplanar-face is a genuine fallback, not the primary
path — the "more work, more failure modes" risk the spike plan flagged is retired.

⚠ **Updated 2026-08-21:** `face.loops.size > 1` is not a host test either — a glued opening creates
no loop (true on only 2 of the 16 real hosts). Use `glued_to`, and note that `face.area` is
consequently **net** of window openings while the loop polygon is **gross**
(`00_Context/DESIGNPH_DATA_MODEL.md` §5.0).

⚠ **Do not infer holes from `cuts_opening?`.** It is `true` on all 46 windows and yet only **2 of 16
host faces** carry inner loops; the rest are unbroken, several hosting six windows each.
`cuts_opening?` is a property of the component **definition** — *"this component is able to cut"* —
not a statement about the host. Trusting it would punch a hole in every emitted `Face3D` and leave 44
apertures with nothing to fill. ~~Test `face.loops.size > 1` on the host instead~~ — that is not a
host test either (above). **`glued_to` is the only one.**

**Step 2 needs a limit, and this is the sharpest lesson of the whole aperture path.** Projection onto
the host plane is *lossy in exactly the way a coordinate-space bug is*: a rectangle a metre off the
wall projects onto it as cleanly as one a millimetre off. Shipping the window transform
parent-relative put all 46 of Adelphi's windows 1.2–3.3 m from their hosts and produced **no symptom
anywhere**. v1 must refuse a rectangle further off the plane than a reveal could explain, and report
the distance on every window that passes (`00_Context/DATA_CONTRACTS.md` §7.0).

Edge cases to handle explicitly: window straddling two faces; window larger than host; host face with
no `DesignPH_dict`; `glued_to` returning nil after a user moved a window; **a host face that does
carry inner loops** (Adelphi has two).

⚠ **Two more that honeybee itself creates, both observed on real data and neither repairable without
fabricating an area** (`DATA_CONTRACTS.md` §7.1.1):

- **A window flush with the host edge.** `Face3D.is_sub_face` takes no tolerance, so a corner 1 µm
  past the boundary — coordinate rounding, not an overhang — reads as *not fully bounded*. 2 of
  Adelphi's 46.
- **A host that already models its opening as an inner loop** subtracts it twice, because honeybee
  expects an aperture on the *gross* face.

v1's answer is to emit the aperture and **predict honeybee's verdict in the report**, saying which
case it is. Shrinking a window to please a validator would fabricate an area.

### 8.3 Assemblies

*(Rewritten after Phase 1 — see `planning/01_sketchup-export/feasibility/RESULTS/PHASE-1_assembly-resolution.md`. The previous
version assumed `layer_table_<id>` was the source for every face; it is the source for under half.)*

**First, read the area group — it decides which id namespace `assemblyID` is in, *and* which entity
type carries it.** designPH uses one key name for two unrelated tables on two different entities:

| Area group | Entity | `assemblyID` names | Target |
|---|---|---|---|
| 15, 16, 17 — thermal bridges | ⚠ **`Sketchup::Edge`** | a **`connections_ud`** row (Psi-value, f_Rsi) | `PhThermalBridge`, **not** a construction |
| everything else | `Sketchup::Face` | an assembly | an opaque construction |

Both namespaces use `NNud` ids, so looking a thermal bridge up in the assembly table returns either
nothing or an unrelated construction. Getting this backwards is silent and plausible-looking.

⚠ **The reader must walk edges as well as faces.** Thermal bridges are linear — PHPP enters them as
lengths — and designPH attaches them to edges. On `2414 Bluff Reach.skp` that is 99 of 293 tagged
entities; **a face-only traversal loses every one of them without an error.** Verified live
2026-08-19; see `00_Context/DESIGNPH_DATA_MODEL.md` §7.1.

**Then resolve the assembly, in four tiers.** Measured across the seven real corpus models:

| Tier | Refs | Translation |
|---|--:|---|
| `layer_table_<id>` in the model | 254 | Map faithfully into `PhDivisionGrid` on `EnergyMaterialPhProperties`. designPH's three parallel paths (`desc1/lambda1` … `surf2_percentage`, `surf3_percentage`) are a 1×3 grid. ⚠ **"The target model supports this natively" is half true — see §8.3.1** |
| `assemblies_*` header row only | 42 | U-value and thickness, no build-up → a single `EnergyMaterialNoMass`. Note it has `divisions = None`, so no grid is possible |
| designPH's **installed** `data/phpp_assemblies_ud.csv` | 95 | Same as above, but the source is *outside the model*. Read it, and **record that the source was the plugin folder, not the file** |
| Certified library `phpp_assemblies_cert.csv` | — | Same shape; PHI-certified components |

**Zero references in the corpus were unresolvable** once the two namespaces are separated — but
**only 254 of 532 carry a build-up.** v1 must not promise a layer stack per surface.

Keep `R_in` / `R_out` as film resistances and `additional_U_value` on PH properties — **do not fold
them into materials.** A reviewer must still be able to see the numbers.

**Report the tier for every surface** (hard rule 4). A U-value with no build-up is a legitimate and
common state, not an error; the failure would be presenting it as though it were a full assembly, or
substituting a default. Never substitute a default.

### 8.3.1 ⚠ honeybee cannot carry a framed assembly's U-value, and the grid does not rescue it

*(Measured 2026-08-21 against designPH 2.4.0 BETA's own U-/R-value calculator.)*

designPH computes a multi-section assembly by **ISO 6946 §6.7 — the mean of an upper and a lower
resistance limit**, and prints the spread between them as its *Error %*. That is not something a
layer can carry:

- **`OpaqueConstruction.u_value` reports the section-1 value**, because a layer's conductivity is one
  number and `lambda1` is the one it gets. On Linde's `06ud`: **0.0698 against designPH's 0.0750 —
  8 % low, in the direction that flatters the building.**
- ⚠ **`PhDivisionGrid.get_equivalent_conductivity` is an area-weighted lambda**, which is ISO 6946's
  **lower** limit. So a PH-aware consumer reading the grid still gets an optimistic number, just a
  less optimistic one.
- **designPH's U includes the surface films**; honeybee's `u_value` is material-only. On unframed
  assemblies that difference alone is 0.004–0.005 W/m²K.

The POC emits the real layers, sets the grid to the **real areas** (equal column widths would
describe a stud bay as half timber), and carries designPH's own figure on the report as
`u_value_iso6946` with the section areas and the spread. **v1 needs a better answer than a report
field, and it is plausibly an upstream one** — `PhDivisionGrid` exists for exactly this case and
computes the wrong limit. Worth raising with honeybee-ph rather than working around locally.

⚠ **Scale, so this is not over-built:** only **4 of 82** `assemblies_calc` rows on Linde carry a
non-zero section percentage, and Wellington and Bluff Reach carry none. 49 % of Linde's *layers* have
a `lambda2`, but a `lambda2` with no area is not a framed layer — counting those overstates the
population fivefold.

This is the easiest place to be quietly wrong. Regression-test computed U-values against designPH's
own reported values — ground truth for the Adelphi building is extracted to
`planning/01_sketchup-export/feasibility/RESULTS/phpp/phpp_u-values_assemblies.csv` (12 assemblies) and `..._layers.csv` (56 layers).

⚠ **One dependency to be honest about: the model is not self-contained.** The `83ud`–`99ud` range is
designPH's shipped default library, living in the plugin folder rather than in the `.skp`. The
extension runs beside those files so it can read them, but output then depends on which designPH the
reader has installed. Adelphi shows the alternative — it carries an `assemblies_ud` *snapshot* of the
library inside the model — but designPH only sometimes writes one.

### 8.4 Spaces and program

`Space`s built from designPH's TFA faces, with `TFA_rf` mapping onto segment weighting factor.

A single **`PH Residential`** program: occupancy derived from `ihg_ud.num_units`, everything else PHI
defaults, nothing user-editable in v1. Seed from `honeybee_revive_standards/` (the `rv2024_*` schedule
set) and `honeybee_energy_ph/library/programtypes.py`. Ship it as a named, versioned program in the
repo so it is inspectable and arguable, not buried in code.

## 9. Legal and licensing

**Not legal advice. Confirm with counsel and with PHI before building on any of it.**

The [designPH Licence Agreement](https://database.passivehouse.com/en/designph/licence-agreement/)
**§2.4(a)** prohibits attempts to "reconstruct or discover any source code, underlying ideas,
algorithms, **file formats or programming interfaces**."

- **Parsing the `.ppp` export is out of scope for v1.** On a plain reading it is reverse-engineering a
  file format, named explicitly.
- **Reading `DesignPH_dict` is defensible.** The data sits in the user's own `.skp` — SketchUp's
  format, not designPH's — and is read through Trimble's public, documented API.
- **§2.4(d)** permits derivative works "expressly authorized **in writing**", so PHI can authorise
  `.ppp` access. That is a v2 conversation.
- The clause carries the standard carve-out for what applicable law protects; EU Software Directive
  2009/24/EC Art. 6 permits decompilation **for interoperability**, and PHI is German. Whether that
  reaches a US developer depends on governing law. **Unresolved — for counsel.**

**Position with PHI:** complementary, and say so loudly. designPH's core value is 3D authoring plus the
shading calculation; we replace neither. If PHI wants to absorb the mechanical-authoring idea into
designPH proper, that is a good outcome. **"PHI actively objects" is the only true deal-breaker in this
plan** — every technical obstacle found so far has a workaround; that one does not.

**Our licence:** decide after the runtime spike. Pyodide vendors honeybee (AGPL-3.0) and forces
AGPL-3.0 on us, which entangles the future hosted products. The Ruby-writer route links nothing — file
formats are not copyrightable — leaving the licence free to choose. Pick deliberately, not by accident.

## 10. Spikes — do these before committing

| # | Spike | Decides | Est. |
|---|---|---|---|
| S1 | ✅ **Done 2026-08-19 — PASS WITH CHANGES (pending Windows).** Real honeybee + honeybee-ph runs inside SketchUp 2022's `HtmlDialog` and writes HBJSON from a real designPH model: 82/82 faces, 0 rejected, boot 2.6 s, 6.87 MB `.rbz`. Four constraints came with it — Pyodide pinned at 0.24.1 by Chromium 88, loopback not `file://`, worker-thread server, `zipfile` not `micropip` | The entire runtime architecture — **Pyodide adopted** (§7.1). Windows untested | 1–2 d |
| S2 | Are designPH windows glued (`glued_to`)? Do they `cuts_opening?` | Aperture strategy (§8.2); openings change the mapping | 30 min |
| S3 | ~~Resolve~~ **Confirm** the `*Auto` vs `*ID` rule — largely settled by the Adelphi model, see `00_Context/DESIGNPH_DATA_MODEL.md` §6 | How to read face assignments | 1 h |
| S4 | Obtain designPH 3.0; re-run S3 and the key inventory against it | Whether v1 can support what the market runs | 1 d |
| S5 | ~~Is PHX pure?~~ ✅ **Done 2026-08-19 — PASS WITH CHANGES.** `honeybee-ph`'s reachable closure is 8 pure wheels / 1.5 MB. PHX *declares* `lxml` and `xlwings` but its **write path imports neither** — `from_HBJSON` → `model` → `to_WUFI_XML` / `to_METr_JSON` runs with both absent. `xlwings` gates PHPP writing only, which §5 already excludes | Phase 3 loads 8 wheels with `deps=False`; PHX's write path is a stretch goal, not out of scope | 30 min |
| S6 | Conversation with PHI | Whether v2 gets `.ppp` and shading | — |

S2 and S3 use the **BT Attribute Inspector** already installed at
`~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/bt_inspector/`.

## 11. Definition of done

v1 ships when, across the regression corpus:

1. **Output validates** against `honeybee-schema` — **scoped to the core geometry and PH payloads**,
   which is all v1 writes.
2. **Output loads and renders correctly** in ph-navigator.

Both automatable; neither requires PHPP or a certifier in the loop. Together they prove the thesis —
a valid standard model a real downstream consumer can use.

✅ *Both criteria were exercised by the POC on real models (2026-08-21).* Criterion 1 passed on all
five outputs. Criterion 2 passed with one named consumer-side exception a v1 must plan around:
**ph-navigator's viewer skips any face whose construction uses `EnergyMaterialNoMass`** — so a
tier-2 (U-value-only) assembly renders without its envelope (Finding 71,
`planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md` §3.2; `00_Context/HONEYBEE_STACK.md` §6.4). The fix is
BLDGTYP's on either side of that seam.

⚠ **Two corrections from Phase 0 §0.4** (`planning/01_sketchup-export/feasibility/RESULTS/reference_hbjson_shape.md`):

- **The scoping in criterion 1 is load-bearing, not hedging.** The *reference* HBJSON does not
  validate against `honeybee-schema` 1.53.1 — 147 objects fail — but every failure sits inside
  `properties.energy`, and **none** touches geometry, boundary conditions or `properties.ph`. Those
  are honeybee-energy payloads v1 does not write. The criterion is sound; do not weaken it on the
  strength of the reference's own failures.
- **`honeybee-ph-schema` was dropped from criterion 1.** At v0.1.0 it is not published to PyPI, every
  model declares `extra="allow"`, and no field is required — a payload of `{}` validates. It is a
  contract stub, not an acceptance gate. **Open decision:** tighten the schema, or replace that half
  of the criterion with an explicit per-field expectation list. *(`AGENTS.md`'s "schema contracts are
  published in `honeybee-ph-schema`" overstates both the publication and the coverage.)*

**Explicitly not a v1 gate:** numerical agreement with PHPP. That is v2, and chasing it now would drag
`.ppp` parsing and shading straight back onto the critical path.

**Regression corpus:** `corpus/adelphi/` is the primary reference — the same building as
designPH `.skp`, `.ppp`, PHPP `.xlsm`, HBJSON, Rhino `.3dm` and Grasshopper `.gh`. Secondary: the
`08_DesignPH` folders that actually hold designPH models *(verified on disk 2026-08-19)* —
2523 Wellington (2.1.10 + 2.2.29), 2524 Linde Residence (2.1.15), 2414 Bluff Reach (2.2.24),
2605 MacDonough (2.2.29), 2536 Holmes Residence (2.2.29). *(Superseded: an earlier draft named High
Street, Arrowhead Ridge, Ikon Optima Plus, and 415 Flint — those folders hold no designPH model.)*

⚠ Caveats on the Adelphi set: ~~the promised HBJSON is absent~~ *(superseded 2026-08-19 —
`adelphi-honeybee-json.hbjson` was supplied: schema 1.53.1, 6 rooms / 52 faces / 44 apertures /
38 spaces / 1287 orphaned shades. It is a **shape reference**, not an equality target — it came from
the Rhino route with solved adjacency, while v1 emits one non-solid Room by design; see
`planning/01_sketchup-export/feasibility/00_OVERVIEW.md`)*. The formats remain only **approximately aligned**, so a numerical
mismatch between them is not by itself evidence of a translator bug.

✅ **The regression corpus is now captured and reconciled** *(POC-2, 2026-08-21)*. Five models —
Adelphi, Bluff Reach, Wellington, `250703 - Linde Residence`, `250708` — spanning designPH
2.1.15–2.2.29 and SketchUp 22–26, live extractions banked in `pocs/01_sketchup-export/_private/fixtures/` and checked
against the offline scan of all 14 corpus files. Between them they exercise every path v1 has:
thermal bridges (99), all four assembly tiers, multi-section assemblies, TFA, `*Auto`-only
assemblies, `descName` overrides at scale, and a model (`250708`) that resolves **nothing** in-model.

⚠ **"Approximately aligned" is now measured, and it has a rule.** Adelphi's `.skp` and its PHPP share
**no id space** — the same constructions are `83ud`/`84ud`/`85ud` in one and `01ud`/`07ud`/`13ud` in
the other — and only 3 of 14 assemblies share a name. **Join by name, and treat the PHPP as ground
truth for arithmetic and method, never for identity** (`00_Context/DATA_CONTRACTS.md` §8). That
distinction is what stopped an alignment artefact reading as a translator bug.

## 12. Distribution

Free and open-source. Adoption matters more than revenue: a paid closed tool will not become the
interchange standard this is trying to be, and open-source substantially defuses the PHI risk — it is
much harder to object to a free community bridge that *sells designPH licences*.

- **Repo:** `github.com/PH-Tools` — reads as community infrastructure rather than a vendor tool.
- **Channel:** GitHub releases first, for iteration speed. Extension Warehouse once the format
  stabilises; its review turnaround will hurt during the weekly-bugfix phase.
- **Platforms:** Windows and Mac, both, at v1. Most CPHCs are on Windows. This cannot slip.
- **Revenue** comes later and elsewhere — hosted viewer, QA, reporting, agentic workflows, sold to
  municipalities and programme administrators, not to CPHCs.

⚠ **Naming / prior art.** BLDGTYP already shipped two small public extensions under the dPH+ brand —
`dPH+ Rooms` (~2021) and `dPH+ Windows` — at `~/Dropbox/bldgtyp-00/00_PH_Tools/design-ph-plus/`.
Useful precedent for the PHI conversation (see `planning/01_sketchup-export/feasibility/PHASE-5`), but decide before release whether
DesignPH-PLUS supersedes that branding, and make sure the new extension's Ruby module and menu
namespace cannot collide with a legacy `dPH+` install on a user's machine.

## 13. Roadmap

**v1 — Envelope → HBJSON.** Read-only. This document.

**v2 — Authoring.** Mechanical, DHW, PV, distribution entered in SketchUp and written to
`DesignPHPlus_dict`. Non-residential and multi-zone program. Multiple ventilators. Requires: a data
model, a real UI, and round-trip rules for what happens when designPH re-runs over PLUS data.
This is where the single-source-of-truth promise is actually kept.

**v3 — Hosted.** ph-navigator integration, sharing, versioning, QA/QC, compliance reporting. Where the
revenue thesis lives.

**Ongoing conversations:** PHI (`.ppp`, shading, possible absorption of the authoring idea);
Ladybug Tools (they have no SketchUp presence — a credible bridge into the largest architectural
modeller is worth more to them than to us; open with something working, not with a maintenance ask).

## 14. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| PHI objects | **Existential** | Early conversation; complementary positioning; open-source; S6 |
| Pyodide fails in `HtmlDialog` | High | S1 before commitment; Ruby-writer fallback is real |
| designPH 3.0 schema differs | High | S4 early; version gate refuses rather than guesses |
| Silent aperture loss | High | Never drop without reporting (§8.2); regression corpus. ⚠ **Retired as a guess, live as a measurement:** the POC lost all 46 to a coordinate-space bug that projection absorbed *silently*. Any lossy step needs a stated limit (§8.2) |
| `*Auto`/`*ID` misread | Medium | S3; read-only v1 means it cannot corrupt anything |
| U-value translation wrong | Medium | Regression test against designPH's own reported values. ⚠ **This risk fired**: framing was ignored entirely, 8 % low and flattering, until the regression was pointed at a model that actually has framed assemblies (§8.3.1) |
| **A check or harness that is wrong about correct data** | **Medium–High** | *New, 2026-08-21.* Three of four real captures failed reconciliation on checks comparing the wrong quantities, and the data was right every time. Validate a check against **more than one model** before trusting it to grade — Adelphi masked every one of these by being the simplest model in the corpus |
| **Evidence from a single sample** | **Medium–High** | *New, 2026-08-21.* Six separate rules on this project were inferred from n=1 and were wrong. Check against the whole corpus baseline before generalising; it is cheap and it exists for this |
| designPH changes attribute schema without notice | Medium | Version gate; it is not a published interface |
| AGPL constrains hosted products | Medium | Licence decision deferred until after S1 |

---

## Appendix — decision log

Design decisions and their rationale, from the 2026-08-19 planning session.

| # | Decision | Because |
|---|---|---|
| 1 | Product for the CPHC market, not internal | BLDGTYP uses Rhino; the market has no path at all |
| 2 | Value is downstream unlock + SSOT, not time saved | If it only saved typing, a PHPP macro would beat it |
| 3 | v1 envelope-only, read-only | Ships the piece everything else depends on; no UI needed; cannot corrupt |
| 4 | Complementary to designPH, not a replacement | Turns the PHI conversation from competitor to partner |
| 5 | `.skp` only, no `.ppp` | Licence §2.4(a) |
| 6 | Shading omitted, explicitly marked | Only needed for a path we are not building (follows from #4) |
| 7 | Single non-solid Room + PH `Space`s | Most designPH models are not solid; volume comes from data |
| 8 | Pyodide preferred, Ruby-writer fallback | Real tested code, zero install; fallback avoids AGPL |
| 9 | One extension, feature-flagged | Two installs, two update cycles, mismatched-version users |
| 10 | Done = schema-valid + loads in viewer | Automatable; avoids dragging `.ppp` back onto the path |
| 11 | Free, open-source, `PH-Tools` | Adoption over revenue; defuses PHI risk |

**Decisions taken during the POC** *(2026-08-21, recorded here because they are product decisions,
not implementation ones)*:

| # | Decision | Because |
|---|---|---|
| 12 | **Degenerate input is reported and carried, never repaired or dropped** | Real models hold slivers, zero-width spurs and sub-micron non-flatness — Adelphi's 82 classified faces include 8 with a sub-mm edge and 7 whose boundary revisits a point. Dropping a classified face breaks *82 of 82*, the first number a reader checks, to save 1.7 cm² |
| 13 | **Noise is flattened below a stated, reported threshold; slope is refused** | 1 mm. Snapping 12 µm of coordinate noise is not the projection that would be fabrication — and the alternative was losing 368 m² of TFA to two faces. The line has to be explicit and every face on either side of it named |
| 14 | **The area group wins over honeybee's geometric inference** | designPH's area group is PHPP's own classification; honeybee infers type from tilt and winding. Where they disagree, flip the geometry to match the group. Letting honeybee win would quietly re-file a TFA marker as roof |
| 15 | **Where honeybee cannot represent designPH's number, emit ours and predict honeybee's verdict** | Applies to framed U-values (§8.3.1) and to apertures honeybee will call unbounded (§8.2). Fabricating geometry or conductivity to satisfy a validator is the one thing worse than a reported discrepancy |
| 16 | **The shading disclosure travels *inside* the HBJSON** (`user_data`) | A marker beside the file can be separated from it. Verified to survive `to_dict`/`from_dict`; the model must not be passable on without the disclosure |
