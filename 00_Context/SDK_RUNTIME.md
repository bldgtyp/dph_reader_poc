# The SketchUp C SDK as a runtime — what it is, what it exposes, and how to get it

DATE: 2026-08-28 · first written during HEADLESS Spike A
STATUS: **API surface documented and verified. No binary has been executed.** Every behavioural
claim below is marked as untested; nothing here has been run.

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
route that works today; whether it may be used is a licensing decision, not a technical one, and
`planning/HEADLESS/RESULTS/HEADLESS-A_results.md` §5 lays out the three options.
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

## 3. What the API exposes (documentation-level, all untested)

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

⚠ **An opening is not proof of a hole.** `cuts_opening?` was true on all 46 Adelphi windows while
only 1 of 16 hosts had an inner loop; nothing says the C layer is more honest. Assert that each
opening's drawing element is one of the known windows before believing it.

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
| strings | `SUStringGetUTF8Length` + `SUStringGetUTF8` | ⚠ **length-aware — use these, never a `c_char_p`.** Marshal blobs contain `0x00` |
| traversal | `SUModelGetEntities` · `SUEntitiesGet{Faces,Edges,Instances,Groups}` (+ `GetNum…`) · `SUComponentInstanceGetDefinition` · `SUComponentDefinitionGetEntities` · `SUGroupGetEntities` | ⚠ groups are a **separate** container from instances; a walk that handles only instances loses group-nested geometry |
| geometry | `SUFaceGetOuterLoop` · `SUFaceGetNumInnerLoops`/`GetInnerLoops` · `SULoopGetVertices` · `SUVertexGetPosition` · `SUFaceGetNormal`/`GetPlane` | |
| area | `SUFaceGetArea` · **`SUFaceGetAreaWithTransform`** | the second was not in the Spike-A plan and is what a scaled instance needs |
| transforms | `SUComponentInstanceGetTransform` · **`SUGroupGetTransform`** · `SUTransformationMultiply` | ⚠ two separate getters, same reason as traversal |
| persistent lookup | `SUModelGetEntitiesByPersistentIDs` · `SUModelGetEntitiesOfTypeByPersistentIDs` · `SUModelGetInstancePathByPid` | a direct pid→entity index, useful for reconciling against a live capture |
| version | `SUModelGetVersion` (enum `SUModelVersion`) · `SUModelGetGuid` · `SUModelGetStatistics` | ⚠ **`SUModelGetVersionString` does not exist** — the enum is the coarser answer available |

## 4. ⚠ What the documentation cannot tell you

Recorded so a later reader does not mistake §3's coverage for a feasibility verdict:

- **Whether the SDK reads live state or historical state.** The whole reason to prefer it over the
  binary parser (`DESIGNPH_FILE_FORMATS.md` §4.3) is untested.
- **Whether `SUFaceGetArea` is net of glued openings** like Ruby's `face.area`, or gross. Either is
  acceptable; not knowing is not. It differs on exactly 81 host faces across the five capture models.
- **Whether the glue query returns the 239 hosts** on real designPH models.
- **Whether the 15 corpus files open**, including the pre-2014 sample.
- **Whether ctypes drives it at reasonable cost**, and whether the dylib is universal or x86_64-only
  (the third-party build is universal2; a Trimble build has not been inspected).

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
