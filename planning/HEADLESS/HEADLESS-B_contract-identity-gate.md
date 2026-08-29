# HEADLESS-B (Spike B) — the contract-v2 identity gate: same model, same capture, same HBJSON

DATE: 2026-08-28
STATUS: ▶ **Unblocked; H0 revision pass DONE 2026-08-29 (§2.1). Nothing else has run.**
Spike A passed ([`RESULTS/HEADLESS-A_results.md`](RESULTS/HEADLESS-A_results.md)) and pre-answered
more of this plan than it anticipated — **H1 is effectively already closed** (§2.1). ⚠ Spike A ran
on a **third-party SDK build**, so everything here inherits that provisional footing.
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

## 3. What already exists (reused, not rebuilt)

- **The frozen contract**: v2 — changes go through the POC contract's §9 process only
  ([`../POC/CONTRACT_extraction-json.md`](../POC/CONTRACT_extraction-json.md)); the frame/glazing
  libraries are hoisted to the model-level `libraries` block; the 1 MB payload warning rule
  applies.
- **The five live captures** in `poc/_private/fixtures/` — the ground truth for claim (c).
- **The harness, unchanged**: `poc/tools/check_extraction.py` (capture ↔ offline-baseline
  reconciliation — already corrected for the three false-alarm classes: dict-carriers vs
  area-group carriers, placements vs entities, `descName`/`descNameAuto` override pairs),
  `poc/tools/validate_output.py` (published honeybee-schema, separate interpreter), and
  `poc/tools/byte_identity.py`'s canonicalisation discipline (sort the four `set`-ordered honeybee
  lists, normalise by name **never by shape** — a canonicaliser that sorts geometry makes a wall
  equal its mirror).
- **The translator, untouched**: `poc/py/dph_translator`. Spike B modifies nothing in it; if a
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

### H1 — Entity identity: the join key

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

### H2 — Contract-v2 emission

- **Method**: the headless collector emits contract v2 verbatim — same keys, same shapes, same
  units (m, world coordinates), `libraries` hoisted to model level, per-field size logging with
  the 1 MB warning rule active.
- **Right answer**: all five captures parse under whatever the harness already uses to load a
  capture; no schema drift; no field over the size warning without a recorded explanation.
  `tracker_data` and embedded filesystem paths are **absent** — asserted by a check, not by
  intention.

### H3 — Reconciliation against the offline baselines

- **Method**: `check_extraction.py`, unchanged, on all five headless captures.
- **Right answer**: PASS on 5/5 — the same result the live captures earn. A firing check gets
  explained before it gets touched; if it fires on most of the five, suspect the *comparison*
  first (the reconciler's own history).

### H4 — Identity against the live captures — claim (c)

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

### H5 — The unchanged translator, to the POC's numbers

- **Method**: `dph_translator` on the five headless captures, on native CPython.
- **Right answer**: the acceptance table verbatim — 545/545 faces, 239/239 windows (every host by
  the capture's resolution route), 99/99 bridges, the three TFA figures, both U-value regressions
  in bounds, and the per-model report (omissions, degeneracies, predicted honeybee verdicts)
  matching the live-capture runs.

### H6 — HBJSON canonical equivalence

- **Method**: canonical compare of headless-capture HBJSON vs live-capture HBJSON per model, using
  the `byte_identity.py` canonicalisation (four `set`-ordered lists sorted; minted
  `properties.ph.*.identifier` uuids excluded — known per-export churn, measured harmless;
  normalise by name, never by shape).
- **Right answer**: canonically identical, 5/5. Same-size-different-hash is the signature of
  ordering — read the *shape* of any failure before the failure.

### H7 — Determinism — claim (d)

- **Method**: run the headless collector twice per model — from **two different CWDs with two
  different `--out` paths** (review item 8): this phase's own rules worry about embedded absolute
  paths, so determinism gets tested against exactly the thing that breaks it.
- **Right answer**: byte-identical (nothing in the headless path mints ids or iterates a set — if
  the captures differ at all, find out what is nondeterministic before trusting anything above).

### H8 — Cost, recorded not gated

Wall time and peak memory per model (Bluff Reach and Linde bracket the corpus), because a server
budget will eventually want them. Numbers only, no threshold.

## 5. Pass / fail

- **PASS** — H1 joins on persistent IDs; H2–H7 all land on their right answers with zero
  unexplained differences.
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
   the SDK record Spike A opened. Contract v2 itself changes only through its §9 process — Spike B
   proposes, never edits.
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
