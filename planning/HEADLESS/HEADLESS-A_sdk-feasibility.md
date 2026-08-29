# HEADLESS-A (Spike A) — SketchUp C SDK feasibility: read a designPH `.skp` headlessly

DATE: 2026-08-28
STATUS: ⛔ **BLOCKED at G0 (2026-08-28)** — the SDK binary is no longer a public download.
Results, including the API-surface answer that closed G1's documentation half:
[`RESULTS/HEADLESS-A_results.md`](RESULTS/HEADLESS-A_results.md)
AUTHOR: Ed May (drafted by Claude)

Context, rules, evidence base and the licensing checklist:
[`00_HEADLESS_OVERVIEW.md`](00_HEADLESS_OVERVIEW.md). This doc is the plan for Spike A only.

---

## 1. The question

**Can the SketchUp C SDK, driven from CPython on macOS with no SketchUp installed, read a real
designPH `.skp` well enough to reproduce what the POC's live Ruby collector read?**

This is the API-feasibility half only. Spike B (drop-in capture device,
[`HEADLESS-B_contract-identity-gate.md`](HEADLESS-B_contract-identity-gate.md)) and Spike C
(deployment, overview §5) follow only if A passes. Spike A runs entirely on the laptop, entirely
offline, against corpus copies. It writes no product code and makes no deployment decision.

## 2. Approach

1. **Download the newest SketchUp Desktop SDK for macOS** (developer.sketchup.com → Desktop SDK).
   Record the exact SDK version in the results doc. **Save the SDK EULA text alongside it** — that
   is task L1 (overview §6); it ships with the download, not on the web pages.
2. **Binding: ctypes against the newest SDK is the primary route** — the SDK is a flat C API
   (`SUInitialize`, `SUModelCreateFromFile`, `SU*Ref` handles, `SUResult` codes), which is
   ctypes-friendly and keeps the whole spike in Python. No compiled code unless forced.
   ⚠ `pyslapi` (the Cython binding Blender's `.skp` importer uses) is **demoted to a curiosity**
   (review item 4): it is pinned to an older SDK generation, an SDK older than the file cannot open
   it, and the corpus writers span SketchUp 22–26 — so a working pyslapi proves nothing for G8 and
   may fail on most of the corpus outright.
3. **Scripts**: PEP 723 `# /// script` headers, run with `uv run`, in
   [`../spikes/headless/`](../spikes/). No venv. One script (or clearly named function) per gate,
   each printing a verdict line — a run nobody can grade at a glance has not reported anything.
4. **Scratch**: corpus copies and all output under `../spikes/headless/_private/` (gitignored,
   `MANIFEST.md`), per overview §4. Every script takes an explicit `--out` there.

## 3. Gate questions

Each gate has a *known right answer* from the POC record. The spike's job is to make the SDK
reproduce it — or to record precisely where it cannot.

### G0 — Boot pre-gate (30 minutes, before any gate work)

Practical hazards first (review item 8): `lipo -info` on the SDK dylib — an x86_64-only build
means `arch -x86_64` plus an x86_64 CPython and changes the whole-spike-in-Python story; clear the
quarantine xattr on the downloaded dylib (`xcrun`/Gatekeeper will otherwise fail the `dlopen`
opaquely); then `SUInitialize` → open the Adelphi *copy* → print `SUModelGetVersion`. One verdict
line. Nothing below runs until it passes.

### G1 — Does the SDK expose the glue relationship? ⚠ the decisive gate

`glued_to` is **the only thing that identifies a window host** — `cuts_opening?` is a definition
capability (true on all 46 Adelphi windows) and `loops.size > 1` is true on only **1 of 16** real Adelphi hosts (and 1 of 81 corpus-wide — remeasured 2026-08-28)
([`CONSTRAINTS.md`](../../00_Context/CONSTRAINTS.md) §4). If the C API cannot answer "which face is
this instance glued to?", nothing else in this spike matters at full strength.

- **Method**: `SUComponentInstanceGetAttachedToDrawingElements` (and its `GetNum…` companion) —
  ✅ **verified in the published C API docs (SketchUp 2018, API 6.0), exactly the instance→host
  direction** (2026-08-28; the review's claim that this name does not exist was itself wrong — see
  `code-review.md` disposition). Still confirm against the downloaded SDK's header before coding.
  Distinguish it from `SUComponentInstanceGetAttachedInstances`, which points the other way
  (things glued *to* this instance). **Cross-check from the host side** (the review's useful half):
  `SUFaceGetOpenings` → `SUOpeningRef` — the 16 Adelphi hosts should report their glued windows as
  openings. ⚠ Openings may conflate glued instances with genuinely *cut* geometry, so assert each
  opening's drawing element is one of the 46 windows — the `cuts_opening?` trap can reappear at the
  C layer. The host-side view may also explain G6's net/gross mechanics for free.
- **Right answer**: 46/46 Adelphi windows resolve to a host face; spot-check ≥1 more model
  (Wellington's 57 or Linde's 47) — full 239/239 corpus coverage is Spike B's job.
- **Fallback if absent**: geometric host resolution — project the rough-opening rectangle onto
  candidate faces; the POC's containment machinery scored 46/46 (with the flush-window tolerance
  trap already solved). Workable, but a *weaker claim* (inference, not a stored fact) and the
  results doc must say so in those words. G1 answering "no, fallback required" makes Spike A
  **PASS WITH CHANGES**, not PASS.

### G2 — Typed attribute reads, uncoerced

- **Method**: read `DesignPH_dict` via `SUEntityGetAttributeDictionary` → `SUTypedValue` off
  **every carrier type**: faces, **component instances** (windows carry their dicts on the
  instance), **edges**, and the **model itself** (the Marshal-table dicts) — not faces alone
  (review item 8). Assert the *type tag*, not just the value.
- **Right answer**: `areaGroupID` comes back as the **String** `'n'` (not an int, not coerced) on
  1359 of Adelphi's 1441 tagged faces; the `*ID`/`*Auto` coalesce works on both generations
  (`250708` keeps every assembly in `assemblyIDAuto`); an entity with no dictionaries reports
  cleanly (the Ruby API returns `nil` — record what the C API's equivalent is, likely
  `SU_ERROR_NO_DATA`).

### G3 — Edges enumerate, with their dictionaries, at depth

Thermal bridges live on `Sketchup::Edge`, and on Bluff Reach **all 99 are nested two levels deep**
— a face-only or top-level-only walk finds zero, silently (CONSTRAINTS §4).

- **Method**: recursive walk collecting edges carrying `DesignPH_dict` — and **state the counting
  basis** (review item 6): walk the instance tree but count **entities**, deduplicating an entity
  seen through multiple placements. That is the live captures' basis; a placements count is the
  known false alarm (`250708`: 2456 placements vs 1781 entities), and "99-ish but wrong" would be
  silent.
- **Right answer**: exactly **99** on Bluff Reach *as an entity count*, each with an `assemblyID`
  resolving in `connections_ud`; 0 on the other four.

### G4 — Marshal tables come through byte-clean

- **Method**: read the model-level attribute dictionaries holding designPH's Marshal blobs; feed
  the raw bytes to the existing `ruby_marshal.py` (construct-nothing decoder) unchanged.
  ⚠ **The named silent-failure risk is NUL truncation** (review item 3): Marshal blobs contain
  `0x00` bytes (symbol terminators guarantee it), and a ctypes read through `c_char_p` stops at
  the first NUL — worst case a false PASS on a partially decoded table. Use the length-aware
  string API (`SUStringGetUTF8Length` + a counted copy), never `c_char_p`; then **prove** it by
  diffing the C-API-read blob **byte-for-byte** against the same table read by the offline parser
  (`skp_decode_tables.py`'s input path). One check settles truncation, encoding, and
  byte-cleanliness, and feeds H4's byte-equal stratum directly.
- **Right answer**: `frames_ud` / `glazing_ud` decode to the full PHPP frame/glazing schema on the
  **3 of 5** capture models that carry them
  ([`DESIGNPH_DATA_MODEL.md`](../../00_Context/DESIGNPH_DATA_MODEL.md) §7.0.1); `assemblies_ud`,
  `connections_ud` and the `layer_table_*` set decode where the offline baseline says they exist
  (Linde: 25 layer tables). `tracker_data` will also be present — confirm it decodes, then confirm
  it is **excluded** from anything that leaves `_private/`.

### G5 — The SDK reads live state, not history

The claimed advantage over the binary parse; verify it rather than assume it.

- **Method**: count entities carrying `DesignPH_dict`, per entity type, and compare against the
  **live captures** (not the offline union), on the two models where live and offline are known to
  diverge.
- **Right answer**: Bluff Reach matches the live capture's counts (576 dict-carriers / 194
  area-group faces / 99 edges, on an entity basis); `250708` yields **1781 entities** (the live
  entity count), not 2456 (placements) and not whatever the historical union holds. Compare like
  with like — entities vs entities — or the comparison repeats the reconciler's three known false
  alarms.

### G6 — `SUFaceGetArea` semantics: net or gross?

In live SketchUp, `face.area` is **net** of glued window openings while the loop polygon is gross —
they differ on exactly Adelphi's 16 host faces, by exactly the window areas (CONSTRAINTS §4).
Whether the SDK's standalone deserializer reproduces the net behavior is unknown.

- **Method**: for the 16 known Adelphi hosts, compare `SUFaceGetArea` against the polygon area from
  the outer loop, and against the live capture's recorded `face.area`.
- **Right answer**: *either* is acceptable — net (matches Ruby) or gross (differs by exactly the
  summed window areas). What is not acceptable is not knowing: the contract ships loops, but the
  Spike-B reconciler compares areas, so the semantics must be recorded here.
- **Decided now** (review item 7): the headless collector records the SDK value **verbatim — never
  a locally recomputed net area**. Recomputing SketchUp's own subtraction would be re-implementing
  half a library's rule, the POC's most-paid-for mistake. G6's *measured* semantics then becomes a
  **named bucket** in H4's diff on exactly the 16 host faces; carry the decision into B's H0.

### G7 — World transforms compose correctly

`ComponentInstance#transformation` is **parent-relative** while every other contract field is world
— the trap that put Adelphi's 46 windows 1.2–3.3 m off their hosts with no symptom (CONSTRAINTS §4).

- **Method**: read per-instance transforms (`SUComponentInstanceGetTransform`), compose through the
  nesting hierarchy to world, convert inches → m (× 0.0254).
- **Right answer**: each Adelphi window's world rough-opening corners (`lenx × leny` from the
  definition origin, `+x`/`+y`, through the composed transform) match the live capture's recorded
  world geometry within **1 mm**; face loop vertices likewise on a sample of classified faces.

### G8 — File-version coverage

- **Method**: open all 14 corpus models with the one newest SDK; record `SUModelGetVersion` (or
  equivalent) and any failures.
- **Right answer**: all 14 open — the writers span SketchUp 22–26 and the newest SDK reads
  everything older than itself. Also run the one pre-2014-era sample
  (`BLDGTYP - Sketchup Sample DesignPH ready Model.skp`) and record what happens; the offline
  reader's result on it is *inconclusive by design*
  ([`DESIGNPH_FILE_FORMATS.md`](../../00_Context/DESIGNPH_FILE_FORMATS.md) §4.1), so any definite
  answer here is new information for `00_Context/`.

## 4. Pass / fail

- **PASS** — G1 answers *yes* (glue is queryable) and G2, G3, G4, G5, G7, G8 all reproduce their
  known answers; G6 is answered either way.
- **PASS WITH CHANGES** — G1 requires the geometric fallback, everything else holds. Spike B then
  inherits a *stated* inference step with a stated limit (the projection-absorbs-the-bug rule: any
  lossy step reports what it absorbed).
- **FAIL** — any of G2–G5/G7/G8 cannot reproduce its known answer, or the SDK cannot be driven from
  Python at reasonable cost. Written down in full either way — a negative result recorded is the
  cheap outcome; a negative result rediscovered is not.

The results doc is `RESULTS/HEADLESS-A_results.md`: one verdict line per gate, the measured numbers
beside the expected ones, the SDK version + binding route + EULA notes. **Spike B does not start
until it exists** (hard rule 7), and Spike B's own H0 revision pass reconciles its plan against it.

## 5. Deliverables

1. `planning/spikes/headless/` scripts — one per gate cluster, PEP 723, kept regardless of outcome.
2. `RESULTS/HEADLESS-A_results.md` — per-gate verdicts.
3. **Durable facts to `00_Context/`** — at minimum: the SDK's glue-query answer, the
   `SUFaceGetArea` semantics, the pre-2014 file answer, and a new record of what the C SDK does and
   does not expose (likely `SDK_RUNTIME.md`, or a `DESIGNPH_FILE_FORMATS.md` section).
4. The saved SDK EULA + first-pass notes for the licensing checklist (overview §6).

## 6. Explicitly out of scope

Spike B and Spike C (planned/sketched — overview §5); licensing resolution (overview §6); any
product code; any writing to any model.

## 7. Method rules that apply (from CONSTRAINTS §9)

- A synthetic model is not evidence; **run gates against the corpus, never a toy file**.
- **Adelphi masks bugs** — Bluff Reach and `250708` are the models that catch count-class errors.
- **State which claim a check tests, then check that one.**
- **One sample is not a unit table**; count before generalising.
- **A check that fires is doing its job** — explain it before silencing it; and when a check fires
  on most of the real data, suspect the check.
- **End every run with a verdict line.**

## 8. Estimated effort

Roughly one laptop-day for G0–G8 once the SDK is downloaded and the evidence base is staged
(overview §3 prerequisites), assuming ctypes cooperates; the decisive G1 answer should fall within
the first hour or two and is worth reporting immediately — if it is a hard *no with no fallback
worth having*, stop and reassess before spending the rest.

---

## Changelog

- 2026-08-28 — drafted. (Originally scaffolded in `00_PH_Tools/design-ph-plus/`, moved here the
  same day.)
- 2026-08-28 — review pass folded in (`code-review.md` + its disposition table): G0 boot pre-gate
  added; binding order flipped (ctypes-on-newest primary, pyslapi demoted); G1's API name verified
  against the published docs and the `SUFaceGetOpenings` host-side cross-check added; G2 widened
  to all four dict-carrier types; G3 states the entity counting basis; G4 gains the NUL-truncation
  rule and the byte-diff proof; G6's verbatim-record decision made.

- 2026-08-28 — **run attempted; blocked at G0.** The SketchUp C SDK is behind a Trimble
  "Request Access" form with no public download (`RESULTS/HEADLESS-A_results.md` §1). What closed
  anyway: **G1's decisive question is YES at the documentation level** — both glue directions are
  published, along with every other function G0–G8 needs (`a1_capi_surface.py`); the expected-answer
  table is now derived from the fixtures rather than prose (`a0_expected_answers.py`); the evidence
  base is staged. ⚠ Two plan assumptions were wrong: pyslapi's *framework* is a 2025-generation
  build (newer than every corpus writer), not an older SDK generation — only its *binding* is stale;
  and `SUModelGetVersionString` does not exist, so G8 gets an enum, not a version string.
