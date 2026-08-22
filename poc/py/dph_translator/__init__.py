"""DesignPH-PLUS -- the translation core.

designPH extraction JSON in (`planning/POC/CONTRACT_extraction-json.md`), HBJSON plus a translation
report out. Pure Python, no SketchUp, no browser: the same package runs under pytest on CPython
3.11, in headless Chromium 88, and inside SketchUp's `HtmlDialog`. **Never fork the logic per
host** -- that shared code path is what made Phase 3's failures attributable.

Targets **Python 3.11 exactly** (Pyodide 0.24.1's CPython). No 3.12+ syntax.

Modules, in the order `build` uses them:

    contract.py       the Ruby -> Python seam; the one place types get checked
    facetypes.py      area group -> face type AND boundary condition, one table
    constructions.py  assemblies, in four tiers, honestly
    apertures.py      windows projected onto their hosts
    bridges.py        thermal bridges from tagged edges
    spaces.py         TFA -- filter, attempt, report; never project or repair
    site.py           climate identifiers, carried not resolved
    report.py         the report schema and the verdict
    build.py          orchestration
    entry.py          `translate_json(str) -> str` -- the seam the dialog calls
"""

from __future__ import annotations

__version__ = "0.2.0"

#: The honeybee-schema version this translator's output is validated against (decision D-2).
#:
#: A **constant**, not `importlib.metadata`: `honeybee-schema` is deliberately absent from both the
#: test venv and the Pyodide payload (it is declared upstream but never imported, and pulling it in
#: would drag Rust `pydantic-core`, which has no pure wheel). honeybee therefore leaves `version`
#: null in its own output, and a downstream consumer that cares would have nothing to read.
#:
#: Pinned to `planning/spikes/phase0/validate_hbjson_core.py`, and a test asserts the two agree.
HBJSON_SCHEMA_VERSION = "1.53.1"
