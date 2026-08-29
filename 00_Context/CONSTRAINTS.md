# Constraints — the things that will stop you

Every hard limit, blocker, and non-negotiable rule found across spike Phases 0–3 **and the
complete POC (closed PASS, 2026-08-21)**, with a pointer to the evidence. **Read this before
planning any development work** — a future V-0 included; the detail lives in the other
`00_Context/` documents, and the ranked list of what a v1 must do differently is
`planning/POC/RESULTS/POC-5_results.md` §4.

⚠ It is no longer one page. That is deliberate: running the pipeline against real models roughly
doubled the list, and every addition is something that was *measured* rather than reasoned about.
§8.1 is the fastest way in — what the corpus settled, and what it left open.

**Evidence base:** five real projects (designPH 2.1.15–2.2.29, SketchUp 22–26) captured live and
reconciled against an offline scan of all 14 corpus files — 545 classified faces, 239 windows, 99
thermal bridges, all four assembly tiers, with designPH's own U-/R-value calculator and the PHPP as
arithmetic ground truth. ▶ **Extended 2026-08-29 by the HEADLESS phase**: the same five models plus
eleven more (16 in total, designPH **1.0.30 → 2.4.0 BETA**, including a **146 MB** model and a
second thermal-bridge project) read again through the **SketchUp C SDK with no SketchUp installed**
— which both re-confirmed every §4 rule independently and added a route with its own constraints
(§0).

Legend: 🔴 blocker · 🟠 constraint you must design around · 🔵 rule with a known correct answer

---

## 0. ⚠ There are now TWO routes, and most of this document is about one of them

Everything below §1 was written for the **extension route** — code running *inside* SketchUp, in
Ruby and in Pyodide inside an `HtmlDialog`. Since 2026-08-29 a second route is proven: a
**headless C-SDK reader**, a plain CPython process with no SketchUp installed and no SketchUp seat
([`HEADLESS_VIABILITY.md`](HEADLESS_VIABILITY.md), `planning/HEADLESS/`).

⚠ **Applying the wrong route's constraints is the mistake this section exists to prevent.** They
are very different, and the headless one is *far* less constrained technically and *equally*
constrained legally.

| Constraint | Extension route | Headless C-SDK route |
|---|---|---|
| §2 Pyodide 0.24.1 ceiling, set by the oldest SketchUp's Chromium | 🔴 hard | ✅ **does not exist** — full modern CPython |
| §2 15.3 MB install footprint, 2.6 s boot | 🟠 | ✅ does not exist |
| §2/§4 the 4 MB `HtmlDialog` bridge | 🟠 | ✅ does not exist |
| §3 threading — the worker/`UI.start_timer` dance that hangs SketchUp | 🔴 | ✅ does not exist |
| §3 `file://` cannot fetch its own assets | 🔴 | ✅ does not exist |
| §4 the designPH read rules (coalesce, `glued_to`, edges, area semantics…) | 🔵 | 🔵 **identical — same rules, same traps, verified byte-for-byte** |
| §5 the honeybee stack and its eight wheels | 🟠 | ✅ relaxed — no purity requirement, real pydantic available |
| §1 the AGPL question · the designPH 3.0 licence · the PHI conversation | 🔴 | 🔴 **unchanged, and AGPL §13 becomes *more* urgent** — a server-side path is what triggers it |
| **SDK availability** (Request Access form, no public download) | n/a | 🔴 **new blocker, and it gates the EULA too** |
| **Reading mutates the in-memory model** | n/a | 🔴 **new** — "never save an opened model" is load-bearing |
| **Memory ratchets and never falls** | n/a | 🟠 **new** — size or recycle the worker |
| **`entity_id` is process-scoped** | n/a | 🟠 **new** — a watcher cannot hash the capture to detect change |

**Where to read the headless route's own limits:** [`HEADLESS_VIABILITY.md`](HEADLESS_VIABILITY.md)
§3 (limits and pitfalls) and §5 (what it means for the product);
[`SDK_RUNTIME.md`](SDK_RUNTIME.md) §1 (availability) and §4 (the five traps).

★ **The one thing both routes share completely is §4** — everything this project learned about
*reading designPH data* transferred to the C SDK unchanged, and was then verified at the byte level:
a headless capture matches the live SketchUp capture with **0 unexplained differences on 5 real
models**, worst geometry deviation **0.000000 mm**. The designPH knowledge is route-independent. The
runtime knowledge is not.

---

## 1. Legal and licensing

| | Constraint | Evidence |
|---|---|---|
| 🔴 | **Never parse the `.ppp`.** Licence §2.4(a) names file formats explicitly. Reading by eye is fine | [`PPP_EXPORT.md`](PPP_EXPORT.md) |
| 🔴 | **The AGPL question is unresolved and blocks v1 / any distribution.** Vendoring honeybee (AGPL-3.0) is now a decision, not a possibility. *(2026-08-19, Ed: internal, never-distributed POC work proceeds — AGPL obligations attach to conveying, not private use; working assumption, for counsel. `planning/POC/00_POC_OVERVIEW.md` §2.3)* | `planning/RESULTS/PHASE-3_licence-question.md` |
| 🟠 | Exposure is entirely **Ladybug Tools'** code. `honeybee-ph` and `ph-units` are BLDGTYP's own copyright | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §8 |
| 🟠 | **"PHI actively objects" is the only true deal-breaker** in the plan. Every technical obstacle so far has a workaround; that one does not | PRD §9 |
| 🔵 | Reading `DesignPH_dict` is defensible: the user's own `.skp`, Trimble's public API | PRD §9 |
| 🟠 | ⚠ **Every designPH `.skp` carries personal data, by two independent routes**: absolute filesystem paths from imported components and the save location, and `tracker_data` — designPH's own analytics table, which logs each calculation run with a **username**, a timestamp and the build (188 rows on one corpus model). Not our defect; entirely our problem the moment a model, an extraction or a report is shared. **Never ship `tracker_data`**, and strip both before corpus data leaves the repo | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §7.0.2, [`DESIGNPH_FILE_FORMATS.md`](DESIGNPH_FILE_FORMATS.md) §4.5 |
| 🔵 | `ph-units` publishes **no licence metadata**. Fix regardless of the legal outcome | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §8 |

## 2. The runtime

| | Constraint | Evidence |
|---|---|---|
| 🔴 | **SketchUp 2022 is Chromium 88.** Pyodide is capped at **0.24.1 / CPython 3.11**. 0.25+ will not run | [`PYODIDE_RUNTIME.md`](PYODIDE_RUNTIME.md) §2 |
| 🔴 | **The oldest SketchUp supported sets the newest Pyodide available.** PRD §7.4's floor is a technical ceiling | PRD §7.1, §7.4 |
| 🔴 | **`file://` cannot work.** `fetch`, `XHR` *and* dynamic `import()` are refused; no shim reaches the third. Confirmed inside SketchUp | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §4.3 |
| 🟠 | Therefore the extension **runs a loopback HTTP server** for the dialog's lifetime | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §4.4 |
| 🟠 | **PHPP writing is permanently blocked** — `xlwings` needs a live Excel. Runtime blocker, not install | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §7 |
| 🔵 | `pyodide-core` ships **no packages**. Install by `zipfile` unpack; **do not ship `micropip`** (release-coupled, fails on 0.24.1) | [`PYODIDE_RUNTIME.md`](PYODIDE_RUNTIME.md) §4 |
| 🔵 | Ruby is **2.7**, pinned to the SketchUp release. `ruby -c` every file | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §2 |

## 3. Threading and I/O — each of these hangs SketchUp

| | Constraint | Evidence |
|---|---|---|
| 🔴 | **A Ruby `Thread` never runs on its own.** The VM is scheduled only while Ruby executes. The socket still *binds*, so the symptom is silence | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §5 |
| 🔴 | **Blocking I/O on the main thread deadlocks CEF.** It needs that thread to drain the socket you are blocked writing to | same |
| 🔵 | The working shape: worker thread for all blocking work **plus** a `UI.start_timer` that only `sleep`s, to release the GVL | same |
| 🔵 | Workers must never touch the SketchUp API, **`puts` included**. Queue and flush from the timer | same |
| 🔵 | Flush the queue **before** killing the timer, or you lose the error explaining the failure | same |
| 🔵 | Never trigger `alert`/`confirm`/`prompt` in an `HtmlDialog` — it blocks all further events | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §10 |
| 🔵 | **`UI.messagebox` blanks the dialog while it is up** — CEF cannot repaint from a blocked main thread. Alarming, not a defect | same |
| 🟠 | **No progress indicator can update during main-thread work** — not the status bar, not the dialog. Measured: a 10.9 s walk showed the user *nothing*, with `status_text` written correctly throughout. It is hard rule 9 from the UI side. ⚠ And a stub has no screen, so an offline suite can only assert the string was **set** — which is not the same claim. Fix is structural: chunk the work across `UI.start_timer` | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §5 rule 3 |
| 🔴 | **`Sketchup::Model#path` is NOT the path of the file you opened.** On 2 of 5 corpus copies it returned the location the model was last saved to on *someone else's* machine — a Windows path among them. Never derive an output path from it, and never build a guard on it: the COPIES-ONLY check silently failed open | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §8.2 |
| 🔴 | **macOS: `Sketchup.open_file` opens a NEW WINDOW**, and `active_model` follows the frontmost. A batch loop writes N files all containing the *first* model's data, silently. Collect what is open, or verify the path changed and stop | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §8.1 |

## 4. Reading the model

| | Constraint | Evidence |
|---|---|---|
| 🔴 | **Thermal bridges are on `Sketchup::Edge`.** A face-only reader loses all of them silently — 99 of 293 tagged entities on a real project | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §5, §7.1 |
| 🔴 | **Coalesce `*ID` / `*Auto`; never version-key.** They are mutually exclusive per face, and both hold real data regardless of the version stamp | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §6.5 |
| 🔴 | **Type-check every attribute read.** `areaGroupID` is a `String` on 1359 of 1441 faces | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §5.4 |
| 🔴 | **A multi-section assembly's U-value is ISO 6946's MEAN OF TWO LIMITS**, not an area-weighted lambda — and `surf2_percentage` is a **percentage**, so `0.0625` means 0.06 % framing, not 6 %. Getting either wrong is silent and flattering: 8 % low on Linde's `06ud` | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §7.2 |
| 🟠 | **designPH's assembly U-value INCLUDES the films; honeybee's `u_value` does not.** Worth 0.004–0.005 W/m²K — enough on its own to fail a ±0.005 regression | same |
| 🟠 | **Assemblies do not always carry a build-up** — 254 of 532 corpus references do. The rest resolve only against designPH's *installed* CSV library, outside the model | `planning/RESULTS/PHASE-1_assembly-resolution.md` |
| 🟠 | **Only 82 of 1441 tagged faces on Adelphi are classified**, out of ~8037 live faces. The unclassified majority is the design problem, not an edge case | §7 below |
| 🔵 | Internal units are **always inches**. `× 0.0254` | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §2.2 |
| 🔵 | Carry the accumulated `Geom::Transformation` through groups and components | same |
| 🔵 | `attribute_dictionaries` returns **`nil`**, not empty | [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §7 |
| 🔴 | **`glued_to` is the ONLY thing that identifies a window host.** `cuts_opening?` is a definition capability (true on all 46); `loops.size > 1` is about *modelled* holes and is true on only **1 of 16** real Adelphi hosts — **1 of 81** across all five captured models (remeasured from the captures 2026-08-28; this table said 2) | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §5.0 |
| 🔴 | **`face.area` is NET of glued window openings; a polygon from the loops is GROSS.** They differ on exactly the 16 host faces, by exactly the window areas. Ship the loops — honeybee and PHPP both subtract apertures themselves | same |
| 🔴 | **A window definition has NO faces at its top level** — `grep(Sketchup::Face)` returns `[]` on all 46. Walk definitions recursively | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §9.1 |
| 🔴 | **The aperture rectangle is `lenx × leny` (rough opening) from the definition origin, `+x`/`+y`, through the WORLD transform.** The definition's largest face is the **glazing** — 41 % too small, and plausibly so. `dynamic_attributes["area"]` is a **stale DC output**, right on only 20 of 46. The corner convention is *measured*: 46/46 land inside their host, against 23 centred | same, §9.1–9.2 |
| 🔴 | **`ComponentInstance#transformation` is PARENT-relative**, while every other geometry field is world. Mixing them put Adelphi's windows **1.2–3.3 m** off their hosts — and **projection onto the host plane absorbs it silently**, so carry an off-plane limit as the tripwire | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §9.3 |
| 🟠 | **A recursive walk visits placements × faces** — Adelphi: **1,023,558** against ~8000 unique, ~3.7 s. Correct, but do not show that number to a user unqualified | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §8.6.1 |
| 🟠 | **Real models contain degenerate geometry, and more of it than one pass finds** — Adelphi's 82 classified faces hold **8** with a sub-mm edge and **7** whose boundary revisits a point (one revisits 21). ⚠ Every edge of a spur is *long*, so a short-edge test misses it. ✅ *Decided 2026-08-21: report and carry, repair nothing* | same, §8.6.2 |
| 🟠 | **The inline frame/glazing option lists are library data on a window.** 44,915 chars, **byte-identical on all 46** Adelphi windows — 2.07 MB per-window against 45 KB deduplicated. Ship them model-level | [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §9.2.1 |
| 🔵 | **designPH writes a placeholder option list** (`&Launch designPH to edit=01ud&`) that claims the same ids. Merge by how many ids a *list* names — "longest name wins" picks the placeholder and un-names the library | same |
| 🔵 | **Never write to `DesignPH_dict`.** v2 writes `DesignPHPlus_dict` | AGENTS.md |
| 🔵 | **Never modify a corpus file.** Copy first | AGENTS.md |

## 5. The honeybee stack

| | Constraint | Evidence |
|---|---|---|
| 🔴 | **`Space.from_room` fails on real designPH data** — Adelphi produced **no PH Space at all** and lost **368 m² of TFA**. Cause: `is_horizontal` tests **z-extent, not orientation**, at **1e-7 m**, and 2 of 40 faces have a 12 µm spread. One face costs the whole room. ✅ *Fixed 2026-08-21: honeybee's own predicate, flatten below a reported 1 mm, drop only the face honeybee names — 368.476 m², 0 lost* | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §4, [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §5.1 |
| 🔴 | **A pre-filter must use the SAME predicate as the thing it protects.** Guarding `Space.from_room` with a normal-direction test measures a different quantity and lets the failing faces straight through | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §4 |
| 🔴 | **`Face3D.is_sub_face` takes NO tolerance**, so a window flush with its host's edge — or one whose host models the opening as an inner loop — reads as *not fully bounded* in `ValidateModel`. Unrepairable without fabricating an area: emit, and predict the verdict in the report | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §4 |
| 🔴 | **`u_value` is material-only; `u_factor` includes films.** The opposite of the obvious reading. Using the wrong one skews every U-value check by the films, plausibly | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §4 |
| 🟠 | **honeybee refuses an aperture on a `Ground` or `Adiabatic` face** — which is where designPH groups 9 and 11 land | same |
| 🟠 | **honeybee's default BC for a `Floor` is `Ground`**, so an unassigned TFA marker reads as ground-coupled envelope | same |
| 🟠 | **honeybee rejects an upward-pointing `Floor`** (40 of 41 on Adelphi). designPH's winding vs honeybee's convention — flip to match the type you assigned. ✅ *Done 2026-08-21; never on an untyped face, where honeybee assigns from the tilt* | same |
| 🟠 | **`honeybee_ph` makes every material fail published `honeybee-schema`** (it adds a `properties` key). Nothing we emit can validate 100 %; scope the gate to geometry/PH | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §6.1 |
| 🟠 | **honeybee-ph fabricates a New York site** on every segment, indistinguishable from real data | same, §4 |
| 🔵 | `honeybee-schema` requires a `Room` to have **≥ 4 faces**. Build validation fixtures with six | same |
| 🔵 | **`Room` takes ownership of its faces** (`face._parent`). A throwaway second Room steals them | same |
| 🔵 | Identifiers **truncate at 100 chars, silently**. Path-qualified ids are long enough to collide | same |
| 🔵 | **Two exports of one model are not the same file.** Three runs on one CPython give three hashes: `honeybee_ph` mints a `uuid4` per newly *constructed* object (152 distinct / 301 occurrences on Adelphi) and `honeybee-energy` orders four lists out of a `set`. ⚠ Reordering changes no bytes of *length*, so two runs differ in hash at identical size. ✅ **Not an upstream defect and not a round-trip problem** — `from_dict` → `to_dict` preserves 152 of 152, measured. Consequence is diff noise, not breakage; a cross-run or cross-host comparison must canonicalise, and must **not** sort geometry, where vertex order is orientation | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §4, `planning/POC/RESULTS/POC-4_results.md` §3 |
| 🟠 | `Model.from_dict` is **~100× the cost of writing** — 36 s for 1441 faces on Chromium 88, 9 s on native CPython. Never call it on a UI path | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §5 |
| 🟠 | `honeybee-energy`'s **default construction set does not validate** against published `honeybee-schema` (either version). Open v1 decision: emit one at all? | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §6 |
| 🟠 | **Version skew is real**: we vendor honeybee-core 1.64.65 and stamp schema 1.53.1; a live Ladybug install runs 1.64.55 / schema **2.1.2**. Three versions in play | same, §6.2 |
| 🟠 | The stack must stay **IronPython 2.7 compatible** — that is what keeps it pure and Pyodide-viable | `ironpython-27-compatibility` skill |
| 🔵 | **Import `honeybee_ph` last** — its `_extend_` hooks graft `.properties.ph` on | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §3 |
| 🔵 | `Face` wants a **face-type object**, not a string | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §4 |
| 🔵 | Declared dependencies ≠ imported ones. `honeybee-schema`/`pydantic` are declared and unreachable | [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §2 |
| 🔵 | `adelphi-honeybee-json.hbjson` **no longer loads** (`tfa_override`). Shape reference only; build fixtures with `Room.from_box` | [`DATA_CONTRACTS.md`](DATA_CONTRACTS.md) §8 |

## 6. Scope boundaries already decided

| | Boundary | Why |
|---|---|---|
| 🔵 | **No shading in v1**, and the output must carry an explicit `shading: not-computed` marker | PRD §7.2 |
| 🔵 | **Shading geometry is out too** — no heuristic separates context from clutter; v1 will ask which SketchUp tags are shading | PRD §7.2 |
| 🔵 | **One non-solid Room**, by design. No watertight repair | PRD §8.1 |
| 🔵 | **No writing to PHPP**, no mechanical data, no multi-zone program, no model writing | PRD §5 |
| 🔵 | **Report, don't guess** — every untranslatable entity named in a report | AGENTS.md |

## 7. The unsolved design problems

Not blockers — the actual work v1 has to do well.

1. ✅ ~~**TFA / `Space` derivation.**~~ **Solved** (2026-08-21): honeybee's own predicate, flatten
   below a stated 1 mm, drop only the face `Space.from_room` names. 368.5 / 1491.9 / 448.2 m² across
   the corpus, nothing lost. ⚠ What remains is *where* TFA markers live — inside the envelope Room,
   where honeybee defaults them to `Ground`.
2. **The 82 / 1441 / 8037 gap.** Only classified faces are exportable, and no rule reliably tells
   the rest apart. Phase 1 refuted every heuristic; the answer is to **ask the user**, not guess.
   ⚠ **And the gap has a third population in the middle**: a face can carry `DesignPH_dict` and no
   area group (Bluff Reach: 576 tagged, 194 with a group). Tagged ≠ classified ≠ area-group carrier,
   and conflating any two of them breaks a reconciliation.
3. **Assemblies that resolve outside the model.** Four tiers, and a layered construction is not
   always producible — `250708` produces **none at all**, 92 of 92 tier-3, and is not broken.
   ⚠ **And a producible one may still be un-representable**: a framed layer's U-value is ISO 6946's
   mean of limits, which honeybee cannot carry (PRD §8.3.1).
4. ✅ ~~**Thermal bridges as edges.**~~ **Solved and exercised**: 99 of 99 on Bluff Reach, resolved
   against `connections_ud`, attached to the model's building segment. ⚠ They serialise under
   `properties.ph.bldg_segments[].thermal_bridges`, not under the Room.
5. **Which SketchUp versions to support.** Now has a technical price attached — and the corpus shows
   the range that arrives in practice: SketchUp **22 to 26** wrote these five files, two of them on
   machines newer than the reader.
6. **Windows/aperture translation.** Hosting, the rectangle and the transform are all solved (239 of
   239). What is not: **the constructions**. ✅ **Reframed 2026-08-21 — this is smaller than it
   looked.** `frames_ud` and `glazing_ud` are not in the contract's shipped tables, but they *are in
   the model*, and they decode to the full PHPP schema: per-edge U-values and frame widths, glazing
   edge and installation psi values, `chi_GT`, plus the g-value/U-value pair
   (`DESIGNPH_DATA_MODEL.md` §7.0.1). So v1's job is **shipping two more tables and a lookup**, not
   research. ⚠ Two of five corpus models carry neither table, and on those the inline option lists
   still give only a *name* (`DESIGNPH_FILE_FORMATS.md` §2.0) — so it stays a tiered resolution
   like assemblies, not a solved problem.
7. **How to present a discrepancy honeybee cannot represent.** Three now exist — the framed U-value,
   the flush aperture, the doubly-subtracted opening — and all three are handled the same way: emit
   ours, predict honeybee's verdict, never fabricate to satisfy a validator. Whether a report field
   is enough for v1 is an open product question (PRD decision 15).
8. ⛔ **The export freezes SketchUp for 4–11 seconds and shows the user nothing** — new, and the
   only POC-4 item that is a *product* problem rather than a note. The collector walk is 60–79 % of
   the wall clock, and **no progress indicator can update during it** (§3, `SKETCHUP_RUNTIME.md`
   §5 rule 3). Measured: 4.2 s on Adelphi, **10.9 s** on Bluff Reach, dialog blank throughout.
   The fix is structural — chunk the walk across `UI.start_timer` callbacks so the run loop turns
   over — which means turning the collector's recursion into an explicit stack. ⚠ **The performance
   complaint a user files will be "it hung", not "it took 13.9 s".** And the fix is *reasoned, not
   measured*: nobody has yet confirmed that a chunked walk actually restores repainting.
9. **What a shared extraction or report is allowed to contain.** Now that personal data is known to
   be in every designPH model (§1), it is a design question rather than an oversight: the POC does
   not ship `tracker_data`, but an extraction still carries `generated_by` and a model name, and a
   report carries tag names straight out of the user's `.skp`. Anything that travels — a bug report,
   a certifier submission, a support attachment — needs a stated answer.

## 8. Untested — do not assume

| | Why it matters |
|---|---|
| **Windows (the OS)** | PRD requires both platforms at v1. `file://` handling and path semantics are exactly what differs between CEF builds |
| **SketchUp 2021, 2023, 2024, 2025, 2026** | Each ships a different CEF, which sets the Pyodide ceiling. Read the plist per version; **do not interpolate** |
| **designPH 3.0** | ⛔ **and it will stay untested: the licence cannot be bought yet** (Ed, 2026-08-21) — a procurement constraint, not a schedule. Phase 4 is blocked on it and no work here unblocks it. The schema has already changed under us once, so treat every 2.x rule as generation-specific. The version gate refuses a 3.x stamp by name, which needs no licence |
| **Bridge above 4 MB** | Never probed. Real extractions are 334–501 KB and the largest HBJSON is 686 KB, so there is headroom — but it is untested headroom |
| ~~**Large real models end to end**~~ | ✅ **Now tested.** Bluff Reach: 194 classified faces, 99 edges, 2.56 M face visits, 9.7 s walk, 686 KB HBJSON. ⚠ Walk time tracks **placements**, not model size — Linde walks 2466 in 100 ms and carries far more assembly data |
| **A model with >1000 classified faces** | The largest in the corpus is 194. 1441 was *tagged*, not classified, and 8037 was live faces. Nothing here says what a genuinely large envelope costs |
| ~~**`frames_ud` / `glazing_ud` resolution**~~ | ✅ **Corrected 2026-08-21 — the data is in the model.** Both tables decode to the full PHPP frame/glazing schema (per-edge U, widths, `psi_G*`, `psi_F*`, `chi_GT`; g-value and U-value) on **3 of 5** corpus models. The POC does not ship them, which is a scope choice and a v1 opportunity — not a limit of designPH. [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md) §7.0.1. ⚠ Still open: the 2 models carrying neither |
| ~~**The report at scale**~~ | ✅ **Asked and answered (POC-5): it is not usable as a flat list.** Bluff Reach's dialog shows 8 omissions "…and 132 more"; Linde's unclassified census is 2392 faces. v1 needs aggregation-by-reason and report-row → select-in-SketchUp linking — `planning/POC/RESULTS/POC-5_results.md` §4.3 |
| **ph-navigator cannot display a no-mass-construction face** | Its viewer schema requires `thickness`/`conductivity`/`density`, so an `EnergyMaterialNoMass` layer (a tier-2 assembly) makes the face vanish, miscounted as an "air boundary" — apertures vanish with it. The HBJSON is right (renders whole in Rhino/GH); the limit is the viewer's, and both sides are BLDGTYP's to fix. Finding 71, `HONEYBEE_STACK.md` §6.4 |

## 8.1 What the first real export settled — and what it opened

*(2026-08-21, Adelphi inside SketchUp 22.0.353. `planning/POC/RESULTS/`.)*

✅ **Settled by running it:**

| | |
|---|---|
| Pyodide + the 8 wheels boot in SketchUp 2022 | **2577 ms** — no regression on Phase 3, with the full translator added |
| The loopback server carries a 9 MB wasm | worker-thread + sleeping-timer shape holds on real hardware |
| The collector reconciles against the offline baseline | **PASS**, 23 checks. 1441 live vs 1441 offline — **no historical-state gap on Adelphi** |
| 82 of 82 classified faces translate | 0 rejected, 96 KB HBJSON *(324 KB once the apertures and TFA were fixed — §8.1.1)* |
| The assembly tiers are exactly as Phase 1 predicted | 42 tier-2 (the in-model `assemblies_ud` snapshot), 40 with no assembly — the TFA markers |
| The output is **interchange** | loads in Rhino/Grasshopper on a *different* honeybee install |
| The area-group → temp-zone table | zero contradictions across all 1441 tagged faces, live |

### 8.1.1 And what the full corpus settled after it

| | |
|---|---|
| **5 of 5** models reconcile | designPH 2.1.15–2.2.29, SketchUp 22–26; classified-face counts match the offline baseline exactly on every one |
| **545 of 545** classified faces translate | 0 rejected, across all five |
| **239 of 239** windows | every host resolved by `glued_to`; 0 unresolved anywhere |
| **99 of 99** thermal bridges | Bluff Reach. ⚠ all nested **two levels deep** — a top-level walk finds none (E-1, answered) |
| TFA | 368.5 / 1491.9 / 448.2 m² on the three models that carry group-1 faces; the other two correctly derive none |
| U-values | tier-2 pass-through **exact**; tier-1 within **0.0005 W/m²K** of designPH's own calculator on 7 of 7 |
| All four assembly tiers exercised | including `250708`, which resolves **nothing** in-model — 92 of 92 tier-3, and not a broken file |
| Payloads | 334–501 KB per extraction, largest HBJSON 686 KB, against a 4 MB bridge |
| **ph-navigator loads and renders the output** *(POC-5)* | Bluff Reach whole — 194/194 faces, all 40 apertures on their hosts, constructions inspectable. ⚠ One exception: no-mass-construction faces are skipped by its viewer (§8 above, Finding 71) |
| **Nothing downstream keys on `properties.ph.*.identifier`** *(POC-5)* | ph-navigator matches nothing across uploads, so the per-export uuid churn is diff noise only. And `global_construction_set` is discarded by honeybee-energy itself on load — inert bytes to any `from_dict` consumer. `HONEYBEE_STACK.md` §6.4 |

✅ **Closed since, 2026-08-21** — all three defects fixed, and **verified against Adelphi's real
geometry without SketchUp**: the parent transform is recoverable from the first capture, so the two
broken window fields can be rebuilt as the fixed collector would emit them and the real translator
run on the result (`planning/spikes/poc/`). ⚠ That is a **rehearsal, not a capture** — it de-risks
the re-capture, it does not replace it.

| | before | after |
|---|---|---|
| Apertures | 0 of 46 | **46 of 46**, 1 with a flush-boundary note |
| TFA | 0 m², 368 lost | **368.476 m², 0 lost**, 2 faces named as flattened |
| Upward-pointing Floors in `check_all` | 40 | **0** |
| Faces | 82 of 82 | 82 of 82, 15 now carrying a named degeneracy |

⚠ **Still open:**

| | |
|---|---|
| `dynamic_attributes["area"]` | what it actually measures is **unknown**. Stale-DC-formula is the leading hypothesis |
| **A framed assembly's U-value cannot be represented in honeybee** | the construction carries the section-1 value, 8 % low and flattering; `PhDivisionGrid.get_equivalent_conductivity` is the lower limit. Ours travels on the report. **A v1 question, plausibly an upstream one** — PRD §8.3.1 |
| **TFA marker faces sit inside the envelope Room** | so honeybee defaults them to a `Ground` boundary condition and a floor-area marker reads as ground-coupled envelope. Harmless in the POC, wrong in principle |
| **honeybee will call 2 of Adelphi's 46 apertures unbounded** | flush with the host edge by 1 µm, and a host that models its own opening subtracts it twice. Emitted, with the verdict predicted in the report |
| What makes `Model#path` go stale | correlates with SketchUp 24+/26 having written the file, on n=5. A correlation, not a mechanism — the rule is to distrust the value regardless |

## 9. Method rules that saved real time

- **Read the engine version offline** before vendoring anything browser-targeted, and **download a
  matching Chromium** to test against. That converted "ask a human to click" into a local loop and
  is how the Pyodide ceiling was found. [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) §4.2
- **Share one code path across hosts.** The same `spike.js`/`spike.py` ran in SketchUp, desktop
  Chrome, and CPython — so a failure was attributable to the host rather than the code.
- **A synthetic model is not evidence about real models.** A six-face test model produced a
  confidently wrong schema rule. Run against the whole corpus baseline before generalising.
- **A capability flag is not a statement about the model** (`cuts_opening?`).
- **A declared dependency is not an imported one.** Resolve, then ask what imports it, then prove it.
- **pydantic 1 inflates validation error counts 16–38×.** Collapse by failing object.
- **`re.DOTALL`** when parsing `.skp` bytes — a `0x0A` inside a length field silently hides records.
- **A run nobody can grade at a glance has not reported anything.** End with a verdict.
- **Do not re-implement half of a library's rule locally.** Three separate bugs in one session came
  from a local approximation of a honeybee predicate: `clean_string` (length cap), `u_value` vs
  `u_factor` (films), `is_horizontal` (z-extent vs orientation). Call the library's own function.
- **A cross-check that fires is doing its job.** The face-area check flagged 16 faces and the first
  instinct was to suppress it; it had found a real distinction (gross vs net). Explain a firing
  check before silencing it.
- **One sample is not a unit table.** `lenx × leny == area` held on the one window anybody had
  dumped, and on only 20 of 46 across the model. Arithmetic that "confirms" a rule on n=1 confirms
  nothing.
- **Ask what a number counts before quoting it.** "8037 faces" and "1,023,558 faces" are both true
  of Adelphi — unique faces, and placements × faces.
- **A capture answers more questions than the run that produced it asked.** The window fix rested on
  an inference (is the definition origin a *corner* of the opening, or its *centre*? — half a window
  apart). The parent transform turned out to be solvable from the already-recorded, *defective*
  capture: local +Z onto host normal by Kabsch, local origin onto host plane by least squares. That
  converted the inference into 46/46 vs 23/46, and then let the whole fixed pipeline be rehearsed —
  all without SketchUp. **Before booking a session to answer a question, ask what the data on disk
  already constrains.**
- **A projection hides the bug it is supposed to survive.** Flattening a window onto its host plane
  works exactly as well from 3 m away as from 3 mm, so the parent-relative transform produced no
  symptom at all. Any lossy step needs a limit on how much it was allowed to absorb.
- **One example is not a census.** "a sliver and a spur" became 8 sub-mm edges and 7 revisited
  boundaries once it was counted — and the spur was invisible to the obvious test, because every
  edge of a spur is long.
- **Before shipping a field per entity, ask whether its values are per entity.** `distinct` is a
  one-line check; on Adelphi's 46 windows it was **2**, and the difference was 2.07 MB of a 2.25 MB
  payload against a bridge verified to 4 MB. The "log anything approaching 1 MB" rule is what
  surfaced it — on the very first capture it ever applied to.
- **A size limit you never breach teaches nothing; the warning that fires is the one worth having.**
- ⚠ **When a check fires on most of your real data, suspect the check.** The reconciler failed on
  **three of four** real captures and the data was right every time — two checks compared the wrong
  quantities, one flagged an override pair as a contradiction. "A synthetic model is not evidence"
  applies to the *harness* as much as to the fixture: **validate a check against more than one model
  before trusting it to grade.**
- ⚠ **The simplest model in the corpus is the most dangerous one to validate on.** Adelphi masked
  every count-invariant bug: all of its tagged faces carry an area group, none of its geometry is
  placed twice, and it has no framed assemblies, no thermal bridges and no layer tables. Being the
  primary fixture makes it the *default* thing to test against, which is exactly the problem.
- ⚠ **A parameter fitted to make a model match cannot then confirm that model.** The multi-section
  U-value was first "confirmed" by solving for the framing fraction that made a simple lambda blend
  reproduce one PHPP number. Circular — and it hid that the method was ISO 6946's mean of two limits.
  The replacement is checked against seven independent assemblies *and* the error figure designPH
  prints beside its own answer.
- ⚠ **A pattern that fits three numbers is not a unit.** `0.0625` and `0.09375` are exactly `1.5/24`
  and `1.5/16` — standard US stud spacings — which reads overwhelmingly as *fractions*. They are
  percentages. One screenshot of designPH's own dialog settled it; the convincing reading would have
  applied a hundredfold framing correction.
- **When the vendor's own UI can answer a question about the vendor's data, ask it.** designPH's
  U-/R-value calculator settled in one screenshot what two rounds of derivation had got wrong. That
  is a cheap Ed round-trip against an expensive analysis, and the ratio is not close.
- ⚠ **A guard built on an untrustworthy value fails in both directions.** The copies-only check read
  `model.path`: matching this machine's `~/Dropbox` let a stale foreign path through, and widening it
  to `/Dropbox/` for any user then refused a legitimate copy. **Ask a positive question — *is this
  verifiably the thing I expect?* — and hand the residue to the human**, who has the fact the API
  does not.
- **A negative result from the wrong container is not a negative result.** Searching a `.skp` for a
  string it definitely contains returned nothing, because the `.skp` is a **zip** and the data is in
  `model.dat` inside it. The tool that reads these files already knew that.
- ⚠ **When a comparison fails on 100 % of your data, suspect the comparison — and read the shape of
  the failure before reading the failure.** POC-4's cross-host check reported 5 of 5 fixtures
  differing, twice, for two different reasons, and the *sizes* diagnosed both. First the CPython leg
  was 180 KB larger every time: it was hashing `translate_json`'s whole envelope while the browser
  leg hashed the `hbjson` field — a comparison of two different artefacts. Then, fixed, the files
  came back the **same size to the byte** with different hashes, which is the signature of
  *ordering*, not arithmetic — 301 fresh uuids and four `set`-ordered lists, both upstream. A float
  repr moves bytes; it does not move exactly zero of them.
- **State which claim a check tests, then check that one.** "Byte-identical" was one word covering
  two different claims — *the translator behaves the same on every host* and *the collector reads
  the same model the same way twice*. Only the first is about hosts, only the second is about
  sessions, and conflating them makes a failure unattributable. Naming them (a) and (b) in the tool
  is what let the first be closed offline while the second waits for SketchUp.
- ⚠ **A tool that drives another tool inherits its defaults — including where it writes.**
  `byte_identity.py` calls `verify_in_chrome.py`, whose baseline defaults to the **committed**
  `planning/POC/RESULTS/baselines/` and embeds 400 characters of the translated model. Run against
  the real corpus, that put client HBJSON in the repo. Caught by reading `git status`, not by a
  check. **A default output location is a decision the composing tool has to make explicitly.**
- ⚠ **Asserting the call is not asserting the surface — four times in one phase.** The banner
  rendered a boolean instead of the headline; the Chromium harness graded that same boolean; a
  refusal never reached the banner at all; and the progress signal was "verified" by checking that
  `status_text` had been *set*, on a feature that cannot display anything (a stub has no screen).
  Every one of them was green, and every one of them was about a surface a user looks at. **When
  the claim is "the user sees X", the assertion has to read X off the surface** — and be shown to
  fail on the code that got it wrong.
- ⚠ **A harness that inspects the objects a UI is built from cannot see the UI.** The dialog banner
  rendered `verdict.passed` (a boolean) while the message box rendered `verdict.headline` (three
  states since POC-3), so a real export showed green `PASSED` with 40 assemblies unresolved.
  `verify_in_chrome.py` could not catch it **because it graded `verdict.passed` too** — and the stub
  fixture has yielded `PASSED WITH OMISSIONS` since the day it was written, so the failing case was
  rendering in every headless CI run with nothing asserting on it. **If the claim is about what a
  user sees, the assertion has to read what a user sees** — the harness now reads the DOM back, and
  was verified to fail on the old code before being trusted.
- ⚠ **A canonicaliser that normalises too much is a check that cannot fail.** Sorting the four
  `set`-ordered honeybee lists is right; sorting every list would reorder `boundary` vertices, which
  are a face's *orientation* — a wall and its mirror image would compare equal, in the very tool
  whose job is catching silent differences. Normalise by name, never by shape.
