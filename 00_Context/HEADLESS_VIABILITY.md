# Reading a designPH `.skp` with no SketchUp — viability, limits, opportunities

DATE: 2026-08-29 · written from HEADLESS Spike A + its capability probe
STATUS: **Technical viability: established.** Every blocker that remains is legal or procurement.
⚠ All measurements come from a **third-party build** of Trimble's SDK — see §6.

This is the *so what* document. [`SDK_RUNTIME.md`](SDK_RUNTIME.md) is the reference (what the API is,
what it exposes, how to call it); this one answers the questions a decision needs: **is it viable,
where does it break, and what did we find that we did not know to look for?**

Evidence: `planning/HEADLESS/RESULTS/HEADLESS-A_results.md` (the eight gates) and
`planning/spikes/headless/a7_capability_probe.py` (the capability sweep, 16 corpus files).

---

## 1. The headline

**Yes — comfortably, and by a wider margin than the phase assumed.**

A CPython process with no SketchUp installed, no SketchUp seat and no compiled code (ctypes only)
reads the five captured designPH models *exactly* as the live Ruby collector read them: **545/545
classified faces, 239/239 windows with every host resolved, 99/99 thermal-bridge edges, 63/63
Marshal tables**, geometry matching to **0.0000 mm** on window transforms.

And the ceiling is high. The entire 16-file, 230 MB corpus — including a **146 MB** model, ~13× the
largest previously baselined — processes in **≈16 seconds total**.

⚠ **The extension route's entire runtime section evaporates on this path.** No Chromium 88, no
Pyodide 0.24.1 ceiling, no 4 MB bridge, no 4–11 s UI freeze, no 15 MB install footprint
([`CONSTRAINTS.md`](CONSTRAINTS.md) §2–3). Full modern CPython, real honeybee, real PHX, real
pydantic. That constraint set was the price of running *inside* SketchUp, and it is simply not paid
here.

## 2. What we now know about the `.skp` as a data source

| Question | Answer, measured |
|---|---|
| Can it be read without SketchUp? | **Yes** — flat C API, ctypes, no compiled extension |
| How far back? | **SketchUp 8.0.1** opens (an 11 MB, 2014-era file) |
| How far forward? | **SketchUp 26.1.188** opens on an **API 13.0 (2025)** SDK |
| Does an older SDK refuse a newer file? | **It did not, on any of 16 files** — see §2.1 |
| How fast? | **≈80–100k entities/second**; whole corpus in ≈16 s |
| How much memory? | peak **851 MB** across the run; §5.4 on why that is not a per-model figure |
| Is the read faithful? | 545/545 · 239/239 · 99/99 · 63/63 against live SketchUp |

### 2.1 ★ The file format has been "versionless" since SketchUp 2021

`SUModelVersion`'s own header says it: *"Starting with SketchUp 2021, SketchUp is using the same
file format across versions."* The enum stops at `SUModelVersion_SU2021`, and every later release
writes that same format.

**This is the single most important structural fact for a server.** The extension route's version
economics ran *backwards* — the oldest SketchUp supported set the newest Pyodide available. Here
there is barely a version axis at all: one SDK read files written by SketchUp 8, 22, 23, 25 and 26.

⚠ **And the guard rail did not fire.** `SUModelCreateFromFileWithStatus` can return
`SUModelLoadStatus_Success_MoreRecent` ("saved by a newer version of SketchUp… update your SDK"). A
**SketchUp 26.1.188 file opened on a 2025 SDK reported plain `Success`**, not `MoreRecent`. So the
signal exists, is worth capturing, and **must not be trusted as the only version guard** — it did
not fire in the one case in the corpus where it plausibly should have. Read it; do not depend on it.

### 2.2 Cost tracks unique entities, not file size

| model | MB | definitions | walk | total |
|---|---:|---:|---:|---:|
| `2618 Lavoie` (scale probe) | **146.2** | 261 | 1.44 s | **3.93 s** |
| `2414 Bluff Reach` | 10.8 | 249 | 1.28 s | 2.52 s |
| `2536 Holmes` | 5.9 | **613** | 0.78 s | 1.45 s |
| `250708` | 4.2 | 101 | 0.03 s | 0.13 s |
| `adelphi-designph` | 3.2 | 101 | 0.10 s | 0.36 s |

**File size is a poor predictor.** Lavoie is 14× Bluff Reach's bytes and costs 1.6× its time —
most of those bytes are textures and materials (318 materials), which a designPH read never touches.
Holmes is the counter-example in the other direction: 5.9 MB and only 2,124 face *placements*, but
**613 component definitions**, and it costs more than models ten times its placement count.

For a watcher, the practical consequence is that **a file-size threshold is the wrong admission
control**. `SUModelGetStatistics` returns a whole-model census in one call, before any walk, and is
the right triage input.

## 3. ⛔ The limits and pitfalls

Ordered by how much damage each would do unnoticed. Every one of these produced a *plausible* number
on a real model before it was caught.

### 3.1 Reading mutates the model

`SUEntityGetAttributeDictionary` is a **get-or-CREATE** — its own header says so — and it is the
only complete way to test whether an entity carries a dictionary. **Measured on all 16 corpus files:
asking one face for a dictionary name it does not have takes it from 1 dictionary to 2.**

⛔ So a C-SDK reader **writes into the model as a side effect of reading it**, in the
`DesignPH_dict` namespace that hard rule 2 forbids touching. This is survivable only because nothing
saves. **"Never call `SUModelSaveToFile` on a model opened for reading" is a load-bearing
invariant** — for a watcher touching real client files, it is *the* safety property, and it should
be enforced by construction (a reader that never links the write symbols), not by discipline.

### 3.2 The read-only alternative silently loses up to 40 % of the data

The obvious way to avoid §3.1 is to enumerate an entity's dictionaries instead of asking by name.
The two halves of the SDK's own two-call idiom **disagree**: `SUEntityGetNumAttributeDictionaries`
returns 1 while `SUEntityGetAttributeDictionaries` returns `SU_ERROR_NONE` **with count 0**. Both
report success.

| model | tagged entities lost to enumeration |
|---|---|
| `250703 Linde` | **731 / 1838 (39.8 %)** |
| `250708` | 716 / 1830 (39.1 %) |
| `2523 Wellington` | 118 / 503 (23.5 %) |
| Adelphi · Bluff Reach · Holmes · MacDonough · Lavoie | **0 %** |

⭐ **It affects `face` entities only** — never edges, never component instances — measured across all
16 files. Cause unknown; the pattern is recorded because a future reader will meet it again.

**The only complete predicate is: ask by name, then require `num_keys > 0`.** An absent dictionary
comes back freshly created and empty, so the key count is what separates real data from §3.1's side
effect. The two traps are therefore *entangled*: you cannot have completeness without the mutation.

### 3.3 Numbers that mean something other than what they say

- **`SUModelGetStatistics` counts PLACEMENTS.** Adelphi reports 1,025,904 faces; it has **8,037**
  unique ones. Both true, different questions — the repo's standing rule, met again.
- **`SUFaceGetArea` takes no transform, so it is the LOCAL area.** Ruby's collector calls
  `face.area(transform)`. On unscaled models the two agree and the bug is invisible; Adelphi has a
  scaled container and 14 of 82 faces came out wrong by a constant 2.96×. Use
  **`SUFaceGetAreaWithTransform`**.
- **`SUModelIsGeoReferenced` can be `true` with coordinates of (0, 0).** Adelphi does exactly this.
  A georeference check must test the coordinates, not the flag.
- **A model GUID is per-SAVE, not per-project.** It is stable across repeated reads of one file
  (3/3 identical) but **differs between a model and its own `~` backup**, which are consecutive
  saves of the same building. Useful for "has this file changed?"; useless for "is this the same
  project?" — §4.3.
- **A published API name is not a signature.** `SUModelGetVersion` takes `(major, minor, build)`,
  not the version enum its name implies; the wrong guess returned a *believable* 22 on Adelphi and
  segfaulted on the next model. Check declarations against the shipped headers.

### 3.4 ⚠ Adelphi and Bluff Reach mask bugs — now three separate times

The corpus warning in `AGENTS.md` has earned a third instance in one spike:

1. **placements vs entities** — nothing in either model is placed twice, so the distinction is
   invisible (Linde 2466 → 1791, 250708 2456 → 1781);
2. **the enumeration gap (§3.2)** — 0 % on both, 40 % on Linde and 250708;
3. **`DesignPH_dict` on windows (§4.5)** — present on 9 of 16 models, absent on both.

**Neither model can validate a rule about designPH data.** Linde and 250708 are the ones that catch
structural errors; Holmes is the one that catches tag- and definition-shaped errors.

### 3.5 What has *not* been established

- **Nothing ran on Trimble's own SDK** (§6).
- **Per-model memory is unmeasured.** `ru_maxrss` is a process high-water mark and the whole sweep
  ran in one process, so 851 MB is "the peak the run reached", not "what Lavoie costs". One process
  per model would answer it; a watcher wants that number.
- **No concurrency test.** Whether two models can be open at once, and whether `SUInitialize` is
  thread-safe, is unknown and matters for a server.
- **Windows and Linux are untested** (Spike C).
- **No `.skp` was written or re-saved**, deliberately.

## 4. ⭐ Opportunities that surfaced — things we did not know to look for

### 4.1 Tags are readable, which reopens the shading question

The PRD took shading geometry **out of v1 scope** because no heuristic separates context from
clutter, and decided v1 would *ask the user* which SketchUp tags are shading (PRD §7.2). That
decision assumed a human in the loop.

**The SDK reads tag (layer) names per entity.** Measured across the corpus:

| model | tags on designPH faces | tags on everything else |
|---|---|---|
| `2536 Holmes` | 1 | **42** |
| `250703 Linde` | **7** | 1 |
| `2414 Bluff Reach` | 2 | 3 |
| `adelphi-designph` | 2 | 1 |

Holmes is the shape the PRD was worried about — 42 distinct tags of non-envelope geometry. A
headless reader can now **enumerate the tag vocabulary and hand it to the user once per project**,
rather than requiring a live SketchUp session to ask the question. That converts a blocking
interactive step into a configuration value a watcher can remember.

### 4.2 SketchUp carries real climate and orientation data, independent of designPH

designPH stores its own `klima_ID`. SketchUp separately stores a geolocation and a north angle, and
the corpus actually uses them:

- **Real lat/long on 5 of 16**: Linde `40.613, -105.060` (Fort Collins CO), Wellington
  `41.491, -81.568` (Cleveland OH), Lavoie `42.080, -74.062` (Catskills NY), the 2014 sample
  `40.792, -73.969` (Manhattan).
- **A meaningful north correction on 7 of 16** — Bluff Reach 25.0007°, Holmes 44.8647°,
  MacDonough 350.6339°, Wellington 359.6239°.

For a Passive House tool this is not incidental: **north correction is solar orientation**, and it
is a value the POC's contract does not currently carry at all. ⚠ Unset reads as `-0.0`, and the
georeference flag lies (§3.3), so both need a validity test rather than a presence test.

### 4.3 A per-save model identity, for free

`SUModelGetGuid` gives a stable GUID (verified: 3 reads of one file, identical). Combined with §2.1's
format stability, a watcher gets cheap change detection without hashing 146 MB. ⚠ It changes between
saves, so it answers *"is this the same file contents?"*, not *"is this the same project?"* — project
identity still has to come from the path or from pholio's own record.

### 4.4 A second, independent host test the Ruby collector never had

`SUFaceGetNumOpenings` is > 0 on **exactly** the 81 distinct host faces across the five capture
models, and `gross − net` equals the summed rough-opening areas precisely. Ruby's nearest
equivalent, `loops.size > 1`, is true on **1 of 81**. The aperture claim — the POC's most
error-prone area — can now be cross-checked from the host side for one call per face.
⚠ Openings and inner loops are different: one Wellington face has a genuine inner loop and no
opening.

### 4.5 designPH data is in more places than the contract reads

The corpus-wide key census (`DESIGNPH_DATA_MODEL.md` §13) turned up three things:

- **Windows carry a `DesignPH_dict` too**, not just `dynamic_attributes` — `descNameAuto` on 9 of 16
  models (and `descNameFreeze` on Wellington). ⚠ **Absent on Adelphi and Bluff Reach**, which is why
  it was never noticed.
- **Thermal-bridge edges exist on two projects, not one** — Bluff Reach (99) *and* **Holmes (42)**,
  which is outside the capture set. The known population is 141, not 99.
- **designPH 1.0.30 is readable**, and carries a `Shader` key on 57 faces that no 2.x model has.

### 4.6 The write surface exists

All six write symbols are present (`SUModelSaveToFile`, `SUEntityAddAttributeDictionary`,
`SUAttributeDictionarySetValue`, …). **Never called, and out of scope** — but it means the PRD's v2
authoring idea (writing to `DesignPHPlus_dict`, its own namespace) is not blocked by the headless
route. ⚠ It is also precisely what makes §3.1 dangerous, so the two facts belong together.

## 5. What this means for the product

- **The pholio watcher model is technically clear.** A folder watcher plus this reader plus the
  POC's verified translator is a working pipeline, at a few seconds per model.
- **Admission control should be `SUModelGetStatistics`, not file size** (§2.2).
- **"Never save" must be structural**, not procedural (§3.1).
- **The privacy story improves**: the reader can strip `tracker_data` and embedded paths at the
  door, and the geolocation finding means a capture may carry a *building's real coordinates* —
  that is client data and belongs in the same bucket.
- **Version risk is far lower than the extension route's**, and mostly evaporates (§2.1).

## 6. ⚠ The standing caveat

Every measurement here was taken with a **third-party re-host** of Trimble's proprietary
`SketchUpAPI.framework`, because Trimble's own SDK is behind a Request Access form with no reported
turnaround. Ed authorised that build for time-boxed laptop feasibility only, in parallel with filing
the form.

**Consequences:** licensing task **L1 (read the SDK EULA) cannot start** — the EULA ships inside the
gated download. Nothing here may ship. And re-running is cheap by design:
`planning/spikes/headless/run_gates.sh` plus `a7_capability_probe.py` reproduce every number in this
document in under a minute.

**A PASS on this evidence is a strong feasibility result and not a commercial green light.**

---

## Changelog

- 2026-08-29 — written from Spike A's eight gates and the `a7` capability sweep over 16 corpus files.
