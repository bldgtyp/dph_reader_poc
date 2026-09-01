# DesignPH-PLUS — Agent Instructions

Canonical agent guidance for this repo. `CLAUDE.md` imports this file; anything Claude-specific lives
there. Keep this file tool-neutral.

---

## What this project is

**DesignPH-PLUS** — a planned free, open-source **SketchUp extension** that reads a designPH model and
writes valid, standard **HBJSON**, opening Passive House envelope data to viewers, QA tools,
reporting, certifiers, and downstream automation.

**Current status: ✅ the POC is COMPLETE (Ed closed it 2026-08-21), and this repo is now the
background-research record for a future V-0 of a real plugin.** All five POC phases closed PASS;
the pipeline ran end to end inside SketchUp on five real project models and its output was
verified in production ph-navigator and in Rhino/Grasshopper. Spike Phases 0–3 are complete
(2026-08-19); Phases 4 and 5 remain **tabled** (Ed, 2026-08-19) on two recorded working
assumptions — a designPH 2.x reader will translate to 3.0 later, and PHI will agree. POC code
lives in **`pocs/01_sketchup-export/`** and stays **internal-only and never distributed** — the AGPL question
(`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md`) blocks *release*, not internal work (working
assumption, for counsel — `planning/01_sketchup-export/implementation/00_POC_OVERVIEW.md` §2.3).

**▶ One follow-on phase is ACTIVE (opened 2026-08-28):
[`planning/02_headless-reader/`](planning/02_headless-reader/.index.md)** — can a headless service read the `.skp` via
the **SketchUp C SDK**, with no SketchUp installed and no SketchUp seat, and emit the POC's
contract-v2 capture? (The passive-scrape question behind pholio's Dropbox-watcher model.)
✅ **Answered yes, twice over: Spikes A and B both PASS (2026-08-29).** Spike C (deployment) is
the remaining technical question; the blocking ones are legal.

✅ **Spike A PASSED 2026-08-29** ([results](planning/02_headless-reader/RESULTS/HEADLESS-A_results.md)). A
headless CPython process, no SketchUp anywhere, reproduces the live Ruby collector's reads exactly
on all five real models — **545/545 classified faces · 239/239 windows, every host via the glue
query · 99/99 thermal-bridge edges · 63/63 Marshal tables · 15/15 files opened**, at ≈3-4 s per
model, with world geometry matching to **0.0000 mm** on windows and 0.0008 mm on face vertices.

✅ **Spike B PASSED the same day** ([results](planning/02_headless-reader/RESULTS/HEADLESS-B_results.md)) —
and it is the one that answers the product question. **A headless reader is a drop-in capture
device.** It emits the frozen contract v2 with **0 unexplained differences on 5/5** models against
the live SketchUp captures (worst geometry deviation **0.000000 mm**), reconciles under the
unchanged harness, feeds the **untouched** translator to the POC's own acceptance numbers
(545/545 · 239/239 · 99/99, TFA 368.5 / 1491.9 / 448.2 m²), and produces **canonically identical
HBJSON** on all five. All **16** staged models emit contract v2 in **11.8 s**; the 146 MB scale
probe reads in 2.5 s at 717 MB peak; two models open at once, two processes and two threads all
work. ⭐ **`2536 Holmes`'s 42 named thermal-bridge edges are captured for the first time** — the
only second bridge model in existence.

The four differences that survive are all named and none is a difference in what was read:
`entity_id` (which the contract already calls session-scoped — ⚠ and it is scoped to the
**process**, so a watcher hashing captures to detect change must exclude it), record order,
**signed zero** (72 coordinates, `-0.0` vs `0.0`, invisible to `==`), and `model.file_name`, where
the headless reader is deliberately **right** and the live one inherited a backup's misspelling
from `Sketchup::Model#path`.

Durable record: [`00_Context/SDK_RUNTIME.md`](00_Context/SDK_RUNTIME.md) §4e-§4g and
[`00_Context/HEADLESS_VIABILITY.md`](00_Context/HEADLESS_VIABILITY.md). ▶ **Spike C (deployment) is
unblocked**, with the licensing block stated first.

⛔ **Three caveats, and the first is not technical.** Trimble's C SDK is **no longer a public
download** — it sits behind a "Request Access" form with no reported turnaround — so Spike A ran on
a third-party re-host of the binary, on Ed's explicit call, as *feasibility-only* evidence to be
re-run against the official SDK; **licensing task L1 (read the SDK EULA) cannot start**, because
the EULA ships inside the download nobody can get. And ⛔ **a C-SDK reader mutates the in-memory
model as a side effect of reading it** (`SUEntityGetAttributeDictionary` is a get-or-CREATE), so
*never save an opened model* is a load-bearing invariant. ✅ Spike B made that **structural** rather
than procedural — the binding declares no writer and the read-only handle refuses to resolve one, 6
of 6. ⚠ And third: **a PASS makes the AGPL §13 reframing (L2) urgent rather than hypothetical**, because
a working server-side path is exactly what triggers it.

The phase reuses the POC's assets as ground truth and reopens none of its verdicts — the contract
stays frozen at v2 and the POC status table below stands.

> ### ▶ **The successor project is [`pholio`](/Users/em/Dropbox/bldgtyp-00/00_PH_Tools/pholio) (2026-08-21).**
> The strategy retrospective that closed this POC concluded the right product is **not** a
> standalone SketchUp extension but *the record above all the tools* — a folder watcher + readers +
> web record ("version control for Passive House"). Its PRD and context live there; this repo's
> `00_Context/` and retro are snapshotted into its `research/designph-plus/`. **This repo stays
> canonical for designPH facts**; product planning continues in pholio.
>
> ### ▶ **Here for the designPH research or the POC itself? Three files, in order:**
> 1. [`planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md`](planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md) **§4 — the
>    ranked "what v1 must do differently" list.** The POC's product; every entry measured.
> 2. [`00_Context/CONSTRAINTS.md`](00_Context/CONSTRAINTS.md) — every hard limit and blocker.
> 3. [`DESIGNPH-PLUS_PRD.md`](DESIGNPH-PLUS_PRD.md) — what the product is and deliberately is not.
>
> ⛔ Three non-technical blocks stand between here and a shipped v1: the **AGPL answer** (counsel),
> the **designPH 3.0 licence** (cannot be bought yet — Phase 4), and the **PHI conversation**
> (Phase 5). Nothing in this repo unblocks them; plan around them, don't rediscover them.

| Phase | State (2026-08-21) |
|---|---|
| Contract | ✅ **FROZEN at version 2.** v1's frame/glazing option lists cost 2.07 MB of a 2.25 MB payload, repeated per window; v2 hoists them to a model-level `libraries` block. Changes go through §9 |
| POC-1 runtime shell | ✅ **PASS** — gate closed inside SketchUp 22.0.353. Boot 2577 ms, no regression on Phase 3 |
| POC-2 Ruby collector | ✅ **PASS** — **5 of 5** models captured and reconciled; E-1 answered (all 99 Bluff Reach bridge edges nest two levels deep) |
| POC-3 translator | ✅ **PASS** — 545/545 faces, 239/239 windows, 99/99 bridges across the corpus; **both U-value regressions PASS** |
| POC-4 integration | ✅ **PASS** — gate closed 2026-08-21. All four Ed runs correct; both identity claims closed; both refusals fire. ⛔ The progress signal does not work and is carried to v1 |
| POC-5 | ✅ **PASS — closed by Ed 2026-08-21, and the POC with it.** Retro + ranked v1 list (`planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md` §4); standing smoke runbook; ph-navigator checked live — Finding 71 (its viewer skips no-mass-construction faces) and the identifier question closed (nothing keys on `properties.ph.*.identifier`) |

⚠ **Two exports of one model are not the same file** — honeybee-ph gives every newly *constructed*
PH object a `uuid4` (152 distinct on Adelphi) and honeybee-energy orders four lists out of a `set`,
so the same translation twice on one CPython gives two hashes. The cross-host gate is therefore
**canonical** equivalence, not byte equality. ✅ **This is not an upstream defect**:
`from_dict` → `to_dict` preserves 152 of 152, measured — `uuid4` is a constructor default for
objects with no identity of their own, and only 1 of the 152 is a real cross-reference. The effect
is diff noise between re-exports, nothing more. `00_Context/HONEYBEE_STACK.md` §4,
`planning/01_sketchup-export/implementation/RESULTS/POC-4_results.md` §3.

**What the corpus proves, in one table** *(2026-08-21, five real projects, designPH 2.1.15–2.2.29,
SketchUp 22–26)*:

| | |
|---|---|
| Classified faces translated | **545 of 545**, none rejected |
| Apertures | **239 of 239** — every host resolved by `glued_to` |
| Thermal bridges | **99 of 99**, all nested two levels deep |
| TFA | 368.5 / 1491.9 / 448.2 m² on the three models that carry group-1 faces |
| U-values vs designPH's own calculator | worst Δ **0.0005 W/m²K** (tier 1); **exact** (tier 2) |
| Interchange | the HBJSON loads in Rhino/Grasshopper on an *independent* honeybee install |

**The first real export changed the documentation more than it changed the code.** Four rules that
had been *inferred* turned out to be wrong, and all four are now measured and recorded in
`00_Context/` — start at `CONSTRAINTS.md` §8.1. The shortest version:

- **`face.area` is NET of glued window openings and `face.loops` never shows them.** So a loop
  polygon is gross and `face.area` is net, and **`glued_to` is the only thing that identifies a
  window host** — `loops.size > 1`, which Phase 1 installed as the fix for the `cuts_opening?` trap,
  is true on only **1 of 16** real Adelphi hosts (1 of 81 corpus-wide, remeasured 2026-08-28).
- **The aperture rectangle is the rough opening via the WORLD transform.** A window definition has no
  top-level faces at all, and its largest face at any depth is the **glazing** — 41 % too small,
  plausibly.
- **`ComponentInstance#transformation` is parent-relative** while every other contract field is
  world. Cost: windows landing 1.2–3.3 m off their hosts.
- **`Face3D.is_horizontal` tests z-extent, not orientation, at 1e-7 m.** Two faces with a 12 µm
  spread cost all 40 TFA faces and 368 m².

And the method rule underneath three of them: **do not re-implement half of a library's rule
locally** — `clean_string`, `u_value`/`u_factor` and `is_horizontal` each broke that way in one
session, and each looked right. A fourth turned up while fixing them:
`Polygon2D.is_point_inside_bound_rect`, used as a fast path in front of the tolerant
`point_relationship`, takes no tolerance and refused every window flush with its host's edge.

**Fixing those three defects added one more method rule, and it is the one that saved a session:
ask what the data on disk already constrains before booking a run to find out.** The window fix
rested on an inference — is the definition origin a *corner* of the rough opening, or its *centre*?,
half a window apart — and the answer came out of the already-recorded *defective* capture: local +Z
onto host normal (Kabsch) plus local origin onto host plane (least squares) determines the parent
transform, which scores the conventions at **46/46 against 23/46** and then lets the whole fixed
pipeline be rehearsed. ⚠ A rehearsal is not a capture; it de-risks the re-capture, it does not
replace it. `planning/spikes/poc/`.

**Then the corpus sweep added the counterpart lesson, and it is about our own tooling.** The
reconciler failed on **three of four** real captures and the data was right every time — two checks
compared the wrong quantities (dict-carriers vs area-group carriers; placements vs entities) and one
flagged an override pair as a contradiction. Adelphi masked all three by being the simplest model in
the corpus.

⚠ **When a check fires on most of your real data, suspect the check.** And validate a check against
more than one model before trusting it to grade — that is the same rule as "a synthetic model is not
evidence", pointed at the harness instead of the fixture.

**Finally: when the vendor's own UI can answer a question about the vendor's data, ask it.** The
multi-section U-value method and the unit of `surf2_percentage` were both settled by one screenshot
of designPH's U-/R-value calculator — after an analysis that had confidently derived a *fitted*
answer and reported the fit as confirmation. A parameter tuned to make a model match cannot then
confirm that model.

✅ **The output is genuine interchange**: the HBJSON loads in Rhino/Grasshopper on an *independent*
honeybee install (`00_Context/HONEYBEE_STACK.md` §6.3). Every other test in the project uses the same
eight vendored wheels and can only prove self-consistency.

✅ **The runtime is decided: Pyodide inside `HtmlDialog`.** Real, unmodified honeybee + honeybee-ph
runs inside SketchUp 2022 and writes HBJSON from a real designPH model — 82 of 82 classified Adelphi
faces, none rejected, boot in 2.6 s, 6.77 MB `.rbz`. Four constraints came with it and
all four are load-bearing:

- ⚠ **Pyodide is pinned at 0.24.1 by SketchUp 2022's Chromium 88.** 0.28+ will not parse; 0.25–0.27
  will not instantiate their wasm. **The oldest SketchUp supported sets the newest Pyodide
  available** — PRD §7.4 is now a product decision with a technical price.
- ⚠ **Serve over `http://127.0.0.1`, never `file://`.** The dialog cannot fetch its own assets from
  `file://` — confirmed inside SketchUp, and no shim reaches the dynamic `import()`.
- ⚠ **The loopback server must be a worker thread pumped by a sleeping `UI.start_timer`.** Each half
  alone hangs SketchUp, silently and differently. See `CLAUDE.md`.
- ⚠ **`zipfile` unpacking is the installer, not `micropip`** — micropip is coupled to the Pyodide
  release and fails on 0.24.1.

⚠ **The AGPL question is now live**, because vendoring honeybee is a decision rather than a
possibility. It is written up for counsel and must be answered before v1.

From Phase 1 (`planning/01_sketchup-export/feasibility/RESULTS/PHASE-1_results.md`), four things change how you should read the
rest of this repo:

- ✅ **`00_Context/DESIGNPH_DATA_MODEL.md` §6 is settled** (§6.5). `*ID` and `*Auto` are **mutually
  exclusive per face**, so the read rule is a *coalesce* — `face[*ID] or face[*Auto]` — and it is
  version-independent. Both earlier candidates were wrong: the version rule, and "prefer `*ID`".
- ⚠ **Thermal bridges are on `Sketchup::Edge`, not on faces.** PHPP measures them as lengths.
  **A reader that iterates only faces loses every one of them, silently** — 99 of 293 tagged
  entities on `2414 Bluff Reach.skp`. Their `assemblyID` also points at `connections_ud`, a
  different table from the assemblies; both use `NNud` ids, so getting it backwards is silent too.
  Read the area group first: 15/16/17 means edge + connection (§7.1).
- ⚠ **Assemblies do not always carry a build-up** — 254 of 532 corpus references do. Some resolve
  only against designPH's *installed* CSV library, outside the model. PRD §8.3 is rewritten around it.
- The two **[Ed]** long leads were **deferred out of Phase 0** (Ed, 2026-08-19), and one of them has
  since hardened into a block: ⛔ **the designPH 3.0 licence cannot be bought yet** (Ed, 2026-08-21).
  That is a procurement constraint, not a scheduling choice — **Phase 4 is blocked on something no
  agent work can unblock, so do not propose starting it.** The PHI opener still fires at the start
  of **Phase 5**. Both are drafted in `planning/01_sketchup-export/feasibility/RESULTS/PHASE-0_long-lead-staging.md`.
  *(Unaffected, and deliberately: the POC's version gate refuses a 3.x stamp by name. It needs no
  licence, and a reader that meets a 3.0 model in the wild must say so rather than half-read it.)*

**Phase 1's gate closed PASS WITH CHANGES (2026-08-19).** Window host lookup is solved —
`glued_to` resolves 46/46 — but `cuts_opening?` is a component-definition capability, not a fact
about the host. ⚠ **And `face.loops.size > 1` is not the fix** (POC, 2026-08-21): a glued opening
creates no loop, so it is true on only **1 of the 16** real Adelphi hosts. **`glued_to` is the only host test.** **Shading geometry came back out of v1
scope**: no heuristic separates context from clutter, so v1 will ask the user which SketchUp tags
are shading rather than guess (PRD §7.2).

**Phase 2's gate closed PASS WITH CHANGES (2026-08-19)** — `planning/01_sketchup-export/feasibility/RESULTS/PHASE-2_results.md`.
The Python stack is pure, and the change widens Phase 3 rather than narrowing it:

- ✅ Phase 3 vendors **8 `py3-none-any` wheels, 1.5 MB**, on a 6.4 MB `pyodide-core` plus
  `micropip` — ≈8 MB total, under the PRD's ~10 MB guess. Install them with
  **`micropip.install(..., deps=False)`**: `honeybee-core` *declares* `honeybee-schema` →
  `pydantic` → `pydantic-core` (Rust), and nothing outside the `cli/` modules ever imports it.
- ⚠ **`pyodide-core` ships no packages at all** — 13 files, no `micropip`. Vendor `micropip`
  (113 KB) and `packaging` (94 KB) too, or unpack the eight pure wheels directly.
- ✅ **PHX's write path is pure too**, overturning "Phase 3 targets honeybee-ph only".
  `from_HBJSON` → `model` → `to_WUFI_XML` / `to_METr_JSON` runs with `lxml`, `xlwings`, `pydantic`
  and `rich` all absent — verified by running it, not by reading imports. Only
  `PHX.from_WUFI_XML` and `PHX.PHPP` are impure.
- ⚠ **`xlwings` blocks PHPP writing at runtime, not at install.** It publishes a pure wheel and
  imports fine; it fails only when it reaches for a live Excel, which a `HtmlDialog` will never have.
- ⚠ **`adelphi-honeybee-json.hbjson` no longer loads** under current `honeybee-ph` —
  `Model.from_dict` raises `KeyError: 'tfa_override'`. It stays a *shape* reference; it is not
  usable as a load fixture. Build fixtures with `Room.from_box`.

Phase 3 took that scope statement verbatim and it held — though `deps=False` turned out to be moot:
`micropip` will not run on the Pyodide version SketchUp's Chromium 88 forces, so the wheels are
unpacked with `zipfile` instead. Every one of them installed and imported.

Read in this order:

0. **`planning/01_sketchup-export/implementation/RESULTS/POC-5_results.md`** — the POC retro: the verdict, the measured tables,
   and §4's ranked "what v1 must do differently" list. If you are picking this up cold — especially
   to plan a V-0 — start here and nowhere else. (`planning/01_sketchup-export/implementation/.index.md` carries the closed
   status table and the same routing.)
1. **`00_Context/CONSTRAINTS.md`** — every hard limit, blocker and non-negotiable rule, with pointers
   into the detail. Cheapest possible way to avoid redoing Phases 0–3 *or the first real export*
2. `DESIGNPH-PLUS_PRD.md` — what we are building and, importantly, what we are deliberately *not*
3. `planning/01_sketchup-export/feasibility/00_OVERVIEW.md` — the phased spike plan and its evaluation protocol
4. `00_Context/` — the foundation layer: designPH's data model, SketchUp as a host, the Pyodide
   runtime, the honeybee stack, and the translation contracts between them. See its
   [`.index.md`](00_Context/.index.md)

## Hard rules

These are not style preferences. Violating any of them breaks the project's legal or technical footing.

1. **Never use the `.ppp` as an input route** *(amended 2026-08-31, Ed; was "never parse")*.
   Extracting designPH-computed data we did not author stays behind PHI's §2.4(d) written
   authorisation. **Validation reads of exports we produced are permitted**: verbatim-needle
   checks always; structural reads sourced only from the `phi-rules` ppp catalog + `PHX.to_PPP`,
   never from probing the file. Full three-tier line and licence reasoning:
   `00_Context/PPP_EXPORT.md` §1. See PRD §9.
2. **Read-only against designPH data.** Never write to `DesignPH_dict`. When v2 authoring arrives it
   writes to `DesignPHPlus_dict` — its own namespace.
3. **Never modify a corpus file.** Copy before experimenting. These are references, some irreplaceable.
4. **Report, don't guess.** Any face, window, or assembly that cannot be translated must be named in a
   report. Silent data loss is the failure mode that would most damage a free tool's reputation.
5. **Type-check every attribute read.** `areaGroupID` is a *String* (`'n'`) on 1359 of 1441 faces in
   the primary corpus model. Nothing about `DesignPH_dict` value types is guaranteed. See
   `00_Context/DESIGNPH_DATA_MODEL.md` §5.4.
6. **Coalesce the key generations; never version-key them.** Read `face[*ID] or face[*Auto]`. The
   two are mutually exclusive per face across all 14 corpus models, and *both* generations hold real
   data on real models regardless of the version stamp — `250708.skp` is 2.1.15 and keeps every
   assembly in `assemblyIDAuto`. Any rule keyed on the version stamp loses envelope data silently.
   See `00_Context/DESIGNPH_DATA_MODEL.md` §6.5.
7. **Do not start a spike phase until the previous phase's gate is evaluated and recorded** in
   `planning/01_sketchup-export/feasibility/RESULTS/`. Negative results get written down too.
8. **Serve the dialog over `http://127.0.0.1`, never `file://`.** A `file://` page cannot fetch its
   own assets — `fetch`, `XHR` *and* dynamic `import()` are all refused, and the third cannot be
   shimmed. Confirmed inside SketchUp. See `00_Context/SKETCHUP_RUNTIME.md` §4.3.
9. **Blocking work goes on a worker thread; a `UI.start_timer` callback exists only to `sleep`.**
   Each half alone hangs SketchUp, silently and in two different ways. Workers must never touch the
   SketchUp API, `puts` included. See `00_Context/SKETCHUP_RUNTIME.md` §5.
10. **Check `HtmlDialog`'s Chromium version before trusting any web API.** It is frozen at the CEF
    that shipped with that SketchUp release — 2022 is **Chromium 88 (January 2021)**, which caps
    Pyodide at 0.24.1. Read the plist; never interpolate between SketchUp versions.

## Languages and tooling

**Ruby (SketchUp extension)** — SketchUp 2022 ships **Ruby 2.7**, pinned to the host release. No
endless methods (`def x = y`), no pattern matching, no `Hash#except`. **Syntax-check every file with
`ruby -c` before installing.** Only `.rb` files directly in `Plugins/` are auto-loaded; subfolders
need a `SketchupExtension` loader stub.

**Python (tools, analysis)** — fully typed, dataclasses/Pydantic. Standalone and throwaway scripts
declare dependencies in a PEP 723 `# /// script` block and run with `uv run`. **Never** install to
system Python; never leave a `.venv` inside a tool folder.

**JavaScript / the dialog** — targets **Chromium 88**, not your browser. No top-level `await`, no
`static {}` class blocks, no `.at()`, no `Object.hasOwn`, no `structuredClone`, no WebAssembly
reference types. `00_Context/SKETCHUP_RUNTIME.md` §4.1.

**Vendored runtime** — **Pyodide 0.24.1** (CPython 3.11), 8 pure wheels installed by `zipfile`
unpack. **`micropip` is deliberately not shipped.** `00_Context/PYODIDE_RUNTIME.md`.

**Downstream stack** — `honeybee_ph`, `PHX`, `PH_units` and friends live at
`~/Dropbox/bldgtyp-00/00_PH_Tools/`. They must remain **IronPython 2.7 compatible** (that constraint
is what makes the stack pure-Python, and therefore Pyodide-viable). Schema contracts are published in
`honeybee-ph-schema`. Reachability, API traps and the PHX write path: `00_Context/HONEYBEE_STACK.md`.

## Layout

```
DESIGNPH-PLUS_PRD.md          product requirements
00_Context/                   ★ the SHARED foundation layer (all POCs) — read CONSTRAINTS.md first
  CONSTRAINTS.md              ★ every hard limit and blocker, one page
  DESIGNPH.md                 basics: authors, versions, licensing, install paths
  DESIGNPH_DATA_MODEL.md      attribute storage, keys, enums, rules, quirks
  DESIGNPH_FILE_FORMATS.md    CSV libraries, ID conventions, .skm, .skp binary layout
  PPP_EXPORT.md               the .ppp: the licence line, and why we stop there
  SKETCHUP_RUNTIME.md         Ruby 2.7, HtmlDialog's Chromium, threading, the bridge
  SDK_RUNTIME.md              SketchUp WITHOUT SketchUp: the C SDK, its access gate, its traps
  PYODIDE_RUNTIME.md          the version ceiling, installing by unpack, performance
  HONEYBEE_STACK.md           the 8 wheels, API traps, PHX's reachable write path
  DATA_CONTRACTS.md           the translation spine: designPH face → JSON → HBJSON
  tools/skp_attr_dump.py      offline .skp attribute reader (uv run)
  tools/skp_decode_tables.py  offline Marshal-table decoder (uv run)
planning/                     ★ one folder per POC — its .index.md is the master router + status
  .instructions.md            this folder's conventions (deviations from planning-conventions)
  01_sketchup-export/         ✅ POC #1 — designPH → HBJSON inside SketchUp (closed 2026-08-21)
    feasibility/              the de-risking spike plan: PHASE-0…5 + RESULTS/
    implementation/           the POC build: POC-1…5, the frozen contract, RESULTS/ (incl. ★ the retro)
  02_headless-reader/         ✅ POC #2 — the headless C-SDK reader (Spikes A+B PASS; C open)
  03_library-import/          ▶ POC #3 — write assemblies/window types INTO designPH models
                              (⭐ Spikes L-A + L-B both PASS 2026-08-31; PHN→designPH contract
                              FROZEN v1 — see 00_Context/DESIGNPH_DATA_MODEL.md §14/§14.7 and
                              planning/03_library-import/CONTRACT_phn-library.md; ▶ L-C next)
  spikes/                     throwaway spike code, kept regardless of outcome; its .index.md
                              maps subfolders to POCs (headless/_private/ is gitignored client data)
pocs/                         ★ POC code, numbered to match planning/ — internal-only, never distributed
  01_sketchup-export/         the extension + translator. Makefile: `make ci` (offline gate),
                              `make identity` (cross-host, needs `_private/`), `make ed` (install);
                              ext/ = Ruby + HtmlDialog page, py/ = `dph_translator` + pytest
                              (venv matches Pyodide's CPython 3.11), tools/ = vendor/build/verify
corpus/                       the reference models — hard rule 3: never modify one
  adelphi/                    primary corpus: one building in six formats (data removed in this copy)
  synthetic/                  small scratch models and inspector dumps
```

Per house convention, check for `.index.md` in a folder before processing its contents.

## Corpus

`corpus/adelphi/` — the same building across formats:

| File | Role |
|---|---|
| `adelphi-designph.skp` | **Primary input.** designPH 2.1.15. 1441 faces carry `DesignPH_dict`, but only **82** are classified — the other 1359 are `areaGroupID='n'` |
| `adelphi-honeybee-json.hbjson` | **Reference output shape.** 6 rooms, 52 faces, 44 apertures, 38 spaces, 1287 orphaned shades |
| `adelphi-phpp.xlsm` | Numerical ground truth (U-values, areas, TFA) |
| `adelphi-designph_PHPP10.ppp` | Reference by eye only — **do not parse** ⚠ Exported by designPH **2.4.0 BETA PRO** while the `.skp` beside it is **2.1.15** — not two views of one tool |
| `adelphi-rhino.3dm`, `adelphi-grasshopper.gh` | The Rhino-route equivalent |

⚠ The formats are **only approximately aligned**. A mismatch between them is not by itself evidence
of a bug. The HBJSON came from the Rhino route (6 solid rooms, solved adjacency) while v1 emits **one
non-solid room** by design — it is a shape reference, never an equality target.

Secondary corpus: `~/Dropbox/bldgtyp/*/08_DesignPH/*.skp` — **11 files across five real projects**,
spanning designPH 2.1.10 to 2.2.29, backups included. All 14 corpus models are baselined key-by-key
in `planning/01_sketchup-export/feasibility/RESULTS/PHASE-0_corpus-baseline.md` — check there before opening a model by hand.

★ **Five of them are now captured live** (contract v2, `pocs/01_sketchup-export/_private/fixtures/`, gitignored client
data — `MANIFEST.md`). This is the evidence base for everything dated 2026-08-21:

| model | designPH | classified | edges | windows | layer tables | what only it can test |
|---|---|---|---|---|---|---|
| `adelphi-designph` | 2.1.15 | 82 | 0 | 46 | 0 | the primary; tier-2 `assemblies_ud`; a PHPP beside it |
| `2414_Bluff Reach` | 2.2.24 | 194 | **99** | 40 | 6 | **thermal bridges**; `descName` overrides at scale (70) |
| `2523 Wellington` | 2.2.29 | 103 | 0 | 57 | 5 | two historical version stamps; a table the live model no longer carries |
| `250703 - Linde Residence` | 2.2.29 | 74 | 0 | 47 | **25** | **tier-1 layered assemblies**; **multi-section framing** |
| `250708` | 2.1.15 | 92 | 0 | 49 | 0 | all-`*Auto` assemblies; **resolves nothing in-model** (tier 3 × 92) |

⚠ **Adelphi is the simplest model in the corpus and it masks bugs.** It hid three separate
reconciliation defects — every one of its tagged faces carries an area group, and none of its
geometry is placed twice. **Never validate a rule or a check on Adelphi alone.**

## Existing tools

- `00_Context/tools/skp_attr_dump.py` — reads attribute dictionaries out of a `.skp` with no SketchUp.
  `uv run skp_attr_dump.py MODEL.skp -d DesignPH_dict`
- `00_Context/tools/skp_decode_tables.py` — decodes the model-level **Marshal tables** (`frames_ud`,
  `glazing_ud`, `assemblies_calc`, `connections_ud`, `layer_table_*`, …) out of a `.skp`, printing
  the `:TOKENS` header and sample rows. Construct-nothing reader, so a corpus file cannot run code.
  It is what settled that the frame/glazing libraries are *in the model*
  (`00_Context/DESIGNPH_DATA_MODEL.md` §7.0.1).
- `planning/spikes/phase0/` — four read-only analysis scripts (corpus baseline, HBJSON validation
  and shape, PHPP extraction). See `planning/spikes/.index.md` for what each produces and how to
  re-run it. All PEP 723 + `uv run`; none needs a venv.
- `planning/spikes/phase1/` — per-face attribute analysis and Marshal decoding, plus three staged
  SketchUp scripts. Two reusable modules worth knowing about before writing anything new:
  `skp_blocks.py` groups attribute records **per entity**, and `ruby_marshal.py` reads designPH's
  `Marshal.dump` blobs in pure Python without constructing anything.
- `pocs/01_sketchup-export/tools/` — the POC's own: `vendor_payload.py` (pin and fetch the Pyodide payload),
  `build_rbz.py` (build the extension; `--check` catches a staged translator that has drifted from
  source; `--install` copies into SketchUp 2022), `verify_in_chrome.py` (drive the built page in a
  real Chromium 88 and refuse any other engine), `check_extraction.py` (reconcile a capture against
  the offline baselines), `validate_output.py` (published honeybee-schema, separate interpreter),
  and `byte_identity.py` (does one extraction translate the same on every host?).
  `cd pocs/01_sketchup-export && make ci` runs the offline lot; `make identity` runs the last one.
- **A Chromium 88 snapshot** at `~/.cache/dph-plus/chromium-88/` — the engine SketchUp 2022 embeds,
  kept outside the repo. One `curl` to recreate; the line is in `verify_in_chrome.py`'s docstring.
  It is what turns "ask Ed to click and report back" into a local loop.
- `planning/spikes/poc/` — two scripts that read **only the already-captured extraction JSON**:
  `solve_window_parent.py` recovers the window parent transform from a capture (Kabsch + least
  squares) and scores the rough-opening conventions against the real hosts; `patch_and_translate.py`
  rehearses a fixed collector's output. They exist because *a recorded capture answers more
  questions than the run that produced it asked*.
- **BT Attribute Inspector** — read-only SketchUp extension at
  `~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/bt_inspector/`. Live inspection,
  selection watching, and a designPH surface report. Use this for *current* model state; the offline
  parser sees historical state too and cannot tell the difference.

## Domain vocabulary

**PHPP** (PHI's Excel workbook, the only tool accepted for PHI certification) · **WUFI-Passive**
(Phius desktop tool, XML) · **METr** (Phius's browser successor to WUFI, JSON) · **PHX** (our
conversion layer to all three) · **HBJSON** (Honeybee's serialization — the interchange target) ·
**TFA** (Treated Floor Area) · **iCFA** (Phius equivalent) · **area group** (PHPP Areas-worksheet
classification, stored raw by designPH).
