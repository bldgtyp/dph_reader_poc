# Phase 2 — Python Purity Audit (S5)

> ✅ **CLOSED 2026-08-19 — PASS WITH CHANGES.** [`RESULTS/PHASE-2_results.md`](RESULTS/PHASE-2_results.md). This file is the plan as written.

**Box:** ~1 h
**Gate:** is the Python stack pure enough for Pyodide — and how much of it?
**Prerequisite:** Phase 1 passed

> ✅ **Complete — PASS WITH CHANGES. [`RESULTS/PHASE-2_results.md`](RESULTS/PHASE-2_results.md) (2026-08-19).**
>
> The change **widens** Phase 3 rather than narrowing it. Phase 3 vendors **8 `py3-none-any` wheels,
> 1.5 MB**, installed `deps=False` ([§2.6](RESULTS/PHASE-2_results.md#26--scope-statement-for-phase-3)).
>
> Two things below were pre-verified wrong and are corrected in the results, not here:
>
> - **"`xlwings` is the hard blocker"** — it publishes a `py3-none-any` wheel and *installs* fine.
>   It blocks at **runtime**, when it reaches for a live Excel, and only on the PHPP-writing path.
> - **"Phase 3 targets honeybee-ph only"** — PHX's *write* path (`from_HBJSON` →
>   `model` → `to_WUFI_XML` / `to_METr_JSON`) imports none of `lxml`, `xlwings`, `pydantic` or
>   `rich`, verified by running it with all four uninstalled. Only `from_WUFI_XML` and `PHPP` are
>   impure. The gate text's own hedge — *"an in-browser WUFI/METr export may be closer than it
>   looks"* — was right, and is now measured rather than guessed.
>
> The **Method** below was also changed: `pip download` resolves for the *host* platform and cannot
> answer whether a pure wheel exists. Replaced by `uv pip compile --universal` + PyPI file lists,
> and by a second script that asks whether an impure package is *imported* at all
> ([§2.1](RESULTS/PHASE-2_results.md#21--method-and-why-it-is-not-the-one-the-plan-wrote)).

---

## Objective

Phase 3 is a two-day spike. This phase is one hour and can rule it out, or sharply narrow its scope.

We already know the *top* of the stack is pure: `honeybee-core`, `ladybug-geometry` and
`ladybug-core` all publish `py3-none-any` wheels, guaranteed by Ladybug's IronPython 2.7
compatibility. Unverified: the **full transitive tree**, and total bundle size.

## Already established (2026-08-19 — PyPI metadata + local `pyproject.toml`, pre-verified)

- **`honeybee-ph` runtime deps are exactly** `honeybee-core`, `honeybee-energy`, `PH-units` — and
  `honeybee-ph`'s own wheel is `py3-none-any`. What remains open is only the *transitive* closure
  (ladybug-*, honeybee-standards, …) and bundle size.
- **`PHX` hard-requires `lxml`, `xlwings`, `pydantic>=2.0`, `rich`.** `xlwings` is the hard blocker
  — it automates desktop Excel and can never run in a browser. So this phase's gate is already
  known to land at best on PASS WITH CHANGES; run the audit anyway to confirm the honeybee-ph
  subtree and to size the bundle.
- **A C extension is not automatically fatal** (the original framing here was too strict). Pyodide
  ships wasm builds of many C extensions in its own package distribution — `lxml` and
  `pydantic-core` are both in its current package list; verify against the Pyodide version actually
  vendored. Classify every impure dependency as one of: (a) pure; (b) impure but Pyodide-packaged;
  (c) impure with no wasm build (`xlwings`). Only (c) is a true blocker.

## Method

Resolve the complete dependency closure and check every wheel's platform tag.

```bash
cd "$SCRATCHPAD"                            # any scratch dir — never inside a tool folder
uv venv --seed .venv && source .venv/bin/activate   # --seed installs pip; plain `uv venv` ships none

# 1. honeybee-ph closure
python -m pip download honeybee-ph --dest ./wheels-hbph 2>&1 | tail -5
ls ./wheels-hbph

# 2. PHX closure
python -m pip download PHX --dest ./wheels-phx 2>&1 | tail -5
ls ./wheels-phx

# 3. flag anything that is not tagged pure
ls ./wheels-hbph ./wheels-phx | grep -v 'py3-none-any\|py2.py3-none-any\|\.tar\.gz$'
```

Anything printed by step 3 is a candidate blocker. For each, determine whether it is genuinely a C
extension or merely a badly-tagged pure package (check the sdist for `.c` / `.pyx` / `setup.py`
`ext_modules`). **Note the filter deliberately lets `.tar.gz` sdists through** — an sdist proves
nothing either way, so every sdist in the closure must also be opened and checked for `ext_modules`
before being counted as pure.

The local repos at `~/Dropbox/bldgtyp-00/00_PH_Tools/{honeybee_ph,PHX,PH_units}` declare the same
dependencies as the published wheels (checked 2026-08-19), so auditing the PyPI closure audits what
we would ship.

## What to record

| Package | Wheel tag | Pure? | Notes |
|---|---|---|---|
| … | … | … | … |

Plus: total closure size (Pyodide bundle budget), and a clear split between the **honeybee-ph
subtree** (needed for Phase 3) and the **PHX subtree** (nice to have).

## Gate

**PASS — full stack pure.** Phase 3 targets honeybee-ph *and* PHX in Pyodide. Best case: the extension
could eventually emit PHPP/WUFI/METr directly, with no server at all.

**PASS WITH CHANGES — honeybee-ph pure, PHX impure.** The near-certain outcome — PHX hard-requires
`xlwings` (see pre-verified facts above). **This is still a pass.** Phase 3 targets honeybee-ph only,
which is all v1 needs — v1 stops at HBJSON by design (PRD §5). PHX stays a separate desktop/CLI step.
Record each blocking dependency and its class (b) or (c), and whether a substitute exists — `lxml`
has a Pyodide build, and `xlwings` only matters for PHPP *writing*, so an in-browser WUFI/METr export
may be closer than it looks. Worth one paragraph in the results file, no more.

**FAIL — honeybee-ph itself pulls a C extension.** Pyodide is dead. Skip Phase 3 entirely and adopt
the PRD §7.1 fallback: **Ruby writes HBJSON directly**, validated against `honeybee-schema` and
`honeybee-ph-schema`. Note this outcome is *good news for licensing* — it links nothing, so the
AGPL entanglement in PRD §9 disappears and the hosted products stay unconstrained.

## Deliverables

- `planning/01_sketchup-export/feasibility/RESULTS/PHASE-2_results.md` with the dependency table
- An explicit scope statement for Phase 3: which packages it must load
- If FAIL: a revised PRD §7.1 naming the Ruby writer as the decided architecture, not the fallback
