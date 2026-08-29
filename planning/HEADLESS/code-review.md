# HEADLESS planning docs — review notes

DATE: 2026-08-28
STATUS: Review of the three planning docs as drafted (pre-Spike-A). Items 1–4 fold in before
Spike A runs; 5–7 can wait for H0 / the results doc.
AUTHOR: Ed May (reviewed by Claude)

Reviewed: `00_HEADLESS_OVERVIEW.md`, `HEADLESS-A_sdk-feasibility.md`,
`HEADLESS-B_contract-identity-gate.md`, against the repo record (contract §2.1, collector source,
licence question, baseline counts, `.gitignore`). The docs' internal cross-references check out:
counts (1441/1359/82, 99, 16 hosts, 46/239), the 1 MB warning rule, the AGPL licence table
(honeybee/ladybug are AGPL-3.0), the path-qualified `persistent_id` id scheme, and the new
`_private` gitignore entry all verify.

---

## 1. The evidence base is not in this working copy (blocks both spikes as scheduled)

This is the cleaned export; `planning/RESULTS/baselines/corpus_baseline.json` does not exist here
(the `baselines/` dir only holds phase 2/3 artifacts), and `poc/_private/fixtures/` is absent
entirely. The harness hardcodes the baseline path (`poc/tools/check_extraction.py:36`), so H3 dies
on missing-file and G4/G5 have no expected answers to grade against. Overview §3 says "everything
the spikes grade against already exists" — true in the canonical repo, false here.

**Fix**: add a prerequisites note (copy the baseline JSON + the five captures + MANIFEST before
Spike A's G4/G5, or run the spikes in the canonical repo).

## 2. G1 names a C-API function that likely does not exist (HEADLESS-A:49)

`SUComponentInstanceGetAttachedToDrawingElements` is not a recognized name in the SU C API. The
glue relationship lives on the **face side**: `SUFaceGetOpenings` → `SUOpeningRef` →
`SUOpeningGetDrawingElement`, i.e. host→window, which is then inverted to window→host.

**Fix**: plan G1 as an inversion walk, verify the name against the downloaded header, and add the
trap that recurs: the openings list may conflate glued instances with cut-opening geometry, so the
gate must confirm each opening's drawing element is one of the 46 glued instances (the
`cuts_opening?` distinction can reappear at the C layer).

Note also: even on the SDK-native route the resolved host is a **derived** field, so B's H0 table
should treat host resolution as derived in every case, not only in the geometric fallback.

## 3. G4 has a named silent-failure risk it does not test for: NUL truncation of Marshal blobs

Marshal payloads almost certainly contain `0x00` bytes (symbol terminators alone guarantee it). If
the SDK returns attribute strings as NUL-terminated `const char*` (as `SUTypedValueGetString`
suggests) without an accompanying length, a ctypes reader stops at the first NUL and hands
`ruby_marshal.py` a truncated blob: confusing decode error at best, false-PASS on a partially
decoded table at worst.

**Fix**: G4 already has the perfect byte reference in-house. Diff the C-API-read blob byte-for-byte
against the same table read by the offline binary parser (`skp_decode_tables.py` / `ruby_marshal.py`
input). That one check settles byte-cleanliness, truncation, and encoding in one move, and its
answer feeds H4's "attribute payloads byte-equal" stratum directly.

## 4. A's binding order (pyslapi first) conflicts with G8 (HEADLESS-A:27-30, :129-136)

pyslapi is pinned to an old SDK generation (the Blender importer's build); an SDK older than the
file cannot open it. The corpus writers span SketchUp 22–26, so a working pyslapi tells you nothing
about version coverage and may fail on most of the corpus outright.

**Fix**: flip the order. ctypes against the newest SDK is the primary route; pyslapi is at most a
cross-check on old files and counts for nothing in G8.

## 5. H1's "right answer" has three unverified links (HEADLESS-B:84-97)

The contract does carry path-qualified persistent ids and the collector records `persistent_id` +
session-scoped `entity_id` (verified at `collector.rb:324-473`). But:

- (a) whether the downloaded SDK exposes persistent IDs at all (and under what name —
  `SUEntityGetID` at B:89 is likewise a name to verify; expect something like
  `SUEntityGetPersistentID`) is header-dependent;
- (b) persistent IDs are stored in-file only for files saved by SketchUp 2020+. The live captures
  came from SketchUp 2022 files so this likely holds, but record the file-version caveat;
- (c) the id is *path-qualified*, so the C side must compose the same path entities in the same
  order.

**Cheap pre-step**: grep the five captures for `persistent_id` coverage per record before
declaring the 1:1 answer.

## 6. G3's walk is ambiguous between definitions and placements (HEADLESS-A:76-78)

"Recursive walk over definitions/groups" — walking definitions counts each defined edge once;
walking the instance tree counts per placement. The 99 count came from the live walk over
placements.

**Fix**: state the walk explicitly (instance tree from `SUModelGetEntities`, expanding definitions
per occurrence), or Bluff Reach can come back 99-ish-but-wrong and the error is silent.

## 7. G6 does not say who computes `face.area` in the headless capture (HEADLESS-A:104-114)

The gate records SUFaceGetArea semantics, but H4 compares the *capture's* recorded areas. If the
headless collector records SUFaceGetArea while the live capture recorded Ruby's net value, 16 faces
flag per model with no named bucket unless G6's answer becomes that bucket.

**Fix**: decide in A. Either the headless collector records SUFaceGetArea verbatim and G6's
recorded semantics becomes the diff's named bucket, or it computes net area itself (loops minus
openings) to match Ruby. Carry the decision into B's H0.

## 8. Smaller items

- **H7**: add a path-independence run (twice, different `--out` and CWD). The phase's own rules
  worry about embedded paths; determinism should be tested against the thing that breaks it
  (HEADLESS-B:146-150).
- **A practical pre-gate is missing**: `lipo -info` on the SDK dylib first (if x86_64-only, the
  whole run needs `arch -x86_64` + an x86_64 Python, which changes the "keeps the whole spike in
  Python" story); quarantine attribute on the downloaded dylib; and a 30-minute G0 "initialize,
  open Adelphi, report version" boot check before any gate work.
- **G2 scope**: typed-attribute reads should name instances and model-level dicts too (windows
  carry their dicts on the instance), not just faces (HEADLESS-A:63-69).
- **Overview §5**: "pholio ADR-019 posture B" — posture B is real in pholio's record; the exact
  ADR number was not confirmed from here. Soften to "pholio's posture-B decision" unless the
  number is verified.

---

## Verdict

Nothing reopens the phase structure: A→B→C sequencing, the frozen contract, claim (a)–(d) naming,
and the licensing checklist L1–L3 are all sound. Items 1–4 fold in before Spike A runs; 5–7 can
wait for H0 / the results doc, but writing them down now is cheaper than rediscovering them
mid-gate.

---

## Disposition (2026-08-28, second-pass verification — incorporated into the plan docs)

| Item | Verdict | Action |
|---|---|---|
| 1 | ✅ **Confirmed, and understated** — measured: `poc/_private/` absent, no `corpus_baseline.json`, and `_adephi_st_example_files/` holds *only its `.index.md`* — the primary `.skp` is missing from this working copy too. Canonical copies verified present in `~/Desktop/dph_plus_testing`; secondary corpus live (13 files) | Prerequisites block added to overview §3 (stage into `planning/spikes/headless/_private/` + MANIFEST, or run from the canonical repo; use `check_extraction.py --baseline`) |
| 2 | ❌ **Headline wrong.** `SUComponentInstanceGetAttachedToDrawingElements` **exists** — verified against the published C API reference (SketchUp 2018, API 6.0), instance→host, exactly as G1 planned. ✅ The useful half survives: `SUFaceGetOpenings`/`SUOpeningRef` is real and is now G1's host-side cross-check, with the cut-vs-glued conflation trap. ❌ "Host is a derived field in every case" also rejected: an instance-side read is a stored fact, same as Ruby's `glued_to`; only the geometric fallback is derived | G1 rewritten: name marked verified, host-side cross-check added |
| 3 | ✅ On the mark — NUL truncation via `c_char_p` is the real ctypes hazard; the byte-diff against the offline parser is the right proof | Folded into G4 (length-aware string API + byte-diff) |
| 4 | ✅ On the mark — pyslapi's SDK pin conflicts with G8's newest-SDK premise | Binding order flipped in A §2; pyslapi demoted to a curiosity |
| 5 | ✅ Mostly right — both `SUEntityGetID` and `SUEntityGetPersistentID` are expected names; the in-file PID version caveat and path-composition point are real | Folded into H1 as links (a)/(b)/(c) + the grep pre-step (depends on item 1's staging) |
| 6 | ✅ On the mark — matches the repo's own placements-vs-entities scar | G3 now states the counting basis (entities, deduplicated — the live captures' basis) |
| 7 | ✅ On the mark, and decided now: the collector records the SDK value **verbatim** (recomputing net locally would re-implement half a library's rule); G6's measured semantics becomes H4's named bucket | Folded into G6 + B's H0 table |
| 8a (H7 path-independence) | ✅ Cheap and pointed at the phase's own worry | Folded into H7 (two CWDs, two `--out`s) |
| 8b (boot pre-gate) | ✅ Practical | Added as **G0** (lipo/arch, quarantine xattr, init+open+version) |
| 8c (G2 scope) | ✅ Correct — windows carry dicts on the instance | G2 now names all four carrier types |
| 8d (ADR-019 softening) | ❌ **Rejected** — ADR-019 = "Dropbox GO, posture B" is verified verbatim in `pholio/AGENTS.md`; the citation stands as written | none |
