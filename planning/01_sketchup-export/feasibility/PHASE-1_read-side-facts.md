# Phase 1 — Read-Side Facts (S2 + S3)

> ✅ **CLOSED 2026-08-19 — PASS WITH CHANGES.** [`RESULTS/PHASE-1_results.md`](RESULTS/PHASE-1_results.md). This file is the plan as written; every ⬜ item in it was settled there — and ⚠ several of its inferences were later overturned by the POC's real-model runs (`00_Context/` is what is true now).

**Box:** ~4 h *(was 3 h — Phase 0 added §1.4 and §1.5)*
**Gate:** can the read layer be built as the PRD specifies?
**Prerequisite:** Phase 0 complete — [`RESULTS/PHASE-0_results.md`](RESULTS/PHASE-0_results.md)

> ✅ **Complete — PASS WITH CHANGES. [`RESULTS/PHASE-1_results.md`](RESULTS/PHASE-1_results.md) (2026-08-19).**
>
> | § | State |
> |---|---|
> | 1.1 | ✅ **answered offline** and the question dissolves — the generations are mutually exclusive per face, so the rule is a coalesce. Live confirmation staged |
> | 1.2 | ✅ **PASS** — `glued_to` resolves 46/46. But `cuts_opening?` is a definition capability, not a host fact: only 1 of 16 hosts has holes |
> | 1.3 | ✅ mostly — `areaGroup`→`tempZone` confirmed per-face, `faceTypeAuto` partly decoded, `'xi'` still open |
> | 1.4 | ✅ answered offline, then ⚠ **corrected live** — thermal bridges are on **edges**, not faces. A face-only reader loses all of them |
> | 1.5 | ❌ **refuted** — neither `faceTypeAuto` nor the bbox test discriminates. Shading geometry leaves v1 scope; v1 will ask the user which tags are shading |
>
> **This phase's premise was wrong, and usefully so.** It assumed every experiment needed SketchUp.
> Grouping the offline attribute records *by the entity that carries them* recovers per-face
> co-occurrence, which answered §1.1, §1.3 and §1.4 across all 14 corpus models instead of the one
> model Ed could click through. Three scripts in [`../../spikes/phase1/`](../../spikes/phase1/) cover what is
> genuinely live-only.

---

## Objective

Settle every remaining unknown about *reading* a designPH model, before writing a translator that
depends on those assumptions. Five sub-questions: the `*ID`/`*Auto` precedence (reopened by Phase 0
and **blocking**), window hosting, the remaining undocumented enum values, where assembly build-ups
live, and the filter that decides which untagged faces become shading geometry.

**[Ed in the loop] — for what is genuinely live-only.** §1.2 and the geometric half of §1.5 need
SketchUp: `glued_to`, `cuts_opening?`, face loops and bounding volumes are not in the attribute
stream. §1.1's write-side half (which key does designPH write when the user re-classifies a face?)
needs the UI. Everything else turned out to be readable offline. The agent prepares each script and
states the expected observation *before* Ed runs it; Ed executes and pastes the output back.

## 1.1 — Settle the `*ID` / `*Auto` precedence ⚠ **BLOCKING** (S3, reopened by Phase 0)

**The version rule is no longer "mostly resolved" — Phase 0 refuted it.** Read
`00_Context/DESIGNPH_DATA_MODEL.md` §6.2 and `RESULTS/PHASE-0_results.md` Finding 2 before starting.

The rule §6.1 proposed was:

```
if designPH_version >= 2.2:  read areaGroupAuto, tempZoneAuto, assemblyIDAuto
else:                        read areaGroupID,   tempZoneID,   assemblyID
```

Baselining all 14 corpus models showed **every real project model stores its real data in the `*ID`
generation, whatever the version stamp.** `areaGroupAuto` is entirely absent from four of the five
2.2-stamped project models. Applying the rule above to `2414 Bluff Reach.skp` — a clean 2.2.24 model
with no 2.1 history — reads **0 area groups, 0 assemblies, and 7 of 293 temperature zones.** The one
model that fits §6.1's description is the six-face auto-classified test file it was derived from.

**The revised reading (§6.3): `*ID` is the authoritative assignment, `*Auto` is the
auto-classification cache.** This phase must confirm or refute it *per-face*, live. The offline
reader reads records, not entities, and `model.dat` retains historical state — it cannot settle this.

> ⚠ **The last sentence is superseded (2026-08-19).** The offline reader groups records by
> *dictionary instance*, and each instance is one entity — so per-face co-occurrence is readable
> offline after all. It settled the read side: the two generations are **never both populated on
> one face** (0 cases in 14 models), so the rule is a coalesce and §6.3's "prefer `*ID`" is also
> wrong — it would lose 301 faces, including every assembly in `250708.skp`. See
> `00_Context/DESIGNPH_DATA_MODEL.md` §6.5.
>
> What remains live-only is the **write** side — step 3 below — plus confirming the count against
> live rather than historical entities. Both are in
> [`../../spikes/phase1/live_1-1_generation_check.rb`](../../spikes/phase1/live_1-1_generation_check.rb).

### The experiment

In SketchUp with designPH loaded, on a **copy** (hard rule 3):

1. Open a copy of `2414 Bluff Reach.skp` — a clean 2.2.24 model with 293 `areaGroupID` and **no**
   `areaGroupAuto`. This is the model that breaks §6.1, so it is the one to test on.
2. With the BT Attribute Inspector, dump one classified envelope face. Record **both** generations,
   and whether `areaGroupAuto` exists on that face at all.
3. Change **only** that face's area group in the designPH UI. Re-dump.
4. Repeat on an *unclassified* face: assign it an area group for the first time, and see which key
   designPH writes.

| Observation | Conclusion |
|---|---|
| `areaGroupID` updates in place; no `areaGroupAuto` appears | **§6.3 confirmed.** Read `*ID`; treat `*Auto` as a cache. Version-keyed reading is dropped |
| A new `areaGroupAuto` appears carrying the new value | Both live simultaneously — the precedence question is real. Determine which designPH itself reads back |
| `areaGroupAuto` appears and `areaGroupID` is cleared | A migration, not a rename. Read `*Auto` when present, `*ID` otherwise |

**The question that decides the reader**, and the one the offline data cannot answer: *can `*Auto`
ever hold a value on a face where `*ID` holds none?* If yes, a naive "prefer `*ID`" rule loses data
just as §6.1's rule does. Check it directly — dump every face of one model and count.

> ✅ **Answered — yes, it can.** 301 faces across six of the seven real project models. The worst
> case is `250708.skp`, where reading only `assemblyID` returns **zero** assemblies. This is why the
> rule is a coalesce rather than a preference.

**FAIL condition:** no consistent per-face precedence exists. The read layer then needs redesigning
around reporting ambiguity rather than resolving it.

## 1.2 — Window hosting and openings (S2) — ✅ **PASS**

Decides the aperture strategy in PRD §8.2. Staged and syntax-checked as
[`../../spikes/phase1/live_1-2_window_hosting.rb`](../../spikes/phase1/live_1-2_window_hosting.rb) — same
approach as below, summarising counts rather than only listing. Paste into the Ruby Console with a corpus model open:

```ruby
def find_windows(ents, xform, out)
  ents.each do |e|
    case e
    when Sketchup::ComponentInstance
      if e.definition.name =~ /designPH_Window/i
        out << [e, xform]
      else
        find_windows(e.definition.entities, xform * e.transformation, out)
      end
    when Sketchup::Group
      find_windows(e.entities, xform * e.transformation, out)
    end
  end
  out
end

wins = find_windows(Sketchup.active_model.entities, Geom::Transformation.new, [])
puts "windows found: #{wins.size}"
wins.first(20).each do |inst, _x|
  b = inst.definition.behavior
  host = inst.glued_to
  puts format("%-28s id=%-6d is2d=%-5s cuts=%-5s snapto=%-2s glued_to=%s",
              inst.definition.name, inst.entityID,
              b.is2d?, b.cuts_opening?, b.snapto,
              host ? "#{host.class.name}##{host.entityID}" : "nil")
end
```

Then check whether host faces carry openings — a face with more than one loop has a hole:

```ruby
wins.map { |i, _| i.glued_to }.compact.uniq.first(10).each do |f|
  puts "face #{f.entityID}: loops=#{f.loops.size} area=#{(f.area*0.00064516).round(2)} m2"
end
```

**Record:** how many windows return a non-nil `glued_to`; whether `cuts_opening?` is true; whether
host faces have inner loops.

**Consequences:**

| Finding | Consequence |
|---|---|
| `glued_to` non-nil for most windows | Host lookup is solved. Geometric projection becomes fallback only |
| `glued_to` mostly nil | Geometric nearest-coplanar-face becomes the primary path — more work, more failure modes |
| `cuts_opening?` true, host faces have inner loops | **PRD §8.2 needs revising.** The Honeybee `Face3D` has a hole and the `Aperture` must fill it, rather than sitting on a solid face |
| `cuts_opening?` false | Windows sit on unbroken faces; project-and-validate-containment as specced |

## 1.3 — Close the undocumented values

Phase 0 closed most of this list from the PHPP's own labels. What remains:

- ✅ **`areaGroupID = 18`** — *resolved:* "Building element towards neighbour" (§5.3).
- ✅ **`tempZoneID` `'i'` vs `'I'`** — *resolved:* `'I'` is the neighbour condition (group 18); `'i'`
  is designPH's untagged marker (§5.3.1). The whole `tempZone` value space is decoded.
- ⬜ **`areaGroupID = 'n'`** (String, on 1359 of 1441 Adelphi faces) — still to confirm live that it
  means unassigned/none, and that nothing else hides in that bucket.
- ⬜ **`faceTypeAuto`** `'xo'` / `'xi'` / `'i'` / nil — encoding still not established. The `x`/`i`
  prefix reads as exterior/interior; the second letter is unknown. **This is now the only wholly
  undecoded face-level enum.**
- ⬜ **Confirm the `areaGroup` → `tempZone` mapping per-face.** §5.3.1 is inferred from exact
  population arithmetic across five models, not observed face by face. Cheap to check with the
  Inspector, and a wrong mapping puts a wrong temperature zone on every surface. Dump one model's
  faces and assert the pair against the table.
- ⬜ **`descName` vs `descNameAuto` vs `descNameFreeze`** — confirm the override/lock semantics
  (§5.2) and that `descName` is what designPH's UI shows the user.

Cross-reference against `adelphi-designph_PHPP10.ppp` **by eye only** (do not write a parser — licence
§2.4(a)). The `adelphi-phpp.xlsm` Areas and U-values worksheets are already extracted to
`RESULTS/phpp/`.

## 1.4 — Where do assembly build-ups actually live? ⚠ (S3) — ✅ **ANSWERED**

> **All three candidates below were partly right, and a fourth was missed.** Faces resolve in four
> tiers with **zero unresolvable references** corpus-wide — but only 254 of 532 carry a build-up, and
> `assemblyID` turns out to carry **two id namespaces** chosen by area group (thermal bridges point
> at `connections_ud`, not at an assembly). The blobs also decode without Ruby. See
> [`RESULTS/PHASE-1_assembly-resolution.md`](RESULTS/PHASE-1_assembly-resolution.md) and
> `00_Context/DESIGNPH_DATA_MODEL.md` §7.1. PRD §8.3 has been rewritten.


Faces reference assemblies that have **no `layer_table_<id>` key in the model**: Adelphi's faces
reference `83ud`–`95ud` with *zero* `layer_table_*` keys; Bluff Reach references up to `114ud` while
carrying only `01ud`–`06ud`. PRD §8.3 assumes `layer_table_<id>` is the source, and calls assemblies
*"the easiest place to be quietly wrong."*

Three candidates: inside the `assemblies_calc` / `assemblies_ud` Marshal blob; resolved against the
shipped library CSVs under `.../Plugins/designPH/data/`; or genuinely unresolvable.

**Decode the blobs.** They are base64 of `Marshal.dump` (§7 of the data-model record), so the cheapest
read is Ruby in the SketchUp console — no Marshal reimplementation needed:

```ruby
require 'base64'
m = Sketchup.active_model
%w[assemblies_calc assemblies_ud].each do |key|
  raw = m.get_attribute("DesignPH_dict", key)
  next unless raw
  data = Marshal.load(Base64.decode64(raw))
  puts "#{key}: #{data.class} #{data.respond_to?(:size) ? data.size : ''}"
  puts data.first(3).inspect
end
```

**Record:** the row shape, whether a row carries its own layers or only a header + U-value, and
whether every `assemblyID` referenced by a face resolves against it. **If assemblies do not resolve
from the model alone, PRD §8.3 needs rewriting before the translator is designed** — and unresolvable
assemblies must be *reported*, never silently defaulted (hard rule 4).

## 1.5 — Define the untagged-face filter (shading geometry) — ◐ **half answered**

> `faceTypeAuto` is the right signal — it splits Adelphi's untagged faces into 420 `'xo'` exterior
> and 405 `'i'` interior — **but it is absent from `2414 Bluff Reach.skp` and `2605 MacDonough.skp`
> entirely**, so it cannot stand alone. The geometric second leg is staged as
> [`../../spikes/phase1/live_1-5_shading_filter.rb`](../../spikes/phase1/live_1-5_shading_filter.rb).


PRD §7.2 now puts shading *geometry* in v1 scope, but Phase 0 refuted "untagged face → orphaned
shade" as a blanket rule: the reference's 1287 shades are purely exterior site context, while
untagged designPH faces are a mixed bag of partitions, furniture and context.

Working from live geometry in SketchUp, determine what actually separates the two. Candidates worth
testing before inventing anything: `faceTypeAuto` (`'xo'` exterior-opaque vs `'i'` interior — if
§1.3 decodes it, this may be the filter already); SketchUp tag/layer membership; whether the face
lies inside the tagged envelope's bounding volume; group/component nesting depth.

**Deliverable:** a filter rule, its false-positive and false-negative rate on the Adelphi model, and
an explicit statement of what gets *reported* rather than exported. A filter that is not obviously
right is worse than no filter — mis-exported furniture becomes wrong shading downstream, silently.

## Gate — ✅ **PASS WITH CHANGES** (2026-08-19)

> Both FAIL conditions cleared: windows have a resolvable host (46/46), and a consistent per-face
> rule for the key generations exists, confirmed on the read *and* write sides. The changes are
> PRD §8.2 (`cuts_opening?` is not a host fact), §8.3 (thermal bridges are on edges), and §7.2
> (shading geometry out of v1 until the user can pick tags). **Phase 2 is unblocked.**

**PASS** — a per-face `*ID`/`*Auto` precedence is established, window hosts are resolvable,
assemblies resolve from the model, and every enum value is either understood or safely ignorable.
Proceed to Phase 2.

**PASS WITH CHANGES** — likely. `cuts_opening?` being true revises PRD §8.2; assemblies not
resolving from `layer_table_*` revises §8.3. Update the PRD and `00_Context/`, then proceed.

**FAIL** — §1.1 finds no consistent per-face precedence, or windows have no resolvable host. Stop.
The read layer needs redesigning before any runtime work is worth doing.

## Deliverables

- `planning/01_sketchup-export/feasibility/RESULTS/PHASE-1_results.md`
- `00_Context/DESIGNPH_DATA_MODEL.md` §5–6 updated with everything learned — in particular §6
  resolved from **CONTESTED** to a rule that can be implemented
- PRD §8.2 revised if openings are cut; §8.3 revised if assemblies do not resolve from
  `layer_table_*`; §7.2 given the untagged-face filter from §1.5
