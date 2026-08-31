# HEADLESS-A results — SketchUp C SDK feasibility

DATE: 2026-08-28 (gates re-run 2026-08-29)
STATUS: ✅ **PASS — every gate green.** ⚠ On a third-party SDK build; see §1 and §7
PLAN: [`../HEADLESS-A_sdk-feasibility.md`](../HEADLESS-A_sdk-feasibility.md)

---

## Verdict

**A headless CPython process, with no SketchUp installed and no SketchUp seat, reproduces the live
Ruby collector's reads of five real designPH models exactly — in under 4 seconds each.**

| Gate | Result |
|---|---|
| **G0** boot | ✅ **PASS** — framework loads on arm64, API **13.0**, all 8 gate symbol sets exported, **15/15** corpus models open |
| **G1** glue — *decisive* | ✅ **PASS** — **239/239** windows resolve to a host face, every one via `SUComponentInstanceGetAttachedToDrawingElements`. Distinct-host counts match the captures exactly (16/14/17/18/16). **No geometric fallback needed** |
| **G2** typed attributes | ✅ **PASS** — type tags preserved; `areaGroupID` reads as String `'n'`, ints as Int32; coalesce works on both key generations |
| **G3** edges at depth | ✅ **PASS** — **99/99** thermal-bridge edges on Bluff Reach, 0 on the other four, on an entity basis |
| **G4** Marshal tables | ✅ **PASS** — **63/63** tables, 68,587 decoded bytes, all parsed by the unmodified Phase-1 reader |
| **G5** live vs historical | ✅ **PASS** — entity counts match the live captures on all five (1441/576/1791/1781/446) |
| **G6** area semantics | ✅ **ANSWERED** — `SUFaceGetAreaWithTransform` equals live `face.area(transform)` on **545/545** faces. Net of glued openings, exactly like Ruby |
| **G7** world transforms | ✅ **PASS** — worst window translation delta **0.0000 mm**, worst face vertex delta **0.0008 mm** (the collector's own 6-dp rounding), 0 unmatched |

```
CORPUS TOTALS, headless vs the five live SketchUp captures
  classified faces  545 / 545        windows          239 / 239
  thermal bridges    99 /  99        glued hosts      239 / 239
  Marshal tables     63 /  63        models opened     15 /  15
```

Reproduce with `planning/spikes/headless/run_gates.sh` (needs `_private/` staged — §6).

⚠ **One premise of this phase is dead, and it is not a technical one:** the SketchUp C SDK is **no
longer a public download**. Everything above ran on a third-party re-host. §1 and §7.

---

## 1. ⛔ The SDK is behind an access gate

Verified live 2026-08-28 in Ed's Chrome, signed in on his Trimble developer account (header showed
"Ed M."): `https://extensions.sketchup.com/sketchup-sdk` renders a holding page —

> "Thank you for your interest in the SketchUp and LayOut C SDKs. They are not available for public
> download at this time. Please fill out the form to request access…"

— with a **Request Access** button and no download list. The overview's §2 claim, "a free developer
download from Trimble", **is false** and is marked superseded.

Corroboration: the Extension Warehouse SPA carries a **`SDK_HOLDING_PAGE`** feature toggle, on in
production; `GET /api/developers/sdkBuilds` returns **401** and `getSdkBuildUrl(id)` issues a
**signed** URL, so no static URL ever existed to guess; Wayback's `SDK_Mac_2019-0-752.zip`-shaped
entries are all ~1 KB SPA stubs; Homebrew, conda-forge, vcpkg and Debian carry nothing. Forum
thread *"SketchUp C SDK 2026 macOS unavailable"* (346672) — ⚠ *reported, not verified here* — says
it went behind the form before 2026-05-05 and that developers report **no response as of
2026-08-16**.

⚠ **`extensions.sketchup.com` returns HTTP 200 with an identical 4387-byte SPA shell for every
path, valid or nonsense.** Status-code probing there proves nothing; check response size. (The
doxygen tree under `/developers/sketchup_c_api/` is a different handler and serves real pages —
which is what let §2 close before any binary existed.)

**Ed's decision (2026-08-28): both routes in parallel** — file Trimble's form, and meanwhile run the
gates against `martijnberger/pyslapi` release 0.24's `SketchUpAPI.framework` (universal2 arm64 +
x86_64, built ~April 2025, Xcode 15.4, min macOS 11.7), **for time-boxed laptop feasibility only**.
⚠ That is a personal redistribution of a proprietary EULA-gated binary. **No EULA ships in the zip,
so licensing task L1 remains unstartable**, and every number in this document must be re-run against
the official SDK before it is trusted.

⚠ The much-linked **RedHaloStudio fork is Windows-only** in every current release. The plan's
demotion of pyslapi ("pinned to an older SDK generation") is **half wrong**: the *binding* is stale,
but the *framework* is API 13.0 — newer than every corpus writer.

⚠ The zip flattens the framework's `Frameworks` symlink, so `dlopen` fails on
`@rpath/libCommonUnits.dylib` until `ln -s Versions/Current/Frameworks Frameworks` is restored.

## 2. The API surface, closed before the binary arrived

The reference docs stayed public. `a1_capi_surface.py` harvests all **1231 published `SU*`
functions** across 89 struct pages plus the free-function headers and checks them per gate: **every
function every gate needs is present**, including both directions of the glue query. That answered
G1 at the documentation level while the binary was still blocked.

⚠ **Two doxygen layouts, and harvesting one alone lies.** Struct members render in the member
table's right cell; **free functions render as plain links on the header page**. `SUInitialize`,
`SUTerminate` and `SUGetAPIVersion` live in `initialize.h` and belong to no struct — a struct-only
scrape reports them absent, which they are not.

## 3. ★ Four traps, each of which produced a plausible wrong answer

These are the spike's most transferable output. Every one passed on at least one real model first.

### 3.1 A published name is not a signature — and the wrong one segfaults *later*

`SUModelGetVersion` sits beside an enum called `SUModelVersion` and reads overwhelmingly like an
enum getter. It is not:

```c
SU_RESULT SUModelGetVersion(SUModelRef model, int* major, int* minor, int* build);
```

The inferred two-arg version wrote through two out-pointers that were never passed. On **Adelphi it
survived and returned 22** — which is even the correct major version for its writer — and
**segfaulted on the next model**. A second declaration was silently wrong and not yet called:
`SUEntityGetType` returns `enum SURefType` **directly**, and is not `SU_RESULT` at all.

✅ `a3_header_audit.py` now parses the shipped headers and checks every ctypes declaration's arity.
67 declarations, 1137 header functions, 0 mismatches. It runs first in `run_gates.sh`.

### 3.2 ⛔ `SUEntityGetAttributeDictionary` is a get-or-**CREATE**

Its own header: *"If a dictionary with the given name does not exist, **one is added to the
entity**."* A function named `Get` writes — and it writes into `DesignPH_dict`, the exact namespace
**hard rule 2** forbids touching.

Using its success as the tagged-test reported **every** entity as tagged: 8037 faces instead of
1441 on Adelphi, 16718 edges instead of 0, 1343 instances instead of 46. Those were not
counting-basis errors; they were counts of entities the test had just modified.

⛔ **A C-SDK reader therefore mutates the in-memory model as a side effect of reading it.** Hard rule
2 survives only because nothing ever calls `SUModelSaveToFile`. **"Never save an opened model" is a
load-bearing invariant for any headless service, not a convention.**

### 3.3 …and the read-only alternative silently under-reports

The obvious fix is to enumerate instead. Measured, the two halves of the SDK's own two-call idiom
**disagree with each other**: `SUEntityGetNumAttributeDictionaries` returns **1** while
`SUEntityGetAttributeDictionaries` returns **`SU_ERROR_NONE` with count 0** and an unset handle —
for dictionaries that demonstrably exist with keys. Both calls report success.

| model | tagged faces lost to enumeration |
|---|---|
| 2523 Wellington | **118 of 446** (26 %) |
| 250703 Linde | **731 of 1791** (41 %) |
| 250708 | **716 of 1781** (40 %) |
| Adelphi, Bluff Reach | 0 — **they mask it completely** |

✅ **The only complete predicate is: ask by name, then require `num_keys > 0`.** A genuinely absent
dictionary comes back freshly created and empty, so the key count is what separates real data from
the SDK's own side effect. With it, all five models match the captures exactly.

### 3.4 `SUFaceGetArea` takes no transform — so it is the LOCAL area

The Ruby collector calls `face.area(transform)` (`collector.rb:377`), i.e. the **world** area.
`SUFaceGetArea` has no transform parameter. On four models this is invisible; on **Adelphi it put 14
of 82 faces wrong**, by a constant ratio of 2.96× in the subtracted amount — the signature of a
scale on a containing group.

✅ The fix was **the library's own `SUFaceGetAreaWithTransform`**, not a local rescale — the repo's
"do not re-implement half of a library's rule" rule, applied. Adelphi's 14 went to **0**, and the
corpus went to **545/545**.

## 4. What G6 actually answered

- **`SUFaceGetAreaWithTransform` == live SketchUp `face.area(transform)` on 545/545 classified
  faces.** Net of glued window openings, exactly like Ruby. The G6 "record verbatim" decision costs
  nothing, because verbatim is already identical.
- The net-vs-gross gap appears on exactly the faces where **`SUFaceGetNumOpenings > 0`**, and the
  amount subtracted equals the summed **rough-opening** areas (`lenx × leny`) precisely.
- ★ **`SUFaceGetNumOpenings` is a reliable host-side cross-check in the C API** — 14/17/18/16/16,
  matching the 81 distinct host faces. This is the thing Ruby could not offer: `loops.size > 1` is
  true on **1 of 81**. The C SDK gives a second, independent host test the Ruby collector never had.
- ⚠ One Wellington face has `SUFaceGetArea` ≠ its own outer loop **without** any opening — a genuine
  modelled inner loop. Openings and inner loops are different things; do not conflate them.

## 5. G4: the hazard this gate was built around does not exist

★ **designPH stores its Marshal tables as BASE64 text, not raw binary.** Every value begins `BAh`,
which is simply base64 for Marshal's `\x04\x08` (hence the collector's `MARSHAL_PREFIX = "BAh"`).

The plan and the pre-spike review's item 3 were built around **NUL truncation** — a `c_char_p` read
stopping at the first `0x00` and yielding a partially decoded table that still parses, i.e. a false
PASS. On this path it **cannot happen**: the transport is ASCII with no NULs at all. `c_char_p`
would have worked. The length-aware read stays because it is right in general and nothing about
designPH's storage is guaranteed, but the named hazard is retired.

⚠ **And the NUL check itself had to be demoted, which is the more interesting half.** It fired on
Linde's `tfa_calc_ud`, and the data was fine: 396 base64 characters decoding to exactly 297 bytes
and parsing to 4 complete rows, while 95-byte payloads elsewhere *do* contain NULs. NUL presence is
content-dependent, not integrity-dependent — the check was testing the wrong property. The proof
that survives is the chain: exact base64 length → clean decode → Marshal magic → complete strict
parse → table set matching the live capture. **63/63 tables, all five models.**

## 6. Method notes worth keeping

- **Walk definitions once, not placements.** Adelphi is 1441 tagged face entities behind
  **1,023,558 face placements**; Wellington's placement walk is 4,255,761 nodes. The first counting
  attempt did not finish. Enumerating each definition once is both the correct **entity basis** and
  ~1000× faster — and the two walks were verified to cover an *identical* entity set (15838 faces,
  zero difference) before the switch.
- **Gates that need world coordinates still need the placement walk**, so it is pruned to subtrees
  that actually contain tagged geometry — 0.3 % of the model. Pruning the traversal, never the answer.
- ⚠ **The parent-relative transform trap reproduced itself inside the reader written to avoid it.**
  `walk_pruned` first yielded each window carrying its *parent's* world transform: Bluff Reach's
  windows landed **29.5 m** out. Same bug, same shape, new codebase.
- **`read_text()` without an encoding** blew up on Linde's capture (locale codec vs UTF-8).
- The captures' `model.file_name` is unreliable — Wellington's reports the backup's misspelling
  ("2523 Weiilington"). **Key on the file.** Tested and rejected the hypothesis that the capture
  came from the backup: the backup scores *worse* (197 vs 328).
- **New corpus material postdates the Phase-0 baseline**: `2618 {BP} Lavoie Certification.skp` +
  backup, **146 MB each** — ~13× the largest baselined model, the natural scale probe. Not staged;
  it has no baseline and no live capture, so it can grade nothing.

## 7. What is NOT established

1. ⛔ **Nothing here was run on Trimble's own SDK.** Every number is from a third-party build. The
   suite is one command, so re-running it is cheap once the official SDK arrives.
2. ⛔ **L1 (read the SDK EULA) remains unstartable** — the EULA ships inside the gated download.
3. **Performance is laptop-scale only**: ≈3-4 s per model over five models of 3-11 MB. The 146 MB
   Lavoie model is untested, and so is any concurrency.
4. **This is not a contract-v2 capture.** Spike A compared *counts and geometry*; emitting the
   actual JSON, byte-for-byte comparable, is Spike B.
5. **Windows/Linux is untested** — Spike C.

## 8. Deliverables

| Artifact | State |
|---|---|
| `planning/spikes/headless/run_gates.sh` | ✅ one command, one verdict line per gate |
| `sdk.py` · `walk.py` | ✅ ctypes binding + entity/placement/pruned walks |
| `a0`–`a6` gate scripts | ✅ all green |
| `_private/` + `MANIFEST.md` | ✅ 15 corpus copies, 5 captures, baselines, SDK — gitignored |
| [`00_Context/SDK_RUNTIME.md`](../../../00_Context/SDK_RUNTIME.md) | ✅ the durable record |
| `00_Context/DATA_CONTRACTS.md` §2.1 | ✅ corrected — `areaGroupIDAuto` does not exist |
| SDK EULA (L1) | ⛔ not obtainable |

## 9. Recommendation

**Spike A passes; Spike B (contract-v2 identity gate) is unblocked** under hard rule 7. Its H0
revision pass must fold in:

- the identity gate keys on the **path-qualified `id`**, never on `entity_id` (session-local);
- `SUEntityGetPersistentID` exists, so the ids are reproducible byte-for-byte;
- the **get-or-create** side effect and the **never save** invariant;
- `SUFaceGetAreaWithTransform`, not `SUFaceGetArea`;
- `SUFaceGetNumOpenings` as a second host test the Ruby collector never had.

⚠ **But B should not be treated as de-risked by A's numbers until the official SDK is in hand.**
A's evidence is provisional in exactly one way, and it is the way that matters commercially.

---

## Changelog

- 2026-08-28 — written. Spike A blocked at G0 on SDK availability; documentation-answerable half of
  G1–G4/G6–G8 closed; expected-answer derivation and evidence staging completed.
- 2026-08-29 — **rewritten: all eight gates PASS.** Ed authorised the parallel route (file Trimble's
  form; run the gates on a third-party build meanwhile). Four traps recorded, each of which produced
  a plausible wrong answer on a real model first.
