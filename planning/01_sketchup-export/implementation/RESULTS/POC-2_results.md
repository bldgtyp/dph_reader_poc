# POC-2 — Ruby Collector — results

**Status: ✅ PASS — gate closed 2026-08-21. All five fixture models captured and reconciled,
contract frozen at v2, E-1 answered.** Runbook: [`POC-2_ed-runbook.md`](POC-2_ed-runbook.md).
**Date:** 2026-08-20, updated **2026-08-21** · **Plan:** [`../POC-2_ruby-collector.md`](../POC-2_ruby-collector.md)

---

## 0. The Adelphi capture, 2026-08-21

First live run of the collector against a real model. `Dph.here` on `adelphi-designph_COPY.skp`,
SketchUp 22.0.353, 3656 ms.

```
1023558 walked / 1441 tagged / 82 classified / 0 edges / 46 windows
tables: assemblies_ud, ihg_ud, tracker_data, vent_ud
```

`uv run pocs/01_sketchup-export/tools/check_extraction.py` → **PASS, 23 checks**, including:

| | |
|---|---|
| census invariant | 82 + 1359 == 1441 ✅ |
| live vs offline area-group carriers | **1441 vs 1441** — no historical-state gap at all on this model |
| classified faces | 82, exactly the baseline's non-bridge groups |
| windows | 46, **all 46 resolving via `glued_to`** — Phase 1's live finding reproduced |
| tables | `assemblies_ud`/`vent_ud`/`ihg_ud` present, `assemblies_calc`/`connections_ud`/`layer_table_*` correctly absent |
| both key generations on one face | 0 |

Fixture banked at `pocs/01_sketchup-export/_private/fixtures/` with `MANIFEST.md`.

**Three findings came out of the same run**, all now in `00_Context/`:

1. **`face.area` is net of glued window openings, and `face.loops` never shows them.** Exact
   16-of-16 match between "faces whose area disagreed with their own boundary" and "window host
   faces" — while only 2 of those 16 report an inner loop. `DESIGNPH_DATA_MODEL.md` §5.0.
2. **A recursive walk visits placements × faces** — 1,023,558 against ~8000 unique. §8.6.1.
3. **Contract W-1 and T-1 are answered; §4 needs three corrections.** See
   [`../CONTRACT_extraction-json.md`](../CONTRACT_extraction-json.md) §8.

### 0.1 All five captured — 2026-08-21

Two sessions, as budgeted. The first ran the v1 collector and produced the corrections in §0.2; the
second re-captured everything on the fixed, v2 collector.

| model | walked | tagged | classified | edges | windows | layer tables | payload |
|---|---|---|---|---|---|---|---|
| `adelphi-designph` | 1,023,558 | 1441 | **82** | 0 | 46 | 0 | 334 KB |
| `2414_Bluff Reach` | 2,556,183 | 576 | **194** | **99** | 40 | 6 | 406 KB |
| `2523 Wellington` | 424,555 | 449 | **103** | 0 | 57 | 5 | 321 KB |
| `250703 - Linde Residence` | 2466 | 2466 | **74** | 0 | 47 | **25** | 501 KB |
| `250708` | 2456 | 2456 | **92** | 0 | 49 | 0 | 472 KB |

`uv run pocs/01_sketchup-export/tools/check_extraction.py ~/Desktop/dph_poc_copies/*.extraction.json` → **5 of 5 PASS.**
Every classified-face count matches the offline baseline exactly, and every payload is under the
contract's 1 MB warn line (v1's Adelphi alone was 2.25 MB — see contract §5.1).

✅ **E-1 answered — and the answer matters.** All **99** of Bluff Reach's tagged edges are nested
**two levels deep**, in groups 15/16/17, every one with a resolvable `connection_ref`. A walk that
looked only at the top level would have found **zero of them**, silently. The recursive walk was
already right; now it is evidenced.

⚠ `faces_walked` is placements × faces and says almost nothing about a model's size: Linde walks
2466 and carries 25 layer tables, Bluff Reach walks 2.5 million and carries 6. Quote
`faces_tagged` or `faces_classified` to a human, never `faces_walked` (§8.6.1).

### 0.2 What the first capture session cost, and what it bought

The first session wrote three files, mis-filed one and lost one. **Every failure was in our tooling;
all five models' data was good.** Four separate defects, and the last two are the durable ones:

| | Defect | Consequence |
|---|---|---|
| 1 | ⚠ **`Sketchup::Model#path` is not the path of the file you opened** — on 2 of 5 it returned where the model was last saved *on somebody else's machine* | The capture was written to `model.path.sub(".skp", ".json")`, so a Windows path became one long filename in `~/Documents` and the other raised `ENOENT`. `SKETCHUP_RUNTIME.md` §8.2 |
| 2 | ⚠ **The COPIES-ONLY guard tested that same value** and silently failed open, then — widened — refused a legitimate copy | A negative test on an untrustworthy value is worthless in both directions. `here` now asks a *positive* question and hands the residue to the human |
| 3 | **The reconciler compared dict-carriers against area-group carriers** | Bluff Reach has 576 tagged faces and 194 with a group; 194 + 99 edges = 293 = the baseline, exactly |
| 4 | **The reconciler counted placements where the baseline counts entities** | `250708` ships 2456 records over 1781 ids; 1781 = the baseline, exactly |

Adelphi masked 3 and 4 completely — every one of its tagged faces has an area group, and none is
placed twice. **A reconciliation check confirmed on one model is confirmed on nothing.**

> `collector.rb` walks faces, **edges**, windows and Marshal tables into contract-v2 extraction
> JSON, and the offline suite holds it to every rule that would otherwise lose data silently. The
> reconciliation harness that grades a live capture is written and tested against the *real* Phase 0
> baseline. §0 above records what happened when both met a real model for the first time.

---

## 1. What was built

| File | What it does |
|---|---|
| `pocs/01_sketchup-export/ext/dph_plus_poc/collector.rb` | The read layer. One recursive walk → contract-**v2** extraction JSON |
| `pocs/01_sketchup-export/ext/tests/sketchup_stub.rb` | A stub SketchUp API — entities, `Geom::Transformation` as real 4×4 column-major maths, `UI` |
| `pocs/01_sketchup-export/ext/tests/test_collector.rb` | **77 checks** over that stub. The suite that keeps the Ed budget at two sessions |
| `pocs/01_sketchup-export/ext/tests/run_collector_console.rb` | `Dph.here` captures the open model **copy** and `Dph.status` says what is left; proves `model.modified?` never changed. ⚠ Batching is *not* the supported path — `Sketchup.open_file` does not switch documents on macOS (§8.1) — and ⚠ **the destination is never derived from `model.path`** (§8.2) |
| `pocs/01_sketchup-export/ext/tests/inspect_window_console.rb` | `DphWin.inspect_one` — dumps a window definition's nesting and its local/parent/world transforms. Written to answer W-1, which it did |
| `pocs/01_sketchup-export/tools/check_extraction.py` | Reconciles a capture against the Phase 0/1 offline baselines. **POC-2's gate, as a tool** |
| `pocs/01_sketchup-export/py/tests/test_check_extraction.py` | **21 tests** of that harness, against the real baseline and synthetic captures |

`main.rb` now calls the real collector; POC-1's stub is gone, and the stub extraction fixture
remains only as synthetic test scaffolding for the translator and the Chromium harness.

## 2. The reconciliation harness derives its expectations — it does not restate them

The plan quotes three numbers to check against: Adelphi's 82 classified faces, Bluff Reach's 293
area-group carriers of which 99 are edges, and Linde `250703`'s 25 layer tables. **All three fall
out of `planning/01_sketchup-export/feasibility/RESULTS/baselines/corpus_baseline.json` arithmetically**, so none of them is
written into the tool:

```
classified faces  = Σ offline records whose area group parses positive and is NOT 15/16/17
bridge edges      = Σ offline records whose area group IS 15/16/17
layer tables      = len(baseline["layer_tables"])
tables the model carries = baseline["model_keys"] ∩ the contract's shipped table list
```

Verified against the baseline: Adelphi (82, 0), Bluff Reach (194, 99) — 194 + 99 = 293 — Linde
`250703` 25 layer tables. And because it is derived rather than listed, **every corpus model checks
its own edge count**, not only the one somebody thought to hardcode: Holmes has 42 thermal bridges
of its own, and would now be caught by the same check.

The one number that *is* written down is Adelphi's **46 windows, 46 resolved by `glued_to`** —
because that came from Phase 1's *live* SketchUp run, not from the offline scan. An independent
observation belongs recorded; a second copy of the same measurement does not.

## 3. Verification — everything provable without SketchUp

`make ci`, green on 2026-08-20 and re-green on 2026-08-21 after §0.2's fixes. New in this phase:

| Suite | Result |
|---|---|
| `ruby ext/tests/test_collector.rb` | **77 checks**, all pass |
| `ruby ext/tests/test_static_server.rb` | 19 checks (collector checks moved out) |
| `pytest` | **165 passed** (21 of them the reconciliation harness) |
| `verify_in_chrome.py` on Chromium 88 | PASSED, cold start 3.2 s |
| `.rbz` / installed | 6.72 MB / 20.81 MB |

What those checks cover, and why each one exists:

| Area | The rule, and what breaks without it |
|---|---|
| Classification | By **value**, never by presence. `areaGroupID` is the String `'n'` on 1359 of Adelphi's 1441 faces; a presence filter ships all 1441 |
| The coalesce | `*ID` ‖ `*Auto` per pair, version-independent. ⚠ Includes a direct regression on **`areaGroupAuto`, not `areaGroupIDAuto`** — the Phase 3 spike's typo, masked on Adelphi, which would have lost `250708`'s 92 assemblies |
| Both generations | A pair with both values non-nil is named for the report rather than silently coalesced |
| Edges | Tagged edges collected, counted, `connection_ref` named apart from `assembly_ref`, length from **transformed** endpoints, anomalous groups still shipped |
| Transforms | Nested composition, scale reaching both geometry and area, mirroring flipping the winding, **no normal shipped** |
| Instancing | One definition placed twice → two records, two path-qualified ids, two world geometries |
| Windows | DC predicate not name-matching, internals **not** walked, `glued_to` hosts, raw per-field units, editor artefacts excluded, instance-over-definition, an unglued window reported rather than guessed. ⚠ `host_has_inner_loops` is shipped but is **not** a host test — a glued opening creates no loop (`DESIGNPH_DATA_MODEL.md` §5.0) |
| Tables | `:TOKENS` at the start **and at the end** (`vent_ud` is a flat array), metadata stripped, symbols → strings, values untouched, `layer_table_*` matched as a family, unconsumed blobs listed not shipped, non-blob keys not mistaken for tables, an undecodable blob shipped as an error |
| Census | `faces_walked` / `faces_tagged` / the contract §6.1 invariant |

⚠ **None of it is evidence about designPH.** The trees are hand-built, and *a synthetic model is
not evidence about real models* — a six-face model already produced one confidently wrong schema
rule on this project. The offline suite proves the collector obeys the rules it was told; the
corpus reconciliation is what proves the rules are the right ones, and that needs Ed.

## 4. Decisions taken while writing it

| Decision | Why |
|---|---|
| ~~`panel_outer_loop` from the **definition's largest face**~~ | ⚠ **SUPERSEDED 2026-08-21.** It was one of contract §4's two candidates and had to be implemented to be testable. It is refused twice over: the definition has no top-level faces at all, and the largest face at any depth is the **glazing**, 41 % smaller than the rough opening. Contract §8.1 |
| `designph_versions` ships the live stamp only | The contract's example shows Wellington's two. Those are visible to the **offline binary reader**, which sees historical state; the live API returns one. Shipping one and saying so beats shipping a shape we cannot fill |
| `dynamic_attributes` is an **allow-list** | The DC dictionary also carries `_lenx_formulaunits`, `_name_label` and a dozen editor artefacts. "Raw passthrough of the designPH-relevant subset" needs a definition of *relevant*. ⚠ The list widened in v2 and then **shed the two option-list keys to model level** — they are library data, and per-window they cost 2.07 MB of a 2.25 MB payload (contract §5.1) |
| ~~The model's name comes from `model.path`~~ | ⚠ **SUPERSEDED 2026-08-21.** It is the last-*saved* path, so Wellington's capture came out named `2523 Weiilington` — a typo from another machine — and Linde's carried a whole `C:\Users\greg\…` path. `Collector.extract` now takes the name the caller asserts (§8.2) |
| Instance values fall back to the **definition** | designPH puts per-window values on instances and the shared template on the definition (`DESIGNPH_DATA_MODEL.md` §8.2). Reading only one gives wrong answers |
| `Marshal.load` used directly, with a v1 note in the code | Acceptable on BLDGTYP's own corpus. The comment names the port of `ruby_marshal.py`'s construct-nothing reader as the thing to do **before v1 ever opens a stranger's file** |

## 5. Findings

| # | Finding | Consequence |
|---|---|---|
| 50 | **The Phase 3 spike's coalesce read a key that does not exist.** It wrote `areaGroupID \|\| areaGroupIDAuto`; the real fallback is **`areaGroupAuto`**, no "ID" — while `assemblyIDAuto` *does* carry it. The asymmetry is designPH's | Masked on Adelphi, where every classified face carries `areaGroupID`. It would have read zero area groups off `250708`. The plan flagged it; the offline suite now regresses it directly |
| 51 | **The offline baseline can derive every count the plan quotes**, per model, for all 14 — including the split between face groups and thermal-bridge groups | Turned three hardcoded model expectations into one rule. Holmes's 42 bridges are now checked by the same code that checks Bluff Reach's 99, and nobody had to notice Holmes |
| 52 | **A stub `Geom::Transformation` has to be real 4×4 column-major arithmetic to be worth anything.** Anything less would pass a scaled-group test without composing anything | It is ~40 lines and it is what makes "nested transforms compose" a real assertion rather than a tautology |
| 66 | ⚠ **`Sketchup::Model#path` returns where the model was last SAVED, not the file you opened.** On 2 of 5 copies it named another machine — `/Users/johnmitchell/…/2523 Weiilington.skp`, `C:\Users\greg\OneDrive\…`. Both strings are embedded verbatim in the `.skp`'s `model.dat`, alongside the source path of every imported component | Never derive an output path from it, never name a fixture from it, and **never build a guard on it**. The two affected models are the two last saved by SketchUp 24+/26 against 22–23 for the rest — a correlation on n=5, not a mechanism. `SKETCHUP_RUNTIME.md` §8.2 |
| 67 | ⚠ **A negative test on an untrustworthy value fails in both directions, and both happened within one hour.** Matching this machine's `~/Dropbox` let the stale `/Users/johnmitchell/Dropbox/…` through; widening it to `/Dropbox/` for any user then refused a legitimate copy on the Desktop | Ask a **positive** question — *is this verifiably the file I expect?* — and hand the residue to the human, who has the fact the API does not. `Dph.here("<name>")` |
| 68 | **The offline baseline counts ENTITIES carrying an AREA-GROUP key; a live walk counts PLACEMENTS of everything carrying a `DesignPH_dict`.** Two independent mismatches, each exactly explaining one failing model: 576 dict-carriers vs 194 group-carriers on Bluff Reach (194 + 99 = 293 = baseline), and 2456 placements over 1781 entities on `250708` (1781 = baseline) | Compare like with like, and **deduplicate by the persistent id at the tail of the path-qualified id**. Adelphi masked both, having neither property |
| 69 | **`descName` + `descNameAuto` on one face is an override pair, not a contradiction.** 70 Bluff Reach faces carry both, with real room names ("104C HALL", "100 FOYER") | Hard rule 6's *rule* (coalesce, user wins) was always right; its *claim* of mutual exclusivity holds only for `areaGroup`/`tempZone`/`assembly` — 0 faces corpus-wide — and was never true of the name pair |
| 70 | **The `.skp` is a zip, so a raw byte scan of the file finds nothing.** Searching for the embedded paths in the container returned no hits; they are in `model.dat` inside it | `skp_attr_dump.read_model_dat` already knew this. A grep over the raw `.skp` is a *negative* result that means nothing |

## 6. Gate

POC-2 §7's PASS clause: *offline suite green; reconciliation green for the five fixture models;
every contract field populated or explicitly null; no write to any model; real fixtures landed with
manifest.*

| Clause | State |
|---|---|
| Offline suite green | ✅ 61 Ruby checks + 16 harness tests |
| Every contract field populated or explicitly null | ✅ asserted on an empty model and on a full one |
| No write to any model | ✅ structurally (nothing calls a setter); the console run **asserts** `model.modified?` across the sweep |
| Reconciliation green for the five fixture models | ✅ **5 of 5** |
| Real fixtures landed in `pocs/01_sketchup-export/_private/` with a manifest | ✅ all five, `MANIFEST.md` current |
| Contract §8's three questions settled, contract frozen | ✅ W-1, T-1 and **E-1** answered; frozen at **v2** |

**Verdict: ✅ PASS.**

⚠ **But read §0.2 before trusting this gate's shape.** The offline suite was green throughout, and
the first real session still found four defects it could not have caught — two *design* errors in
the contract (the window rectangle rule, the local-vs-world transform) and two in the reconciler
itself. The house rule earning its keep: a synthetic model is not evidence about real models, and a
check validated on one model is validated on nothing.

Two of those were found by the harness *disagreeing with correct data*, which is the failure mode to
expect next time: when a check fires on three of four real captures, suspect the check.

## 7. Out of scope, unchanged

Type normalisation, classification decisions, geometry maths beyond transforms (all POC-3);
unclassified-face *export*; any UI; writing `DesignPHPlus_dict` (v2).
