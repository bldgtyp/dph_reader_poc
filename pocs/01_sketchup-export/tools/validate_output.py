# /// script
# requires-python = ">=3.11"
# ///
"""DesignPH-PLUS POC — validate translator output against published `honeybee-schema`.

Two interpreters, on purpose. The translator's venv holds **exactly the eight vendored wheels** so
that a passing test says something about what SketchUp will run; `honeybee-schema` and `pydantic`
are deliberately absent from it (declared upstream, never imported, and pulling them in would drag
Rust `pydantic-core`, which has no pure wheel). So validation shells out to the repo's existing
PEP 723 validator, which brings its own pinned pair.

⚠ **The gate is scoped, and the scope is the finding.** Errors under `properties.energy.*` are
upstream drift, not our data — honeybee-energy's default construction set has never validated
against published honeybee-schema (Phase 3, Finding 40), and **honeybee-ph's `_extend_` hook adds a
`properties` key to every material, which schema 1.53.1 forbids outright**. Nothing we can do about
either while the stack is loaded. What must be zero is errors touching **geometry or the PH
segment** — the part v1 actually writes.

Usage:
    uv run pocs/01_sketchup-export/tools/validate_output.py   # a synthetic model carrying every payload
    uv run pocs/01_sketchup-export/tools/validate_output.py --hbjson MODEL.hbjson # a captured real output
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
POC = HERE.parent
REPO = POC.parents[1]
VENV_PYTHON = POC / "py" / ".venv" / "bin" / "python"
VALIDATOR = REPO / "planning" / "spikes" / "phase0" / "validate_hbjson_core.py"

#: Generates the synthetic model in the translator's own venv, so the thing validated is the thing
#: the tests exercise — `full_model_document` is the shared definition.
GENERATE = """
import sys
sys.path.insert(0, {py!r})
from dph_translator.build import translate
from dph_translator.contract import parse
from tests.synthetic import full_model_document

result = translate(parse(full_model_document()))
open({out!r}, "w").write(result.hbjson)
print(result.verdict["headline"])
"""


def generate(destination: Path) -> str:
    if not VENV_PYTHON.exists():
        raise SystemExit(f"no venv at {VENV_PYTHON} — run `make venv`")
    source = GENERATE.format(py=str(POC / "py"), out=str(destination))
    result = subprocess.run([str(VENV_PYTHON), "-c", source], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stdout + result.stderr)
    return result.stdout.strip()


def validate(hbjson: Path, verdict_path: Path) -> dict[str, object]:
    result = subprocess.run(
        ["uv", "run", str(VALIDATOR), str(hbjson), "--out", str(verdict_path)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    if not verdict_path.exists():
        raise SystemExit(result.stdout + result.stderr)
    return json.loads(verdict_path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hbjson", type=Path, help="validate this file instead of a synthetic one")
    parser.add_argument("--out", type=Path, help="keep the verdict JSON here")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="dph-validate-") as scratch:
        hbjson = args.hbjson
        if hbjson is None:
            hbjson = Path(scratch) / "synthetic_full.hbjson"
            print(f"  translated a synthetic model carrying every PH payload: {generate(hbjson)}")
        verdict_path = args.out or Path(scratch) / "verdict.json"
        verdict = validate(hbjson, verdict_path)

    core = int(verdict["errors_touching_core_or_ph"])  # type: ignore[arg-type]
    containers = verdict["failing_containers"]
    assert isinstance(containers, dict)
    energy_only = all(name.startswith("properties.energy") for name in containers)

    print(f"\n  ================ {'PASSED' if core == 0 else 'FAILED'} ================")
    print(f"  {'ok    ' if core == 0 else 'FAIL  '}zero errors touching geometry or PH  ({core})")
    print(
        f"  {'ok    ' if energy_only else 'note  '}all remaining failures are upstream "
        f"`properties.energy.*`  ({sum(containers.values())} object(s))"
    )
    for name, count in sorted(containers.items()):
        print(f"          {count:4d}  {name}")
    if not energy_only:
        # Not a gate failure by itself — but a container outside `properties.energy` is a new class
        # of drift and should be read before it is dismissed.
        print("\n  ⚠ a failing container is outside `properties.energy.*`; read it before dismissing")
    print(f"\n  declared version: {verdict['declared_version']}")
    return 0 if core == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
