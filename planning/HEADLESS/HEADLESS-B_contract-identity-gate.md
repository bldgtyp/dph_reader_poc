# HEADLESS-B (Spike B) — the contract-v2 identity gate: same model, same capture, same HBJSON

DATE: 2026-08-28
STATUS: Scoped — provisional. **Blocked on Spike A** (hard rule 7), and §2's revision pass is the
mandatory first step: this plan was written *before* Spike A ran and must be reconciled against
`RESULTS/HEADLESS-A_results.md` before anything here executes.
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

| Spike-A finding | What it changes here |
|---|---|
| **G1 fallback** (no glue query; geometric host resolution) | H4/H5's aperture claims weaken from "stored fact" to "inference with a stated limit" — the capture must then *report* each host resolution's residual (the projection-absorbs-the-bug rule), and the identity diff must compare resolved hosts as a derived field, not a read one |
| **G6** (`SUFaceGetArea` gross, not net) | the reconciler's area cross-check expectations flip on the 16 host faces. A's G6 decision is already made: the collector records the SDK value **verbatim**, and the measured semantics becomes H4's named bucket. May still need a contract *note* (not a schema change) recording which semantics `face.area` carries per capture device |
| **Binding route** (pyslapi vs ctypes) | tooling only; no gate changes |
| **Entity-ID semantics** (whatever the G-work reveals about `SUEntityGetID` / persistent IDs) | H1's join strategy — see below |
| **Any gate that closed PASS WITH CHANGES** | carry its stated limitation into the matching H-gate explicitly, so a firing check can be attributed |

Record the revision as a dated changelog block at the bottom of this file. An unrevised plan
executing after Spike A is the "believed once written down" failure mode the POC paid for twice.

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

§2, done and recorded. Nothing below starts first.

### H1 — Entity identity: the join key

Comparing two captures of one model needs a way to say *this face here is that face there*. The
live captures carry the Ruby side's entity identifiers; whether the C SDK's IDs (`SUEntityGetID`,
persistent IDs) coincide with them is unknown until measured — and pholio's identity rule (ids
come from the capture device, never minted per export) makes this the gate that decides what the
*service's* stable IDs will be.

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
