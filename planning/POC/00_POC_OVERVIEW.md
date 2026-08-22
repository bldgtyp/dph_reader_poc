# DesignPH-PLUS POC — Implementation Plan Overview

**Status:** ✅ **COMPLETE — all five phases closed PASS, and Ed closed the POC 2026-08-21.**
This is the plan as written; [`.index.md`](.index.md) carries the closing state, and
[`RESULTS/POC-5_results.md`](RESULTS/POC-5_results.md) is the retro — §4 of it is the "what v1
must do differently" list any successor (V-0) starts from.
**Grounding:** [`../../00_Context/CONSTRAINTS.md`](../../00_Context/CONSTRAINTS.md) (read first, always) ·
[`../../DESIGNPH-PLUS_PRD.md`](../../DESIGNPH-PLUS_PRD.md) ·
[`../RESULTS/PHASE-3_results.md`](../RESULTS/PHASE-3_results.md)

> Build a working, installable proof-of-concept: one menu item in SketchUp 2022 that reads a real
> designPH model and writes a **valid HBJSON plus a translation report** to disk. Purpose: learn what
> a real plugin entails, find the problems planning cannot, and produce something Ed can smoke-test
> by hand.

---

## 1. What the POC is — and is not

**Is:** the full designPH → HBJSON path, end to end, on real corpus models, honest about everything
it cannot translate. A `.rbz` Ed installs on his own machine (SketchUp 2022, macOS) and runs against
*copies* of corpus models.

**Is not — deliberately:**

| Not in the POC | Why |
|---|---|
| A release, or anything shared outside BLDGTYP | §2.3 — the AGPL question blocks *distribution*, not internal work |
| Windows (the OS) | No machine in this environment. Stays on the v1 register (Phase 3 gate is *pending-Windows*) |
| SketchUp versions other than 2022 / designPH other than 2.x | POC targets the one host we can test. Version gate refuses everything else |
| The shading-tag picker UI (PRD §7.2) | POC reports untagged geometry, exports none of it. The UI is a v1 problem |
| PHPP writing, mechanical data, authoring, multi-zone | PRD §5 non-goals, unchanged |
| UI polish | One menu item, one dialog, a verdict banner. Nothing more |

**POC ≠ v1.** v1 decisions the POC deliberately postpones: which SketchUp versions to support
(the Pyodide-ceiling question, PRD §7.4), the shading UI, Extension Warehouse packaging, the licence.
The POC's job is to make those decisions better-informed, not to take them.

## 2. The two standing assumptions (Ed, 2026-08-19)

Spike Phases 4 and 5 are **tabled**, not resolved. The POC proceeds on two working assumptions, both
recorded here so their risk stays visible:

1. **A designPH 2.x reader will translate to designPH 3.0 later.** ⛔ The 3.0 licence **cannot be
   bought yet** (Ed, 2026-08-21) — a procurement constraint, not a scheduling choice, so Phase 4 is
   blocked on something no amount of work here can unblock. Risk: the schema has already changed
   under us once (`*ID`/`*Auto`),
   and 3.0 is what the market runs. Mitigation: the read layer is one Ruby module behind one JSON
   contract (§5), so a 3.0 schema change is contained to POC-2's collector — the translator, runtime,
   and tests survive it.
2. **PHI will agree.** The PHI opener is not being sent yet (Phase 5 tabled). "PHI actively objects"
   remains the only existential risk (PRD §9). Mitigation: everything the POC reads is defensible
   (`DesignPH_dict` via Trimble's public API, hard rule 1 still absolute — no `.ppp` parsing), and
   nothing is distributed.

### 2.3 The AGPL position for the POC — working assumption, not legal advice

`planning/RESULTS/PHASE-3_licence-question.md` blocks **v1** on the AGPL question because v1 means
*distributing* a `.rbz` that vendors AGPL-3.0 code. AGPL obligations attach to conveying software and
to network interaction — not to private, internal use. **A POC built and run inside BLDGTYP, never
distributed, does not trigger them.** So: POC code may be written now; *release* stays blocked until
counsel answers. Consequences:

- The POC `.rbz` is **never** shared outside BLDGTYP — not to a friendly beta tester, not to PHI,
  not in a public repo. Sharing is the act that changes the legal footing.
- This repo stays private/local until the licence question is answered.
- Confirm this reading with counsel alongside the four questions already staged for them.

## 3. Architecture — decided, not open

The Phase 3 spike settled the runtime; the POC promotes that architecture, it does not revisit it.

```
Sketchup::Face / ::Edge / DC windows + DesignPH_dict        Ruby (POC-2 collector)
        │  walk, coalesce, transform, decode Marshal tables
        ▼
extraction JSON  ──────────────────────── the one seam ──── CONTRACT_extraction-json.md
        │  Ruby → HtmlDialog via execute_script (loopback-served page)
        ▼
Pyodide 0.24.1 · CPython 3.11 · 8 vendored wheels           Python (POC-3 translator)
        │  contract parse → typed records → honeybee Model
        ▼
HBJSON string + translation report JSON
        │  JS → Ruby via bridge callback
        ▼
<model>_export/<name>.hbjson + <name>.report.json           Ruby writes to disk (POC-4)
```

Fixed by Phases 0–3 (see `CONSTRAINTS.md` for the full list — every item below has evidence):

- **Pyodide 0.24.1 / CPython 3.11**, pinned by SketchUp 2022's Chromium 88.
- **Loopback HTTP server**, never `file://`. Worker thread + sleeping `UI.start_timer` pump.
- **Wheels installed by `zipfile` unpack**; `micropip` not shipped.
- **JSON strings across every hop** — no proxies, no Ruby objects.
- **Import `honeybee_ph` last** (the `_extend_` hooks).
- **Read-only** against `DesignPH_dict`; **never modify a corpus file** — copies only.
- **Report, don't guess** — every untranslatable entity named in the report.

## 4. Phases

| Plan | Builds | Depends on | Gate decides |
|---|---|---|---|
| [`POC-1_runtime-shell.md`](POC-1_runtime-shell.md) | Extension skeleton + loopback server + Pyodide boot, promoted from the Phase 3 spike | — | The shell is a stable base — boots in SketchUp, verdict banner, fixture HBJSON written |
| [`POC-2_ruby-collector.md`](POC-2_ruby-collector.md) | The read layer: faces, **edges**, windows, model tables → extraction JSON | — (its §1 *produces* the contract freeze) | Extraction matches the Phase 0/1 offline baselines, count for count |
| [`POC-3_python-translator.md`](POC-3_python-translator.md) | The translation core, developed and tested on native CPython 3.11 | 3a: nothing; 3b: POC-2's fixtures | Valid HBJSON + complete report from real fixtures; U-values check out |
| [`POC-4_integration.md`](POC-4_integration.md) | Wire collector → bridge → translator → disk, inside SketchUp | POC-1, -2, -3 | End-to-end run on Adelphi; SketchUp output byte-identical to CPython **for the same extraction** |
| [`POC-5_corpus-validation.md`](POC-5_corpus-validation.md) | Corpus sweep, schema validation, ph-navigator load, Ed's smoke-test runbook | POC-4 | The POC verdict, and the list of what v1 must do differently |

**Sequencing and the contract freeze (the order matters):** POC-1, POC-2 and POC-3 all start
immediately — the freeze is not a precondition for starting work. **POC-2 §1 is the pre-freeze
work**: one Ed session settles the contract's three §8 questions, and that session may move *only*
the contract fields §8 names (edge details, window panel/units). The contract freezes the moment
that session returns; POC-3 works on everything except aperture geometry until then. POC-3's gate
is split for the same reason: **POC-3a** (synthetic fixtures) closes independently; **POC-3b**
(real-fixture goldens, U-value regressions) closes only after POC-2 lands fixtures.

**The gate rule carries over:** do not start a dependent phase before its prerequisites' gates are
evaluated and recorded in [`RESULTS/`](RESULTS/) (`POC-N_results.md`, negative results included).

## 5. Where the code lives

```
poc/
  ext/
    dph_plus_poc.rb              SketchupExtension loader stub (only .rb in Plugins/ root)
    dph_plus_poc/
      main.rb                    menu, dialog lifecycle, bridge dispatch
      server.rb                  the loopback server, extracted whole from the spike
      collector.rb               POC-2 — the read layer
      html/                      dialog page + JS + translator entry
      vendor/                    Pyodide 0.24.1 + the 8 wheels (gitignored, regenerable)
  py/
    dph_translator/              POC-3 — the translation package (pure Python 3.11)
    tests/                       pytest; fixtures in tests/fixtures/
    .venv/                       uv venv, python 3.11 — matches Pyodide's CPython exactly
  tools/
    vendor_payload.py            ported from planning/spikes/pyodide/; also zips dph_translator
    build_rbz.py                 ported; builds poc/dist/dph_plus_poc.rbz; staleness-checks the zip
    verify_in_chrome.py          ported; drives the page in headless Chromium 88 (rev 827102)
  _private/                      real corpus extractions, fixtures, HBJSON outputs — CLIENT DATA,
                                 gitignored, manifest-tracked
  dist/                          built .rbz (gitignored; .venv/ and ext vendor/ gitignored too)
```

Naming: Ruby module `DphPlusPoc`, menu item under `Extensions` — distinct from both `designPH` and
the legacy `dPH+` extensions (PRD §12 collision note applies even to a POC on Ed's machine).

**One translator code path, three hosts.** The same `dph_translator` package runs under pytest on
CPython 3.11, in headless Chromium 88 via `verify_in_chrome.py`, and inside SketchUp — the Phase 3
method rule that made failures attributable. Never fork the logic per host.

## 6. What the POC translates

| designPH source | Target | Plan |
|---|---|---|
| Classified faces (coalesced `areaGroup`) | `Face` with mapped type, in one non-solid `Room` | POC-3 §3 |
| Face names (`descName` ‖ `descNameAuto`) | Face identifiers/display names | POC-3 §3 |
| Assemblies — tiers 1–2 + in-model `assemblies_ud` snapshot | `OpaqueConstruction` (tier 1) / no-mass (tier 2), tier recorded per face | POC-3 §5 |
| **Thermal bridges on edges** (groups 15/16/17 + `connections_ud`) | `PhThermalBridge` on the Room's PH building segment (`ph_bldg_segment.add_new_thermal_bridge`) | POC-3 §6 |
| Window DC instances + `glued_to` hosts | `Aperture`, projected to host plane; reveal into PH props | POC-3 §4 |
| TFA faces + `TFA_rf` + `vent_ud` | PH `Space`s from horizontal Floor faces; the rest **reported** | POC-3 §7 |
| `klima_ID` / `Klima_Standort` | Site identification on the model | POC-3 §8 |
| Everything else that carries designPH data | **The report** — named, counted, not guessed at | POC-3 §9 |

**Stretch (only if the phases above are green):** tier-3 assembly resolution against the installed
designPH CSV library; PHX `to_WUFI_XML`/`to_METr_JSON` demo from the produced HBJSON; the residential
program (PRD §8.4).

## 7. Definition of done — the POC verdict

The POC is done when, recorded in `RESULTS/POC-5_results.md`. ✅ **All six criteria closed
2026-08-21** — `RESULTS/POC-5_results.md` §1 is the item-by-item verdict:

| # | Criterion | State |
|---|---|---|
| 1 | **Adelphi COPY** exports end to end inside SketchUp: HBJSON on disk, **zero schema errors touching core geometry or PH**, report naming every untranslated entity | ✅ **done.** 82/82 faces, **46/46 apertures**, **368.476 m² TFA**, 324 KB, verdict `PASSED WITH OMISSIONS` — and the omissions are now genuine ones (40 TFA markers legitimately carry no assembly), not the missing apertures and TFA of the first run |
| 2 | The same HBJSON **loads and renders in ph-navigator** (PRD §11 criterion 2) | ✅ **done, in production ph-navigator** — with one named consumer-side exception: the viewer skips no-mass-construction faces (Finding 71, `RESULTS/POC-5_results.md` §3.2); Bluff Reach renders whole, apertures on hosts. Also loads/renders in **Rhino/Grasshopper** on an independent honeybee install (`HONEYBEE_STACK.md` §6.3) |
| 3 | **≥ 3 secondary corpus models** export cleanly, counts matching the Phase 0/1 baselines — must include `2414 Bluff Reach` **and** `250703 - Linde Residence` | ✅ **4 of 3**, both required models included. All five reconcile PASS; the translator emits **545/545 classified faces, 239/239 windows and 99/99 thermal bridges** across them |
| 4 | **U-values** check out — tier-2 on Adelphi (joined by **name**), tier-1 on `250703` | ✅ **both PASS.** Tier-2 pass-through exact (worst Δ 5.6e-17); tier-1 matches designPH's own U-/R-value calculator on 7 of 7 Linde assemblies, worst Δ **0.0005** against a ±0.005 tolerance. It took fixing two real defects to get there — `POC-3_results.md` §10.5 |
| 5 | Ed has run the smoke-test runbook and graded it | ✅ **done in substance** — nine graded sessions across POC-1/-2/-4 served as the smoke evidence and Ed closed the POC on them; the standing runbook (`RESULTS/POC-5_ed-smoke-runbook.md`) exists for every future build |
| 6 | A **"what v1 must do differently"** list exists — the POC's actual product | ✅ **assembled and ranked** — `RESULTS/POC-5_results.md` §4, every entry measured |

⚠ **Criterion 3 asked for "export cleanly", and all five do — but "cleanly" was the wrong bar and it
is worth saying why.** Every failing check in this phase came from the *harness*, not the models:
three of four captures failed reconciliation on checks that compared the wrong quantities, and the
data was right every time. A criterion phrased around the model's cleanliness cannot distinguish
"the model is bad" from "our check is wrong", and on this corpus the second was the answer in every
single case.

**Explicitly not a POC gate:** numerical agreement with PHPP beyond the U-value spot-checks; Windows;
performance beyond "the Phase 3 numbers did not regress".

## 8. Standing rules for the coding agent

All of `AGENTS.md`'s hard rules, plus:

- **Read `00_Context/CONSTRAINTS.md` before each phase.** It is one page and every line was paid for.
- **Corpus copies only.** Copy into `~/Desktop/dph_poc_copies/` (or similar) before any live run.
  Never open a corpus original in SketchUp for POC work.
- `ruby -c` every Ruby file before install; Ruby 2.7 syntax only.
- Translator targets **Python 3.11** exactly (Pyodide 0.24.1's CPython). Fully typed, dataclasses,
  pytest. No 3.12+ syntax.
- Everything captured from real corpus models — fixtures, extractions, HBJSON outputs, reports —
  lives under **`poc/_private/`** (gitignored): it is **client project data** and stays out of any
  repo that ever becomes public. Keep a manifest of which corpus model each file came from.
- **Division of labour:** the agent writes and tests everything it can offline (CPython, headless
  Chromium 88, offline baselines). Ed runs the SketchUp sessions from a runbook the agent stages —
  same pattern as Phases 1 and 3. Budget Ed round-trips: each phase names its Ed runs up front.
- When a POC finding contradicts `00_Context/` or the PRD, **update the document and mark what was
  superseded** — the docs-pass habit continues through implementation.
