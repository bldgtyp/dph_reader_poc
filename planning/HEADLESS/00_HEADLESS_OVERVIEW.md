# HEADLESS — can a service read a designPH `.skp` with no SketchUp?

DATE: 2026-08-28
STATUS: Active phase — Spike A Scoped, nothing has run
AUTHOR: Ed May (drafted by Claude)

---

## 1. The question

**Can a headless process — no SketchUp installed, no SketchUp license — read a designPH `.skp` well
enough to emit the POC's contract-v2 capture?**

If yes, the scrape becomes *passive*: a Dropbox watcher (the pholio model —
`~/Dropbox/bldgtyp-00/00_PH_Tools/pholio`) notices a saved `.skp`, a service reads it, and the
HBJSON pipeline the POC already verified runs server-side with no user involvement. For now assume
manual upload; the watcher is pholio's problem, not this phase's.

The POC proved every downstream step (`../POC/RESULTS/POC-5_results.md`): 545/545 classified faces,
239/239 windows, 99/99 thermal bridges across five real models, output verified in production
ph-navigator and Rhino/Grasshopper. What it did *not* prove is that the **capture device** can be
anything other than a Ruby collector inside a running SketchUp. That is this phase's whole subject.

## 2. Why the C SDK — and what was ruled out

The proposed route is the **SketchUp C SDK** ("SketchUp Desktop SDK") — already named as one of the
two supported routes in [`../../00_Context/DESIGNPH_FILE_FORMATS.md`](../../00_Context/DESIGNPH_FILE_FORMATS.md) §4.
It deserializes a `.skp` standalone — **the live model only** — and exposes entities, faces, loops,
edges, component definitions/instances, transforms, and typed attribute dictionaries. ⛔ **It is
NOT a free developer download** — superseded 2026-08-28 by Spike A, which found the SDK behind a
Trimble "Request Access" form with no public download and no reported turnaround
([`RESULTS/HEADLESS-A_results.md`](RESULTS/HEADLESS-A_results.md) §1,
[`../../00_Context/SDK_RUNTIME.md`](../../00_Context/SDK_RUNTIME.md) §1). Its *reference
documentation* remains fully public, which is how Spike A closed the glue question anyway. It is a
flat C API in a dylib, which should make it drivable
from CPython via ctypes with no compiled code.

**Ruled out — growing the offline binary parser** (`00_Context/tools/skp_attr_dump.py` and
friends) into the production reader, for three measured reasons:

1. **`model.dat` holds historical state.** The binary parse is a union over the file's history and
   cannot tell a live face from a deleted one; the corpus showed the counts diverging both ways
   (Bluff Reach 576 live vs 293 offline records; `250708` 2456 placements vs 1781 entities —
   `DESIGNPH_FILE_FORMATS.md` §4.3). A service silently exporting deleted geometry is the exact
   failure mode hard rule 4 (report, don't guess) exists to prevent.
2. **No geometry.** Face loops, world transforms, edge endpoints and the window→host glue graph are
   all undecoded, and the `.skp` geometry layout is undocumented and versioned.
3. **It is the unsupported route.** For a commercial service, Trimble's blessed API is the right
   legal posture. The binary parser stays what it is: reconnaissance and this phase's independent
   cross-check.

**Ruled out — running SketchUp on a server.** SketchUp has no headless mode; the Ruby API exists
only inside the running GUI app. So "would we need a SketchUp license on the server?" dissolves:
the SDK route never runs SketchUp and needs no seat. (The SDK's *own* EULA still needs reading —
§6, L1.)

**A strategic note on version economics**: the extension's constraint ran *backwards* — the oldest
SketchUp supported set the newest Pyodide available. The server reader runs *forwards*: always ship
the newest SDK, which reads every older file (the corpus writers span SketchUp 22–26). The entire
runtime section of [`../../00_Context/CONSTRAINTS.md`](../../00_Context/CONSTRAINTS.md) §2–3 —
Chromium 88, Pyodide 0.24.1, the 4 MB bridge, the 4–11 s freeze — does not exist on this path.
Full modern CPython, real honeybee, real PHX.

## 3. Evidence base

Everything the spikes grade against already exists and is measured
([`CONSTRAINTS.md`](../../00_Context/CONSTRAINTS.md) §8.1):

- **The corpus**: 14 models baselined key-by-key in
  [`../RESULTS/PHASE-0_corpus-baseline.md`](../RESULTS/PHASE-0_corpus-baseline.md).
- **Five live captures** (contract v2 JSON) in `poc/_private/fixtures/` — what the Ruby collector
  actually read inside SketchUp, from five real projects. **The ground truth.**
- **The harness and translator, unchanged**: `poc/tools/check_extraction.py`,
  `validate_output.py`, `byte_identity.py`'s canonicalisation discipline, and
  `poc/py/dph_translator`.
- ⚠ **Adelphi is the simplest model in the corpus and it masks bugs.** No gate in this phase may be
  graded on Adelphi alone.

⚠ **But this working copy does not hold that evidence base** (review item 1, verified and
strengthened 2026-08-28). This repo is the *cleaned export*: `poc/_private/` is absent,
`planning/RESULTS/baselines/` carries no `corpus_baseline.json` (phase-2/3 artifacts only), and
`_adephi_st_example_files/` holds only its `.index.md` — **no primary `.skp` at all**. The
canonical copies live in `~/Desktop/dph_plus_testing` (`poc/_private/fixtures/` — the five
captures + MANIFEST; `planning/RESULTS/baselines/corpus_baseline.json`; the primary corpus files);
the secondary corpus is live at `~/Dropbox/bldgtyp/*/08_DesignPH/` (13 files, confirmed).
**Prerequisite for Spike A**: stage copies into `planning/spikes/headless/_private/` (gitignored)
with a `MANIFEST.md` naming each source path — or run the spikes from the canonical repo. Note
`check_extraction.py:36` hardcodes the baseline path under the repo root; when staging, pass its
`--baseline` flag explicitly.

## 4. Rules in force

All ten hard rules in [`../../AGENTS.md`](../../AGENTS.md) apply unchanged — the ones that bind
hardest here: **never parse the `.ppp`** (1), **read-only** (2), **copy every corpus file before
the SDK touches it** (3), **report, don't guess** (4), **type-check every attribute read** (5),
**coalesce `*ID`/`*Auto`** (6), **results recorded before the next spike starts** (7).

Phase-specific additions:

- **Client data scratch lives in `planning/spikes/headless/_private/`** (gitignored,
  `MANIFEST.md`), and **nothing containing `tracker_data` or embedded filesystem paths leaves it**
  — a server-shaped reader makes CONSTRAINTS §1's personal-data finding *more* binding, not less.
- **Set every output location explicitly** — the `byte_identity.py` default-output incident
  (CONSTRAINTS §9) is the standing warning; every script here takes an explicit `--out` under
  `_private/` and refuses to run without it.
- **Durable facts flow to `00_Context/`, not results docs** — the SDK's capabilities and limits
  belong beside the other runtime records (likely a new `SDK_RUNTIME.md`, or a section in
  `DESIGNPH_FILE_FORMATS.md`); `RESULTS/` records what happened, `00_Context/` records what is
  true.

## 5. The spike sequence

| Spike | Question | Plan |
|---|---|---|
| **A** | Does the SDK *expose* the data? (glue query, typed attrs, edges, Marshal tables, live-vs-historical, transforms, version coverage) | [`HEADLESS-A_sdk-feasibility.md`](HEADLESS-A_sdk-feasibility.md) |
| **B** | Is a headless collector a *drop-in capture device*? (contract v2 out; identical to the five live captures; unchanged translator to the POC's numbers) | [`HEADLESS-B_contract-identity-gate.md`](HEADLESS-B_contract-identity-gate.md) — drafted pre-A, **its H0 revision pass runs first** |
| **C** | Where does it run? Ranked: macOS worker (native, boring, likely winner) · Wine + Windows SDK in a Linux container (only if Linux-only hosting is a hard requirement; gate = the whole Spike-B suite passing inside the container) · on the user's machine inside the pholio watcher (deletes the server-platform question *and* the biggest privacy exposure — only the ~500 KB capture travels, never the 17 MB `.skp`; runs against pholio ADR-019 posture B, so it is a pholio ADR conversation, not just a spike) | Not planned. Sketch only, blocked on B |

## 6. Licensing checklist (alongside, no code, resolves nothing without counsel)

- **L1 — Read the SketchUp SDK EULA.** It ships with the download (not published on the web pages);
  save a copy beside the SDK. Check: redistribution of SDK binaries with a shipped app/watcher, use
  in a commercial network service, any non-compete clause. Summarize into the counsel packet.
- **L2 — Reframe the AGPL question for server-side use.** The filed question
  ([`../RESULTS/PHASE-3_licence-question.md`](../RESULTS/PHASE-3_licence-question.md)) is about
  *conveying* an extension. A network service triggers **AGPL §13** (remote network interaction)
  instead — a different question, plausibly easier (the AGPL code is Ladybug's, unmodified and
  public; honeybee-ph/PHX are BLDGTYP's own), but not covered by the existing internal-use working
  assumption. Add to the same packet.
- **L3 — designPH posture: unchanged.** The user's own `.skp`, read via Trimble's official SDK; the
  `.ppp` stays unparsed; `tracker_data` never ships — and a server *ingesting uploads* should strip
  `tracker_data` and embedded paths at the door.

## 7. Relationship to the closed POC

This phase does not reopen the POC — its verdicts, contract freeze (v2, changes only through its
§9 process), and the V-0/pholio routing all stand. It *reuses* the POC's assets as ground truth and
adds one new claim to the POC's named set: the POC closed **(a)** translator identical across hosts
and **(b)** collector reads the same model the same way twice; this phase tests **(c)** a headless
collector reads the same model the live collector read, and **(d)** it does so deterministically.
