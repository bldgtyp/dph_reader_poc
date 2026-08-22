# Phase 1 — Results — **gate: PASS WITH CHANGES**

**Run:** 2026-08-19 · **Box:** ~4 h · **Plan:** [`../PHASE-1_read-side-facts.md`](../PHASE-1_read-side-facts.md)
**Prerequisite:** Phase 0 — [`PHASE-0_results.md`](PHASE-0_results.md)

---

> **Closed 2026-08-19.** Ed ran the three staged SketchUp experiments; results and the gate verdict
> are in [**Live results**](#live-results-ed-2026-08-19) at the foot of this file. Two predictions
> were refuted — the shading filter, and (indirectly) the claim that thermal bridges sit on faces.
> Everything above this line is the offline half, kept as written; the corrections are marked
> where they land.

## Status — the offline half

Phase 1 was written as a wholly **[Ed in the loop]** phase: *"every experiment in this phase runs
inside SketchUp."* That premise turned out to be wrong for most of it. Grouping the offline
attribute records **by the entity that carries them** recovers per-face co-occurrence, which is what
§1.1, §1.3 and §1.4 actually needed — so three of the five sub-questions are answered here, against
all 14 corpus models rather than the one model Ed could reasonably click through.

| § | Question | State |
|---|---|---|
| 1.1 | `*ID` / `*Auto` precedence ⚠ blocking | **Answered offline** — and the question dissolves. Live confirmation staged |
| 1.2 | Window hosting and openings | **Not started.** Purely geometric; needs SketchUp. Staged |
| 1.3 | Remaining undocumented values | **Mostly answered.** `areaGroup`→`tempZone` confirmed per-face; `faceTypeAuto` partly decoded; `'xi'` still open |
| 1.4 | Where assembly build-ups live ⚠ | **Answered offline.** Zero unresolvable references corpus-wide |
| 1.5 | The untagged-face shading filter | **Half answered.** A candidate filter exists but is unavailable on 2 of 7 real models. Staged |

**Gate verdict at the time: withheld** — §1.2 was untouched and the gate names it explicitly
(*"windows have no resolvable host" → FAIL*). ✅ **Now closed: PASS WITH CHANGES.** See
[Live results](#live-results-ed-2026-08-19). Each staged script stated its expected observation
before it ran, which is what made two refutations legible as refutations rather than as noise.

## Findings

| # | Finding | Effect |
|---|---|---|
| 6 | **`*ID` and `*Auto` are never both populated on one face** — 0 cases in 14 models | §1.1's precedence question dissolves. The rule is a *coalesce*. `00_Context` §6 moves from CONTESTED to settled |
| 7 | **301 faces in 6 of 7 real models carry an `*Auto` value and no `*ID`** | Phase 0's own fallback rule ("prefer `*ID`") would have lost them. Both generations must be read |
| 8 | **`assemblyID` has two id namespaces**, chosen by area group — assemblies, or `connections_ud` thermal bridges | Explains 141 refs that looked unresolvable. **PRD §8.3 needs revising** |
| 9 | **Assemblies do not fully resolve from the model alone** — 95 of 532 refs resolve only against designPH's *installed* CSV library | PRD §8.3: v1 cannot promise a build-up for every surface |
| 10 | **Marshal blobs decode without Ruby** | `00_Context` §7's "Ruby-only" caveat is wrong, and Pyodide/`.rbz` portability is unaffected by it |
| 11 | **`areaGroup` → `tempZone` confirmed per-face**: 7931 pairs, 0 disagreements | Phase 0 Finding 1 upgraded from population arithmetic to observation |

---

## 1.1 — The `*ID` / `*Auto` precedence ⚠ **BLOCKING — resolved**

Full data: [`PHASE-1_face-attribute-matrix.md`](PHASE-1_face-attribute-matrix.md).

Phase 0 refuted the version-rename rule and proposed a fallback: `*ID` authoritative, `*Auto` a
cache, read `*ID`. It also flagged the one thing that would break that fallback — *can `*Auto` hold
a value on a face where `*ID` holds none?* — and recorded that the offline reader could not tell.

It can, once records are grouped per entity. Both halves now have answers, and they point the same way.

### Finding 6 — the two generations are mutually exclusive per face

Across all 14 corpus models, **not one face carries both `areaGroupID` and `areaGroupAuto`**, or both
`tempZone*`, or both `assemblyID*`. Every `both agree` and `both differ` cell in the matrix is zero.

This is a stronger result than a precedence rule, because it means **there is no precedence question
to answer.** The two keys are complementary, never competing:

```
value = face["...ID"] or face["...Auto"]     # never both, so order cannot matter
```

That also explains why Phase 0's evidence looked contradictory. `*ID` and `*Auto` are not two
generations of the same field at all — they are *the assignment* and *the auto-classification*, and
designPH writes exactly one of them per face depending on whether the user has classified it.

### Finding 7 — and "prefer `*ID`" would still have lost data

**301 faces across 6 of the 7 real project models** carry an `*Auto` value with no `*ID` counterpart.
The worst case is not marginal:

| Model | Pair | Faces reading empty under "prefer `*ID`" |
|---|---|--:|
| `250708.skp` (Linde, 2.1.15) | `assemblyID` | **92 of 92** — every assembly assignment in the model |
| `2523 Wellington.skp` | `tempZoneID` | 169 |
| `250703 - Linde Residence.skp` | `areaGroupID` | 8 |
| `2605 MacDonough.skp` | `tempZoneID` | 13 |

`250708.skp` is the decisive one: reading only `assemblyID` returns **zero** assemblies on a real
2.1.15 project model. That is the same class of silent total loss that Phase 0's Finding 2 caught in
the version rule — arrived at from the opposite direction.

**Note this is not version-keyed either.** `250708.skp` is 2.1.15 and stores assemblies in `*Auto`;
`2414 Bluff Reach.skp` is 2.2.24 and stores them in `*ID`. Any rule keyed on the version stamp is
wrong. Coalescing is version-independent, which is why it survives.

### The rule, for the reader

```
areaGroup = face["areaGroupID"]  or face["areaGroupAuto"]
tempZone  = face["tempZoneID"]   or face["tempZoneAuto"]
assembly  = face["assemblyID"]   or face["assemblyIDAuto"]
```

With two standing obligations: **type-check every read** (hard rule 5 — `areaGroupID` is a String
`'n'` on most faces), and **report** any face that somehow carries both, since the corpus says that
should be impossible and a violation means the model is not what we think it is.

### Still to confirm live ⚠

`model.dat` retains historical state, so the offline reader cannot distinguish a live entity from a
deleted one. Finding 6 is a statement about **7,900 dictionaries that were written at some point**,
which is strong but not a census. [`live_1-1_generation_check.rb`](../spikes/phase1/live_1-1_generation_check.rb)
walks live faces only and prints the same table; the expected result is that every `both` count is 0.
The same script dumps a selected face before and after Ed changes its area group in the designPH UI —
the write-side half of the question, which no offline method can reach.

## 1.2 — Window hosting and openings — **NOT STARTED**

Nothing here is readable offline: `glued_to`, `cuts_opening?` and face loops are all live-geometry
questions, and the `.skp` geometry stream is out of scope (and adjacent to the licence line the PRD
draws at §9). [`live_1-2_window_hosting.rb`](../spikes/phase1/live_1-2_window_hosting.rb) is the plan's
script, extended to summarise rather than only list, and syntax-checked with `ruby -c`.

**This is the one open item that can still FAIL the gate.** Its two consequential outcomes are
unchanged from the plan: `glued_to` mostly nil makes geometric projection the primary path, and
`cuts_opening?` true with holed host faces revises PRD §8.2.

## 1.3 — The undocumented values

### Finding 11 — `areaGroup` → `tempZone`, now observed rather than inferred

**7,931 face-level pairs across 14 models. Zero disagreements** with the table Phase 0 derived from
the PHPP's own `Areas` summary. Phase 0's stated caveat — *"a count-level match, not a per-face
match"* — is discharged; the mapping is per-face fact.

The one apparent exception was a gap in this script's expectation table, not in the data: groups
12–14 are PHI's *user-defined* slots and pair with `'X'`, which Phase 0 recorded and the first run
here omitted. Corrected.

**Consequence, unchanged and now safe to rely on:** the translator needs only the area group, and
reading `tempZone` too is a free integrity check. A pair that disagrees means an inconsistent model
and should be reported.

### `faceTypeAuto` — partly decoded, and not a universal key

Values corpus-wide are exactly `'xo'`, `'i'`, `'xi'`. The area-group cross-tab reads clearly for two
of them:

- **`'xo'`** co-occurs with groups 8, 9, 10, 11 — external wall (ambient and ground), roof, floor
  slab. It is the **exterior opaque envelope**. On untagged faces it marks geometry that *looks*
  like envelope but has not been classified.
- **`'i'`** co-occurs overwhelmingly with `'n'` (untagged) and occasionally 8/10/14. **Interior.**
- **`'xi'`** — 19 faces in Adelphi, 5 in Linde 250703, 1 in 250708, and **always on an untagged
  face**. Never once beside a classified area group. Still undecoded; too small and too consistent a
  population to guess from. Staged for a live look in
  [`live_1-5_shading_filter.rb`](../spikes/phase1/live_1-5_shading_filter.rb), which prints each
  `'xi'` face's area, normal, nesting depth and tag.

⚠ **`faceTypeAuto` is absent from `2414 Bluff Reach.skp` and `2605 MacDonough.skp` entirely** — two
of the seven real models. Whatever it is, designPH does not always write it, so nothing in the
reader may *depend* on it. That is what stops §1.5 closing here.

### The `descName` triple

`descNameFreeze` is **independent of whether `descName` exists**. `2523 Wellington.skp` carries it
`true` on 116 faces while carrying no `descName` at all. So Freeze is not "an override exists" — it
is "stop regenerating this name", and it can lock a *generated* name in place.

No face anywhere carries `descName` without `descNameAuto` except in `2605 MacDonough.skp` (34, all
of its classified faces). Phase 0 Finding 5's consequence holds unchanged: **`display_name` must
prefer `descName` and fall back to `descNameAuto`.**

### `areaGroupID = 'n'`

Behaves exactly as an unassigned marker throughout: 1359 faces in Adelphi, all pairing with
`tempZoneID = 'i'`, none carrying an assembly. Nothing else hides in the bucket. Confirmed as far as
offline data can — the live scripts re-check it on real entities.

## 1.4 — Where assembly build-ups live ⚠ — **resolved**

Full data: [`PHASE-1_assembly-resolution.md`](PHASE-1_assembly-resolution.md).

Phase 0 flagged that faces reference assemblies with no `layer_table_<id>` anywhere in the model —
Adelphi referencing `83ud`–`95ud` with *zero* layer tables, Bluff Reach reaching `114ud` while
carrying only `01ud`–`06ud`. PRD §8.3 assumes `layer_table_<id>` is the source.

Decoding every Marshal blob in all 14 models and checking every face reference against it:

| Tier | Refs (7 real models) | What is readable |
|---|--:|---|
| `layer_table_<id>` in the model | 254 | **The full build-up** — 3 parallel material/lambda paths and a thickness |
| Model `assemblies_*` header only | 42 | Name, U-value, thickness. **No layers** |
| designPH's *installed* CSV library | 95 | Name and defaults, from outside the model |
| `connections_ud` — a thermal bridge | 141 | Psi-value and f_Rsi. **Not an assembly at all** |
| **Unresolvable** | **0** | — |

### Finding 8 — `assemblyID` carries two id namespaces, and the key name does not say which

The 141 references that looked unresolvable are **thermal bridges**. A face in PHPP area group 15,
16 or 17 — the groups entered on the `Areas` worksheet as *lengths*, not areas — points `assemblyID`
at a `connections_ud` row, not at an assembly:

```
connections_ud: ['101ud', 'Footing',            17, 'Thermal Bridges Floor Slab / Basement Ceiling', 0.04, 0.7]
                ['102ud', 'BG to AG Wall',      16, 'Perimeter Thermal Bridges',                     0.04, 0.7]
                ['103ud', 'Intermediate Floor', 15, 'Thermal Bridges Ambient',                       0.04, 0.7]
```

Bluff Reach has 55 + 16 + 28 = 99 thermal-bridge faces and had 99 "unresolvable" references; Holmes
13 + 16 + 13 = 42 and 42. Exact, on both models.

**The area group is the discriminator**, and it must be read *before* the assembly is looked up.
Resolving a thermal bridge against the assembly table would silently return either nothing or —
worse — a real assembly that happens to share the id, since both namespaces use `NNud`.

### Finding 9 — and the model is not self-contained

95 references (Adelphi's `83ud`–`95ud` bucket, Linde 250708's whole assembly set) resolve only
against `phpp_assemblies_ud.csv` in designPH's **installed** `Plugins/designPH/data/` folder. Both
the installed 2.2.29 and the 2.4.0 BETA ship the same `83ud`–`99ud` defaults, so this is stable —
but it is *outside the model*, version-dependent, and gone on a machine without designPH.

Adelphi is the exception that shows the mechanism: it carries an `assemblies_ud` blob — a snapshot of
that same library saved into the model — which is why its 42 references resolve where Linde
250708's 92 identical-looking ones do not.

### Consequences for PRD §8.3

1. **v1 cannot promise a layer build-up for every surface.** Only the `layer_table_<id>` tier has
   one; that is 254 of 532 references in the real corpus, under half.
2. **Read the area group first, then choose the namespace.** Thermal bridges are not assemblies.
3. **Report every tier below "layers"**, per hard rule 4 — an assembly with a U-value but no build-up
   is a legitimate, common state, not an error, and the report should say which it is.
4. Resolving against the installed library is *possible* (the extension runs inside SketchUp beside
   designPH's own files) but makes output depend on the reader's machine. Recommend v1 reads it,
   records the source, and never silently substitutes a default.

### Finding 10 — and it decodes without Ruby

`00_Context/DESIGNPH_DATA_MODEL.md` §7 states these blobs are **"Ruby-only — every other reader needs
a Ruby to decode"**, and warns that `Marshal.load` executes. Both are addressed by
[`ruby_marshal.py`](../spikes/phase1/ruby_marshal.py), a Marshal 4.8 reader that constructs nothing:
unknown classes become inert records of their name. Every blob in all 14 models decodes, including
`tracker_data`, which embeds a Ruby `Time`.

This does not change the shipping architecture — the extension is Ruby and reads these natively —
but it removes a stated portability constraint from the record, and it is what let this analysis run
across the whole corpus offline.

## 1.5 — The untagged-face shading filter — **half answered**

The candidate the plan named first is the right one, and it is not sufficient alone.

`faceTypeAuto` splits Adelphi's 1359 untagged faces cleanly:

| Value | Faces | Reading |
|---|--:|---|
| `'xo'` | 420 | Exterior opaque — **shading candidates** |
| `'i'` | 405 | Interior — partitions and clutter. **Must not be exported** |
| `'xi'` | 19 | Undecoded |
| nil | 515 | designPH never classified them |

That is a real signal, and it matches Phase 0 Finding 4's refutation of the blanket rule: the
untagged bucket genuinely is mixed, and this key separates the mixture.

**But it is not available everywhere.** Bluff Reach and MacDonough carry no `faceTypeAuto` at all,
and 515 of Adelphi's untagged faces have it nil. A filter resting on it alone would export nothing
on two of seven real models — the mirror image of the failure Phase 0 caught in the version rule.

So the filter needs a geometric second leg, and that needs SketchUp.
[`live_1-5_shading_filter.rb`](../spikes/phase1/live_1-5_shading_filter.rb) buckets every untagged
live face by `faceTypeAuto` × inside-the-tagged-envelope-bbox × nested × tag, which is the smallest
evidence set that can decide between the candidates the plan lists.

**Standing position until it does:** untagged faces are **reported, not exported.** A filter that is
not obviously right is worse than no filter — mis-exported furniture becomes wrong shading
downstream, silently.

---

## Deliverables

| Item | Path |
|---|---|
| Per-face attribute matrix | [`PHASE-1_face-attribute-matrix.md`](PHASE-1_face-attribute-matrix.md) · [`baselines/phase1_face_attributes.json`](baselines/phase1_face_attributes.json) |
| Assembly resolution + table schemas | [`PHASE-1_assembly-resolution.md`](PHASE-1_assembly-resolution.md) · [`baselines/phase1_assemblies.json`](baselines/phase1_assemblies.json) |
| Spike code | [`../spikes/phase1/`](../spikes/phase1/) — 3 Python, 3 Ruby |

No corpus file was modified. No `DesignPH_dict` was written. No SketchUp was involved.

## Documents updated

| Document | Change |
|---|---|
| `00_Context/DESIGNPH_DATA_MODEL.md` | §5 `faceTypeAuto` co-occurrence evidence · §6 **CONTESTED → settled** as a coalesce, with Findings 6 and 7 · §7 the `assemblies_ud` schema, the two id namespaces, and the "Ruby-only" caveat corrected · §12 open questions re-ranked |
| `DESIGNPH-PLUS_PRD.md` | §8.3 rewritten around the four resolution tiers and the two namespaces |
| `planning/PHASE-1_read-side-facts.md` | Progress banner; §1.1, §1.3, §1.4 marked answered; §1.2 and §1.5 carry the staged scripts |
| `planning/00_OVERVIEW.md`, `planning/.index.md`, `RESULTS/.index.md`, `spikes/.index.md` | Status and new files |

## What Ed needs to run

**Step-by-step: [`PHASE-1_ed-runbook.md`](PHASE-1_ed-runbook.md).** Working copies are already made at
`~/Desktop/dph_phase1_copies/`; each script writes its output to `phase1_live/` rather than needing
the console copied out. Summary:

| Script | Model | Expected observation |
|---|---|---|
| [`live_1-1_generation_check.rb`](../spikes/phase1/live_1-1_generation_check.rb) | `2414_Bluff Reach.skp` — the model that broke the old rule | Every `both` count **0**. Then select one classified face, `BTPhase1.dump_selected`, change its area group in the designPH UI, dump again |
| [`live_1-2_window_hosting.rb`](../spikes/phase1/live_1-2_window_hosting.rb) | `adelphi-designph.skp` — 44 apertures in the reference | How many windows return a non-nil `glued_to`; whether `cuts_opening?` is true; whether host faces have inner loops |
| [`live_1-5_shading_filter.rb`](../spikes/phase1/live_1-5_shading_filter.rb) | `adelphi-designph.skp`, then `2414_Bluff Reach.skp` (no `faceTypeAuto`) | Whether `'xo'` untagged faces sit outside the envelope bbox and `'i'` ones inside; what the 19 `'xi'` faces actually are |

## Handover

1. **§1.2 is the gate.** It is the only remaining item that can turn Phase 1 into a FAIL.
2. **§1.5 needs the geometric leg** before any untagged face is exported.
3. **`'xi'` is the last undecoded face-level value.** Small, consistent, always untagged.
4. **PRD §8.3 is rewritten but its acceptance criteria are not.** If v1 cannot promise a build-up per
   surface, §11 should say what it *does* promise.
5. Phases 2 and 3 are **not blocked** by any of this — they are runtime questions, and nothing found
   here touches them.

---

# Live results (Ed, 2026-08-19)

Raw output: [`phase1_live/`](phase1_live/). Two of the five predictions were wrong, and the second
one is the more useful failure.

| Run | § | Verdict |
|---|---|---|
| 1 | 1.2 windows | ✅ **PASS** — `glued_to` resolves on **46 of 46**. Host lookup is solved |
| 2 | 1.5 shading filter | ❌ **Prediction refuted.** Neither signal discriminates. §1.5 is *not* solved |
| 3a | 1.1 read side | ✅ **Confirmed live** — `both=0` on all three pairs |
| 3b | 1.1 write side | ✅ **Confirmed** — designPH updates `*ID` in place; no `*Auto` appears |
| — | 1.4 | ⚠ **Correction: thermal bridges are on EDGES, not faces** |

## Finding 12 — ⚠ thermal bridges are attached to **edges**, and a face-only reader loses all of them

Run 3a walked live **faces** on Bluff Reach and found **194** carrying `areaGroupID` where the
offline reader counts **293** records. It found **54** carrying `assemblyID` where the offline reader
counts **153**. Both gaps are **99** — and 99 is exactly that model's thermal-bridge count
(groups 15 + 16 + 17 = 55 + 16 + 28).

Three independent lines agree:

| Evidence | Result |
|---|---|
| Live face walk | 293 − 99 = **194** ✓ · 153 − 99 = **54** ✓ |
| Cached materials | The 99 thermal-bridge blocks **never** carry `Material`/`BackMaterial`. designPH writes those only when it repaints a *face* (§5.1) |
| PHPP semantics | Groups 15–17 are entered on `Areas` as **lengths**, not areas. An edge is the natural carrier |

**This corrects Finding 8 above**, which said "a *face* in area group 15, 16 or 17". It is an edge.
The two-namespace conclusion stands and is strengthened — but the mechanism is not one key doing
double duty on one entity type. It is **two entity types**, and the reader must walk both.

⚠ **A translator that iterates `Sketchup::Face` loses every thermal bridge, silently** — the exact
failure hard rule 4 exists to prevent. Confirming script staged:
[`live_1-4_edge_thermal_bridges.rb`](../spikes/phase1/live_1-4_edge_thermal_bridges.rb), which
deliberately reports **every** entity class carrying a `DesignPH_dict` rather than only checking for
edges — assuming the answer is how this was missed the first time.

## 1.2 — Windows ✅ **PASS**, with one revision to PRD §8.2

```
windows found: 46          glued_to non-nil: 46 / 46          cuts_opening?: 46 / 46
distinct host faces: 16    hosts with inner loops (holes): 1 / 16
```

**Host lookup is solved.** Every window returns a host face. Geometric nearest-coplanar-face
projection is not needed at all — the risk the plan flagged (*"more work, more failure modes"*) is
retired. 46 windows against the reference HBJSON's 44 apertures is the right neighbourhood.

**But `cuts_opening?` is not the question it looks like.** It is `true` on all 46 — and yet only
**1 of 16 host faces** carries inner loops. The one that does (face 7805, 80.76 m², `loops=3`) has
two holes; the other fifteen are unbroken, several hosting six windows each.

`cuts_opening?` is a property of the component **definition** — *"this component is able to cut"* —
not a fact about the host. Reading it as evidence that the host has a hole would have put a hole in
every `Face3D` we emit and left 44 apertures with nothing to fill. That is precisely the
"plausible-looking and wrong" failure this phase exists to catch.

**PRD §8.2:** windows sit on **unbroken** faces, so project-and-validate-containment stands as
specced. But **test `face.loops.size > 1` per face** — holes do occur, and inferring from
`cuts_opening?` is wrong in 15 cases out of 16.

## 1.1 — Confirmed on both sides ✅

**Read side (run 3a, live faces on Bluff Reach):**

```
areaGroupID   id_only=194  auto_only=0  both=0  neither=7273
tempZoneID    id_only=194  auto_only=7  both=0  neither=7266
assemblyID    id_only=54   auto_only=0  both=0  neither=7413
```

`both=0` on all three, against **live** entities. The historical-state caveat on Finding 6 is
discharged. `auto_only=7` on `tempZoneID` matches the offline count for this model exactly.

**Write side (run 3b) — the half no offline method could reach.** One classified face, before and
after changing its area group in the designPH UI:

| Key | Before | After |
|---|---|---|
| `areaGroupID` | `10` (Integer) | **`14`** — updated **in place** |
| `tempZoneID` | `"A"` | **`"X"`** — followed the area group |
| `assemblyID` | `"05ud"` | `"05ud"` — untouched |
| `Material` / `BackMaterial` | *absent* | **`"Default"`** — appeared |

Three things settle at once:

1. **No `areaGroupAuto` appeared.** designPH writes the `*ID` generation on user assignment. The
   coalesce rule (§6.5) is confirmed from the write side, and the first row of §1.1's decision table
   is the one that matched.
2. **`tempZoneID` moved `A` → `X` to follow group 10 → 14** — Finding 11's mapping, confirmed by a
   live write rather than by counting. Group 14 is a user-defined slot and pairs with `X`, exactly as
   the PHPP `Areas` summary says.
3. **`Material`/`BackMaterial` appeared on the change**, confirming §5.1: they are a stash written
   when designPH repaints a face for the coloured display mode, not a material assignment. They also
   turn out to be the signature that distinguishes a face record from an edge record (Finding 12).

## 1.5 — ❌ The filter prediction is refuted. Shading geometry cannot ship on a heuristic

**The stated expectation was:** `'xo'` faces mostly outside the envelope, `'i'` faces mostly inside.
**Adelphi says otherwise:**

| `faceTypeAuto` | outside envelope | inside envelope |
|---|--:|--:|
| `'xo'` | 252 | 168 |
| `'i'` | 167 | 238 |
| `'xi'` | 10 | 9 |
| nil | 7050 | 61 |

A 60/40 and 59/41 split is not a discriminator. **Neither signal separates shading from clutter, and
they do not agree with each other.** The bounding-box test is also weaker than it looked: the
envelope bbox is the *tagged* faces' extent, so "inside" means "within the building volume" — which
contains both interior partitions and the envelope's own faces.

And the scale is worse than the offline record suggested. Adelphi has **8037 live faces**, not the
1441 the offline reader saw — only **82** are tagged, leaving **7955** untagged. Bluff Reach: 7467
live, 194 tagged, **7273** untagged. Any rule that exports untagged-and-outside would emit ~6700
shades where the reference HBJSON has 1287.

### But a better signal turned up, and it is not a heuristic at all

Both models carry **SketchUp tags that name the intent outright**:

| Model | Tag | Faces |
|---|---|--:|
| Adelphi | `04_SHADING_TREES` | 392 |
| Bluff Reach | `Shading_Tree` | 4 |
| Bluff Reach | `*Vn50` | 360 |

The modeller already said which geometry is shading. Nothing needs inferring — but the tag *names*
are user-authored and differ between models, so no fixed rule can read them either.

**Recommendation — stop guessing and ask.** v1 should present the model's tag list and let the user
choose which tags are shading geometry, defaulting to none. That is a small UI, it is exactly hard
rule 4 applied at the design level rather than the reporting level, and it is right on every model
including ones with no `faceTypeAuto` at all. The alternative — any of the heuristics considered
here — silently exports furniture as shading on some models and nothing on others.

⚠ **Until that exists, shading geometry should come *out* of v1 scope** rather than ship on a filter
this evidence does not support. PRD §7.2 updated. Phase 0's promotion of shading into v1 was made on
the strength of the destination being well-formed, which is still true; the *source* rule is what has
now failed twice.

### `'xi'` — characterised, not yet identified

19 faces in Adelphi, **0 in Bluff Reach**. Every one is nested at depth 1, horizontal, normal exactly
`(0,0,1)`, and — except the last at 0.01 m² — **all exactly 0.26 m²**. Identical size, identical
orientation, repeated: this reads as one repeated component, not as building fabric.

**[Ed]** the entity ids are in [`phase1_live/1-5_shading_filter__adelphi-designph_COPY.txt`](phase1_live/1-5_shading_filter__adelphi-designph_COPY.txt)
(`14164`, `14208`, `14216`, …). Selecting one in the model and saying what it is closes the last
undecoded value in the face-level schema.

## Gate — **PASS WITH CHANGES**

The FAIL conditions are both cleared: windows have a resolvable host (46/46), and a consistent
per-face rule for the key generations exists and is confirmed on both the read and write sides.

Carried into the record rather than left open:

| Change | Where |
|---|---|
| Thermal bridges are on **edges**; a face-only reader loses them | `00_Context` §7.1, PRD §8.3, AGENTS.md |
| `cuts_opening?` is a definition capability, not a host fact — test `loops` per face | PRD §8.2 |
| Shading geometry **out of v1 scope** until the user can choose tags | PRD §7.2 |

Still open, and neither blocks Phase 2: the `'xi'` identification, and confirming the edge walk with
[`live_1-4_edge_thermal_bridges.rb`](../spikes/phase1/live_1-4_edge_thermal_bridges.rb).

**Phase 2 is unblocked.**
