# POC-2 — SketchUp runbook **[Ed]**

**Status: ✅ COMPLETE, 2026-08-21. All five captured and reconciled; kept as the record of what was asked, and as the template for the next corpus sweep.**

| | State |
|---|---|
| **A1** — Marshal blobs live *(T-1)* | ✅ **answered.** All four blob keys decoded from the live model; they are base64 `String`s starting `BAh`, as the offline evidence said |
| **A2** — the window rectangle *(W-1)* | ✅ **answered** — by `DphWin.inspect_one` rather than the snippet below, and it **refuted both** contract candidates. See `../CONTRACT_extraction-json.md` §8.1 |
| **A3** — edges inside groups *(E-1)* | ✅ **answered by the capture itself.** All **99** of Bluff Reach's tagged edges are **two levels deep** in groups, area groups 15/16/17, every `connection_ref` resolvable. A top-level-only walk would have found zero |
| **B** — capture the fixtures | ✅ **5 of 5**, reconciled PASS. `poc/_private/MANIFEST.md` |

**Nothing is outstanding.** What follows is kept as the record of what was asked and why, and as the
template for the next corpus sweep — designPH 3.0 will need one.

### What the two sessions actually cost, for planning the next one

The budget was two SketchUp sessions and it took exactly two, but **not for the reason planned**.
Session A was meant to answer three contract questions and capture all five; it answered two
questions and its captures then had to be thrown away, because the same session revealed two
*design* errors in the contract (the window rectangle, the local-vs-world transform). Session B
re-captured everything on the fixed collector.

⚠ **Budget a re-capture into any session that also asks an open question.** If the answer changes
the contract, the captures taken alongside it are worthless — and the two cannot be separated,
because it takes a real capture to surface the question.

Three tooling defects also cost real time in session B, all now fixed and all worth knowing before
the next sweep:

- ⚠ **`model.path` is not the file you opened** — it is the last-*saved* path, on whatever machine
  saved it. Two of five copies reported somebody else's. `Dph.here` no longer derives anything from
  it; when it cannot identify the model it lists the copies and asks. `SKETCHUP_RUNTIME.md` §8.2.
- **Run `Dph.status`** to see what is captured and what is left. It reads the folder, which is the
  only thing that can be trusted.
- **Rebuild before capturing** (`cd poc && make ed`) whenever the collector has changed — though
  note `Dph.here` loads `collector.rb` straight from the repo, so a re-`load` of the console script
  is enough for capture; the rebuild only matters for the dialog/Export path.

**Everything here is read-only.** Nothing writes to `DesignPH_dict`, nothing writes to any model.
The console script *proves* it: it records `model.modified?` before and after each collection and
stops if it ever changes.

⚠ **COPIES ONLY** (hard rule 3). Nothing below opens a corpus original. ⚠ The script's check is
**advisory, not enforcement** — it reads `model.path`, which cannot be trusted (§8.2). What *is*
guaranteed is that collection never writes: `model.modified?` is asserted across every run.

---

## Setup — **done** (2026-08-21)

The five model **copies** are staged in `~/Desktop/dph_poc_copies/`, and all five are captured.

| Copy | Why it is on the list |
|---|---|
| `adelphi-designph_COPY.skp` | The primary corpus model. 82 classified faces, 46 windows, an in-model `assemblies_ud` snapshot, and **no layer tables at all** |
| `2414_Bluff Reach_COPY.skp` | **The thermal-bridge model.** 99 of its 293 tagged entities are on edges. A face-only reader loses every one of them silently |
| `250703 - Linde Residence_COPY.skp` | The **only** corpus model carrying `layer_table_*` — 25 of them. Without it the tier-1 assembly path is untested |
| `250708_COPY.skp` | Keeps every one of its 92 assemblies in `assemblyIDAuto`. The coalesce regression |
| `2523 Wellington_COPY.skp` | Two designPH version stamps in one file, and 169 faces whose temp zone lives only in `*Auto` |

Open **Window → Ruby Console** first. Everything reports there.

---

## Session A — the three contract questions ⚠ **do this first**

Paste each block into the Ruby Console and send me what it prints. Each is a few lines and reads
nothing but the open model.

### A1 — Marshal blobs, live *(question T-1)*

Open `adelphi-designph_COPY.skp`, then:

```ruby
d = Sketchup.active_model.attribute_dictionary("DesignPH_dict")
d.keys.each { |k| v = d[k]; puts "#{k}: #{v.class} #{v.is_a?(String) ? v[0,3].inspect : v.inspect[0,40]}" }
```

**Expected:** the table keys (`assemblies_ud`, `vent_ud`, `ihg_ud`, `tracker_data`) come back as
`String` starting `"BAh"`. Anything else — a `Hash`, an `Array`, a different prefix — and the
collector's decoder is aimed at the wrong thing.

### A2 — the window's units and its rectangle *(question W-1, the big one)*

Same model. Select **one window** in the model, then:

```ruby
i = Sketchup.active_model.selection.first
dc = i.attribute_dictionary("dynamic_attributes")
puts "definition: #{i.definition.name}"
puts "instance dc:"
dc.each_pair { |k, v| puts "  #{k} = #{v.inspect} (#{v.class})" } if dc
puts "faces in the definition (local area, in²):"
i.definition.entities.grep(Sketchup::Face).each_with_index { |f, n| puts "  #{n}: #{f.area.round(1)}  #{f.outer_loop.vertices.size} pts" }
puts "transform: #{i.transformation.to_a.map { |x| x.round(4) }.inspect}"
puts "glued_to: #{i.glued_to.class}"
```

**What I am looking for:**

1. Whether `lenx` × `leny` (inches, as Strings) × 0.00064516 equals `area` (m²). That confirms the
   per-field unit table the contract currently *infers*.
2. Whether the definition's **largest face** is the window rectangle, or whether it is a frame part.
   The collector currently derives `panel_outer_loop` from the largest face; the alternative is
   transform × `lenx`/`leny`, and the loser gets deleted from the contract.

### A3 — are tagged edges inside groups? *(question E-1)*

Open `2414_Bluff Reach_COPY.skp`, then:

```ruby
top = 0; nested = 0
walk = lambda do |ents, depth|
  ents.each do |e|
    if e.is_a?(Sketchup::Edge) && e.attribute_dictionary("DesignPH_dict")
      depth.zero? ? top += 1 : nested += 1
    elsif e.is_a?(Sketchup::Group) then walk.call(e.entities, depth + 1)
    elsif e.is_a?(Sketchup::ComponentInstance) then walk.call(e.definition.entities, depth + 1)
    end
  end
end
walk.call(Sketchup.active_model.entities, 0)
puts "tagged edges: #{top} at top level, #{nested} nested (expect 99 total)"
```

**Why it matters:** if edges only ever sit at the top level, edge transform accumulation is dead
code. If they nest, it is load-bearing — and it is already implemented and tested either way, so
this question costs nothing to answer and closes an open item.

**Send me A1, A2 and A3 before running session B.** The contract freezes on those three answers.

---

## Session B — capture the fixtures

Load the script once:

```ruby
load "/Users/em/Desktop/dph_plus_testing/poc/ext/tests/run_collector_console.rb"
```

Then, for **each** of the five copies: open it, and run

```ruby
Dph.here
```

⚠ **Open each model yourself rather than letting a script do it.** SketchUp on macOS is a
multi-document app: `Sketchup.open_file` opens a *new window* instead of replacing the current
model, and `Sketchup.active_model` follows whichever window is frontmost. A batch loop can therefore
write five files, named after five different models, all containing the **first** model's data —
and nothing would look wrong. (`Dph.sweep` exists and checks for exactly that, stopping rather than
guessing. `Dph.here` avoids the question entirely.)

Expect, per model, something like:

```
adelphi-designph_COPY.skp
  8037 walked / 1441 tagged / 82 classified / 0 edges / 46 windows  (nnn ms)
  tables: assemblies_ud, ihg_ud, tracker_data, vent_ud
  -> adelphi-designph_COPY.extraction.json
  ✓ done
```

| What you see | What it means |
|---|---|
| `✓ done`, five times | ✅ Done. Tell me and I reconcile them |
| `✗ STOP: the model was modified during collection` | A real bug and the important kind — the collector must be read-only. Stop and tell me |
| `✗ REFUSED` | You opened an original, not a copy. Open the one in `dph_poc_copies` |
| A traceback | Send it. The other models are unaffected; carry on with them |
| SketchUp hangs on a big model | Note which and roughly how long. Bluff Reach and Linde are the large ones |

The counts printed are what I reconcile, so a screenshot of the console is as useful as the files.

⚠ **Do not save any model**, even if SketchUp offers. The copies must stay byte-identical for
POC-5's re-run diffs.

## What happens next (no action from you)

I run:

```
uv run poc/tools/check_extraction.py ~/Desktop/dph_poc_copies/*.extraction.json
```

which reconciles every capture against the Phase 0/1 offline baselines — classified faces,
thermal-bridge edges, which tables each model carries, how many layer tables — and grades each
model PASS/FAIL. That is POC-2's gate, and it is why the counts above are worth reading even
before I see the files.

## Grading it — how it actually came out

```
A1: base64 String, prefix "BAh"           ✅ as the offline evidence said
A2: lenx×leny×0.00064516 == area?  NO — 20 of 46.   largest definition face is the pane? NO — it is
    the GLAZING, and grep(Face) finds nothing at the definition's top level anyway. BOTH candidates
    refuted; the rectangle is the rough opening through the WORLD transform (contract §8.1)
A3: 0 at top level, 99 nested TWO levels deep   ✅ a top-level walk finds none of them
B:  5 of 5 collected, 5 of 5 reconciled
```

⚠ **A2 is the one to remember.** It was written expecting a yes/no between two candidates, and the
answer was *neither* — including one candidate that could not even be evaluated, because
`definition.entities.grep(Sketchup::Face)` returns `[]` on all 46 windows. A question phrased as a
choice between two hypotheses cannot report that both are wrong unless somebody looks at what is
actually there; `DphWin.inspect_one` is what did that, and it was not in this runbook.
