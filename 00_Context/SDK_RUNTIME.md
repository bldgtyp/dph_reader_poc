# The SketchUp C SDK as a runtime — what it is, what it exposes, and how to get it

DATE: 2026-08-28 · first written during HEADLESS Spike A
STATUS: ✅ **Behaviourally verified on five real designPH models** (2026-08-29, Spike A: 545/545
faces, 239/239 windows, 99/99 edges, 63/63 Marshal tables, 15/15 files opened) — and ✅ **a full
contract-v2 capture reproduces those live captures with 0 unexplained differences** (Spike B, same
day: worst geometry deviation **0.000000 mm**, canonically identical HBJSON 5/5, 16 models emitted
in 11.8 s). §4e-§4g. ⚠ **On a third-party SDK build, not Trimble's** — §1. Re-run against the
official SDK before trusting it commercially.

Sits beside [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) (SketchUp as a *host*, the Ruby API, the
`HtmlDialog`) and covers the other route: reading a `.skp` with **no SketchUp installed and no
SketchUp seat**. Written for the HEADLESS phase
([`../planning/HEADLESS/`](../planning/HEADLESS/.index.md)).

---

## 1. ⛔ Availability — the thing to know before planning anything

**The SketchUp and LayOut C SDKs are no longer a public download.** Verified live 2026-08-28 while
signed in on a Trimble developer account: `https://extensions.sketchup.com/sketchup-sdk` renders a
holding page reading *"They are not available for public download at this time"* with a **Request
Access** form and no download list.

- The Extension Warehouse SPA carries a **`SDK_HOLDING_PAGE`** feature toggle, currently on in
  production, switching between the real download table and that holding page.
- The download API is authenticated and issues **signed URLs**: `GET /api/developers/sdkBuilds`
  → 401; `getSdkBuildUrl(id)` → `{download_url}`. **There has never been a guessable static URL.**
  Wayback holds `SDK_Mac_2019-0-752.zip`-shaped entries, but every "capture" is a ~1 KB SPA stub.
- Not in Homebrew, conda-forge, vcpkg or Debian — checked against each project's own API.
- Reported on the SketchUp developer forum (*"SketchUp C SDK 2026 macOS unavailable"*, thread
  346672 — **reported, not verified here**): gated since before 2026-05-05, form working by
  2026-05-14, purpose stated as understanding who uses the C SDK; **multiple developers report no
  response as of 2026-08-16**, with no SLA and no confirmation email.

⚠ **`extensions.sketchup.com` returns HTTP 200 with an identical 4387-byte SPA shell for every
path, valid or nonsense.** Status-code probing against that host is worthless — check the response
*size and content*. (The doxygen tree under `/developers/sketchup_c_api/` is a different handler and
does serve real pages.)

⚠ A **third-party re-host** of a universal2 macOS `SketchUpAPI.framework` plus the full public
header tree exists and downloads unauthenticated
(`martijnberger/pyslapi` release 0.24, `sketchup_importer_0.24_macOS.zip`, 36 MB; built ~April 2025,
Xcode 15.4, min macOS 11.7, claims files up to SketchUp 2025.1). **It is a personal redistribution
of a proprietary EULA-gated binary, not an authorized mirror.** Recorded because it is the only
route that works today; whether it may be used is a licensing decision, not a technical one.
**Ed's call, 2026-08-28: both routes in parallel** — file Trimble's form, and meanwhile run Spike A's
gates on this build as *feasibility-only* evidence. Everything in §3-§4c was measured that way and
must be re-run against the official SDK before it is trusted commercially.
⚠ The zip flattens the framework's `Frameworks` symlink, so `dlopen` fails on
`@rpath/libCommonUnits.dylib` until `ln -s Versions/Current/Frameworks Frameworks` is restored.
⚠ The much-linked **RedHaloStudio fork is Windows-only** in every current release — its macOS
assets are gone. The working macOS build is on the *upstream* repo.

**Consequence for L1** (read the SDK EULA): **it cannot be started.** The EULA ships inside the
download that nobody can obtain.

## 2. The documentation is public even though the binary is not

Full doxygen reference, no login:
`https://extensions.sketchup.com/developers/sketchup_c_api/sketchup/`

**1231 `SU*` functions across 89 struct pages** plus free-function headers (harvested and re-checkable
with `planning/spikes/headless/a1_capi_surface.py`). This is what made it possible to answer *"does
the API expose the glue relationship at all?"* with the binary blocked — a documentation answer, and
labelled as one.

⚠ **Two doxygen layouts, and harvesting one of them alone lies.** Struct member functions render in
the member table's right-hand cell; **free functions render as plain links on the header page**.
`SUInitialize`, `SUTerminate` and `SUGetAPIVersion` live in `initialize.h` and belong to no struct —
a struct-only scrape reports them ABSENT, which they are not.

## 3. What the API exposes — ✅ all of the following now measured, not inferred

### 3.1 ★ The glue relationship IS queryable — both directions

This is the fact the whole headless route turns on, because `glued_to` is the **only** thing that
identifies a window host ([`CONSTRAINTS.md`](CONSTRAINTS.md) §4):

```c
// instance → host.  @since SketchUp 2018, API 6.0
SUResult SUComponentInstanceGetAttachedToDrawingElements(
    SUComponentInstanceRef instance, size_t len, SUDrawingElementRef elements[], size_t* count);
SUResult SUComponentInstanceGetNumAttachedToDrawingElements(...);

// host → openings, the cross-check
SUResult SUFaceGetNumOpenings(SUFaceRef face, size_t* count);
SUResult SUFaceGetOpenings(SUFaceRef face, size_t len, SUOpeningRef openings[], size_t* count);
SUResult SUOpeningGetNumPoints(...);  SUResult SUOpeningGetPoints(...);
```

⚠ **`SUComponentInstanceGetAttachedInstances` points the other way** — things glued *to* this
instance. The two names are one word apart and mean opposite things.

✅ **Measured: 239/239 windows across five real models resolve to a host face this way**, and the
distinct-host counts match the live SketchUp captures exactly (16/14/17/18/16). The geometric
fallback the plan held in reserve is not needed.

✅ **And `SUFaceGetNumOpenings` corroborates independently** — > 0 on exactly those 81 host faces.
Unlike `cuts_opening?` (true on all 46 Adelphi windows) and `loops.size > 1` (true on 1 of 81), this
one is a real host test. See §4a.

### 3.2 ★ Both id flavours the contract needs

```c
SUResult SUEntityGetPersistentID(SUEntityRef entity, int64_t* pid);   // STABLE across sessions
SUResult SUEntityGetID(SUEntityRef entity, int32_t* id);              // session-local
```

**This is the most load-bearing find for a drop-in headless collector.** The POC's contract-v2 `id`
is `([kind] + ancestor persistent_ids + [own persistent_id]).join("_")`
(`poc/ext/dph_plus_poc/collector.rb:597`), so a C-SDK reader can reproduce byte-identical ids.
⚠ The contract's separate `entity_id` field is the **session-local** `entityID` and must never be
compared across captures.

### 3.3 The rest, by concern

| Concern | Functions | Note |
|---|---|---|
| boot | `SUInitialize` · `SUTerminate` · `SUGetAPIVersion` | free functions, `initialize.h` |
| open a file | `SUModelCreateFromFile` · `…WithStatus` · `SUModelCreateFromBuffer…` | the `WithStatus` variants report *how* a file was loaded |
| typed attributes | `SUEntityGetAttributeDictionary(ies)` · `SUAttributeDictionaryGetValue`/`GetKeys`/`GetName` · `SUTypedValueGetType`/`GetString`/`GetInt32`/`GetDouble`/`GetBool` | the type tag is available, so hard rule 5 is satisfiable |
| model-level dicts | `SUModelGetAttributeDictionary(ies)` · `SUModelGetNumAttributeDictionaries` | where designPH's Marshal tables live |
| strings | `SUStringGetUTF8Length` + `SUStringGetUTF8` | length-aware; returns raw bytes. ⚠ But see §4b — designPH's tables are base64, so the NUL hazard this guards against does not arise on that path |
| traversal | `SUModelGetEntities` · `SUEntitiesGet{Faces,Edges,Instances,Groups}` (+ `GetNum…`) · `SUComponentInstanceGetDefinition` · `SUComponentDefinitionGetEntities` · `SUGroupGetEntities` | ⚠ groups are a **separate** container from instances; a walk that handles only instances loses group-nested geometry |
| geometry | `SUFaceGetOuterLoop` · `SUFaceGetNumInnerLoops`/`GetInnerLoops` · `SULoopGetVertices` · `SUVertexGetPosition` · `SUFaceGetNormal`/`GetPlane` | |
| area | `SUFaceGetArea` · **`SUFaceGetAreaWithTransform`** | ⚠ **use the second** — the first takes no transform and is the LOCAL area. §4.3 |
| transforms | `SUComponentInstanceGetTransform` · **`SUGroupGetTransform`** · `SUTransformationMultiply` | ⚠ two separate getters, same reason as traversal |
| persistent lookup | `SUModelGetEntitiesByPersistentIDs` · `SUModelGetEntitiesOfTypeByPersistentIDs` · `SUModelGetInstancePathByPid` | a direct pid→entity index, useful for reconciling against a live capture |
| version | `SUModelGetVersion` (enum `SUModelVersion`) · `SUModelGetGuid` · `SUModelGetStatistics` | ⚠ **`SUModelGetVersionString` does not exist** — the enum is the coarser answer available |

## 4. ⛔ The five traps that make a C-SDK reader wrong while looking right

Every one of these produced a **plausible number on a real model** before it was caught.
`planning/HEADLESS/RESULTS/HEADLESS-A_results.md` §3 has the accounting for 4.1-4.4;
`HEADLESS-B_results.md` for 4.5.

### 4.1 `SUEntityGetAttributeDictionary` is a get-or-CREATE

Its own header: *"If a dictionary with the given name does not exist, one is added to the entity."*
**A function named `Get` writes**, into `DesignPH_dict` — the namespace hard rule 2 forbids
touching. Using its success as a tagged-test reports every entity as tagged (8037 faces instead of
1441 on Adelphi).

⛔ **A C-SDK reader mutates the in-memory model as a side effect of reading it.** Hard rule 2 holds
only because nothing calls `SUModelSaveToFile`. **"Never save an opened model" is a load-bearing
invariant for any headless service.**

### 4.2 …and the read-only enumeration silently under-reports

`SUEntityGetNumAttributeDictionaries` returns **1** while `SUEntityGetAttributeDictionaries` returns
**`SU_ERROR_NONE` with count 0** and an unset handle, for dictionaries that exist with keys. Both
report success. Cost: **118 of 446** tagged faces on Wellington, **731 of 1791** on Linde, **716 of
1781** on 250708 — and **0 on Adelphi and Bluff Reach, which mask it entirely**.

✅ **The only complete predicate is: ask by name, then require `num_keys > 0`.** An absent dictionary
comes back freshly created and empty, so the key count separates real data from the side effect.

### 4.3 `SUFaceGetArea` takes no transform, so it is the LOCAL area

Ruby's collector calls `face.area(transform)` — the **world** area. On unscaled models the two agree
and the difference is invisible; Adelphi has a scaled container and **14 of 82 faces came out wrong**
by a constant 2.96× in the subtracted amount. ✅ Use **`SUFaceGetAreaWithTransform`** — the library's
own function, not a local rescale.

### 4.4 A published name is not a signature

`SUModelGetVersion(model, int* major, int* minor, int* build)` — four arguments, not the enum getter
its name suggests. The wrong declaration returned a *believable* 22 on Adelphi and segfaulted on the
next model. `SUEntityGetType` returns `enum SURefType` directly and is not `SU_RESULT` at all.
✅ `planning/spikes/headless/a3_header_audit.py` checks every declaration against the shipped headers.

⚠ Harvesting the doxygen struct pages alone reports `SUInitialize`/`SUTerminate`/`SUGetAPIVersion`
as absent — they are **free functions in `initialize.h`** and belong to no struct.

### 4.5 A published *enum* is not the shipped enum either

`SURefType` in the doxygen reference puts **`Face` at 9**. The API 13.0 header that ships with the
framework inserts `Environment` and `Environments` at 8 and 9, so **`Face` is 11** and every member
after `Edge` sits two higher.

⛔ **A host-face type check written against the documented order rejects every glued host on every
model** — 0 of 239 — which reads exactly like "the glue query does not work", and it is not. The
symptom appears only in a reader that *checks the type*; Spike A's gates never did, so no Spike A
result changes.

✅ `sdk.py` now **parses both enums out of the framework's own headers** at load time and fills the
module maps in place, so no importer can hold a stale copy, and calling code asks
`sdk.ref_type("Face")` rather than writing a literal. Same rule as 4.4, one level down: check
against the shipped headers, never against a doc page.

## 4a. ★ What the SDK gives that the Ruby API did not

- **`SUFaceGetNumOpenings` is a real host-side test.** It is > 0 on exactly the 81 distinct host
  faces across the corpus, and `gross − net` equals the summed rough-opening areas precisely. Ruby's
  nearest equivalent, `loops.size > 1`, is true on **1 of 81**. This is a second, independent host
  check the Ruby collector never had. ⚠ Openings and inner loops are different: one Wellington face
  has a genuine inner loop and no opening.
- **`SUEntityGetPersistentID`**, so a headless capture can reproduce the collector's path-qualified
  ids byte-for-byte.

## 4b. designPH's Marshal tables are BASE64, not raw binary

★ Every model-level table value begins `BAh` — base64 for Marshal's `\x04\x08` (hence the
collector's `MARSHAL_PREFIX = "BAh"`). **The NUL-truncation hazard the whole G4 gate was designed
around does not exist on this path**: the transport is ASCII with no NULs, so a `c_char_p` read
would have worked. Keep the length-aware read anyway — it is right in general — but do not plan
around a hazard that measurement retired. 63/63 tables decode across the corpus.

## 4c. Performance: walk definitions, not placements

Adelphi is 1441 tagged face entities behind **1,023,558 face placements**; Wellington's placement
walk is 4,255,761 nodes and does not finish in Python. Enumerating each **definition** once is both
the correct entity basis and ~1000× faster, and the two walks were verified to cover an identical
entity set. Gates needing world coordinates use a placement walk **pruned** to subtrees containing
tagged geometry — ~0.3 % of the model. Measured cost with pruning: **≈3-4 s per model** for 3-11 MB
files.

## 4d. Measured capability sweep (2026-08-29, 16 corpus files)

`planning/spikes/headless/a7_capability_probe.py`. The decision-shaped reading of all of this is
[`HEADLESS_VIABILITY.md`](HEADLESS_VIABILITY.md); this is the reference table.

| Capability | Call | Measured on the corpus |
|---|---|---|
| **File-format reach** | `SUModelCreateFromFileWithStatus` | **16/16 open**, written by SketchUp **8.0.1 → 26.1.188**, on one API-13.0 SDK |
| **Newer-file warning** | `SUModelLoadStatus` | ⚠ `Success_MoreRecent` **never fired**, not even for a SketchUp 26 file on a 2025 SDK. Capture it; do not depend on it |
| **Whole-model census** | `SUModelGetStatistics` | one call, no walk — Edge/Face/ComponentInstance/Group/Image/ComponentDefinition/Layer/Material. ⚠ **PLACEMENTS**, not entities |
| **Model identity** | `SUModelGetGuid` | present on all 16; **stable across repeated reads** (3/3) but **differs between a file and its own `~` backup** — a per-*save* identity |
| **Tags / layers** | `SUDrawingElementGetLayer` → `SULayerGetName` | readable per entity. Holmes carries **42** distinct tags on non-designPH faces; Linde **7** on designPH faces |
| **Geolocation** | `SUModelIsGeoReferenced` → `SUModelGetLocation` → `SULocationGetLatLong` | real lat/long on **5 of 16**. ⚠ Adelphi reports `geo_referenced = true` with **(0, 0)** |
| **Solar orientation** | `SUModelGetNorthCorrection` | non-zero on **7 of 16** (25.0007° · 44.8647° · 350.6339° · 359.6239° …). Unset reads `-0.0` |
| **Display units** | `SUModelGetUnits` | Meters or Inches across the corpus — cosmetic; geometry is always internal inches |
| **Write surface** | `SUModelSaveToFile`, `SUEntityAddAttributeDictionary`, `SUAttributeDictionarySetValue`, … | **6/6 present.** Never called. Bounds a future authoring path — and is why §4.1 is dangerous |

### 4d.1 The cost model

**Cost tracks unique entity count (~80–100k entities/second), not file size.** Whole corpus —
16 files, 230 MB — in **≈16 s**.

| model | MB | definitions | open | walk | total |
|---|---:|---:|---:|---:|---:|
| `2618 Lavoie` | **146.2** | 261 | 1.17 s | 1.44 s | **3.93 s** |
| `2414 Bluff Reach` | 10.8 | 249 | 0.60 s | 1.28 s | 2.52 s |
| `2536 Holmes` | 5.9 | **613** | 0.36 s | 0.78 s | 1.45 s |
| `adelphi-designph` | 3.2 | 101 | 0.14 s | 0.10 s | 0.36 s |
| `250708` | 4.2 | 101 | 0.07 s | 0.03 s | 0.13 s |

⚠ **File size is a poor predictor**: Lavoie is 14× Bluff Reach's bytes for 1.6× the time (most of
those bytes are 318 materials and their textures, which a designPH read never touches). Holmes is the
opposite case — 5.9 MB and 2,124 face *placements*, but **613 definitions**, costing more than models
with a thousand times its placement count. For admission control use `SUModelGetStatistics`, not
`stat()`.

⚠ **Peak RSS reached 851 MB across the sweep, and that is NOT a per-model figure.** `ru_maxrss` is a
process high-water mark and the whole sweep ran in one process, so the number says "the run peaked
here", not "Lavoie costs this". One process per model would answer it, and a server budget needs
that. Recorded as unmeasured rather than estimated.

## 4e. ★ A full contract-v2 capture, and what it costs (Spike B, 2026-08-29)

Spike A proved the SDK *exposes* the data. Spike B emitted the frozen contract from it and compared
against the live SketchUp captures: **0 unexplained differences on 5/5 models, worst geometry
deviation 0.000000 mm**, and the untouched translator then produced **canonically identical
HBJSON**. [`../planning/HEADLESS/RESULTS/HEADLESS-B_results.md`](../planning/HEADLESS/RESULTS/HEADLESS-B_results.md).

**The structure that makes it affordable.** The contract's `counts` are **placement** counts
(Adelphi's `faces_walked` is 1,023,558) while every attribute is a property of the **entity**.
Reading attributes per placement does not finish. The shape that works:

1. index every container once — the model's top level plus each component and group *definition* —
   reading every attribute exactly once per entity;
2. expand `faces_walked` and the untagged-tag histogram over the container **DAG** with memoisation
   (a definition's children repeat once per placement of it), never over the placement tree;
3. run a placement walk **pruned** to containers whose subtree holds tagged geometry, for the ~0.3 %
   that needs world coordinates.

⚠ **Cost tracks neither file size nor placements.** `2618 Lavoie` is 139 MB and reads in 2.49 s;
`2414 Bluff Reach` is 10.3 MB with **2.5 M placements** and takes 1.73 s; `2536 Holmes` has **900**
placements and takes 1.06 s. What it tracks is the **entity enumeration** — every face, edge and
instance of every definition, each with an attribute-dictionary probe. Holmes carries 613 component
definitions and ~206k edge entities.

| | |
|---|---|
| whole 16-model corpus (230 MB) | **11.8 s**, one process per model |
| slowest single model | **2.49 s** (`2618 Lavoie`, 139 MB) |
| heaviest peak RSS | **717 MB** (same) · process floor with the SDK loaded and no model open: **63 MB** |
| ⚠ share of read time spent in `SUModelCreateFromFile` | **43 %** across eight models (35–59 %) |
| ⚠ reading the model's designPH version stamps, once open | **0.000 s** — free |
| ⛔ memory returned by `SUModelRelease` | **none** — see below |
| two models open at once in one process | ✅ works, 761 MB peak |
| two processes in parallel | ✅ works |
| two threads in one process | ✅ works, no errors — ⚠ **one observation, not a thread-safety proof** |

⚠ Per-model peak RSS **requires one process per model**. `ru_maxrss` never comes down, so the
capability sweep's 851 MB is "the run peaked here", not "this model costs that".

⛔ **And that is not only a measurement artefact — the memory really is not released.** Live RSS
through one process, reading five models and closing each:

```
SDK loaded, no model open                              63 MB
2618 Lavoie      open  631 MB   read  715 MB   close  571 MB
2414 Bluff Reach open  721 MB   read  724 MB   close  723 MB
2523 Wellington  open  725 MB   read  727 MB   close  726 MB
2605 MacDonough  open  726 MB   read  726 MB   close  726 MB
adelphi-designph open  726 MB   read  726 MB   close  726 MB
```

The memory is in the **open** (63 → 631 MB), not the walk (631 → 715 MB) — the same shape as the
timing. ✅ It is *not* an unbounded leak: repeated reads of one model plateau (296 → 295 → 407 → 407
→ 407 MB), and the process settles flat again after a large model. It ratchets to a high-water mark
and stops. ⚠ Two heavy models held open together are close to **additive** (63 → 631 → 798 MB, and
973 MB after reading both), not shared.

★ Consequence for any service: **a persistent worker converges on the peak of the heaviest model it
has ever seen, plus fragmentation, and holds it for the life of the process.** Size for that, or
recycle. `HEADLESS_VIABILITY.md` §2.4 and §5.

## 4f. ⚠ Two values that are not stable, and both mattered

**`SUEntityGetID` is scoped to the PROCESS, not to the model.** Reading thirteen other models first
moves every one of Adelphi's 128 ids and grows the capture by 384 bytes. Contract v2 already calls
`entity_id` session-scoped and a debugging aid only, so this is the contract being right — but the
operational consequence is concrete: ⛔ **a watcher that hashes captures to detect change must
exclude `entity_id`, or re-read in a fresh process.** Two captures of one file are otherwise
byte-identical, including across working directories and relative-vs-absolute path arguments.

⚠ It is also what made a concurrency check report a mismatch on **two plain parallel processes**,
where nothing concurrent was happening at all.

**Signed zero.** The C arithmetic reaches an exact zero from below where Ruby reaches it from
above — **72 coordinates across the corpus, always headless `-0.0` against live `0.0`**. `-0.0 ==
0.0` is `True`, so field-by-field comparison absorbs it silently; `json.dumps` writes two different
tokens, so hashes disagree with no locatable difference. A vertex at `-0.0 m` is the same vertex,
and this is below every tolerance in the project — it matters only for hashing, which is exactly
what change detection is.

## 4g. The never-save invariant, made structural

§4.1 means reading mutates the in-memory model, so hard rule 2 survives only because nothing writes
the file back. An *intention* not to save is not a check. The reader therefore wraps the loaded
library so it can only resolve symbols the binding **declared**, and the binding declares no writer:
the binary exports `SUModelSaveToFile`, `SUModelSaveToFileWithVersion`,
`SUEntityAddAttributeDictionary`, `SUAttributeDictionarySetValue`, `SUModelFixErrors` and
`SUModelMergeCoplanarFaces`, and the read-only handle refuses **6 of 6**. Adding a writer becomes a
visible edit to the signature table rather than an accident.

## 5. Practical hazards recorded in advance

- **`lipo -info` the dylib first.** An x86_64-only build forces `arch -x86_64` plus an x86_64
  CPython and ends the whole-spike-in-Python story.
- **Clear the quarantine xattr** on anything downloaded, or `dlopen` fails opaquely.
- **Never read a string through `c_char_p`.** Marshal blobs contain NULs; a truncated read can pass
  a decode check and produce a *false* PASS. Use `SUStringGetUTF8Length` + a counted copy, then diff
  byte-for-byte against `00_Context/tools/skp_decode_tables.py`'s read of the same table.
- **Count entities, not placements.** Deduplicate on `persistent_id`; the live captures' own
  placements-vs-entities gap is 2466→1791 on Linde and 2456→1781 on 250708, and **Adelphi and Bluff
  Reach mask it entirely**.

---

## Changelog

- 2026-08-28 — created during HEADLESS Spike A. Availability block recorded; API surface harvested
  and verified against all eight Spike-A gates; no binary executed.
- 2026-08-29 — **Spike A ran: all eight gates PASS on a third-party build.** §3-§4c rewritten from
  measurement; four traps recorded (§4.1-§4.4); §4d added from the 16-file capability sweep.
- 2026-08-29 — **Spike B ran: a full contract-v2 capture reproduces the live SketchUp captures.**
  Added §4.5 (the shipped `SURefType` puts `Face` at 11, not the documented 9 — a type check against
  the doc order rejects **every** glued host), §4e (the container-index shape that makes a capture
  affordable, and the measured cost/concurrency table), §4f (`SUEntityGetID` is process-scoped, and
  signed zero differs 72 times), §4g (never-save enforced structurally: 6 of 6 writers refused).
