# Reading a designPH `.skp` with no SketchUp — viability, limits, opportunities

DATE: 2026-08-29 · written from HEADLESS Spike A + its capability probe; extended by Spike B
STATUS: **Technical viability: established, and now demonstrated end to end.** Spike B emitted the
frozen contract v2 from a headless read and it is **indistinguishable from the live SketchUp
capture** apart from four named fields, translating to **canonically identical HBJSON**. Every
blocker that remains is legal or procurement.
⚠ All measurements come from a **third-party build** of Trimble's SDK — see §6.

This is the *so what* document. [`SDK_RUNTIME.md`](SDK_RUNTIME.md) is the reference (what the API is,
what it exposes, how to call it); this one answers the questions a decision needs: **is it viable,
where does it break, and what did we find that we did not know to look for?**

Evidence: `planning/02_headless-reader/RESULTS/HEADLESS-A_results.md` (the eight gates),
`planning/spikes/headless/a7_capability_probe.py` (the capability sweep, 16 corpus files), and
`planning/02_headless-reader/RESULTS/HEADLESS-B_results.md` (the nine identity gates).

---

## 1. The headline

**Yes — comfortably, and by a wider margin than the phase assumed.**

A CPython process with no SketchUp installed, no SketchUp seat and no compiled code (ctypes only)
reads the five captured designPH models *exactly* as the live Ruby collector read them: **545/545
classified faces, 239/239 windows with every host resolved, 99/99 thermal-bridge edges, 63/63
Marshal tables**, geometry matching to **0.0000 mm** on window transforms.

And the ceiling is high. The entire 16-file, 230 MB corpus — including a **146 MB** model, ~13× the
largest previously baselined — processes in **≈16 seconds total** (Spike B, emitting the full
contract one process per model: **11.8 s**, slowest single model **2.5 s**, heaviest **717 MB**
peak RSS).

★ **Spike B closed the remaining question, which was not "can it read" but "is it the same read".**
A headless capture matches the live SketchUp capture with **0 unexplained differences on 5/5
models** — worst geometry deviation **0.000000 mm** — and the *untouched* POC translator then
reproduces the acceptance table exactly (545/545 faces, 239/239 windows, 99/99 bridges) and emits
**canonically identical HBJSON**. The four differences that do exist are `entity_id` (which the
contract already calls session-scoped), record order, signed zero, and one field where the headless
reader is deliberately **right**: `model.file_name`, because `Sketchup::Model#path` is the last-
*saved* location and one live capture is stamped with a backup's misspelling.

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
| How fast? | **≈80–100k entities/second**; the whole corpus emits full contract-v2 captures in **11.8 s** |
| Where does the time go? | ⚠ **43 % of it is `SUModelCreateFromFile`** — opening the file, before any walk. §2.3 |
| How much memory? | **63 MB floor**, **104–718 MB** peak per model. ⛔ And it **never comes back** — §2.4 |
| Can two models be open at once? | **Yes**, and two processes and two threads also work — §4.7 |
| Is the read faithful? | 545/545 · 239/239 · 99/99 · 63/63 against live SketchUp — and the **whole contract-v2 document** matches with 0 unexplained differences (§1) |

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
control**. `SUModelGetStatistics` returns a whole-model census in one call and is a far better
triage input than bytes.

⚠ **But it is not a cheap one, and the first version of this paragraph implied it was.**
`SUModelGetStatistics` — like the version stamp, like everything — requires the model to be *open*,
and the open is **43 % of the whole read** (§2.3). There is no peek. Triage decides whether to
*walk*; it cannot decide whether to *open*, and opening is the expensive half.

### 2.3 ⚠ The open dominates — in time and in memory

Measured per phase on eight models, one process, the SDK already loaded:

| model | file | `SUModelCreateFromFile` | version stamps | the walk | open as % |
|---|---:|---:|---:|---:|---:|
| `2618 Lavoie` | 139 MB | **1.12 s** | 0.000 s | 1.21 s | 48 % |
| `2414 Bluff Reach` | 10.3 MB | 0.57 s | 0.000 s | 1.01 s | 36 % |
| `2536 Holmes` | 5.6 MB | 0.34 s | 0.000 s | 0.62 s | 35 % |
| `250703 Linde` | 6.9 MB | 0.33 s | 0.000 s | 0.39 s | 46 % |
| `2523 Wellington` | 6.5 MB | 0.23 s | 0.000 s | 0.25 s | 47 % |
| `adelphi-designph` | 3.0 MB | 0.13 s | 0.000 s | 0.18 s | 42 % |
| `250708` | 4.0 MB | 0.07 s | 0.000 s | 0.11 s | 39 % |
| **all eight** | | **2.79 s** | ~0 | 3.78 s | **43 %** |

Three consequences, and each one changes a design decision:

1. ⭐ **Reading the model's designPH version stamps is FREE once open** — 0.000 s on every model. So
   a pre-walk version gate costs nothing beyond the open it already needed. Its value is **safety**,
   not saved time: it stops a schema this reader has never seen from meeting a collector written for
   2.x. Do not justify it on cost.
2. ⛔ **Opening twice is a ~45 % regression**, and it is an easy mistake: an early version of the
   headless collector read the stamps on its own `open_model` and then opened the file again to walk
   it. On Lavoie that was 3.75 s against 2.57 s, and the CLI's own reported time *excluded* the
   first open, so the tool under-reported its own cost by nearly half.
3. **Neither bytes nor entity count predicts the open on its own.** Lavoie is 139 MB with 261 k
   edges and opens in 1.12 s; Bluff Reach is 10 MB with **26 M** edges and opens in 0.57 s. Both
   axes matter; budget from the observed maximum, not a formula.

### 2.4 ⛔ Memory ratchets, and `SUModelRelease` returns nothing to the OS

**This is the single most important operational finding for a long-running service, and it was not
visible until Spike B measured one process per model.**

Live RSS through one process, reading five models and closing each:

```
SDK loaded, no model open                              63 MB
2618 Lavoie      open  631 MB   read  715 MB   close  571 MB
2414 Bluff Reach open  721 MB   read  724 MB   close  723 MB
2523 Wellington  open  725 MB   read  727 MB   close  726 MB
2605 MacDonough  open  726 MB   read  726 MB   close  726 MB
adelphi-designph open  726 MB   read  726 MB   close  726 MB
```

- ⛔ **Closing a model frees nothing back to the OS.** The process sits at its high-water mark
  forever.
- ✅ **It is not an unbounded leak**, which was worth establishing separately: reading *the same*
  model five times plateaus (296 → 295 → 407 → 407 → 407 MB), and after a large model the process
  settles flat again (715 MB across three further reads). It ratchets and then stops.
- ⚠ **The plateau sits above the largest single model's own peak** — 715 MB where Lavoie alone
  measured 603 in that run — so allocator fragmentation adds headroom on top.
- ⚠ **The memory is in the OPEN, not the walk.** Lavoie: 63 → 631 MB on `SUModelCreateFromFile`,
  then only 631 → 715 MB for the entire walk. The same shape as the timing in §2.3.
- **Two heavy models held open together are close to additive, not shared**: 63 → 631 → 798 MB, and
  973 MB after reading both. Plan for the sum, not the max.

★ **What this means for a real service**, and it is a genuine architecture input for Spike C:
**a persistent worker converges on the peak of the heaviest model it has ever seen, plus
fragmentation, and holds it for the life of the process.** For this corpus that is ~1 GB. So either
size every worker for the largest model the watcher may ever meet, or **recycle the process** after
N models. One process per model — which is what the cost gate does — is the conservative default and
costs only the ~0.07 s interpreter start plus the framework load.

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

### 3.4 ⛔ Identity: one of the two id flavours is scoped to the PROCESS

The contract carries two identifiers per entity, and Spike B established that they behave
completely differently — which decides what identity a *service* can offer.

| | `SUEntityGetPersistentID` | `SUEntityGetID` (the contract's `entity_id`) |
|---|---|---|
| scope | **the file** | **the process** |
| stable across reads? | ✅ yes — 883/883 entities joined to captures taken a week earlier in SketchUp | ❌ no |
| stable across process history? | ✅ yes | ⛔ **no** — reading thirteen other models first moves *every* one of Adelphi's 128 ids, and grows the capture 384 bytes |

Measured: two captures of one unchanged file are byte-identical from two working directories and two
output paths — but **0 of 15 stay byte-identical once another model has been read in the same
process**, and **15 of 15** are identical the moment `entity_id` is excluded.

⛔ **Consequence for a watcher: you cannot hash the capture to detect change.** Not as it stands.
Either exclude `entity_id` from the comparison, re-read in a fresh process, or drop the field. It is
also what made a concurrency check report a mismatch on **two plain parallel processes**, where
nothing concurrent was happening at all — *when a check fires on 100 % of your data, suspect the
check.*

⚠ **And a second exclusion joined it (POC #3 L-B, 2026-08-31): `tracker_data`.** designPH's save
re-dumps that table even when untouched — Ruby `Time` payloads re-serialised representation-only
(187 rows moved on Linde with zero value changes) — and every calc event (launch and re-initialise
included) appends a row. The contract-v2 capture deliberately omits `tracker_data`, so *capture*
hashing is unaffected; but anything hashing the `.skp` file itself, or a full model-table dump,
must canonicalise or exclude it (`DESIGNPH_DATA_MODEL.md` §14.7).

★ The good half is the one that matters: **the path-qualified persistent id is a real, file-stable,
cross-session identity**, reproducible byte-for-byte from a headless process. That is the foundation
a record-keeping product needs, and it comes from the file rather than from the reader.

### 3.5 ⚠ Two float values are equal and not identical, and `==` sees only the first

`-0.0 == 0.0` is `True` in Python (and in Ruby, and in C). `json.dumps` writes two different tokens.
So a field-by-field comparison passes while the hashes disagree, and the first symptom is
**canonically mismatched documents with no locatable difference**.

Measured across the five capture models: the C arithmetic reaches an exact zero from below where
Ruby reaches it from above on **72 coordinates**, always in that direction, at the 1e-17 level, on
`outer_loop` and `panel_outer_loop`. A vertex at `-0.0 m` is the same vertex; it is below every
tolerance in the project. **It matters only for hashing — which is exactly what change detection
is.**

⚠ **And it cannot be cleanly fixed at the source**, which was measured rather than assumed: making
the reader emit an unsigned zero takes the disagreements from 72 to **12, not to 0**, because both
readers emit `-0.0` on 12 more. Any capture format that wants byte-comparability across capture
devices has to specify this; it is not something a reader can quietly normalise away.

### 3.6 ⚠ A published *enum* is not the shipped enum

§3.3 records that a published API *name* is not a signature. The same is true of enum ordering, and
it costs more: the doxygen `SURefType` puts `Face` at **9**, while the API 13.0 header that ships
with the framework inserts `Environment` and `Environments` at 8 and 9, so **`Face` is 11** and
every member after `Edge` moves by two.

⛔ A host-face type check written against the documented order **rejects every glued host on every
model** — 0 of 239 — which reads exactly like "the glue query does not work", and it is not. Parse
the enums out of the framework's own headers; never transcribe them.

### 3.7 ⚠ Adelphi and Bluff Reach mask bugs — now three separate times

The corpus warning in `AGENTS.md` has earned a third instance in one spike:

1. **placements vs entities** — nothing in either model is placed twice, so the distinction is
   invisible (Linde 2466 → 1791, 250708 2456 → 1781);
2. **the enumeration gap (§3.2)** — 0 % on both, 40 % on Linde and 250708;
3. **`DesignPH_dict` on windows (§4.5)** — present on 9 of 16 models, absent on both.

**Neither model can validate a rule about designPH data.** Linde and 250708 are the ones that catch
structural errors; Holmes is the one that catches tag- and definition-shaped errors.

### 3.8 What has *not* been established

Spike B closed four of the six items this section used to list. What remains:

- ⛔ **Nothing ran on Trimble's own SDK** (§6). This is the one that matters commercially, and it is
  not a technical question.
- **macOS arm64 only.** Windows and Linux are untested — Spike C.
- ⚠ **Thread safety is observed, not proven.** Two threads in one process read two models and
  produced captures matching the sequential ones, with no errors. That is *one* observation, on two
  models, with no contention on a shared model handle. It is enough to say "not obviously
  forbidden"; it is not enough to build a threaded worker on.
- **No `.skp` was written or re-saved**, deliberately, and §3.1 means that must stay true.
- **Two of sixteen models can grade nothing.** `2618 Lavoie` has no offline baseline and no live
  capture — it proves the reader does not fall over at 146 MB and nothing about correctness. The
  designPH 1.0.30 sample is refused by the version gate, so it is evidence about the *refusal*, not
  about reading 1.x.
- **A genuinely large envelope is still unmeasured.** The largest classified-face count in the
  corpus is 194. `CONSTRAINTS.md` §8's "a model with >1000 classified faces" is open on both routes.

✅ Established since this list was written: per-model peak memory (§2.4), concurrency (§4.7), the
cost split between open and walk (§2.3), and whether a headless capture is *the same read* as a live
one (§1).

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

### 4.7 ⭐ Concurrency works — all three shapes of it

Spike A listed this as unknown and flagged it as mattering for a server. Measured, on the two
heaviest models, each producing captures **identical to the sequential ones**:

| | wall | peak RSS | captures match |
|---|---:|---:|---|
| two models open at once in one process | 2.49 s | 718 MB | ✅ |
| two processes in parallel | 2.57 s | — | ✅ |
| two threads in one process, one `SUInitialize` | 2.47 s | 718 MB | ✅ — no errors |

⚠ Read this as *"none of the three is forbidden"*, not as a thread-safety proof (§3.8). The
practical reading: **a worker pool of separate processes is available and boring**, which is the
answer a watcher wanted, and §2.4's memory ratchet is a much stronger argument for processes than
any thread-safety doubt.

⚠ The agreement check is what makes this worth anything. "It did not crash" is not "it read the same
thing", and an earlier version of this measurement reported *only* wall time — two threads silently
producing a wrong capture would have looked like a success.

### 4.8 ⭐ The headless reader knows things the in-SketchUp one cannot

Not an efficiency gain — a correctness one, and it was a surprise.

`collector.rb` has to derive the model's name from `Sketchup::Model#path`, which is **where the file
was last saved**. On 2 of 5 corpus copies that is somebody else's machine, and one live capture is
stamped `2523 Weiilington` — a backup's misspelling, carried into the HBJSON, the `Room` name and the
building segment. A headless reader is *handed the path it opened*, so it simply knows.

The general form is worth keeping: **the in-process reader is not automatically the more
authoritative one.** SketchUp's API answers questions about *the model*; a service also knows things
about *the file*, and file-level facts (which path, which mtime, which watched folder, which project)
are exactly what a record-keeping product is built on.

### 4.9 ⭐ A refusal is cheap and total

The version gate reads the model's designPH stamps in **0.000 s** once the file is open (§2.3), and
on a stamp it does not understand the reader exits non-zero and **writes nothing at all**. Measured
on the designPH 1.0.30 sample: refused by name, exit 2, no file.

That is the shape a passive watcher needs. It will meet files nobody vetted — other people's models,
old generations, non-designPH `.skp`s — and the failure mode to avoid is not a crash, it is a **plausible
partial capture that does not say it is partial**. The precedent is this repo's own: the offline
parser returned a clean *zero* on the 1.0.30 file and that stood for ten days.

## 5. What this means for the product

Every line here is a decision input with a measurement behind it, not a preference.

**The pipeline is proven, not just plausible.** A folder watcher plus this reader plus the POC's
**unmodified** translator produces HBJSON that is canonically identical to what SketchUp produces,
on five real projects. There is no remaining "will it work" question on macOS; the open questions
are legal, platform, and operational.

**Sizing, from §2.3 and §2.4:**

| | |
|---|---|
| a designPH read of a real project | **0.2–2.5 s**, whole 230 MB corpus 11.8 s |
| of which, opening the file | **43 %** — unavoidable, and there is no cheap peek |
| memory, per model | 104–718 MB peak · **63 MB** process floor |
| memory, after closing the model | ⛔ **unchanged** — it ratchets and never falls |
| a persistent worker converges on | the peak of the **heaviest model it has ever seen**, ≈1 GB here |

⛔ **So: one process per model, or recycle after N.** A long-lived worker that reads a stream of
client models will hold ~1 GB forever after it meets one big one. Process-per-model costs ~0.07 s of
interpreter start plus the framework load, which against a 0.2–2.5 s read is noise. This is the
clearest architecture input Spike C has.

**Admission control is `SUModelGetStatistics`, not file size** (§2.2) — but it needs the model open,
so it gates the *walk*, not the *open*. If a watcher needs to avoid opening some files at all, the
only free signals are the path, the extension and the mtime.

⛔ **Change detection cannot hash the capture as it stands** (§3.4). `entity_id` moves with process
history. Exclude it, re-read in a fresh process, or drop the field — and note that
`SUModelGetGuid` (§4.3) answers "has this file changed?" for one open call, which is very likely the
better instrument anyway.

⛔ **"Never save an opened model" is the safety property, and it must be structural** (§3.1). Reading
mutates the in-memory model — unavoidably, because the only complete way to test for an attribute
dictionary is the call that creates one. The reader used here cannot resolve a write symbol at all:
the binding declares none, and the loaded library is wrapped so that anything undeclared raises. The
binary exports six writers; the handle refuses six of six. **Do this by construction, not by
discipline** — for a watcher touching real client files it is the property that keeps hard rule 2
true.

**Privacy has three named exposures**, and the reader can strip all of them at the door:
`tracker_data` (usernames and a dated run history), embedded filesystem paths, and — the one that
was a surprise — **a building's real latitude and longitude** (§4.2), present on 5 of 16 models. The
last is client data by any reasonable reading, and it is *more* sensitive than most of what the
contract already treats carefully.

**A refusal must be total and must say why** (§4.9). A watcher meets files nobody vetted; the
failure to design against is a partial capture that looks complete.

**Version risk is far lower than the extension route's, and mostly evaporates** (§2.1) — one SDK
read files written by SketchUp 8 through 26, and the format has been versionless since 2021. The
*designPH* version axis is the live one, and it is handled by refusing what the reader does not
understand.

## 6. ⚠ The standing caveat

Every measurement here was taken with a **third-party re-host** of Trimble's proprietary
`SketchUpAPI.framework`, because Trimble's own SDK is behind a Request Access form with no reported
turnaround. Ed authorised that build for time-boxed laptop feasibility only, in parallel with filing
the form.

**Consequences:** licensing task **L1 (read the SDK EULA) cannot start** — the EULA ships inside the
gated download. Nothing here may ship. And re-running is cheap by design:
`planning/spikes/headless/run_gates.sh`, `run_gates_b.sh` and `a7_capability_probe.py` reproduce
every number in this document in about two minutes.

⚠ And a PASS here makes the **AGPL §13 reframing (L2) urgent rather than hypothetical**: a working
server-side path is exactly what triggers it. L2 is actionable now; L1 is not.

**A PASS on this evidence is a strong feasibility result and not a commercial green light.**

---

## Changelog

- 2026-08-29 — written from Spike A's eight gates and the `a7` capability sweep over 16 corpus files.
- 2026-08-29 — **substantially extended from Spike B**, which changed this document from "can it be
  read" to "what does it cost and where does it break":
  - **§2.3 the open dominates** — `SUModelCreateFromFile` is **43 %** of read time and most of the
    memory; the version stamps are free once open, so a pre-walk gate is a *safety* device, not a
    cost saving. §2.2's advice that `SUModelGetStatistics` is cheap triage is **corrected**: it
    needs the open, and there is no peek.
  - ⛔ **§2.4 memory ratchets and never falls.** `SUModelRelease` returns nothing to the OS; a
    persistent worker converges on the peak of the heaviest model it has ever seen (≈1 GB here) and
    holds it. Measured not to be an unbounded leak. **The clearest architecture input Spike C has.**
  - **§3.4 identity** — `SUEntityGetPersistentID` is file-stable and reproduces the live captures
    883/883; `SUEntityGetID` is **process**-scoped, so a watcher cannot hash the capture to detect
    change.
  - **§3.5 signed zero** and **§3.6 the shipped enum order** — two more ways to be equal-but-not-
    identical, and to be confidently wrong from published documentation.
  - **§3.8 rewritten** — four of its six open items are now closed.
  - **§4.7 concurrency works** (three shapes, all agreeing with sequential reads), **§4.8 the
    headless reader knows file-level facts the in-SketchUp one cannot**, **§4.9 a refusal is cheap
    and total**.
  - **§5 rewritten** around the measured sizing, the process-recycling conclusion, and the three
    named privacy exposures.
