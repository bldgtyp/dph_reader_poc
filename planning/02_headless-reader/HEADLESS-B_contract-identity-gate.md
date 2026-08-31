# HEADLESS-B (Spike B) — the contract-v2 identity gate: same model, same capture, same HBJSON

DATE: 2026-08-28
STATUS: ✅ **COMPLETE — PASS. H1-H7 and H9 green, H8 recorded (2026-08-29).**
Results: [`RESULTS/HEADLESS-B_results.md`](RESULTS/HEADLESS-B_results.md). A headless CPython
process is a **drop-in capture device**: contract v2 out, **0 unexplained differences on 5/5**
models against the live SketchUp captures, worst geometry deviation **0.000000 mm**, the untouched
translator to the POC's own numbers (545/545 · 239/239 · 99/99), and **canonically identical
HBJSON** 5/5. ⚠ Run on a **third-party SDK build**, so every number is feasibility-only evidence
until it is re-run against Trimble's own.
AUTHOR: Ed May (drafted by Claude)

Context, rules, evidence base:
[`00_HEADLESS_OVERVIEW.md`](00_HEADLESS_OVERVIEW.md).

---

## 1. The question

**Does a headless C-SDK collector read the same model the live Ruby collector read — and does the
unchanged POC translator then produce equivalent HBJSON?**

Spike A established (or will have established) that the SDK *exposes* the data. Spike B establishes
that a collector built on it is a **drop-in replacement for the capture device**: it emits the
frozen contract v2, reconciles under the existing harness, matches the five live captures
field-for-field, and feeds the untouched `dph_translator` to the POC's own acceptance numbers.

Name the claims, per the POC's discipline (CONSTRAINTS §9 — "state which claim a check tests, then
check that one"). The POC closed:

- **(a)** the translator behaves the same on every host — closed, POC-4;
- **(b)** the live collector reads the same model the same way twice — closed, POC-4.

Spike B adds two new ones, and tests them separately:

- **(c)** the headless collector reads the same model the live collector read;
- **(d)** the headless collector reads the same file the same way twice (its own determinism).

## 2. Mandatory first step: the revision pass (H0)

Before any code, re-read this plan against `RESULTS/HEADLESS-A_results.md` and revise it. The
sections most likely to need changes, flagged now:

Record the revision as a dated changelog block at the bottom of this file. An unrevised plan
executing after Spike A is the "believed once written down" failure mode the POC paid for twice.

### 2.1 The revision, done — 2026-08-29

Every row this section anticipated resolved in the *favourable* direction, and two of them dissolve
the gate they were written for.

| Anticipated | What Spike A actually found | Effect here |
|---|---|---|
| **G1 fallback** — no glue query, geometric host resolution | ✅ **Not needed.** `SUComponentInstanceGetAttachedToDrawingElements` resolved **239/239** windows on five real models; distinct-host counts match the captures exactly | **Row void.** H4/H5's aperture claims stay a *stored fact*, not an inference. No residual reporting, no derived-field comparison |
| **G6** — `SUFaceGetArea` gross, not net | ✅ **Neither guess.** `SUFaceGetArea` is the **LOCAL** area; `SUFaceGetAreaWithTransform` is the world area and equals live `face.area(transform)` on **545/545** faces | **H4's named area bucket is EMPTY** — provided the collector uses the WithTransform variant. A contract *note* is still worth proposing: which call a capture device used |
| **Binding route** | ctypes on the newest available SDK, as planned. pyslapi's *binding* unused; only its framework | tooling only, as expected |
| **Entity-ID semantics** | ★ **`SUEntityGetPersistentID` exists, and A already proved the join end to end** | **H1 is effectively closed** — see below |
| **PASS WITH CHANGES carry-overs** | none — all eight gates closed clean | nothing to carry |

★ **H1 is pre-answered, and this is the single biggest change to Spike B's shape.** Spike A's G7
work matched **545/545 faces and 239/239 windows with 0 unmatched**, joining purely on the
path-qualified id it *reconstructed* from `SUEntityGetPersistentID`. That id is byte-identical to
the one `collector.rb:597` writes. So H1's "right answer" (persistent IDs align 1:1) is already
measured on all five models, and its fallback matcher is not needed. H1 remains in the sequence as
a **cheap explicit assertion**, not an open question.

⚠ **Three new constraints Spike A discovered, which this plan did not anticipate and which H2/H4/H7
must now carry:**

1. ⛔ **The reader mutates the in-memory model.** `SUEntityGetAttributeDictionary` is a
   get-or-CREATE (its own header says so), and it is the *only* complete way to test for a
   dictionary — the read-only enumeration silently under-reports by up to 41%. **H2 must assert the
   collector never calls `SUModelSaveToFile`**, as a check, not an intention — the same discipline
   H2 already applies to `tracker_data`. This is hard rule 2's survival condition.
2. **designPH's Marshal tables are stored as BASE64.** H4's "attribute payloads byte-equal (Marshal
   blobs included)" must say **which form** it compares. Compare the **stored base64 string**, which
   is what the contract carries and what a byte-equality claim can actually mean; decoding first
   would compare two decoders, not two captures.
3. ★ **`SUFaceGetNumOpenings` is a second, independent host test** the Ruby collector never had
   (> 0 on exactly the 81 host faces; Ruby's `loops.size > 1` is true on 1 of 81). **H4 should
   cross-check the glue-resolved host set against it** — a free corroboration of the aperture claim
   that costs one call per face.

**H8 already has numbers**: ≈3-4 s per model for 3-11 MB files on an M-series laptop, whole corpus
in under 4 s for the count gates. Spike A also surfaced the scale probe H8 will eventually want —
`2618 {BP} Lavoie Certification.skp`, **146 MB**, ~13× the largest baselined model, currently
unstaged because it has no baseline and no live capture.

⚠ **And the caveat that outranks all of the above:** Spike A ran on a **third-party re-host** of
Trimble's SDK, because the official one is behind an unanswered access form. Spike B inherits that
footing exactly. A PASS here is a strong feasibility result and **not** a commercial green light
until the suite is re-run on Trimble's own build.

### 2.2 Second revision — the capability sweep (same day)

§2.1 reconciled this plan against Spike A's eight *gates*. A follow-on capability sweep over **16**
corpus files (`a7_capability_probe.py`, distilled in
[`../../00_Context/HEADLESS_VIABILITY.md`](../../00_Context/HEADLESS_VIABILITY.md)) then changed
Spike B's **shape**, not just its details. Three structural changes and four proposals.

#### ★ Structural change 1 — two corpora, not one

Spike B has been written as if all its gates need the five live captures. **They do not**, and the
distinction is worth real coverage:

| gate | needs a live capture? | corpus |
|---|---|---|
| H4 identity · H6 HBJSON equivalence | **yes** — they compare against one | **the 5 captured models** |
| H2 emission · H3 reconciliation · H5 translator · H7 determinism · H8 cost | **no** | ▶ **all 16 staged files** |

Running the emission-side gates on all 16 buys coverage the POC never had:

- ⭐ **`2536 Holmes` carries 42 named thermal-bridge edges** and was never captured
  (`DESIGNPH_DATA_MODEL.md` §13.4). It is the **only second bridge model in existence** — and
  "confirmed on one model is confirmed on nothing" is this repo's most-repeated lesson. H5 running
  the translator over Holmes's bridges is the highest-value single addition to this plan.
- ⭐ **`2618 Lavoie`, 146 MB**, is the scale probe H8 wanted.
- ⭐ **The 1.0.30 sample** exercises a designPH generation below anything the translator has met.

#### ★ Structural change 2 — a new gate, H9: what does the reader do with a version it does not know?

The POC's version gate refuses a 3.x stamp *by name*. The corpus now spans **designPH 1.0.30 →
2.4.0 BETA**, and 1.0.30 is structurally different: a `Shader` key no 2.x model has, `tfa_calc`
without the `_ud` suffix, `Klima_Standort` with a capital K (§13.1). A reader that meets it must
**say so**, not half-read it — hard rule 4, applied to the version axis rather than the entity axis.

- **Method**: run the collector against the 1.0.30 sample and the 2.4.0 BETA model. Record what the
  version gate does with each.
- **Right answer**: not yet decided, and that is the gate. Either it reads them and says which
  fields it could not resolve, or it refuses by name and says why. **Silently producing a partial
  capture is the failure.** ⚠ Note the precedent: the offline parser returned a clean *zero* on the
  1.0.30 file for ten days (`DESIGNPH_FILE_FORMATS.md` §4.1) — a plausible wrong answer with no
  error. Do not reproduce that shape.

#### ★ Structural change 3 — H2 and H7 inherit a safety property, not just a check

⛔ Spike A proved on all 16 files that **reading mutates the in-memory model**: asking a face for a
dictionary it lacks takes it from 1 dictionary to 2, and that is the *only complete* way to read
(`HEADLESS_VIABILITY.md` §3.1–3.2). H2's "assert the collector never saves" should therefore be
**structural, not procedural** — the reader should be incapable of saving (never resolve the write
symbols), and H2 asserts that property, rather than asserting that a save did not happen.

#### Four contract proposals — for the §9 process, NOT for this spike to implement

Spike A found four things the SDK exposes that **contract v2 does not carry**. Spike B *proposes*;
it never edits the frozen contract (§6.3). Each needs a decision before v3, and each is cheap:

| candidate | evidence | why it may matter |
|---|---|---|
| ⭐ **north correction** | non-zero on 7 of 16 (25.0007° · 44.8647° · 350.6339° …) | **solar orientation.** A Passive House model's geometry is currently emitted with no true-north reference at all |
| ⭐ **lat / long** | real coordinates on 5 of 16 | climate. ⚠ Also **client data** — a building's real location — so it inherits the `tracker_data` handling rule, and ⚠ `geo_referenced` is `true` with `(0,0)` on Adelphi |
| **tag / layer name on classified faces** | v2 carries `tag` only on *unclassified* records | the shading question (PRD §7.2). Holmes has 42 tags on non-designPH faces |
| **model GUID** | stable across reads, differs between saves | cheap change detection for a watcher without hashing 146 MB |

⚠ **One open question, deliberately left open**: windows carry a `DesignPH_dict` with `descNameAuto`
on 9 of 16 models (§13.3) that the contract does not read. It may be a fourth redundant name
alongside `designph_name` / `definition_name` / `instance_name`, or the authoritative one. **Measure
before proposing** — this is exactly the shape of a field added because it exists rather than
because it is needed.

#### Smaller carry-overs

- **H8 has starting numbers** — ≈16 s for the whole 230 MB corpus, cost tracking *unique entities*
  (~80–100k/s) rather than file size. ⚠ **Per-model peak memory is still unmeasured**: the sweep ran
  in one process and `ru_maxrss` is a process high-water mark, so 851 MB is "the run peaked here",
  not "Lavoie costs this". H8 should run **one process per model**.
- ➕ **Concurrency is unmeasured and belongs in H8**: can two models be open at once, and is
  `SUInitialize` thread- or process-safe? A watcher will want to know before Spike C picks a host.
- **H4's diff gets a free corroborator**: `SUFaceGetNumOpenings` is > 0 on exactly the 81 host faces,
  so the aperture claim can be cross-checked host-side for one call per face (§2.1 already noted it;
  it is now measured across the corpus).

## 3. What already exists (reused, not rebuilt)

- **The frozen contract**: v2 — changes go through the POC contract's §9 process only
  ([`../01_sketchup-export/implementation/CONTRACT_extraction-json.md`](../01_sketchup-export/implementation/CONTRACT_extraction-json.md)); the frame/glazing
  libraries are hoisted to the model-level `libraries` block; the 1 MB payload warning rule
  applies.
- **The five live captures** in `pocs/01_sketchup-export/_private/fixtures/` — the ground truth for claim (c).
- **The harness, unchanged**: `pocs/01_sketchup-export/tools/check_extraction.py` (capture ↔ offline-baseline
  reconciliation — already corrected for the three false-alarm classes: dict-carriers vs
  area-group carriers, placements vs entities, `descName`/`descNameAuto` override pairs),
  `pocs/01_sketchup-export/tools/validate_output.py` (published honeybee-schema, separate interpreter), and
  `pocs/01_sketchup-export/tools/byte_identity.py`'s canonicalisation discipline (sort the four `set`-ordered honeybee
  lists, normalise by name **never by shape** — a canonicaliser that sorts geometry makes a wall
  equal its mirror).
- **The translator, untouched**: `pocs/01_sketchup-export/py/dph_translator`. Spike B modifies nothing in it; if a
  headless capture makes it misbehave, that is a *finding about the capture*, recorded, not a
  patch applied.
- **The acceptance numbers** (the POC's own table): 5/5 models reconcile; **545/545 classified
  faces, 239/239 windows, 99/99 thermal bridges**; TFA **368.5 / 1491.9 / 448.2 m²** on the three
  models carrying group-1 faces (the other two derive none); U-values tier-2 **exact**, tier-1
  within **0.0005 W/m²K** of designPH's own calculator.

⚠ **Set every output location explicitly.** `byte_identity.py` once inherited
`verify_in_chrome.py`'s default baseline dir and wrote client HBJSON into the committed repo
(CONSTRAINTS §9). Every Spike-B script takes an explicit `--out` under
`planning/spikes/headless/_private/` and refuses to run without it.

## 4. Gates

### H0 — Revision pass

✅ **DONE 2026-08-29 — §2.1.** Outcome: G1's fallback row is void, G6's area bucket is empty, H1 is
pre-answered, and three new constraints (never-save, base64 payload comparison, `SUFaceGetNumOpenings`
cross-check) are folded into H2/H4.

### H1 — Entity identity: the join key — ✅ **PASS** (883/883 join, 0 degenerate ids)

Comparing two captures of one model needs a way to say *this face here is that face there*. The
live captures carry the Ruby side's entity identifiers; whether the C SDK's IDs (`SUEntityGetID`,
persistent IDs) coincide with them is unknown until measured — and pholio's identity rule (ids
come from the capture device, never minted per export) makes this the gate that decides what the
*service's* stable IDs will be.

★ **Largely answered by Spike A already** (§2.1): the path-qualified id reconstructed from
`SUEntityGetPersistentID` matched the live captures on 545/545 faces and 239/239 windows, 0
unmatched, on all five models. What remains is to assert it explicitly and record per-file
persistent-id coverage.

- **Method**: for Adelphi + Bluff Reach, extract (entity-id, persistent-id, dict-fingerprint) per
  tagged entity from both capture routes; measure the overlap. Three links to verify on the way
  (review item 5): **(a)** the C-side names — expect `SUEntityGetID` (the 32-bit id) *and*
  `SUEntityGetPersistentID`; confirm both against the downloaded header; **(b)** persistent IDs
  are stored in-file only for files saved by SketchUp versions that write them (≈2020+ for the
  full entity range) — the capture files were written by SketchUp 22–26 so this likely holds, but
  record it per file; **(c)** the contract's id is *path-qualified*, so the C side must compose
  the same path of entities in the same order. **Cheap pre-step**: grep the five staged captures
  for `persistent_id` coverage per record before declaring the 1:1 answer (needs the overview §3
  staging done first).
- **Right answer**: persistent IDs align 1:1 on tagged entities. **Fallback**: join on
  (dictionary fingerprint + geometry within tolerance); allowed, but then claim (c) is graded
  through a matcher whose own misses must be counted and reported — an unmatched entity is a
  finding, never silently dropped from the diff.

### H2 — Contract-v2 emission — ✅ **PASS** (16/16 models, 6/6 writers refused)

- **Method**: the headless collector emits contract v2 verbatim — same keys, same shapes, same
  units (m, world coordinates), `libraries` hoisted to model level, per-field size logging with
  the 1 MB warning rule active.
- **Right answer**: all five captures parse under whatever the harness already uses to load a
  capture; no schema drift; no field over the size warning without a recorded explanation.
  `tracker_data` and embedded filesystem paths are **absent** — asserted by a check, not by
  intention.

### H3 — Reconciliation against the offline baselines — ✅ **PASS** (14/14 gradeable; 2 have no baseline)

- **Method**: `check_extraction.py`, unchanged, on all five headless captures.
- **Right answer**: PASS on 5/5 — the same result the live captures earn. A firing check gets
  explained before it gets touched; if it fires on most of the five, suspect the *comparison*
  first (the reconciler's own history).

### H4 — Identity against the live captures — claim (c) — ✅ **PASS** (0 unexplained, 0.000000 mm)

- **Method**: canonical field-by-field diff, headless vs live, per model. Compare in three strata,
  each with its own equality rule: **attribute payloads** byte-equal (Marshal blobs included);
  **geometry** equal within a stated tolerance (1 mm linear — C and Ruby float reprs will differ;
  the tolerance is a limit on what the comparison may absorb, and the max observed deviation is
  reported even when it passes); **derived fields** (resolved hosts, composed transforms) equal
  under H1's join. Entity ordering normalised by the H1 key, never by shape.
- **Right answer**: **zero unexplained differences** on 5/5. Every difference lands in a named
  bucket — float repr, walk order, known G6 area semantics, a Spike-A PASS-WITH-CHANGES
  carry-over — or it is a defect, and defects get root-caused before this gate closes. ⚠ Grade all
  five; Adelphi passing alone counts for nothing.

### H5 — The unchanged translator, to the POC's numbers — ✅ **PASS** (545/545 · 239/239 · 99/99)

- **Method**: `dph_translator` on the five headless captures, on native CPython.
- **Right answer**: the acceptance table verbatim — 545/545 faces, 239/239 windows (every host by
  the capture's resolution route), 99/99 bridges, the three TFA figures, both U-value regressions
  in bounds, and the per-model report (omissions, degeneracies, predicted honeybee verdicts)
  matching the live-capture runs.

### H6 — HBJSON canonical equivalence — ✅ **PASS** (5/5, and the check is shown to still fail)

- **Method**: canonical compare of headless-capture HBJSON vs live-capture HBJSON per model, using
  the `byte_identity.py` canonicalisation (four `set`-ordered lists sorted; minted
  `properties.ph.*.identifier` uuids excluded — known per-export churn, measured harmless;
  normalise by name, never by shape).
- **Right answer**: canonically identical, 5/5. Same-size-different-hash is the signature of
  ordering — read the *shape* of any failure before the failure.

### H7 — Determinism — claim (d) — ✅ **PASS** (16/16 byte-identical; scoped — see results §4)

- **Method**: run the headless collector twice per model — from **two different CWDs with two
  different `--out` paths** (review item 8): this phase's own rules worry about embedded absolute
  paths, so determinism gets tested against exactly the thing that breaks it.
- **Right answer**: byte-identical (nothing in the headless path mints ids or iterates a set — if
  the captures differ at all, find out what is nondeterministic before trusting anything above).

### H8 — Cost, recorded not gated — ✅ **RECORDED** (11.8 s corpus, 717 MB peak, concurrency works)

Wall time and peak memory per model, because a server budget will eventually want them. Numbers
only, no threshold.

▶ **Revised (§2.2)**: Spike A already has wall-clock — ≈16 s for the whole 230 MB corpus, cost
tracking **unique entity count (~80–100k/s), not file size**. What is missing:

- **Per-model peak RSS**, which requires **one process per model** — the sweep's 851 MB is a
  process high-water mark across the whole run and cannot be attributed to any one file.
- **Concurrency**: two models open at once; `SUInitialize` thread/process safety.
- Bracket with **`2618 Lavoie` (146 MB)** and **`250708` (0.13 s)**, not Bluff Reach and Linde —
  the real spread is wider than this plan assumed.

### H9 — Unknown designPH versions ⭐ NEW (§2.2) — ✅ **PASS** (1.0.30 refused by name, nothing written)

The corpus now spans **designPH 1.0.30 → 2.4.0 BETA**, and 1.0.30 is structurally different.

- **Method**: run the collector against the 1.0.30 sample and the 2.4.0 BETA model; record what the
  version gate does.
- **Right answer**: it **names what it could not resolve**, whichever way it goes — read-with-report
  or refuse-with-reason. A silent partial capture fails this gate. ⚠ Precedent: the offline parser
  returned a clean zero on the 1.0.30 file and that stood for ten days
  (`DESIGNPH_FILE_FORMATS.md` §4.1).

## 5. Pass / fail

- **PASS** — H1 joins on persistent IDs; H2–H7 all land on their right answers with zero
  unexplained differences; **H9 reports rather than half-reads**.
- **PASS WITH CHANGES** — a fallback path holds (H1 matcher-join, or a G1/G6 carry-over) with its
  limitation stated and its residue reported. The results doc names exactly which claims are now
  inference.
- **FAIL** — any unexplained semantic difference in H4/H6, any acceptance number missed in H5, or
  nondeterminism in H7. Written down in full; a negative result here is precisely the thing that
  stops a bad service architecture cheaply.

Results: `RESULTS/HEADLESS-B_results.md`, one verdict line per gate with measured-vs-expected,
before any Spike C work (hard rule 7).

## 6. Deliverables

1. The headless collector under `planning/spikes/headless/` — still spike code, not product code;
   no packaging, no watcher, no server.
2. `RESULTS/HEADLESS-B_results.md`.
3. **Durable facts to `00_Context/`** — at minimum the entity-ID answer (it becomes pholio's
   identity foundation), any contract *notes* (per-device `face.area` semantics), and updates to
   [`SDK_RUNTIME.md`](../../00_Context/SDK_RUNTIME.md) /
   [`HEADLESS_VIABILITY.md`](../../00_Context/HEADLESS_VIABILITY.md). Contract v2 itself changes only
   through its §9 process — Spike B **proposes** (§2.2's four candidates), never edits.
4. A one-paragraph go/no-go recommendation for Spike C, with the H8 numbers attached.

## 7. Explicitly out of scope

- Deployment (macOS worker vs Wine/Linux vs on-user-machine) — Spike C, and partly a pholio ADR
  conversation (overview §5).
- Any translator or harness modification (findings about them are recorded and fixed on their own
  track, never inline here).
- Licensing resolution — L1–L3 continue alongside (overview §6); note only that a PASS here makes
  the AGPL §13 reframing *urgent* rather than hypothetical, since a working server-side path is
  what triggers it.
- The 14-model corpus beyond the five captured ones — there is no live ground truth for the other
  nine, so they prove nothing about claim (c); running them is Spike-C-adjacent burn-in, not
  identity evidence.

## 8. Method rules that bind hardest here

- **A comparison that fails on 100 % of the data is suspect, and the shape of the failure (sizes,
  ordering) is read before the failure.**
- **A canonicaliser that normalises too much is a check that cannot fail** — never sort geometry.
- **A tolerance is a limit on what a lossy step may absorb** — report what it absorbed even when
  it passes.
- **Validate a check against more than one model before trusting it to grade** — the matcher (H1
  fallback) and the diff (H4) are themselves new checks, subject to the same rule as the readers.
- **An unmatched or unexplained entity is a finding, never a dropped row.**

---

## Changelog

- 2026-08-28 — drafted, pre-Spike-A. Provisional by construction; H0 revision pass required before
  execution. (Originally scaffolded in `00_PH_Tools/design-ph-plus/`, moved here the same day.)
- 2026-08-28 — review pass folded in (`code-review.md` + its disposition table): H0's G6 row
  carries A's verbatim-record decision; H1 gains the three verified links (API names, in-file PID
  version caveat, path composition) and the capture-grep pre-step; H7 runs from two CWDs / two
  `--out`s.

---

## Changelog

- 2026-08-28 — drafted, pre-Spike-A, deliberately provisional.
- 2026-08-29 — **H0 revision pass done (§2.1)**, reconciled against `RESULTS/HEADLESS-A_results.md`.
  Two anticipated rows dissolved (G1's geometric fallback is not needed; G6's area bucket is empty),
  **H1 is pre-answered** by A's 545/545 + 239/239 id join, and three unanticipated constraints were
  folded in: the collector must assert it never saves (the attribute read mutates the in-memory
  model), H4 compares the **stored base64** payload rather than decoded Marshal, and
  `SUFaceGetNumOpenings` becomes a free second host cross-check. H8 inherits A's timings. The whole
  plan now carries A's third-party-SDK caveat.
- 2026-08-29 — **second revision (§2.2)**, from the `a7` capability sweep over 16 files. Three
  structural changes: the emission-side gates (H2/H3/H5/H7/H8) run on **all 16 staged models** while
  only H4/H6 need the five captures — which brings **Holmes's 42 named thermal-bridge edges**, the
  **146 MB** scale model and the **1.0.30** generation into scope; a **new H9** on unknown designPH
  versions; and H2's never-save assertion becomes a **structural** property rather than a check.
  Four contract-v3 candidates recorded for the §9 process (north correction, lat/long, tag names,
  model GUID) plus one deliberately-open question (windows carry an unread `DesignPH_dict`).
  H8 gains per-process memory and concurrency, and re-brackets on Lavoie/250708.
- 2026-08-29 — **EXECUTED. Verdict: PASS** (`RESULTS/HEADLESS-B_results.md`). H1-H7 and H9 green,
  H8 recorded. Four findings that each produced a plausible wrong answer on a real model first:
  the shipped `SURefType` puts `Face` at **11**, not the documented 9, and a host-face type check
  against the doc order rejects **every** glued host; `-0.0 == 0.0` hides a real difference from
  `==` and the check written to catch it could not fire; `entity_id` is **process-scoped**, which
  made a concurrency check fail on two plain parallel processes; and the collector was not running
  the version gate at all. Two new contract-v3 candidates (emit an exact zero unsigned; drop or
  exclude `entity_id`) join §2.2's four.
