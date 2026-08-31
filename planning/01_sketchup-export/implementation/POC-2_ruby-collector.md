# POC-2 — Ruby Collector (the read layer)

> ✅ **CLOSED — PASS, 2026-08-21.** [`RESULTS/POC-2_results.md`](RESULTS/POC-2_results.md). 5 of 5 corpus models captured and reconciled; contract frozen at **v2**; E-1 answered (all 99 Bluff Reach bridge edges are nested two levels deep). ⚠ Read §0.2 there before planning another capture session — every failure in this phase was in the tooling, not the models.

**Builds:** `pocs/01_sketchup-export/ext/dph_plus_poc/collector.rb` — walks a live designPH model and emits the
[extraction JSON](CONTRACT_extraction-json.md).
**Depends on:** nothing — **§1 is the pre-freeze work that enables the freeze** (it may move only
the contract fields its §8 names; everything else is fixed as written, so collector work on faces,
edges, and tables starts immediately). Ships into POC-1's shell but is developed and offline-tested
before POC-1 lands (a console-run script needs no extension).
**Box:** ~1–2 agent sessions + **two batched Ed SketchUp sessions** (§1 and §6.1 — each covers
several questions/models in one sitting; the offline suite in §5.5 exists to keep it at two).
**Grounding:** `00_Context/DESIGNPH_DATA_MODEL.md` (the whole document is this phase's spec),
`00_Context/DATA_CONTRACTS.md` §2.

> The collector is the module the designPH-3.0 assumption lands on: when 3.0 arrives, this file and
> the contract are the blast radius. Keep it free of translation logic — it reads, coalesces,
> transforms, decodes, and ships. Every judgement call belongs to Python.

---

## 1. Settle the contract's open questions first

Before writing the walker, resolve the three contract §8 questions — each is one small console
script or bt_inspector session against a corpus copy:

- **W-1 (window rectangle + units):** dump one Adelphi window's definition faces + instance
  transform; decide `panel_outer_loop` derivation; verify the per-field `dynamic_attributes` unit
  table (contract §4's annotations, including that `area` is m² while `lenx`/`leny` are inches);
  record the `transformation.to_a` layout as observed.
- **T-1 (Marshal live representation):** `model.get_attribute("DesignPH_dict", "assemblies_ud").class`
  on Adelphi — expect `String` starting `BAh`.
- **E-1 (edges in groups):** on Bluff Reach COPY, count tagged edges at top level vs inside
  groups/components.

**[Ed]** These three share one SketchUp session (runbook staged by the agent). Freeze the contract
at version 1 immediately after — the session may move only contract §3/§4 per its §8 pre-freeze
scope. **POC-3 may start everything except aperture geometry before the freeze.**

> ⚠ **What actually happened, and the planning lesson.** The session answered W-1 and T-1 but
> **refuted both of W-1's candidates** rather than choosing between them — a question phrased as a
> choice between two hypotheses cannot report that both are wrong, and it was `DphWin.inspect_one`
> (written *during* the session, not staged) that found the real answer. E-1 could not be answered
> at all, because Adelphi has zero tagged edges; it fell out of POC-2's capture instead.
>
> The freeze then happened **twice**: v1 with the corrections, and v2 an hour later when the first
> capture on the fixed collector came in at 2.25 MB. ⚠ **Budget a re-capture into any session that
> also asks an open question** — if the answer changes the contract, the captures taken alongside it
> are worthless, and the two cannot be separated because it takes a real capture to surface the
> question.

## 2. The walk

One recursive traversal from `model.entities`, accumulating `Geom::Transformation`:

- **`Sketchup::Face`** → face record if classified; if tagged-but-unclassified → a compact
  `unclassified.tagged_faces` record (id, raw area group, SketchUp tag name); if untagged →
  aggregated into `unclassified.untagged_by_tag`.
- **`Sketchup::Edge`** → edge record if it carries `DesignPH_dict`. **This is the rule that a
  face-only reader breaks silently** — 99 of 293 tagged entities on Bluff Reach are edges.
- **`Sketchup::ComponentInstance` / `Sketchup::Group`** → recurse with composed transform; if the
  instance carries designPH window `dynamic_attributes` (`frametypeid` present), emit a window
  record **and do not** recurse into it — window internals are neither walked nor counted, per the
  contract's §6.1 census rules.
- **Component instancing:** a definition placed twice is visited once per placement, each with its
  own composed transform and its own **path-qualified id** (contract §2.1) — two placements are two
  envelope surfaces, and their ids must not collide.
- Everything else → ignored, but counted in `faces_walked`-style census totals.

Mechanics, all with evidence behind them:

- `attribute_dictionaries` returns **`nil`**, not empty — guard every access.
- Coalesce `*ID` ‖ `*Auto` per pair; if a pair ever has both non-nil, append the pair's name to
  `both_generations` (contract: an array, normally `[]` — corpus says impossible; ship it, let
  Python report it).
- `descName` ‖ `descNameAuto` — the user's name wins.
- Lengths: `× 0.0254`; areas: `face.area(accumulated_transform) × 0.00064516`. SketchUp internal
  units are always inches.
- Vertices: `vertex.position.transform(accumulated)`; outer loop **and** inner loops (contract §2),
  **preserving SketchUp's loop order verbatim** — orientation is derived from winding in Python
  (contract §2.2). No normal is shipped; do not compute one.
- Edge lengths: from the **transformed endpoints**, never from `Edge#length` with a transform
  argument (unverified API).
- **No writes anywhere.** Not even a temp attribute. Read-only is structural, not a convention.

## 3. Windows

- Identify: instance whose `dynamic_attributes` includes `frametypeid` (settle exact predicate in
  §1's session; definition-name matching is the fallback, not the primary — users rename).
- Read the `dynamic_attributes` subset **raw** — units are per-field (contract §4), do not convert,
  do not parse. Read from the **instance**, falling back to the **definition** (designPH puts
  per-window values on instances, the shared template on the definition —
  `DESIGNPH_DATA_MODEL.md` §8.2).
- Resolve `designph_name` per the contract's fallback order (instance name ‖ designPH-generated
  name ‖ definition name + id suffix) — it must never be null; every report line downstream names
  its window with it.
- Host: `glued_to` (46/46 on Adelphi). **No geometric fallback in Ruby** — the contract's
  "Ruby stays dumb" rule holds; `host_resolution: "unresolved"` is legal and ships with the window's
  transform and panel loop, so Python can attempt coplanar recovery (POC-3 §4) if real fixtures ever
  show an unresolved host. Report either way.
- `host_has_inner_loops` from `face.loops.size > 1`. **Never consult `cuts_opening?`** — it is a
  definition capability, true on every designPH window, and means nothing about the host.

## 4. Tables

Decode every model-level Marshal blob per contract §5: `Base64` + `Marshal.load`, normalise the
`:TOKENS` row (start *or* end), strip `["#", …]` metadata rows, symbols → strings. Ship the five
named POC tables **plus every `layer_table_*` key present** (a family — Linde `250703` carries 25);
list the rest in `counts.tables_found`. A failed decode ships as `{"error": …}`.

`Marshal.load` executes on load — acceptable for the POC on our own corpus models, and the code
comment says exactly that plus the v1 note: consider porting `ruby_marshal.py`'s construct-nothing
approach to Ruby before v1 ever reads a stranger's file.

## 5. Census

Fill `counts` exactly as the contract defines (§6.1 census rules) — the census is the verification
instrument, not decoration. `faces_walked` counts every live face visited (window internals
excluded); `unclassified.untagged_by_tag` aggregates untagged faces only, and the tagged-but-
unclassified go per-entity into `unclassified.tagged_faces`.

## 5.5 Offline collector tests — before any Ed session

`test_static_server.rb` already proves the technique: load the module against a **stub `Sketchup`
API**, no SketchUp. Everything genuinely bug-prone in the collector is testable that way, and a
first live run realistically will not reconcile — the offline suite is what keeps the Ed budget at
two sessions:

- `pocs/01_sketchup-export/ext/tests/test_collector.rb` with a stub entity tree: transform accumulation (nested,
  scaled, mirrored groups), the `*ID`‖`*Auto` coalesce, `nil` dictionary guards, path-qualified id
  construction, the census invariants.
- Marshal/Base64 table decode + `:TOKENS` normalisation, with fixtures lifted from the Phase 0
  baselines' recorded blobs (both `:TOKENS`-first and `:TOKENS`-last shapes).
- ⚠ **Promote, don't rewrite:** `planning/spikes/pyodide/ext/dph_plus_spike/main.rb` already
  contains a working `walk_faces` / `face_record` / `classified?` — the collector starts from that
  code (it ran inside SketchUp against Adelphi), extends it to edges/windows/tables, and keeps its
  shape. POC-1's "stub collector" is the *entry point* being stubbed, not a licence to discard the
  spike walker. ⚠ **One known bug to fix on promotion:** the spike coalesces
  `areaGroupID || areaGroupIDAuto` — the real fallback key is **`areaGroupAuto`** (no "ID",
  `DESIGNPH_DATA_MODEL.md` §5). Masked on Adelphi (all its classified faces carry `areaGroupID`);
  it would silently drop `*Auto`-only models like `250708`. The offline coalesce test must cover
  exactly this.

A live run happens only once this suite is green.

## 6. Verification — the offline baselines are the harness

This is the phase with the best regression instrument in the project: **Phase 0/1 already counted
everything, offline, for all 14 corpus models.**

1. **[Ed] One batched console-script session:** a standalone
   `pocs/01_sketchup-export/ext/tests/run_collector_console.rb` that loads `collector.rb`, loops over every model in a
   folder of copies, and writes one extraction JSON each. The copy set is the **full fixture list**:
   Adelphi, `2414_Bluff Reach.skp` (underscore — the on-disk name), `250708.skp`, Wellington,
   **and `250703 - Linde Residence.skp`**
   (the only model known to carry `layer_table_*` — POC-3's tier-1 evidence).
2. **Count reconciliation, automated:** a `pocs/01_sketchup-export/tools/check_extraction.py` (PEP 723, `uv run`) that
   compares an extraction JSON against the model's baseline:
   - Adelphi: 82 classified faces, 46 windows with `host_resolution: "glued_to"`, tables include
     `assemblies_ud` (and **no** `layer_table_*` — its absence is the tier-2 case, expected).
   - Bluff Reach: **entities carrying a coalesced area-group key, of any value** — classified faces
     + unclassified tagged faces with the key + edges — must total **293**, with **99** on edges;
     `connections_ud` present. (Do not assert 293 as "classified" — the live 194 faces include
     `'n'`-valued reads, per the Adelphi precedent.)
   - `250703`: `layer_table_*` count = 25.
   - Every model: `faces_tagged` ≤ the offline record count (live ≤ historical — `.skp` files keep
     prior state; a live count *exceeding* the baseline is a bug), and the contract §6.1 census
     invariant holds.
   ⚠ Where live counts undershoot the offline baseline beyond the known thermal-bridge and
   historical-state gaps, **ask which entity type is missing before assuming history** — that is
   how the edge finding was made.
3. **Fixture capture:** the verified outputs land in `pocs/01_sketchup-export/_private/fixtures/` (gitignored — client
   data) with a manifest naming source model, copy path, capture date, and collector git-sha.

## 7. Gate

**PASS:** offline suite green; reconciliation green for the **five** fixture models; every contract
field populated or explicitly null; no write to any model (assert via a before/after
`model.modified?` check in the console script); real fixtures landed with manifest.
**PASS WITH CHANGES:** counts reconcile only after a contract bump — record what the corpus taught.
**FAIL:** any silent undercount that cannot be attributed (stop; that is a new entity-type finding,
and it goes to `00_Context/` before code continues).

Record in `RESULTS/POC-2_results.md`, including per-model reconciliation tables.

## 8. Out of scope

Type normalisation, classification decisions, geometry math beyond transforms (all POC-3);
unclassified-face export; any UI; writing `DesignPHPlus_dict` (v2).
