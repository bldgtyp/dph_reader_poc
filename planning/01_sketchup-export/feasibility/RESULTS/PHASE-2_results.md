# Phase 2 — Results — **gate: PASS WITH CHANGES**

**Run:** 2026-08-19 · **Box:** ~1 h · **Plan:** [`../PHASE-2_python-purity-audit.md`](../PHASE-2_python-purity-audit.md)
**Prerequisite:** Phase 1 — [`PHASE-1_results.md`](PHASE-1_results.md)

---

> **The change is an expansion, not a reduction.** The plan's method section expected `honeybee-ph`
> pure and **PHX out entirely** — "Phase 3 targets honeybee-ph only". Its gate text then hedged, and
> the hedge was the right instinct: *"`xlwings` only matters for PHPP writing, so an in-browser
> WUFI/METr export may be closer than it looks."* It is closer than that. The whole HBJSON →
> `PhxProject` → **WUFI-Passive XML** and **METr JSON** write path runs with `lxml`, `xlwings`,
> `pydantic`, `rich` and `honeybee-schema` **not installed at all** — verified by running it, not by
> reading imports. Phase 3 can target `honeybee-ph` *and* PHX's write path. Only PHPP writing stays out.

## Findings

| # | Finding | Effect |
|---|---|---|
| 12 | **The `honeybee-ph` model-building path needs 8 wheels, 1.5 MB, all `py3-none-any`** | Phase 3's scope statement. Nothing to compile, nothing to substitute |
| 13 | **`click`, `honeybee-schema`, `pydantic` and `pydantic-core` are declared but unreachable** — `click` only from `cli/` modules, `honeybee_schema` only from inside a function in `honeybee_energy/cli/validate.py`, `pydantic` only from `PHX.from_WUFI_XML` and `PHX.PHPP` | The declared `honeybee-ph` closure (17 packages) is more than double the reachable one (8). Install `deps=False` |
| 14 | **PHX's write path is pure** — `from_HBJSON`, `model`, `to_WUFI_XML`, `to_METr_JSON`, `to_PPP` and `xl` contain zero impure imports | Overturns the plan's "Phase 3 targets honeybee-ph only" and settles its own hedge: WUFI/METr export in the browser is reachable, not speculative |
| 15 | **`xlwings` is an install-clean, run-time blocker** — it publishes a `py3-none-any` wheel and imports fine; it fails only when it tries to drive Excel | The blocker is real but narrower than stated: it gates PHPP *writing* only, and PHX imports it inside `if __name__ == "__main__"` |
| 16 | **The only true class-(c) packages are `appscript`, `psutil` and `pywin32`** — all three arrive via `xlwings`, all three are marker-gated to `darwin`/`win32` | On Emscripten they would never even be requested. They are not a Pyodide problem |
| 17 | **Zero sdist-only packages in either closure** | The plan's "open every sdist and check `ext_modules`" step has nothing to check. Recorded so it is not re-run |
| 18 | **The reference HBJSON no longer round-trips through current `honeybee-ph`** — `PHPPSettings10.from_dict` raises `KeyError: 'tfa_override'` | Side finding, not a purity result. Phase 3 must not use `adelphi-honeybee-json.hbjson` as a *load* fixture |

Raw data: [`PHASE-2_dependency-audit.md`](PHASE-2_dependency-audit.md) (packaging) and
[`PHASE-2_import-reachability.md`](PHASE-2_import-reachability.md) (imports), plus
[`baselines/phase2_closure.json`](baselines/phase2_closure.json).

---

## 2.1 — Method, and why it is not the one the plan wrote

The plan's method was `pip download` into a venv, then grep the filenames for non-pure wheel tags.
Run on this machine that resolves for **macOS arm64**, so `lxml` comes back as
`lxml-6.1.2-cp314-cp314-macosx_11_0_arm64.whl` — which says nothing about whether a pure wheel
exists, only that pip preferred a native one. The same run on Linux CI would produce a different
answer for the same closure.

Two changes, both in the direction of a more defensible answer:

1. **Resolve platform-independently, classify from PyPI.** `uv pip compile --universal` gives the
   union of every platform's requirements — a superset of what Emscripten needs, so a marker-hidden
   dependency cannot slip past. Purity is then read from PyPI's *file list* for the resolved version:
   does a `py3-none-any` wheel exist at all. → [`purity_audit.py`](../../../spikes/phase2/purity_audit.py)
2. **Ask whether the impure thing is reachable, not just present.** The packaging answer and the
   import answer disagree for four packages here, and the import answer is the one that decides
   Phase 3's scope. → [`import_reachability.py`](../../../spikes/phase2/import_reachability.py)

The plan's class (a)/(b)/(c) split is kept verbatim, because it is the right split — it just needed
a fourth column for *reachable*.

## 2.2 — The dependency table

Resolved for Python 3.14 (Pyodide `314.0.5` runs CPython 3.14.2), checked against the
`pyodide-lock.json` of both current stable releases: **`314.0.5`** (356 packages, 2026-08-17) and
**`0.29.4`** (379 packages, CPython 3.13).

| Package | Version | Class | Reachable from the write path? | Size |
|---|---|---|---|---|
| `honeybee-core` | 1.64.65 | (a) pure | ✅ yes | 192 KB |
| `honeybee-energy` | 1.123.23 | (a) pure | ✅ yes | 573 KB |
| `honeybee-ph` | 1.33.48 | (a) pure | ✅ yes | 209 KB |
| `honeybee-standards` | 2.0.7 | (a) pure | ✅ yes | 11 KB |
| `ladybug-core` | 0.44.56 | (a) pure | ✅ yes | 269 KB |
| `ladybug-geometry` | 1.35.3 | (a) pure | ✅ yes | 200 KB |
| `ladybug-geometry-polyskel` | 1.7.52 | (a) pure | ✅ yes | 38 KB |
| `ph-units` | 1.5.38 | (a) pure | ✅ yes | 31 KB |
| `phx` | 1.56.88 | (a) pure | ✅ write path only | 414 KB |
| `click` | 8.1.7 | (a) pure | ❌ `cli/` only | 96 KB |
| `honeybee-schema` | 2.2.0 | (a) pure | ❌ `honeybee_energy/cli/validate.py` only | 86 KB |
| `pydantic-openapi-helper` | 1.0.5 | (a) pure | ❌ via `honeybee-schema` | 10 KB |
| `pydantic` | 2.13.4 | (a) pure | ❌ `PHX.from_WUFI_XML`, `PHX.PHPP` | 461 KB |
| `annotated-types`, `typing-extensions`, `typing-inspection`, `colorama` | — | (a) pure | ❌ via `pydantic` / `click` | 97 KB |
| `markdown-it-py`, `mdurl`, `pygments` | — | (a) pure | ❌ via `rich` | 1,321 KB |
| `rich` | 15.0.0 | (a) pure | ❌ `PHX.from_WUFI_XML` only | 303 KB |
| `xlwings` | 0.36.17 | (a) pure wheel | ❌ **runtime blocker** — see §2.4 | 694 KB |
| `pydantic-core` | 2.46.4 | **(b)** Pyodide ships 2.41.5 | ❌ via `pydantic` | wasm |
| `lxml` | 6.1.2 | **(b)** Pyodide ships 6.0.2 | ❌ `PHX.from_WUFI_XML` only | wasm |
| `appscript` | 1.4.0 | **(c)** no wasm build | ❌ `sys_platform == 'darwin'`, via `xlwings` | — |
| `psutil` | 7.2.2 | **(c)** no wasm build | ❌ `sys_platform == 'darwin'`, via `xlwings` | — |
| `pywin32` | 312 | **(c)** no wasm build | ❌ `sys_platform == 'win32'`, via `xlwings` | — |

**No package in either closure is sdist-only**, so the plan's sdist-inspection step (open each
`.tar.gz`, look for `ext_modules`) had nothing to inspect. Recorded so it is not re-run.

The three class-(c) packages are the whole of the "impure with no wasm build" category, and all
three are `xlwings`' platform shims. `--universal` resolution surfaces them precisely *because* it
ignores markers; a resolution for Emscripten would never request any of them.

## 2.3 — Reachability: the declared closure is more than twice the real one

`honeybee-core` hard-declares `honeybee-schema==2.2.0`, which pulls `pydantic-openapi-helper` →
`pydantic` → `pydantic-core` (Rust). On the packaging evidence alone, the `honeybee-ph` subtree is
**not** pure, and Phase 2 would have to argue class (b).

It never gets there. The only imports of `honeybee_schema` anywhere in the reachable closure are
three *inside a function* in `honeybee_energy/cli/validate.py` — not one at module level. Every
top-level import of `click` is in a `cli/` module. Nothing on the model-building path touches
either. The same holds for PHX, per subpackage:

| PHX subpackage | Impure top-level imports |
|---|---|
| `from_HBJSON` — HBJSON → `PhxProject` | ✅ none |
| `model` — the PHX object model | ✅ none |
| `to_WUFI_XML` — WUFI-Passive export | ✅ none |
| `to_METr_JSON` — METr export | ✅ none |
| `to_PPP` | ✅ none |
| `xl` — the Excel adapter | ✅ none — it is Protocol-typed, the framework is injected |
| `from_WUFI_XML` — the WUFI **reader** | ❌ `lxml`, `pydantic`, `pydantic_core`, `rich` |
| `PHPP` | ❌ `pydantic` (in `phpp_localization/shape_model.py`) |
| `hbjson_to_phpp.py` | `xlwings`, guarded by `if __name__ == "__main__"` |

`PHX.xl` reading clean is the surprising one and it is not an accident: `xl_typing.py` defines
`xl_app_Protocol`, `xl_Book_Protocol`, `xl_Range_Protocol` and friends, and `xl_app.py` takes the
framework as a constructor argument. PHX never imports `xlwings`; the caller passes it in.

**The empirical proof.** Install the nine pins with `--no-deps` — so none of `appscript`, `click`,
`honeybee_schema`, `lxml`, `numpy`, `psutil`, `pydantic`, `pydantic_core`, `pywin32`, `rich`,
`win32com`, `xlwings` exists in the environment — then run the real conversion:

```
python                 3.14.0
HBJSON faces           6
PhxProject variants    1
WUFI-Passive XML       ~29,000 chars
METr JSON              ~51,600 chars
impure modules loaded  NONE
```

(The two character counts drift by a byte or two between runs — PHX stamps generated identifiers
into both outputs. Only `impure modules loaded` is the result; the lengths are there to show that
real content came out, not an empty document.)

Reproduce with `uv run planning/spikes/phase2/import_reachability.py`. A missing hard dependency
fails loudly with `ModuleNotFoundError`; nothing here rests on reading imports and inferring intent.

## 2.4 — `xlwings`: a runtime blocker, not an install blocker

The plan's pre-verified note reads "`xlwings` is the hard blocker — it automates desktop Excel and
can never run in a browser." The conclusion is right; the mechanism is not, and the difference
matters for what Phase 3 may attempt.

`xlwings` publishes `xlwings-0.36.17-py3-none-any.whl`. It would install under `micropip` and
`import xlwings` would very likely succeed — its platform shims (`pywin32`, `appscript`, `psutil`)
are marker-gated to Windows and macOS and would not be requested on Emscripten. What cannot work is
the thing it exists to do: COM / Apple-events automation of a running Excel process. There is no
Excel in a `HtmlDialog`.

So the boundary is not "PHX is out". It is **"PHPP writing is out"** — the one path that needs a
live Excel — which PRD §5 already lists as an explicit v1 non-goal *for unrelated reasons*
(designPH keeps the PHPP-writing job; we are complementary). The constraint and the product
decision happen to agree.

## 2.5 — Bundle budget

| Item | Compressed |
|---|---|
| `pyodide-core-314.0.5.tar.bz2` — the vendorable runtime | **6.4 MB** |
| `micropip` 0.11.1 + `packaging` 26.1 — see the caveat below | **0.2 MB** |
| Minimal `honeybee-ph` set — 8 wheels (§2.6) | **1.5 MB** |
| `+ phx` — the write path | **+0.4 MB** |
| **Total `.rbz` payload, honeybee-ph only** | **≈ 8.1 MB** |
| **Total `.rbz` payload, incl. PHX write path** | **≈ 8.5 MB** |

⚠ **`pyodide-core` does not contain `micropip`.** The 6.4 MB tarball holds exactly 13 files —
`pyodide.js`, `pyodide.asm.wasm`, `python_stdlib.zip`, `pyodide-lock.json` and the CLI shims — and
no packages at all. `micropip` is a separate 113 KB wheel and pulls `packaging` (94 KB); both must
be vendored beside our own eight, or `micropip.install` will not exist to call. Verified by
downloading and listing the tarball, 2026-08-19. The alternative is to skip `micropip` entirely and
unpack the eight wheels straight onto Pyodide's filesystem — they are pure, so there is nothing for
`micropip` to resolve. Phase 3 step 2 should try `micropip` first and keep that in reserve.

For comparison, the full declared `PHX` closure installed with default resolution is 5.0 MB of pure
wheels *plus* Pyodide's `lxml` and `pydantic-core` wasm — roughly triple the payload, for code
nothing on our path imports.

PRD §7.1's "~10 MB vendored runtime" was a good guess and can now be stated as **≈8 MB**, which is
under it. The full 334 MB Pyodide distribution is the *build* artifact, not the shippable one — only
`pyodide-core` plus our own wheels needs to be in the `.rbz`.

## 2.6 — Scope statement for Phase 3

Phase 3's plan asks Phase 2 for "a scope statement naming the packages to load". This is it.

**Step 2 of Phase 3 (`the stack imports`) vendors `micropip` and `packaging` — neither ships inside
`pyodide-core`, see §2.5 — plus exactly these 8 wheels, installed with dependency resolution off:**

```
honeybee_core-1.64.65-py3-none-any.whl
honeybee_energy-1.123.23-py3-none-any.whl
honeybee_ph-1.33.48-py3-none-any.whl
honeybee_standards-2.0.7-py2.py3-none-any.whl
ladybug_core-0.44.56-py3-none-any.whl
ladybug_geometry-1.35.3-py3-none-any.whl
ladybug_geometry_polyskel-1.7.52-py3-none-any.whl
ph_units-1.5.38-py3-none-any.whl
```

```python
await micropip.install(WHEEL_URLS, deps=False)   # deps=False is load-bearing — see §2.3
```

**`deps=False` is not an optimisation.** With resolution on, `honeybee-core`'s declared
`honeybee-schema==2.2.0` pulls `pydantic`, and `micropip` would satisfy it with Pyodide's own
`pydantic` 2.12.5 + `pydantic-core` 2.41.5 wasm build rather than PyPI's 2.13.4 / 2.46.4. That
*probably* resolves (`pydantic-openapi-helper` asks only for `~=2.0`) — but it triples the payload,
adds a wasm module to cold start, and makes the extension's behaviour depend on a version pin inside
whichever Pyodide release is vendored. None of that buys anything: no code we call imports it.

**Optional, for a stretch goal only:** add `phx-1.56.88-py3-none-any.whl` and import *only*
`PHX.from_HBJSON`, `PHX.model`, `PHX.to_WUFI_XML`, `PHX.to_METr_JSON`. Never `PHX.from_WUFI_XML`,
never `PHX.PHPP`, never `PHX.hbjson_to_phpp`. That is not a v1 goal and must not be allowed to
consume the two-day box — but if step 3 lands early, it is the highest-value thing to point the
remaining time at, because it would put Phius export in the browser.

**Fixture warning for step 3.** `adelphi-honeybee-json.hbjson` does **not** load under current
`honeybee-ph` — `Model.from_dict` raises `Failed to apply ph properties to the Model: 'tfa_override'`
from `PHPPSettings10.from_dict` (Finding 18). It was written by an older `honeybee-ph` and predates
that key. It remains valid as a *shape* reference, per `AGENTS.md`; it is not usable as a load
fixture. Build fixtures with `Room.from_box` as the probe does, or re-export the model.

## Gate — **PASS WITH CHANGES**

The plan's three verdicts do not map cleanly, so the reasoning is stated rather than the label alone.

- Not plain **PASS**: PASS was defined as "full stack pure … the extension could eventually emit
  PHPP/WUFI/METr directly". WUFI and METr, yes. **PHPP, no** — `xlwings` needs a live Excel and
  always will. Claiming PASS would overclaim by exactly one export format.
- Not the plan's **PASS WITH CHANGES** as written either — that reads "honeybee-ph pure, PHX impure,
  Phase 3 targets honeybee-ph only". PHX's write path is pure and reachable.
- Emphatically not **FAIL**: `honeybee-ph`'s reachable closure pulls no C extension at all. The
  PRD §7.1 Ruby-writer fallback is not triggered by this phase.

**Verdict: PASS WITH CHANGES, where the change widens Phase 3's ceiling rather than narrowing it.**
Phase 3 proceeds as planned with an 8-wheel, 1.5 MB scope for its required steps, and PHX's write
path as a documented stretch goal for step 4 if time allows.

Phase 3 remains the decisive one and nothing here softens its risks — CSP, `SharedArrayBuffer`,
cold start and the Ruby↔JS bridge are all untouched by a dependency audit. What this phase removes
is only the risk that the *packages* would not load.

### Consequences recorded elsewhere

| Document | Change |
|---|---|
| `DESIGNPH-PLUS_PRD.md` §7.1 | Vendored-runtime estimate "~10 MB" → measured **≈8 MB**; the wheel list named |
| `DESIGNPH-PLUS_PRD.md` §10, S5 | Row rewritten — "confirmed impure" was a packaging fact, not an import fact |
| `planning/01_sketchup-export/feasibility/00_OVERVIEW.md`, `planning/.index.md` | Phase 2 status |

### Not answered here, deliberately

- **Does `micropip` resolve these wheels inside SketchUp's `HtmlDialog`?** Untestable without
  Pyodide running. That is Phase 3 step 2 and this phase does not pretend to have de-risked it.
- **Does the AGPL analysis change?** No. Vendoring `honeybee-core` triggers PRD §9 whether the
  bundle is 8 MB or 20 MB, and whether PHX ships or not. Still for counsel, after Phase 3 passes.
