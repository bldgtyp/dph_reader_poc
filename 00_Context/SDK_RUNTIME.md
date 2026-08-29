# The SketchUp C SDK as a runtime — what it is, what it exposes, and how to get it

DATE: 2026-08-28 · first written during HEADLESS Spike A
STATUS: ✅ **Behaviourally verified on five real designPH models** (2026-08-29, Spike A: 545/545
faces, 239/239 windows, 99/99 edges, 63/63 Marshal tables, 15/15 files opened). ⚠ **On a
third-party SDK build, not Trimble's** — §1. Re-run against the official SDK before trusting it
commercially.

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

## 4. ⛔ The three traps that make a C-SDK reader wrong while looking right

Every one of these produced a **plausible number on a real model** before it was caught.
`planning/HEADLESS/RESULTS/HEADLESS-A_results.md` §3 has the full accounting.

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
