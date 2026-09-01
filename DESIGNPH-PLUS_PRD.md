# DesignPH-PLUS Product Requirements

**Status:** Draft v2 · 2026-09-01 · BLDGTYP (Ed May, John Mitchell)
**Reframed 2026-09-01 around four affordances (§2)**, after POC #3's passes and the 2026-08-31
product-shape discussion. Draft v1 (2026-08-19) was an exporter-only thesis; its technical spec
survives intact as the **Export** affordance (§6 to §8, §11), and where the POC contradicted it,
the section carries a dated correction in place. Read the POC #1 retro
(`planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md` §4, the ranked list of
what a v1 must do differently) before treating any uncorrected section as settled.
✅ **Evidence base:** the Export pipeline ran end to end on five real models (POC #1, closed PASS
2026-08-21) and was reproduced headless (POC #2, 2026-08-29); the Import write path is proven
with a frozen mapping contract (POC #3, 2026-08-31).
**Business model (Ed, 2026-09-01, decided later the same day):** a commercial pairing with
PH-Navigator, **Model 2 selected**: the plugin is free and open-source (manual Export
included), the hosted PHN subscription is the revenue, and pholio is a separate paid
downstream service (§12.1). PHN productization is the critical path to revenue; the 2026-08-17
PassivSure proposal is being revisited for it (§12.5). *(Supersedes Draft v1's free/open-source
thesis and decision log #11; the brief both-paid working model is superseded by #26.)*
**Naming (Ed, 2026-09-01):** the extension ships as **PH-Navigator for SketchUp**; designPH
appears only descriptively; "DesignPH-PLUS" stays the internal codename (§12.4).
**Relationship to pholio** *(supersedes v1's "superseded as a product thesis" banner)*: the
2026-08-21 retrospective concluded the record above the tools is its own product. That product
is [`pholio`](/Users/em/Dropbox/bldgtyp-00/00_PH_Tools/pholio/context/PRD.md), and it stays
fully separate. The 2026-08-31 product-shape discussion re-established DesignPH-PLUS as the
**tool-side** product beside it: a plugin inside the CPHC's own workflow, while pholio remains
the record above the tools. The two share the frozen contracts and `00_Context/`, never a
product surface.
**Grounding:** [`00_Context/DESIGNPH_DATA_MODEL.md`](00_Context/DESIGNPH_DATA_MODEL.md) · [`00_Context/DESIGNPH_FILE_FORMATS.md`](00_Context/DESIGNPH_FILE_FORMATS.md) · [`00_Context/DESIGNPH.md`](00_Context/DESIGNPH.md)

> A SketchUp extension that makes the designPH model the complete, transparent center of a
> Passive House project: **import** library data from PH-Navigator, **build** the data designPH
> is missing, **export** the whole model as standard **HBJSON**, and, as a research question,
> carry the CPHC ↔ certifier **conversation** spatially on the model itself.

---

## 1. Problem

designPH is where essentially every PHI-CPHC does Passive House geometry, and for PHI
certification work it is effectively mandatory. PHI certifiers in practice refuse projects that
skip its shading calculation. But the model it produces stops short in four distinct ways, and
each one maps onto an affordance of this product (§2):

- **The data is trapped** *(→ C · Export)*. It lives in a `.skp` on one person's laptop. No
  viewer, no API, no diff, no automated QA. A contractor, owner, certifier, or municipality
  cannot read it, and neither can a reporting or QA system.
- **designPH only does half the work required** *(→ B · Build)*. designPH covers envelope.
  Mechanical (heat pumps, DHW, PV), distribution (ducts, pipes), non-residential and multifamily
  program, zoning, volumes, spaces, ventilation flow-rates, and multiple ventilators are all
  absent, so a large share of every project is still hand-typed into PHPP.
- **designPH data entry hurts** *(→ A · Import)*. designPH only allows manual typed data entry
  for assemblies, window-frames, and window-glazing, per project. This manual entry is slow,
  error-prone, and opaque, and there is no way to share it across projects. The same data
  already gets built once, properly, in a library tool like PH-Navigator.
- **Review happens blind** *(→ D · Notes)*. A certifier's comment arrives as an email or a PDF
  markup pointing at "the north wall". It sits outside the model, carries no version, and the
  next person who opens the file never sees it. No spatial, cataloged conversation attaches to
  the geometry being reviewed.

The first three combine into the problem underneath: **PHPP has a dual-entry provenance
problem.** Some inputs arrive via designPH and some by hand, indistinguishably. Six months
later, when the model needs editing, nobody can tell where a number came from or where to
change it. No single source of truth, no way to validate one side against the other.

The existing alternative, Rhino → Grasshopper → Honeybee → Honeybee-PH → PHX → PHPP, works well
for BLDGTYP but is unusable for ~99% of the market. The learning curve is prohibitive, and on
small projects you *still* need a parallel designPH model for certification, so it buys almost
nothing.

**There is no bridge from where the industry actually works to the open building-data
ecosystem.**

## 2. The product: four affordances

*(This section is the 2026-09-01 reframe. Draft v1 proposed only what is now affordance C; the
POC results and the 2026-08-31 product-shape discussion widened the product to four sides of one
plugin.)*

One SketchUp extension, four affordances, one shared data store: the model.

| | Affordance | What it does | Status · evidence |
|---|---|---|---|
| **A** | **Import** | Pull assemblies, window frames, and glazing types down from PH-Navigator into the model's own designPH library tables | ⭐ **Proven** (POC #3): designPH lists, assigns, computes (8/8 exact incl. Error %), saves, and exports our writes; mapping contract **frozen v1**. The v-0 product (§2.1) |
| **B** | **Build** | Author the data designPH is missing in the model, under our own namespace: rooms, ventilation airflows, multiple ventilators, ducts, pipes, mechanical, DHW, and the rest of §2.2's list | Vision (v-2, staged). The data model exists (honeybee-ph); needs UI + round-trip rules (§2.2) |
| **C** | **Export** | Emit the whole model, designPH's data plus PLUS's, as standard HBJSON for every downstream consumer | ⭐ **Proven twice** (POC #1 in SketchUp: 545/545 · 239/239 · 99/99; POC #2 headless: canonically identical output). Release gated on the AGPL answer. §2.3; spec §6 to §8 |
| **D** | **Notes** | A spatial review conversation: notes pinned to geometry, threaded, cataloged, navigable | ▶ **Research** (added 2026-09-01), §2.4 |

```
                        ┌────────────── the designPH model (.skp) ──────────────┐
A · Import ───────────► │  DesignPH_dict (designPH's own library tables)        │
  (from PH-Navigator)   │  DesignPHPlus_dict (rooms, vent, mech, DHW, …)        │ ◄── B · Build (in SketchUp)
                        │  review threads on the geometry (research)            │ ◄── D · Notes (CPHC ↔ certifier)
                        └───────────────────────────┬───────────────────────────┘
                                                    │  C · Export
                                                    ▼
                                          HBJSON ──┬──► viewers / QA / reporting (PH-Nav, PassivSure)
                                                   └──► PHX ──► PHPP / WUFI-Passive / METr
```

### 2.1 A · Import: the PHN library sync *(the v-0 product)*

**Pull-based, inside SketchUp, model open.** This is the only transport ever proven; every
POC #3 write ran this way. PH-Navigator stays a web app and never learns SketchUp exists; the
extension is a read-only consumer of the PHN API (project-scoped token). Windows are **types
only**: frames and glazings per the frozen contract, with window geometry staying the user's
job in SketchUp.

The evidence (POC #3, 2026-08-31, `planning/03_library-import/`): designPH accepts foreign
model-level library writes with zero entity-level side-requirements. 8 real PHN assemblies
(multi-section 3-path included) reproduce their intended U-value **and Error % exactly** in
designPH's own calculator, on two models and both base64 styles, and reach the PHPP export. The
foreign `phn_id` column is read-tolerated, save-preserved, and export-inert, so re-import is a
rename-safe **update** rather than a duplicate. Mapping:
[`CONTRACT_phn-library.md`](planning/03_library-import/CONTRACT_phn-library.md) (frozen v1);
durable write rules: `00_Context/DESIGNPH_DATA_MODEL.md` §14.

**No honeybee inside.** The write path is pure Ruby with native `Marshal`, so this affordance
has no AGPL exposure. Its remaining licensing questions are the designPH-licence wording and
the PHI conversation (§9). Known limits: proven on two models, one machine, designPH 2.2.29
stable. The v-0 scope document (the POC #3 L-C gate) carries the version-sweep hardening budget
and the UX: a dry-run report before every write, `phn_id` semantics bound to UI, and
"re-initialise designPH after import" as a first-class instruction.

**Import also carries the commercial logic** (§12): the library is PH-Navigator's product, and
this affordance delivers it into the tool every PHI-CPHC already uses.

### 2.2 B · Build: the missing half of the building *(v-2, staged)*

A large amount of data that PHPP needs still gets input by hand since designPH does not support it yet: **rooms/spaces and ventilation airflows, multiple ventilators, ERV ducting, DHW piping, fans, pumps, heat pumps, hot-water tanks, mechanical-system assignment, site energy, occupancy, lighting, electrical appliances, foundations.** The goal: the SKP is the one place the project's data is managed, and the one file handed over for certifier review with all the data in it.

**BLDGTYP is user zero** (Ed, 2026-09-01). Even at zero external sales, Build pays for itself
in BLDGTYP's own project work: the Rhino route has known stumbling blocks (shading above all),
a designPH model happens on every project anyway, and a better designPH workflow is direct
internal value. That underwrites building Build inside the free plugin (§12.1).

Three structural decisions, made now so Build stays buildable:

1. **Most of this is data rather than modeling, and that is what stages it.** Ventilator
   counts, tanks, occupancy, and appliances need forms and storage, not geometry, and
   data-shaped items can also arrive down the Import channel (PHN already holds much of it).
   The geometric items are different. Duct runs, pipe runs, and rooms are what SketchUp is
   good at, and they are the pieces a certifier can least verify from paper: a 3D model of the
   DHW loop or the ERV runs is a better review artifact than a PHPP cell. Geometric authoring
   is Build's long-term case; the forms come cheaper and earlier.
2. **The namespace is ours.** Build writes only `DesignPHPlus_dict` (hard rule 2); designPH's
   entity data is never touched.
3. **The data model is honeybee-ph's, not a new one.** The schema exists, round-trips, and PHX
   already serializes it to PHPP / WUFI / METr. Build is a SketchUp UI over a proven model. It
   mirrors the core `honeybee_grasshopper_ph` toolkit's semantics rather than inventing new
   ones.

**How Build data reaches PHPP:** designPH will not carry it. The path is
C · Export → PHX → PHPP (PHX's existing write path), or the certifier reads it from the
HBJSON viewer. That is how §1's dual-entry problem dies: everything enters model-side with
provenance, and the calculator (PHPP today, OpenPH eventually) becomes a throwaway compute
artifact instead of today's mix of calculator and information model.

**Open, and required before any Build code:** round-trip rules for what happens when designPH
re-runs over a model carrying PLUS data (flagged since Draft v1, still unanswered), and the
staging order within the list.

### 2.3 C · Export: the open record *(v-1)*

The Draft-v1 thesis, intact: one action, one schema-valid HBJSON, report-don't-guess. The
technical spec is §6 to §8; the definition of done is §11. Both are POC-validated on five real
models and reproduced headless. Engineering does not gate release, and with Model 2 selected
(§12.1) neither does the business model: the plugin ships open-source, so vendoring honeybee is
AGPL-compatible and the proven Pyodide runtime stands. Counsel confirms the posture rather than
choosing the architecture (§9); the remaining AGPL work item is server-side, in PHN (§12.5).
The Ruby-writer alternative (serialize against the published schemas, link nothing) remains a
fallback (§7.1). A headless export is deliberately not this product; that is pholio's reader.

### 2.4 D · Notes: the spatial review conversation *(research, added 2026-09-01)*

The values first: **certifier transparency and communication are core things this plugin exists
to enable.** Today a certifier's comment is an email pointing at "the north wall". The feature
pins notes spatially to model geometry (*"THIS wall right here is the wrong assembly type"*),
threads them with conversation history, catalogs them in a panel with filters for status,
author, and entity, and navigates on click: pick a note and the camera goes there. The review
conversation lives on the thing being reviewed.

**Status: a feature to research and consider, with no commitment to any version yet.** The
open questions, named before anyone falls in love with a UI:

| # | Question |
|---|---|
| N-1 | **Anchoring.** A note → entity binding that survives geometry edits (entity deleted, split, copied). Attribute on the entity vs a model-level table of persistent-id references; what an orphaned note does |
| N-2 | **Storage & sync.** In-model (travels with the `.skp`, works offline, but two people annotating two copies is a merge conflict) vs a service of record (live, multi-user, but needs accounts and network) vs hybrid. ⚠ Dropbox is the transport most clients actually have |
| N-3 | **The certifier's seat.** Most certifiers will not open SketchUp. The strong version is cross-surface: notes authored on the *exported* model in a web viewer (PH-Nav / pholio) flow back into the SketchUp panel. That requires **stable identifiers across export**, and the record already says identifiers churn per export (`00_Context/HONEYBEE_STACK.md` §4). Stable ids written to `DesignPHPlus_dict` are a named prerequisite rather than an implementation detail |
| N-4 | **The pholio boundary.** pholio reviews *versions of files*; Notes discusses *specific geometry*. Complementary on paper, and the research should prefer pholio or PHN as Notes' service of record over building a third messaging system. If the boundary cannot be drawn cleanly, Notes may belong in pholio rather than in this plugin. That is an acceptable research outcome, decided by the research rather than by attachment |
| N-5 | **Scope discipline.** Threads, open/resolved status, spatial anchors, history, and nothing else. No general chat, no notification empire |

First steps when this activates: a feasibility spike (anchor + catalog + camera navigation is
cheap to probe in Ruby) and a one-page product boundary against pholio (N-4).

### 2.5 One plugin, and what stays separate

The four affordances are bundled deliberately. They share the model as their one data store and
namespace, install once, and compound: Import feeds the libraries Build assigns; Export is how
Build's data reaches anything; Notes reviews what the other three put in the model. One
extension, feature-flagged (§7.3), so each affordance ships when its own gate clears without a
second install.

Fully separate products, on purpose:

- **pholio**, the record above the tools (folder watcher, versions, diffs, PassivSure feed).
  Different motion (passive vs tool-in-hand), different buyer, different licensing exposure
  (AGPL §13, the C-SDK access gate). It shares this repo's contracts and `00_Context/`, never
  a product surface.
- **PH-Navigator** stays a web app and becomes the subscription half of the commercial pairing
  (§12). DesignPH-PLUS is a consumer of its API, nothing more.
- **HBJSON → fresh SKP** (`planning/04_hbjson-to-skp/`), a separate deferred spike. It never
  edits an existing designPH model.

## 3. Why this is viable now

Five findings from the August 2026 investigation, all documented in `00_Context/`. Findings 4
and 5 are proven end to end, not argued:

1. **designPH's data is readable without designPH.** Everything lives in one standard SketchUp
   `AttributeDictionary` (`DesignPH_dict`), reachable through Trimble's public, documented Ruby API.
   No reverse engineering required.
2. **Room-level data does not require watertight geometry.** `honeybee-ph` models rooms as
   `Space` → `SpaceFloor` → `SpaceFloorSegment` with a weighting factor, built from tagged floor
   faces rather than closed solids. designPH already tags TFA faces and stores `TFA_rf`. This
   removes the obstacle most likely to have killed the project.
3. **The whole honeybee stack is pure Python** (`py3-none-any` wheels, guaranteed by Ladybug's
   IronPython 2.7 compatibility). That makes running real honeybee inside SketchUp's Chromium
   `HtmlDialog` via Pyodide a live option: no server, no bundled interpreter.
4. **designPH accepts foreign library writes** *(POC #3, 2026-08-31)*. Model-level table writes
   are listed, assigned, computed exactly, save-stable, and exported, with no entity-level
   side-requirements, and a foreign `phn_id` column survives everything and leaks nowhere. The
   Import affordance rests on a frozen, measured contract.
5. **The read pipeline is proven twice** *(POCs #1 and #2)*: inside SketchUp (545/545 faces,
   239/239 windows, 99/99 thermal bridges across five real models) and headless (canonically
   identical HBJSON). Export is an engineering-complete affordance waiting on a legal answer.

## 4. Users

| User | What they get (by affordance) |
|---|---|
| **CPHC / PH consultant** (primary) | **A**: their PHN / office-standard library lands in the model in one click, exact to the Error % digit, with no more per-project retyping. **B**: one place to manage all project data. **C**: one button → a standard model file they can share, archive, diff, and hand to anyone |
| **Certifier** | **C**: a machine-readable model to review alongside the PHPP, instead of a proprietary `.skp`. **D** *(research)*: comments pinned to the actual geometry, with history. Eventually, a 3D model of the ducts and piping they can only guess at from paper today |
| **Contractor / owner** | **C**: a web-viewable model (ph-navigator) without SketchUp or a licence |
| **Municipality / program administrator** | **C**: a standard format for compliance reporting and portfolio analysis (PassivSure) |
| **Tooling & agents** | **C**: an open input for QA/QC, checklists, automated review |

**Day-one rule (product decision, 2026-08-31):** the product serves **existing designPH users
in their existing process**. It makes what they already do faster and more transparent, with
exact values, and never asks them to learn a new platform. It piggybacks on the PHI-side
*requirement* to use designPH (the shading calculation) rather than competing with it. Under a
paid model (§12) this rule sharpens: the plugin must beat its price in saved hours from the
first session.

## 5. Goals and non-goals

*(Restructured 2026-09-01: goals are stated per affordance, in ship order.)*

### A · Import goals (v-0)

1. Pull assemblies, frames, and glazings from a PHN project into the open model's designPH
   library tables, exactly per the frozen contract. designPH lists, computes, and exports them
   as its own.
2. Re-import **updates** rather than duplicates (`phn_id` key, rename-safe); a dry-run report
   precedes every write.
3. Refuse and report anything unmappable (hard rule 4); never touch entity-level data.
4. State the supported designPH version range; refuse 3.x by name.

### C · Export goals (v-1, Draft v1's goals unchanged)

1. Produce a schema-valid HBJSON from any supported designPH model, read-only, with one action.
2. Carry envelope geometry, assemblies, apertures, and PH `Space`s (TFA) faithfully, plus
   `DesignPHPlus_dict` data once Build exists.
3. Never silently lose or misrepresent data. Report, don't guess.
4. Install as a single `.rbz` with no other dependencies.

### B · Build and D · Notes

Goals are set by their own scoping passes (§2.2, §2.4). Stating acceptance criteria now would
be guessing; on this project, criteria invented ahead of evidence get rewritten.

### Explicit non-goals

These are not deferred by oversight. Each one is load-bearing.

- **No writing to `DesignPH_dict` entity data, ever.** Face/edge/window classification stays
  read-only (hard rule 2). *(Supersedes Draft v1's blanket "no writing to the model" as of
  2026-08-31: Import writes model-level library tables under the frozen contract with a
  capture-diff after every write; Build writes only our own `DesignPHPlus_dict`.)*
- **No writing to PHPP from this plugin.** designPH keeps its export job; PLUS data reaches
  PHPP via HBJSON → PHX downstream, never by this plugin driving Excel.
- **No shading factors.** Omitted and explicitly marked; see §7.2.
- **No `.ppp` parsing as an input route.** Licence; see §9. *(Hard rule 1 as amended 2026-08-31
  permits validation reads of exports we ourselves produced; `00_Context/PPP_EXPORT.md` §1.)*
- **No non-residential or multi-zone program** in v-0/v-1.
- **No watertight-geometry repair.** Non-solid models are accepted and reported.
- **No replacement ambition.** designPH keeps 3D envelope authoring and the shading
  calculation. §9's position with PHI depends on this staying true.
- **No push channel into closed files.** Import is pull-only, user-present (§2.1). A file-level
  writer, if it ever matters, is a pholio-shaped question.

## 6. Export scope: what C · Export v-1 converts

*(§6 to §8 are the Export affordance's technical spec, carried from Draft v1 and POC-validated.
Import needs none of this machinery; it is pure Ruby, §2.1.)*

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

## 7. Architecture: the Export runtime

*(This whole section is C · Export's. A · Import runs with none of it: no Pyodide, no loopback
server, no vendored wheels. One Ruby write path and the PHN payload.)*

### 7.1 Runtime, decided (Phase 3, 2026-08-19)

**Pyodide inside the extension's `HtmlDialog`.** Ruby collects the model → hands JSON to the dialog →
real, unmodified honeybee + honeybee-ph runs in WebAssembly → HBJSON returns → Ruby writes it. Zero
install, offline, no server exposed off the machine, and it uses the actual tested library rather than
a reimplementation.

**This is no longer a preference between options.** It was built, run inside SketchUp 2022 on
real designPH models, and measured. First the Phase 3 spike: 82 of 82 classified Adelphi faces,
87 KB of HBJSON, boot in 2.6 s. Then the whole five-model corpus: **545 of 545 classified
faces, 239 of 239 windows, 99 of 99 thermal bridges, none rejected.** Full evidence and the
gates:
[`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_results.md`](planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_results.md) and
[`planning/01_sketchup-export/implementation/RESULTS/`](planning/01_sketchup-export/implementation/RESULTS/.index.md).

Four constraints came with it, and each is load-bearing:

**(a) Pyodide 0.24.1, pinned by the dialog's engine.** SketchUp 2022 embeds **CEF 88.2.4 =
Chromium 88** (January 2021). Modern Pyodide will not run there. 0.28+ fails to *parse* (ES2022
static blocks, Chromium 94) and 0.25 to 0.27 fail to instantiate their wasm (reference types,
Chromium 96). 0.24.1 (CPython 3.11) is the newest that works, verified end to end against a
real Chromium 88. See §7.4: **the oldest SketchUp we support sets the newest Pyodide we can
use.**

**(b) Served over `http://127.0.0.1`, never `file://`.** A `file://` page cannot fetch its own
assets: `fetch`, `XMLHttpRequest` *and* the dynamic `import()` Pyodide uses are all refused, and
the third cannot be polyfilled. Confirmed inside SketchUp, not merely in stock Chromium. The
extension therefore runs a `TCPServer` on loopback: OS-assigned port, random path token, shut
down with the dialog. It is also the only way to set the COOP/COEP headers `SharedArrayBuffer`
would need.

**(c) The server is a worker thread pumped by a sleeping `UI.start_timer`.** Both halves are
required and each omission hangs SketchUp silently; see the CLAUDE.md lessons. This is the
single most fragile part of the design and needs a comment in the code saying why.

**(d) Wheels are installed by unpacking, and `micropip` is not shipped.** `micropip` is coupled
to the Pyodide release and cannot run on 0.24.1; every wheel in the payload is `py3-none-any`,
so unpacking *is* installing. Phase 2 planned the reverse and kept the unpack in reserve; the
reserve became the mechanism.

**Measured cost:** **6.66 MB `.rbz`**, 20.7 MB installed, 2.6 s cold start, 28.8 MB WASM heap,
4 MB verified across the Ruby↔JS bridge in both directions. Exporting a worst-case 1441-face
model costs **139 ms**; the HBJSON is byte-identical to what CPython produces.

**The Python side is settled (Phase 2).** Eight `py3-none-any` wheels (`honeybee-core`,
`honeybee-energy`, `honeybee-ph`, `honeybee-standards`, `ladybug-core`, `ladybug-geometry`,
`ladybug-geometry-polyskel`, `ph-units`), 1.5 MB, with no C or Rust extension anywhere in the
reachable closure.

⚠ **The licence question is now live**, because vendoring honeybee (AGPL-3.0) is a decision
rather than a possibility. Written up for counsel:
[`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md`](planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md).
**Resolve it before v1 code is written** (§9). The Model 2 selection (§12.1) sets the posture:
the plugin ships open-source, which is AGPL-compatible, so counsel confirms rather than
redirects. The remaining AGPL work item is PHN's server-side extraction (§12.5).

**Retained as a real alternative:** *Ruby writes HBJSON directly*, reimplementing honeybee's
serialization only, validated in CI against published `honeybee-schema` and
`honeybee-ph-schema`. It ships no third-party code and links nothing, so it is the answer if
counsel finds real AGPL entanglement risk despite the open-source posture (§12.1). It costs
schema-drift maintenance forever. That is the price of the freedom, and it should be paid
deliberately rather than by default.

**Rejected:** bundled Python interpreter (corporate-IT hostile, the thing Ladybug Tools most
regret); server-side `.skp` parsing (no Linux build of the SketchUp C SDK); user-installed
Python (support burden on a mass-market tool).

### 7.2 Shading

**Omitted from v1.** Because PLUS does not write the envelope to PHPP, shading is only needed
for a path we are not building. Certifiers continue to receive designPH's shading through
designPH's own `.ppp` import, exactly as today.

The output **must** carry an explicit `shading: not-computed` marker. Emitting zeros, or
omitting silently, would let a downstream consumer mistake an incomplete model for a complete
one.

**Shading *geometry* without the factors is OUT of v1 scope again, pending a UI.**
*(Promoted by Phase 0 §0.4 on the strength of the destination; withdrawn by Phase 1 §1.5 on the
failure of the source rule. See `planning/01_sketchup-export/feasibility/RESULTS/PHASE-1_results.md`.)*

**The destination still stands.** Exterior context geometry has a well-formed home in HBJSON as
`orphaned_shades` with `is_detached: true` and a `ShadePhPropertiesAbridged` block. That was
never the problem.

**The source rule has now failed twice.** Phase 0 refuted "untagged face → shade". Phase 1
tested the two remaining candidates live and refuted both:

| `faceTypeAuto` | outside envelope bbox | inside |
|---|--:|--:|
| `'xo'` | 252 | 168 |
| `'i'` | 167 | 238 |
| nil | 7050 | 61 |

A 60/40 split is not a discriminator, and the two signals disagree with each other.
`faceTypeAuto` is also **absent entirely** from two of the seven real project models. The
bounding-box test is weaker than it looks: the bbox is the *tagged* faces' extent, so "inside"
means "within the building volume", which contains interior partitions and the envelope's own
faces alike.

The scale makes a wrong rule expensive. Adelphi has **8037 live faces**, only **82** tagged.
Bluff Reach: 7467 live, 194 tagged. Exporting untagged-and-outside would emit ~6700 shades
where the reference HBJSON has 1287.

**The signal that does work is the user's own.** Both models carry SketchUp tags naming the
intent: `04_SHADING_TREES` (Adelphi, 392 faces), `Shading_Tree` and `*Vn50` (Bluff Reach). The
modeller already said which geometry is shading, but the tag *names* are user-authored and
differ per model, so no fixed rule can read them either.

**Therefore: v1 asks rather than guesses.** Present the model's tag list, let the user tick
which tags are shading geometry, default to none. Small UI, no heuristic, works on every model
including those with no `faceTypeAuto`. Until that exists, untagged faces are **reported, not
exported** (hard rule 4), which is where Phase 0 left them and the position the evidence still
supports.

### 7.3 Packaging

One extension, feature-flagged, so each affordance adds capability without a second install.
Loader stub + `SketchupExtension` per SketchUp convention. Writes go to their own namespaces
only: Import to the model-level designPH library tables under the frozen contract, Build to
**`DesignPHPlus_dict`**, and never into designPH's entity data.

### 7.4 Supported versions

**SketchUp 2021+** (VFF container era), **designPH 2.2+**. Read `designPH_version` from the
model and **refuse politely on anything unrecognised** rather than guessing. A
wrong-but-plausible HBJSON would do more damage to the tool's reputation than a clear refusal.

⚠ **The SketchUp floor is now a technical constraint, not just a compatibility preference.**
SketchUp 2022 = Chromium 88 caps the vendored runtime at Pyodide 0.24.1 / CPython 3.11 (§7.1).
Every SketchUp release ships a newer CEF, so raising the floor raises the ceiling.
**Unresolved: which SketchUp versions the market actually runs**, and whether dropping 2022
buys enough to be worth the users it costs. Decide before v1 pins a runtime. *(Import is
unaffected; it has no dialog runtime.)*

⚠ **Open question on the 2.2 floor.** The primary corpus model `adelphi-designph.skp` is
designPH **2.1.15**, below the stated floor, so v1's own version gate would refuse it. Decide
in Phase 1 whether the floor drops to 2.1 or the corpus model gets re-saved from a newer
designPH.

*(Phase 0 update: this is cheaper than it looked. The version-keyed read rule in §6 of the
data-model record did not survive the full corpus: every real project model stores its data in
the `*ID` keys whatever its version stamp. If that holds per-face in Phase 1, the 2.1/2.2
distinction largely stops mattering for reading, and the floor can drop to 2.1 at no cost. The
version gate still earns its keep as a **refuse-on-unrecognised** guard for versions above what
we have tested.)*

## 8. Translation rules

### 8.1 Rooms and geometry

One `Room` per model, built from the face list. **Non-solid is accepted.** designPH models are
surface models and most real ones will not be solid; requiring solidity would reject most of
the market. Run `check_solid()` and surface the result in a validation report.

Volume comes from designPH's `vent_ud` (`room_height`, `V_n50`), not from geometry, so
non-solid geometry does **not** make the PH results wrong. It only limits downstream uses
needing a sealed volume (daylight, CFD), which are not v1's consumers.

### 8.2 Apertures

Windows are Dynamic Components offset from the wall plane by their reveal depth, so naive
extraction produces non-coplanar apertures that honeybee rejects.

1. Find the host face with **`ComponentInstance#glued_to`**; fall back to nearest coplanar face.
2. Project the window rectangle onto the host plane, **discarding the reveal offset**.
3. Carry reveal depth into PH aperture properties, not geometry.
4. Validate containment. **On failure, report the window by its designPH name; never drop
   silently.**

✅ **Host lookup is solved** *(Phase 1 live run, 2026-08-19)*. `glued_to` resolves on **46 of
46** windows in the Adelphi model. Geometric nearest-coplanar-face is a fallback, not the
primary path; the "more work, more failure modes" risk the spike plan flagged is retired.

⚠ **Updated 2026-08-21:** `face.loops.size > 1` is not a host test either. A glued opening
creates no loop (true on only 2 of the 16 real hosts). Use `glued_to`, and note that
`face.area` is consequently **net** of window openings while the loop polygon is **gross**
(`00_Context/DESIGNPH_DATA_MODEL.md` §5.0).

⚠ **Do not infer holes from `cuts_opening?`.** It is `true` on all 46 windows and yet only **2
of 16 host faces** carry inner loops; the rest are unbroken, several hosting six windows each.
`cuts_opening?` is a property of the component **definition** (*"this component is able to
cut"*), not a statement about the host. Trusting it would punch a hole in every emitted
`Face3D` and leave 44 apertures with nothing to fill. ~~Test `face.loops.size > 1` on the host
instead~~; that is not a host test either (above). **`glued_to` is the only one.**

**Step 2 needs a limit, and this is the sharpest lesson of the whole aperture path.**
Projection onto the host plane is lossy in exactly the way a coordinate-space bug is: a
rectangle a metre off the wall projects onto it as cleanly as one a millimetre off. Shipping
the window transform parent-relative put all 46 of Adelphi's windows 1.2 to 3.3 m from their
hosts and produced **no symptom anywhere**. v1 must refuse a rectangle further off the plane
than a reveal could explain, and report the distance on every window that passes
(`00_Context/DATA_CONTRACTS.md` §7.0).

Edge cases to handle explicitly: window straddling two faces; window larger than host; host
face with no `DesignPH_dict`; `glued_to` returning nil after a user moved a window; **a host
face that does carry inner loops** (Adelphi has two).

⚠ **Two more that honeybee itself creates, both observed on real data and neither repairable
without fabricating an area** (`DATA_CONTRACTS.md` §7.1.1):

- **A window flush with the host edge.** `Face3D.is_sub_face` takes no tolerance, so a corner
  1 µm past the boundary reads as *not fully bounded*. That is coordinate rounding, not an
  overhang. 2 of Adelphi's 46.
- **A host that already models its opening as an inner loop** subtracts it twice, because
  honeybee expects an aperture on the *gross* face.

v1's answer is to emit the aperture and **predict honeybee's verdict in the report**, saying
which case it is. Shrinking a window to please a validator would fabricate an area.

### 8.3 Assemblies

*(Rewritten after Phase 1; see `planning/01_sketchup-export/feasibility/RESULTS/PHASE-1_assembly-resolution.md`. The previous
version assumed `layer_table_<id>` was the source for every face; it is the source for under
half.)*

**First, read the area group. It decides which id namespace `assemblyID` is in, *and* which
entity type carries it.** designPH uses one key name for two unrelated tables on two different
entities:

| Area group | Entity | `assemblyID` names | Target |
|---|---|---|---|
| 15, 16, 17 (thermal bridges) | ⚠ **`Sketchup::Edge`** | a **`connections_ud`** row (Psi-value, f_Rsi) | `PhThermalBridge`, **not** a construction |
| everything else | `Sketchup::Face` | an assembly | an opaque construction |

Both namespaces use `NNud` ids, so looking a thermal bridge up in the assembly table returns
either nothing or an unrelated construction. Getting this backwards is silent and
plausible-looking.

⚠ **The reader must walk edges as well as faces.** Thermal bridges are linear, PHPP enters them
as lengths, and designPH attaches them to edges. On `2414 Bluff Reach.skp` that is 99 of 293
tagged entities; **a face-only traversal loses every one of them without an error.** Verified
live 2026-08-19; see `00_Context/DESIGNPH_DATA_MODEL.md` §7.1.

**Then resolve the assembly, in four tiers.** Measured across the seven real corpus models:

| Tier | Refs | Translation |
|---|--:|---|
| `layer_table_<id>` in the model | 254 | Map faithfully into `PhDivisionGrid` on `EnergyMaterialPhProperties`. designPH's three parallel paths (`desc1/lambda1` … `surf2_percentage`, `surf3_percentage`) are a 1×3 grid. ⚠ "The target model supports this natively" is half true; see §8.3.1 |
| `assemblies_*` header row only | 42 | U-value and thickness, no build-up → a single `EnergyMaterialNoMass`. Note it has `divisions = None`, so no grid is possible |
| designPH's **installed** `data/phpp_assemblies_ud.csv` | 95 | Same as above, but the source is *outside the model*. Read it, and **record that the source was the plugin folder, not the file** |
| Certified library `phpp_assemblies_cert.csv` | n/a | Same shape; PHI-certified components |

**Zero references in the corpus were unresolvable** once the two namespaces are separated, but
**only 254 of 532 carry a build-up.** v1 must not promise a layer stack per surface.

Keep `R_in` / `R_out` as film resistances and `additional_U_value` on PH properties; **do not
fold them into materials.** A reviewer must still be able to see the numbers.

**Report the tier for every surface** (hard rule 4). A U-value with no build-up is a legitimate
and common state, not an error; the failure would be presenting it as though it were a full
assembly, or substituting a default. Never substitute a default.

### 8.3.1 honeybee cannot carry a framed assembly's U-value, and the grid does not rescue it

*(Measured 2026-08-21 against designPH 2.4.0 BETA's own U-/R-value calculator.)*

designPH computes a multi-section assembly by **ISO 6946 §6.7, the mean of an upper and a lower
resistance limit**, and prints the spread between them as its *Error %*. No single layer can
carry that:

- **`OpaqueConstruction.u_value` reports the section-1 value**, because a layer's conductivity
  is one number and `lambda1` is the one it gets. On Linde's `06ud`: **0.0698 against
  designPH's 0.0750, 8 % low, in the direction that flatters the building.**
- **`PhDivisionGrid.get_equivalent_conductivity` is an area-weighted lambda**, which is ISO
  6946's **lower** limit. So a PH-aware consumer reading the grid still gets an optimistic
  number, just a less optimistic one.
- **designPH's U includes the surface films**; honeybee's `u_value` is material-only. On
  unframed assemblies that difference alone is 0.004 to 0.005 W/m²K.

The POC emits the real layers, sets the grid to the **real areas** (equal column widths would
describe a stud bay as half timber), and carries designPH's own figure on the report as
`u_value_iso6946` with the section areas and the spread. **v1 needs a better answer than a
report field, and it is plausibly an upstream one.** `PhDivisionGrid` exists for exactly this
case and computes the wrong limit. Worth raising with honeybee-ph rather than working around
locally.

⚠ **The scale, so this is not over-built:** only **4 of 82** `assemblies_calc` rows on Linde
carry a non-zero section percentage, and Wellington and Bluff Reach carry none. 49 % of Linde's
*layers* have a `lambda2`, but a `lambda2` with no area is not a framed layer; counting those
overstates the population fivefold.

This is the easiest place to be quietly wrong. Regression-test computed U-values against
designPH's own reported values. Ground truth for the Adelphi building is extracted to
`planning/01_sketchup-export/feasibility/RESULTS/phpp/phpp_u-values_assemblies.csv` (12 assemblies) and `..._layers.csv` (56 layers).

⚠ **One dependency: the model is not self-contained.** The `83ud` to `99ud` range is designPH's
shipped default library, living in the plugin folder rather than in the `.skp`. The extension
runs beside those files so it can read them, but output then depends on which designPH the
reader has installed. Adelphi shows the alternative, an `assemblies_ud` *snapshot* of the
library inside the model, but designPH only sometimes writes one.

### 8.4 Spaces and program

`Space`s built from designPH's TFA faces, with `TFA_rf` mapping onto segment weighting factor.

A single **`PH Residential`** program: occupancy derived from `ihg_ud.num_units`, everything
else PHI defaults, nothing user-editable in v1. Seed from `honeybee_revive_standards/` (the
`rv2024_*` schedule set) and `honeybee_energy_ph/library/programtypes.py`. Ship it as a named,
versioned program in the repo so it is inspectable and arguable, not buried in code.

## 9. Legal and licensing

**Not legal advice. Confirm with counsel and with PHI before building on any of it.**

The [designPH Licence Agreement](https://database.passivehouse.com/en/designph/licence-agreement/)
**§2.4(a)** prohibits attempts to "reconstruct or discover any source code, underlying ideas,
algorithms, **file formats or programming interfaces**."

- **Parsing the `.ppp` export is out of scope for v1.** On a plain reading it is
  reverse-engineering a file format, named explicitly. *(Hard rule 1 as amended 2026-08-31
  permits validation reads of exports we ourselves produced: verbatim-needle checks always,
  structural reads only from the `phi-rules` catalog. Extraction of designPH-computed data
  stays behind §2.4(d) written authorisation. `00_Context/PPP_EXPORT.md` §1.)*
- **Reading `DesignPH_dict` is defensible.** The data sits in the user's own `.skp`, which is
  SketchUp's format rather than designPH's, and is read through Trimble's public, documented
  API.
- **§2.4(d)** permits derivative works "expressly authorized **in writing**", so PHI can
  authorise `.ppp` access. That is a v2 conversation.
- The clause carries the standard carve-out for what applicable law protects; EU Software
  Directive 2009/24/EC Art. 6 permits decompilation **for interoperability**, and PHI is
  German. Whether that reaches a US developer depends on governing law. **Unresolved; for
  counsel.**

**The write side** *(added 2026-09-01, from POC #3)*: Import writes model-level library tables
that designPH consumes. That is a deeper interop posture than reading, and it gets its own
explicit judgment before anything ships (POC #3 task **LI-1**: re-read the designPH licence for
writing/interop language, decision written down). The drafted PHI opener must be updated to
mention the write side before any external release (**LI-2**), and everything stays
internal-only until then (**LI-3**).

**Position with PHI:** complementary, and say so loudly. designPH's core value is 3D authoring
plus the shading calculation; we replace neither, and every DesignPH-PLUS seat presupposes a
designPH licence. If PHI wants to absorb the mechanical-authoring idea into designPH proper,
that is a good outcome. **"PHI actively objects" is the only true deal-breaker in this plan.**
Every technical obstacle found so far has a workaround; that one does not. ⚠ A *paid*
DesignPH-PLUS (§12) sharpens this conversation: a commercial product built on designPH interop
invites more scrutiny than a free community bridge, so LI-2's opener must be drafted knowing
which business model we are in.

**Our licence** *(posture set by the Model 2 selection, §12.1)*: the plugin is open-source.
Pyodide vendors honeybee (AGPL-3.0) and forces AGPL-3.0 on the plugin; an open-source plugin
can carry that, so the proven runtime stands, and the Ruby-writer route (which links nothing;
file formats are not copyrightable) stays a fallback rather than a requirement. Counsel
confirms the posture. ⚠ **On the plugin side the AGPL question is scoped to Export.** Import
vendors nothing (pure Ruby) and ships first regardless. The live AGPL work item is
server-side: PHN's backend pulls the AGPL stack in exactly three modules, and the §12.5
extraction moves them behind a network boundary before any commercial layer lands.

## 10. Spike and evidence status *(refreshed 2026-09-01)*

Draft v1's "do these before committing" list is done or superseded. The ledger, for the record:

| # | Spike | Outcome |
|---|---|---|
| S1 | Runtime: honeybee inside `HtmlDialog` | ✅ **Done 2026-08-19, PASS WITH CHANGES.** Pyodide adopted (§7.1); then corpus-proven by POC #1 |
| S2 | Are designPH windows glued? | ✅ **Done 2026-08-19 (Phase 1).** `glued_to` resolves 46/46 and is the **only** host test; `cuts_opening?` is a definition capability, not a host fact (§8.2) |
| S3 | `*Auto` vs `*ID` rule | ✅ **Settled.** Coalesce, version-independent (hard rule 6; `00_Context/DESIGNPH_DATA_MODEL.md` §6.5) |
| S4 | Obtain designPH 3.0; re-run the key inventory | ⛔ **Blocked.** The 3.0 licence cannot be bought yet (Ed, 2026-08-21). No agent work unblocks it; the version gate refuses 3.x by name in the meantime |
| S5 | Is PHX's write path pure? | ✅ **Done 2026-08-19, PASS WITH CHANGES.** `from_HBJSON` → `to_WUFI_XML`/`to_METr_JSON` runs with `lxml`, `xlwings`, `pydantic` absent; `xlwings` gates only PHPP writing, which §5 excludes from the plugin |
| S6 | Conversation with PHI | ▶ **Pending (tabled Phase 5)**, and widened twice: by POC #3 (the write posture, LI-2) and by the paid model (§9, §12) |
| S7 | Import: does designPH accept foreign library writes, and does real PHN data compute exactly? | ⭐ **Done 2026-08-31.** POC #3 Spikes L-A + L-B both PASS; contract frozen v1 (§2.1) |
| S8 | Notes feasibility (anchor + catalog + camera navigation) + the pholio boundary page | ▶ **Research, unscheduled.** Activates with affordance D (§2.4) |
| S9 | HBJSON → fresh SKP | ▶ **Scoped, not started.** Separate POC (`planning/04_hbjson-to-skp/`), deferred behind v-0 |

## 11. Definition of done: Export

*(Import's definition of done lives in its v-0 scope document, the POC #3 L-C gate. This
section is the Export gate, carried from Draft v1 and already exercised by the POC.)*

Export v-1 ships when, across the regression corpus:

1. **Output validates** against `honeybee-schema`, scoped to the core geometry and PH payloads,
   which is all v1 writes.
2. **Output loads and renders correctly** in ph-navigator.

Both automatable; neither requires PHPP or a certifier in the loop. Together they prove the
thesis: a valid standard model a real downstream consumer can use.

✅ *Both criteria were exercised by the POC on real models (2026-08-21).* Criterion 1 passed on
all five outputs. Criterion 2 passed with one named consumer-side exception a v1 must plan
around: **ph-navigator's viewer skips any face whose construction uses `EnergyMaterialNoMass`**,
so a tier-2 (U-value-only) assembly renders without its envelope (Finding 71,
`planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md` §3.2; `00_Context/HONEYBEE_STACK.md` §6.4). The fix is
BLDGTYP's on either side of that seam.

⚠ **Two corrections from Phase 0 §0.4** (`planning/01_sketchup-export/feasibility/RESULTS/reference_hbjson_shape.md`):

- **The scoping in criterion 1 is load-bearing, not hedging.** The *reference* HBJSON does not
  validate against `honeybee-schema` 1.53.1 (147 objects fail), but every failure sits inside
  `properties.energy`, and **none** touches geometry, boundary conditions or `properties.ph`.
  Those are honeybee-energy payloads v1 does not write. The criterion is sound; do not weaken
  it on the strength of the reference's own failures.
- **`honeybee-ph-schema` was dropped from criterion 1.** At v0.1.0 it is not published to PyPI,
  every model declares `extra="allow"`, and no field is required; a payload of `{}` validates.
  It is a contract stub, not an acceptance gate. **Open decision:** tighten the schema, or
  replace that half of the criterion with an explicit per-field expectation list.
  *(`AGENTS.md`'s "schema contracts are published in `honeybee-ph-schema`" overstates both the
  publication and the coverage.)*

**Explicitly not a v1 gate:** numerical agreement with PHPP. That is v2, and chasing it now
would drag `.ppp` parsing and shading straight back onto the critical path.

**Regression corpus:** `corpus/adelphi/` is the primary reference, the same building as
designPH `.skp`, `.ppp`, PHPP `.xlsm`, HBJSON, Rhino `.3dm` and Grasshopper `.gh`. Secondary:
the `08_DesignPH` folders that actually hold designPH models *(verified on disk 2026-08-19)*:
2523 Wellington (2.1.10 + 2.2.29), 2524 Linde Residence (2.1.15), 2414 Bluff Reach (2.2.24),
2605 MacDonough (2.2.29), 2536 Holmes Residence (2.2.29). *(Superseded: an earlier draft named
High Street, Arrowhead Ridge, Ikon Optima Plus, and 415 Flint; those folders hold no designPH
model.)*

⚠ Caveats on the Adelphi set: ~~the promised HBJSON is absent~~ *(superseded 2026-08-19:
`adelphi-honeybee-json.hbjson` was supplied. Schema 1.53.1, 6 rooms / 52 faces / 44 apertures /
38 spaces / 1287 orphaned shades. It is a **shape reference**, not an equality target; it came
from the Rhino route with solved adjacency, while v1 emits one non-solid Room by design; see
`planning/01_sketchup-export/feasibility/00_OVERVIEW.md`)*. The formats remain only
**approximately aligned**, so a numerical mismatch between them is not by itself evidence of a
translator bug.

✅ **The regression corpus is now captured and reconciled** *(POC-2, 2026-08-21)*. Five models
(Adelphi, Bluff Reach, Wellington, `250703 - Linde Residence`, `250708`) spanning designPH
2.1.15 to 2.2.29 and SketchUp 22 to 26, live extractions banked in `pocs/01_sketchup-export/_private/fixtures/` and
checked against the offline scan of all 14 corpus files. Between them they exercise every path
v1 has: thermal bridges (99), all four assembly tiers, multi-section assemblies, TFA,
`*Auto`-only assemblies, `descName` overrides at scale, and a model (`250708`) that resolves
**nothing** in-model.

⚠ **"Approximately aligned" is now measured, and it has a rule.** Adelphi's `.skp` and its PHPP
share **no id space**: the same constructions are `83ud`/`84ud`/`85ud` in one and
`01ud`/`07ud`/`13ud` in the other, and only 3 of 14 assemblies share a name. **Join by name,
and treat the PHPP as ground truth for arithmetic and method, never for identity**
(`00_Context/DATA_CONTRACTS.md` §8). That distinction is what stopped an alignment artefact
reading as a translator bug.

## 12. Business model and distribution

*(Rewritten 2026-09-01. Draft v1 declared "free and open-source; adoption over revenue".
Superseded (Ed, 2026-09-01): DesignPH-PLUS is a **commercial pairing with PH-Navigator**, and
later the same day the revenue split was decided: **Model 2**. The plugin itself returns to
free and open-source; the revenue lives in the hosted PHN subscription.)*

### 12.1 The candidate models, and the selection

| | **Model 1: both paid** *(not chosen)* | **Model 2: free plugin, paid service** ⭐ *(SELECTED, Ed 2026-09-01)* |
|---|---|---|
| DesignPH-PLUS | Paid extension, licensed like designPH itself | **Free and open-source** |
| PH-Navigator | Paid subscription for the library + web frontend | **Paid subscription, the sole plugin-side revenue source** |
| Adoption logic | Product revenue funds both halves; a price signals a supported professional tool; designPH's own market already pays for extensions | The plugin recruits: every plugin user is a PHN prospect; free maximizes reach and the interchange-standard ambition |
| Precedent | designPH (paid SketchUp extension) | Ladybug Tools (free tools) + hosted platforms; every freemium plugin-plus-cloud pairing |

**The selection, stated per artifact** (Ed, 2026-09-01):

- **The plugin is free and open-source, manual Export included.** Open-sourcing is not a
  concession; it is what lets the plugin vendor honeybee under the AGPL, so the proven Pyodide
  runtime ships as-is and the Ruby-writer rewrite stays unbuilt (§7.1). It also removes the
  plugin licensing mechanism entirely: value-gating happens server-side, because Import
  without a PHN subscription has no data source.
- **The hosted PHN subscription is the revenue.** §12.5 for how it gets built.
- **pholio is a separate paid downstream service** (automatic read/export, versions, the diff
  and review record). Free manual export does not undercut it: pholio sells automation and the
  record rather than the capability, and every free export creates exactly the artifacts
  pholio versions and diffs.
- **Free Build is underwritten by BLDGTYP itself** (user zero, §2.2): even at zero external
  sales, a better designPH workflow is direct internal project value.
- The per-affordance split considered earlier is resolved in this shape: the open,
  standard-setting affordance ships free, and the durable assets (the library, the hosted
  records) are what get paid for.

### 12.2 What bound the choice *(recorded reasoning)*

- **The AGPL coupling (Export only).** Selling AGPL-derived code is permitted; closing it is
  not, because copyleft compels source availability. Model 1 with a closed extension therefore
  cannot vendor honeybee: it forces the Ruby-writer route (§7.1) or an open-source-but-paid
  posture. Import (pure Ruby, entirely ours) prices freely under every model.
- **The PHI posture changes.** Draft v1's "a free community bridge defuses the PHI risk"
  argument does not survive Model 1. A paid interop product invites a sharper reaction, and it
  also reframes the pitch: a commercial partner whose every seat sells a designPH licence.
  LI-2's opener is drafted after the model is chosen, not before (§9).
- **The affordance asymmetry.** Import's value is really PHN's value; the library is the
  product and the plugin is delivery. That argues for charging where the durable asset lives,
  which is Model 2's shape. Build and Notes create plugin-side value that Model 1 monetizes
  more directly.
- **The day-one rule (§4).** Existing CPHCs already pay for designPH; either model can respect
  the rule, but a paid plugin must beat its price in saved hours from the first session.
- **The interchange ambition (§1).** "A paid closed tool will not become the interchange
  standard" was Draft v1's argument and it still has force, but it applies to Export rather
  than to the whole product. The per-affordance split exists because the standard-setting
  affordance and the revenue affordances differ.

**Decision: Model 2 (Ed, 2026-09-01).** The bullets above stand as the recorded reasoning.
v-0 stays internal-only until LI-1/LI-2 clear (LI-3); repo, licence, and channel choices now
assume the open-source plugin.

### 12.3 Distribution mechanics

- **Repo:** with the plugin open-source again (§12.1), `github.com/PH-Tools` fits it after
  all. The PHN commercial layer is what lives elsewhere (§12.5).
- **Channel:** GitHub releases first, for iteration speed, while internal-only. A free plugin
  needs no licence check, so the Extension Warehouse becomes the natural public channel once
  the format stabilises.
- **Platforms:** Windows and Mac, both, at first public release. Most CPHCs are on Windows.
  This cannot slip.

### 12.4 Naming *(decided 2026-09-01, Ed)*

**The extension ships as "PH-Navigator for SketchUp". "DesignPH-PLUS" stays as the internal
codename only** (this repo and the POC record). The reasoning, recorded so it stays decided:

- **Trademark.** designPH is PHI's mark. A product *named* with it implies endorsement, and a
  paid product makes that worse. A product *described* with it ("library sync and HBJSON
  export for designPH models") is nominative use and standard practice, so the mark appears in
  listings and copy descriptively, never in the name. This also keeps the LI-2 conversation
  about the interop rather than about the name, and removes the cheap, separable objection a
  designPH-branded name would hand PHI. If PHI ever offers co-branding after seeing the
  working product, that is a partnership negotiated from strength, not a plan to depend on.
- **One brand survives every §12.1 model.** v-0 Import requires a PHN project token, so the
  first shipped affordance already begins with a PH-Navigator login. The plugin is a client of
  the platform under Model 1 (a bundle module) and Model 2 (the free client that recruits)
  alike. One name at purchase, in the extension menu, in the web app, and on the invoice.
- **Licensing rides PHN auth.** The plugin is free to download and unlocks affordances per
  subscription tier through the PHN account. That resolves the Warehouse licence-check problem
  above and makes the Model 1 / Model 2 / per-affordance choice a pricing toggle rather than a
  product-identity commitment.
- **PH-Navigator is not renamed.** "designPH-PLUS-web" would multiply the trademark exposure
  and shrink the platform's scope to one integration; PHN also serves the Rhino/honeybee route
  and the dashboard viewer. *(If the platform ever gets a different market name, this
  pre-launch moment is the one cheap time to change it, and the plugin rule transfers:
  `<Platform> for SketchUp`.)*
- **PH-Tools stays the open-commons org** (schemas, contracts, and now the open-source plugin
  itself, §12.3). It is not a customer brand.
- **"OpenPH" is reserved, not spent** (Ed, 2026-09-01). It was considered as a community brand
  for the plugin and set aside for v-0: the funnel argument and the community argument pull in
  opposite directions, and v-0 Import is PHN-coupled to its core, so a community name would
  misdescribe the first shipped thing. The name stays with the open calculation engine (the
  PHPP port), which is the most OpenPH-shaped asset we own and the §13 long-term aim. An
  eventual open-commons umbrella (engine, schemas, maybe someday the plugin) is a later,
  deliberate consolidation, made when a community exists to carry it.

**Community posture** *(with the Model 2 selection)*: the plugin is open-source and
**BLDGTYP-led, open to contributions**; "community-led" would overstate what a two-person firm
can staff. The designPH hack-makers get absorbed by pull request, not by an extension API. The
ladder: open source + PRs now; a documented public Ruby module other extensions can call, when
demand shows; a real extensibility layer only if an ecosystem emerges. An extension API is a
product in itself (stable interfaces, versioning, third-party code running beside client models
in a runtime whose constraints took a POC to map), and nothing yet justifies one.

⚠ **Prior art / namespace.** BLDGTYP already shipped two small public extensions under the
dPH+ brand, `dPH+ Rooms` (~2021) and `dPH+ Windows`, at
`~/Dropbox/bldgtyp-00/00_PH_Tools/design-ph-plus/`. Useful precedent for the PHI conversation
(see `planning/01_sketchup-export/feasibility/PHASE-5`). PH-Navigator for SketchUp supersedes
that branding; still make sure the new extension's Ruby module and menu namespace cannot
collide with a legacy `dPH+` install on a user's machine.

### 12.5 PHN productization: the PassivSure proposal *(revisit opened 2026-09-01)*

Model 2 puts every plugin-side revenue dollar behind PH-Navigator becoming a real multi-tenant
commercial service, and PHN today is an internal tool. That workstream already has a concrete,
scoped proposal: **Megan Ring's one-pager of 2026-08-17**
(`~/Downloads/2026-08-17-phnavigator-onepager-for-ed.md`; file a copy somewhere durable). Ed
declined it at the time because the only downstream consumer was the Rhino route, unrealistic
for ~99% of CPHCs. **The SketchUp pathway removes that objection, and the proposal is being
revisited (Ed, 2026-09-01).** Its shape, as proposed:

- **PassivSure builds and funds the commercial layer**; BLDGTYP keeps the building science and
  the modeling. Scoped at 26 to 38 engineer-weeks: M0 licensing extraction (2 to 3 weeks), M1
  tenant isolation and shares (design-partner revenue at roughly 3 to 4 months, onboarded and
  invoiced by hand), M2 self-serve (identity, billing, seats, admin console, suite
  integration).
- **"Hosting, not features."** The Navigator source stays open and self-hostable, the catalog
  stays public (with its own data licence still to sort out), hosted is paid with one free
  project. This is the same line as Model 2's plugin split, which is part of why the pairing
  fits.
- **Her licensing scoping matches §12.2's AGPL point, with numbers.** Exactly three PHN
  backend modules pull the AGPL dependencies (`gh_api/constructions_export.py`,
  `model_viewer/extraction.py`, `project_location/sun_path.py`); moved behind a network
  boundary, the core can relicense Apache-2.0 or MPL-2.0, with `ps-phx-parser` as the built
  precedent. ⚠ The PHN repo carries no LICENSE file today, so M0 comes first for a reason, and
  counsel's AGPL question now has a concrete server-side work item attached.
- **PassivSure's running downstream half**: permit and reviewer workflows, IECC / Title 24
  compliance checks, metered-utility benchmarking, and a `model_updates` endpoint that already
  accepts a model envelope. The plugin's Export feeds that chain directly, which is the
  "design → permit with no re-entry" leg of her roadmap.
- **Open before anything is signed**: the commercial rights structure, the Reimagine Buildings
  Collective question, the name and domain, and decision rights once PassivSure funds the
  build. Terms stay in the negotiation, not in this PRD.

## 13. Roadmap *(rewritten 2026-09-01: the ship order follows the gates)*

**v-0, A · Import (Library Sync).** Ships first because nothing legal blocks it: pure Ruby, no
honeybee, the contract frozen, the transport proven. Scope document = the POC #3 L-C gate
(`planning/03_library-import/`). Internal-only until LI-1/LI-2 clear (§9).

**v-1 adds C · Export.** Draft v1's thesis. The pipeline is already proven twice, and the
Model 2 selection settles the architecture: open-source plugin, Pyodide runtime as validated
(§12.1, §9). Counsel confirms the AGPL posture before public release. Feature two of the same
extension.

**v-2 adds B · Build, staged.** Data-shaped items first (rooms, ventilation airflows,
ventilator counts: the entries PHPP needs on every project), geometric authoring (duct and pipe
runs) after. Requires the honeybee-ph data model bound to a SketchUp UI and the designPH
round-trip rules (§2.2). This is where the single-source-of-truth promise is actually kept and
the dual-entry problem dies.

**Research track, in parallel: D · Notes** (§2.4: feasibility spike + the pholio boundary page)
and **HBJSON → fresh SKP** (`planning/04_hbjson-to-skp/`, its own POC).

**Parallel workstream, on the critical path to revenue: PHN productization** (§12.5). The
PassivSure proposal is the concrete plan; its M1 threshold puts design-partner revenue at
roughly 3 to 4 months into the commercial build.

**The long-term aim** *(recorded 2026-08-31)*: all project data flows into the calculator from
the model side, with provenance, and the calculator (PHPP today, OpenPH eventually) becomes a
throwaway compute artifact rather than a mixed calculator-and-information-model. One strategic
question is deliberately open: whether the SKP or the pholio record is the canonical certifier
hand-over artifact. That is a decision memo for Ed, not a spike.

**Ongoing conversations:** PHI (`.ppp`, shading, the write posture, the commercial posture,
possible absorption of the authoring idea); Ladybug Tools (they have no SketchUp presence, and
a credible bridge into the largest architectural modeller is worth more to them than to us;
open with something working, not with a maintenance ask).

## 14. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| PHI objects | **Existential** | Early conversation; complementary positioning (every plugin seat presupposes a designPH licence); S6. ⚠ *Updated 2026-09-01, twice:* under the selected Model 2 the plugin is free and open-source again, so the "free community bridge" argument returns for the plugin; commercial scrutiny attaches to the hosted PHN service instead. LI-2's opener is drafted on that split |
| Pyodide fails in `HtmlDialog` | High | S1 before commitment; the Ruby-writer fallback stays real if counsel surprises. The Model 2 selection means the business model no longer forces it (§12.1) |
| designPH 3.0 schema differs | High | S4 early (⛔ currently blocked on procurement); version gate refuses rather than guesses |
| Silent aperture loss | High | Never drop without reporting (§8.2); regression corpus. ⚠ **Retired as a guess, live as a measurement:** the POC lost all 46 to a coordinate-space bug that projection absorbed silently. Any lossy step needs a stated limit (§8.2) |
| `*Auto`/`*ID` misread | Medium | S3; the Export path is read-only and cannot corrupt anything |
| U-value translation wrong | Medium | Regression test against designPH's own reported values. ⚠ **This risk fired**: framing was ignored entirely, 8 % low and flattering, until the regression was pointed at a model that actually has framed assemblies (§8.3.1) |
| **A check or harness that is wrong about correct data** | **Medium to High** | *New, 2026-08-21.* Three of four real captures failed reconciliation on checks comparing the wrong quantities, and the data was right every time. Validate a check against **more than one model** before trusting it to grade; Adelphi masked every one of these by being the simplest model in the corpus |
| **Evidence from a single sample** | **Medium to High** | *New, 2026-08-21.* Six separate rules on this project were inferred from n=1 and were wrong. Check against the whole corpus baseline before generalising; it is cheap and it exists for this |
| designPH changes attribute schema without notice | Medium | Version gate; it is not a published interface. ⚠ It now bites the **write** side too: Import emits the schema the model already carries (`:TOKENS`, per-key base64 style), never the one we like |
| AGPL constrains the product | Medium | Plugin side resolved by the open-source posture (§12.1); counsel confirms. The live item is PHN's server-side extraction, three modules behind a network boundary, landed before the commercial layer (§12.5) |
| **All revenue sits behind PHN productization, and the partnership is unsigned** | High | §12.5: the PassivSure proposal is scoped (design-partner revenue at M1, roughly 3 to 4 months of commercial build); open items are rights, RBC, and governance. Hedge: BLDGTYP is user zero (§2.2), so the plugin pays for itself internally at zero external revenue |
| **PHI objects to *writing* designPH data** | **Existential** (shared with the read risk) | *New, 2026-08-31.* LI-1 licence re-read before shipping; LI-2 updates the PHI opener; internal-only until both clear. Import makes designPH *more* valuable, and that is the mitigation |
| **Build scope creep**: a mirror of `honeybee_grasshopper_ph` is a multi-year product | High | Stage it (§2.2): data-shaped items ride forms and the Import channel; only geometric authoring needs new SketchUp UI. No Build code before the round-trip rules exist |
| **Notes duplicates pholio's review surface** | Medium | N-4 is answered *first*: prefer pholio/PHN as the service of record over a third messaging system. "Notes belongs in pholio" is an acceptable research outcome |
| **Unstable identifiers break Notes across export** | Medium | Known uuid churn per export (`00_Context/HONEYBEE_STACK.md` §4). Stable ids in `DesignPHPlus_dict` are a named prerequisite (N-3), decided before any Notes build rather than discovered during it |

---

## Appendix: decision log

Design decisions and their rationale, from the 2026-08-19 planning session.

| # | Decision | Because |
|---|---|---|
| 1 | Product for the CPHC market, not internal | BLDGTYP uses Rhino; the market has no path at all |
| 2 | Value is downstream unlock + SSOT, not time saved | If it only saved typing, a PHPP macro would beat it |
| 3 | v1 envelope-only, read-only | Ships the piece everything else depends on; no UI needed; cannot corrupt *(scope superseded by the §2 reframe; the read-only rule survives as Export's, and as hard rule 2 for entity data)* |
| 4 | Complementary to designPH, not a replacement | Turns the PHI conversation from competitor to partner |
| 5 | `.skp` only, no `.ppp` | Licence §2.4(a) *(amended 2026-08-31: validation reads of our own exports permitted; §9)* |
| 6 | Shading omitted, explicitly marked | Only needed for a path we are not building (follows from #4) |
| 7 | Single non-solid Room + PH `Space`s | Most designPH models are not solid; volume comes from data |
| 8 | Pyodide preferred, Ruby-writer fallback | Real tested code, zero install; fallback avoids AGPL *(the choice now also follows the §12 business model)* |
| 9 | One extension, feature-flagged | Two installs, two update cycles, mismatched-version users |
| 10 | Done = schema-valid + loads in viewer | Automatable; avoids dragging `.ppp` back onto the path |
| 11 | ~~Free, open-source, `PH-Tools`~~ | **Superseded 2026-09-01 (Ed)**: commercial pairing with PH-Navigator; see #24 and §12. *(Was: adoption over revenue; defuses PHI risk)* |

**Decisions taken during the POC** *(2026-08-21, recorded here because they are product
decisions, not implementation ones)*:

| # | Decision | Because |
|---|---|---|
| 12 | **Degenerate input is reported and carried, never repaired or dropped** | Real models hold slivers, zero-width spurs and sub-micron non-flatness. Adelphi's 82 classified faces include 8 with a sub-mm edge and 7 whose boundary revisits a point. Dropping a classified face breaks *82 of 82*, the first number a reader checks, to save 1.7 cm² |
| 13 | **Noise is flattened below a stated, reported threshold; slope is refused** | 1 mm. Snapping 12 µm of coordinate noise is not the projection that would be fabrication, and the alternative was losing 368 m² of TFA to two faces. The line has to be explicit and every face on either side of it named |
| 14 | **The area group wins over honeybee's geometric inference** | designPH's area group is PHPP's own classification; honeybee infers type from tilt and winding. Where they disagree, flip the geometry to match the group. Letting honeybee win would quietly re-file a TFA marker as roof |
| 15 | **Where honeybee cannot represent designPH's number, emit ours and predict honeybee's verdict** | Applies to framed U-values (§8.3.1) and to apertures honeybee will call unbounded (§8.2). Fabricating geometry or conductivity to satisfy a validator is the one thing worse than a reported discrepancy |
| 16 | **The shading disclosure travels *inside* the HBJSON** (`user_data`) | A marker beside the file can be separated from it. Verified to survive `to_dict`/`from_dict`; the model must not be passable on without the disclosure |

**Decisions from the product-shape discussion and this reframe** *(2026-08-31 / 2026-09-01)*:

| # | Decision | Because |
|---|---|---|
| 17 | **One plugin, four affordances** (A Import / B Build / C Export / D Notes); pholio and PH-Navigator stay fully separate products | The four affordances share one model, one namespace, and one install, and they compound (§2.5); the watcher and the web app have different motion, buyer, and licensing exposure |
| 18 | **v-0 = Import (Library Sync)**: pull-only, inside SketchUp, PHN stays web-only | The only affordance with no legal gate, on the only transport actually proven |
| 19 | **Import windows are types only** (frames + glazings) | The type data is the tedious, error-prone part; geometry stays the user's job |
| 20 | **Export release waits on the AGPL answer; a headless export belongs to pholio** | AGPL §13 and the C-SDK gates attach to server-side reading, not to this plugin |
| 21 | **Notes is added as a research affordance, not a commitment** (2026-09-01) | Certifier transparency and communication are core values; feasibility, anchoring, and the pholio boundary (N-1…N-5) are unresearched |
| 22 | **Build's data model is honeybee-ph's, not a new schema** | The schema exists, round-trips, and PHX already writes it to PHPP/WUFI/METr; Build is UI + storage over a proven model |
| 23 | **HBJSON → designPH means a FRESH `.skp`, never surgery on an existing model** | Edit-in-place collides with designPH's auto-classification and hard rule 2's face-level line; a fresh model is ours, with designPH invited in (`planning/04_hbjson-to-skp/`) |
| 24 | ~~Commercial pairing with PH-Navigator; working model = paid extension + paid PHN subscription; revenue split OPEN~~ (Ed, 2026-09-01) | **The pairing stands; the working model was superseded the same day by #26** (Model 2 selected). Kept for the record of how the choice moved |
| 25 | **The extension is named "PH-Navigator for SketchUp"; designPH appears only descriptively; "DesignPH-PLUS" stays the internal codename** (Ed, 2026-09-01) | One brand and one PHN account survive every §12.1 model (v-0 Import already requires a PHN token); PHI's mark stays out of the name so LI-2 is about interop; licensing rides PHN auth, making the revenue split a pricing toggle (§12.4) |
| 26 | **Model 2 selected: free, open-source plugin (manual Export included); the hosted PHN subscription is the revenue; pholio a separate paid downstream service** (Ed, 2026-09-01) | Resolves #24's open split. Open-sourcing lets the plugin vendor honeybee, so the proven Pyodide runtime stands and no plugin licensing mechanism exists at all (value-gating is server-side); free export seeds the artifacts pholio monetizes; BLDGTYP as user zero underwrites free Build (§12.1, §2.2) |
| 27 | **"OpenPH" reserved for the calculation engine and the open commons, not spent on the plugin; community posture is BLDGTYP-led, open to contributions; extensibility deferred to the PR → public-Ruby-API → platform ladder** (Ed, 2026-09-01) | The funnel and community arguments conflict at v-0 (Import is PHN-coupled); the engine is the most OpenPH-shaped asset and the §13 long-term aim; an extension API is a product a two-person firm cannot staff yet (§12.4) |
| 28 | **Revisit the PassivSure proposal for PHN productization** (Ed, 2026-09-01) | Declined in August for lack of a non-Rhino downstream; the SketchUp pathway supplies one. The proposal is already scoped (26 to 38 engineer-weeks; design-partner revenue at M1) and its "hosting, not features" line matches Model 2 (§12.5) |
