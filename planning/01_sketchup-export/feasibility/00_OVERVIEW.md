# DesignPH-PLUS — Phased Spike Plan

**Purpose:** de-risk the [PRD](../../../DESIGNPH-PLUS_PRD.md) before any production code, one phase at a
time, with an explicit evaluation gate after each. Written for handoff to an implementation agent.

**Rule: do not start a phase until the previous phase's gate has been evaluated and recorded.**
The point of this sequence is to stop early if something fails, not to complete all six.

---

## Where we are

| Phase | State |
|---|---|
| 0 | ✅ **complete 2026-08-19** — [results](RESULTS/PHASE-0_results.md) |
| 1 | ✅ **complete 2026-08-19 — PASS WITH CHANGES** — [results](RESULTS/PHASE-1_results.md) |
| 2 | ✅ **complete 2026-08-19 — PASS WITH CHANGES** — [results](RESULTS/PHASE-2_results.md) |
| 3 | ✅ **complete 2026-08-19 — PASS WITH CHANGES (pending Windows)** — [results](RESULTS/PHASE-3_results.md). Pyodide adopted. Real honeybee runs inside `HtmlDialog`; 82/82 Adelphi faces → HBJSON on disk |
| 4 | ⏸ **tabled** (Ed, 2026-08-19) — the designPH 3.0 licence is not being ordered yet. POC work proceeds on the working assumption that a 2.x reader translates to 3.0 later |
| 5 | ⏸ **tabled** (Ed, 2026-08-19) — the PHI opener is not being sent yet. POC work proceeds on the working assumption that PHI will agree |

**2026-08-19 — the plan moves to POC implementation planning.** With Phases 0–3 closed and Phases
4–5 tabled, the work moved to [`../implementation/`](../implementation/.index.md) — phased implementation plans for a
proof-of-concept that exercises the full designPH → HBJSON path. The two tabled phases stay on the
risk register; their assumptions and unwind cost are recorded in
[`../implementation/00_POC_OVERVIEW.md`](../implementation/00_POC_OVERVIEW.md) §2.

✅ **2026-08-21 — the POC is complete** (all five POC phases PASS; Ed closed it). Its unwind check
([`../implementation/RESULTS/POC-5_results.md`](../implementation/RESULTS/POC-5_results.md) §6) confirms neither tabled phase
got more expensive: the collector is still the blast radius for designPH 3.0, and nothing was
distributed or `.ppp`-parsed that would change the PHI conversation. Phases 4 and 5 remain the
next *external* moves whenever a V-0 is taken up.

✅ **The `*ID`/`*Auto` question is settled** (`00_Context/DESIGNPH_DATA_MODEL.md` §6.5). The two are
**mutually exclusive per face** across all 14 corpus models, so the rule is a *coalesce* — read
`*ID`, fall back to `*Auto` — and there is no precedence to resolve. Both earlier candidate rules
were wrong: the version rule (Phase 0) and "prefer `*ID`" (which would lose 301 faces, including
every assembly in `250708.skp`).

⚠ **Two Phase 1 refutations change the build, not just the record.** Thermal bridges are attached to
**`Sketchup::Edge`**, so a face-only reader loses all of them silently (PRD §8.3). And **shading
geometry has come back out of v1 scope** — no heuristic separates exterior context from interior
clutter, so v1 will ask the user which SketchUp tags are shading rather than guess (PRD §7.2).

✅ **Window hosting passed**: `glued_to` resolves 46 of 46. But `cuts_opening?` is a component
*definition* capability, not a statement about the host — only 1 of 16 host faces actually has holes.

⚠ **`file://` is a dead end, and the runtime architecture moves to a loopback server.** Phase 3
found that stock Chromium refuses `fetch`, `XMLHttpRequest` *and* the dynamic `import()` Pyodide
needs, all under one CORS rule — and that no JS shim can rescue it, because a module import is not
interceptable. The same tree served from `http://127.0.0.1` works first try, and is the only strategy
that can set the COOP/COEP headers `SharedArrayBuffer` would need. The spike extension implements
both and reports which one `HtmlDialog` accepts.

✅ **The stack runs in Chromium, fast enough and small enough.** Cold start to `import honeybee_ph`
is **2.3 s**; the `.rbz` is **8.07 MB** (15.3 MB installed); exporting a 1441-face model costs
**187 ms**. Pyodide is a consistent **~2× slower than native CPython**, not the order of magnitude
that would have killed it, and the HBJSON it writes is byte-identical.

✅ **The Python stack is pure enough, and further than expected.** Phase 3 vendors **8 wheels,
1.5 MB**, installed `deps=False` — `honeybee-core` *declares* `honeybee-schema`/`pydantic` but
nothing outside `cli/` imports them. And **PHX's write path is pure too**: HBJSON → `PhxProject` →
WUFI-Passive XML *and* METr JSON runs with `lxml`, `xlwings`, `pydantic` and `rich` all absent,
overturning the plan's "Phase 3 targets honeybee-ph only". Only PHPP writing is genuinely blocked, by
`xlwings`' need for a live Excel — and §5 excludes it anyway.

---

## Sequencing

Phases are ordered by **cost × decisiveness**, not by the PRD's S-numbers. Cheap facts that could
invalidate expensive work come first.

| Phase | Spike | Question | Box | Gate decides |
|---|---|---|---|---|
| [0](PHASE-0_setup-and-long-leads.md) | — | Harness, corpus, and the baselines everything else diffs against | 2 h | Nothing — enables everything |
| [1](PHASE-1_read-side-facts.md) | S2, S3 | Can we read designPH faces and windows correctly? | 4 h | Whether the read layer is buildable as specced |
| [2](PHASE-2_python-purity-audit.md) | S5 | Is the full Python stack pure? | 1 h | **Scope of Phase 3** — go/no-go on Pyodide |
| [3](PHASE-3_pyodide-spike.md) | S1 | Does real honeybee run inside SketchUp? | 2 d | **The runtime architecture.** The big one |
| [4](PHASE-4_designph-3-compat.md) | S4 | Does designPH 3.0 break our reader? | 1 d + 1–3 wk wait | Whether v1 can serve the actual market |
| [5](PHASE-5_phi-and-licence.md) | S6 | Is PHI on side? What licence do we ship? | weeks | v2 scope; the only existential risk |

**Long-lead items — deferred to their own phases (Ed, 2026-08-19).** The original plan started both
in Phase 0 to run their multi-week latency in the background. Ed has moved the designPH 3.0 purchase
to the **start of Phase 4** and the PHI conversation to the **start of Phase 5**; work proceeds up to
those two boundaries.

**The tradeoff, stated once so it is not rediscovered as a surprise:** that latency is now on the
critical path rather than in the background. Phase 4 cannot begin its work until the licence arrives
(realistically 1–3 weeks after ordering), and Phase 5's gate cannot close until PHI replies. Both are
fully staged in [`RESULTS/PHASE-0_long-lead-staging.md`](RESULTS/PHASE-0_long-lead-staging.md), so
each phase opens by firing its half — nothing needs drafting at that point.

```
Phase 0 ── Phase 1 ── Phase 2 ── Phase 3 ──► build v1
                                     (gate)

Phase 4:  order dPH 3.0 ──(1-3 wk wait)──► compatibility testing
Phase 5:  send PHI opener ──(reply)──────► the conversation, then the licence decision
```

## Evaluation protocol

After every phase, before starting the next:

1. Write findings into `planning/01_sketchup-export/feasibility/RESULTS/PHASE-N_results.md` — **including negative results.**
2. Answer the phase's gate question with one of: **PASS**, **PASS WITH CHANGES**, **FAIL**.
3. If PASS WITH CHANGES or FAIL, update the [PRD](../../../DESIGNPH-PLUS_PRD.md) and
   [`00_Context/`](../../../00_Context/) *before* continuing. The record staying honest is the point.
4. Stop and report to Ed. Do not roll into the next phase unattended.

## Standing rules for the implementation agent

- **Read-only against designPH data.** Never write to `DesignPH_dict`. Never save over a corpus model.
- **SketchUp 2022 ships Ruby 2.7.** No endless methods (`def x = y`), no pattern matching, no
  `Hash#except`. Syntax-check every SketchUp file with `ruby -c` before installing it.
- **Python scratch scripts use PEP 723 + `uv run`.** No `.venv` inside any tool folder.
- **Type-check every attribute read.** `areaGroupID` is a String on most faces in a real model
  (see `00_Context/DESIGNPH_DATA_MODEL.md` §5.4). Assume nothing about type.
- **Report, don't guess.** Any face or window that cannot be translated gets named in a report.
  Silent loss is the failure mode that would most damage this tool.
- Existing tools: `00_Context/tools/skp_attr_dump.py` (offline reader) and the **BT Attribute
  Inspector** at `~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/bt_inspector/`
  (live, in-SketchUp).

## Division of labour — agent vs Ed

This plan is executed by a coding agent working in this environment, with Ed in the loop for the
steps a machine cannot do. For every **[Ed]** task the agent's job is to *stage* it — draft the
email, write the console script, name the model and the expected observation — not to wait on it.

| Needs Ed | Where |
|---|---|
| Purchase the designPH 3.0 licence | Phase 4 §4.0 *(staged in Phase 0; deferred by Ed)* |
| Send the PHI opener | Phase 5 §5.0 *(staged in Phase 0; deferred by Ed)* |
| Any step that clicks the designPH UI (change an area group, re-classify a face) | Phase 1 §1.1, Phase 4 §4.2–4.3 |
| Running Ruby in the SketchUp console / installing spike extensions — agent writes the code, Ed runs it and pastes results back | Phases 1, 3, 4 |
| Windows-platform testing (no Windows machine in this environment) | Phase 3 step 5 |
| The PHI meeting itself; counsel questions | Phase 5 |

Everything else — offline `.skp` dumps, dependency audits, HBJSON validation, PHPP extraction,
diffing, writing results files — is agent-runnable here without assistance.

## Regression corpus

Primary reference set at [`../../../corpus/adelphi`](../../../corpus/adelphi) — the same
building in six formats:

| File | Use |
|---|---|
| `adelphi-designph.skp` | **Primary input.** designPH 2.1.15. 1441 faces carry `DesignPH_dict`; only **82** are classified |
| `adelphi-designph_PHPP10.ppp` | Reference *only* — do not parse (licence §2.4(a)). Read by eye to check expectations ⚠ Exported by designPH **2.4.0 BETA PRO** while the `.skp` beside it is **2.1.15** — not two views of one tool |
| `adelphi-phpp.xlsm` | Ground truth for U-values, areas, TFA |
| `adelphi-honeybee-json.hbjson` | **Reference output.** honeybee schema 1.53.1 — 6 rooms, 52 faces, 44 apertures, 38 spaces, 56 constructions, 1287 orphaned shades |
| `adelphi-rhino.3dm`, `adelphi-grasshopper.gh` | The Rhino-route equivalent, for comparison |

⚠ **The reference HBJSON is a *shape* reference, not a target to match.** It came from the Rhino
route and has **6 solid Rooms with solved interior adjacency** (15 Adiabatic, 10 Surface boundary
conditions). v1 produces **one non-solid Room** by design (PRD §8.1). Use it to check that our output
is well-formed and plausibly populated — never to assert equality.

⚠ **The files are known to be only approximately aligned.** Use them for shape and sanity, not for
exact numerical agreement, and never let a mismatch here alone condemn the translator.

Secondary corpus — real project models spanning designPH versions. **Verified on disk 2026-08-19;
supersedes an earlier list that named four projects (High Street, Arrowhead Ridge, Ikon Optima Plus,
415 Flint) whose `08_DesignPH` folders turned out to hold no model at all.** The glob
`~/Dropbox/bldgtyp/*/08_DesignPH/*.skp` finds exactly these five projects:

| Model | designPH version stamp(s) |
|---|---|
| `~/Dropbox/bldgtyp/2523 Wellington/08_DesignPH/2523 Wellington.skp` | `2.1.10` **and** `2.2.29` — both key generations, never purged |
| `~/Dropbox/bldgtyp/2524_Linde_Residence/08_DesignPH/250708.skp` | `2.1.15` |
| `~/Dropbox/bldgtyp/2524_Linde_Residence/08_DesignPH/250703 - Linde Residence.skp` | `2.2.29` — **a separate, later model, not a backup** |
| `~/Dropbox/bldgtyp/2414 Bluff Reach/08_DesignPH/2414_Bluff Reach.skp` | `2.2.24` |
| `~/Dropbox/bldgtyp/2605 MacDonough/08_DesignPH/2605 MacDonough.skp` | `2.2.29` |
| `~/Dropbox/bldgtyp/2536 Holmes Residence/08_DesignPH/2536 Holmes.skp` | `2.2.29` |

Each has a `~.skp` backup beside it — include the backups in baselines (a `~.skp` backup is what
cracked the version rule in the first place). No real project on disk is stamped 2.4; the only
2.4.0 BETA sample is `corpus/synthetic/designph_test.skp`.

**Corrections from the Phase 0 baseline (2026-08-19):** the glob resolves to **11 files across five
projects**, not the ten implied above. `250703 - Linde Residence.skp` is a *third* Linde model, not a
backup of `250708.skp`, and is the corpus's richest model-level sample (25 `layer_table_*` keys, 47
distinct keys). Wellington's backup is on disk as `2523 Weiilington~.skp` — a filename typo, not a
different model. All 14 corpus models are baselined in
[`RESULTS/PHASE-0_corpus-baseline.md`](RESULTS/PHASE-0_corpus-baseline.md).

## What is deliberately *not* in this plan

No production code. No UI. No mechanical data model. No PHPP writing. Phases 0–3 exist to answer
"can this be built as specced"; only after Phase 3's gate does v1 implementation begin.
