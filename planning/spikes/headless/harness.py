# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shared plumbing for the Spike B gates — the things that were being written once per script.

Nothing here decides anything. It exists because the same four facts were copy-pasted across nine
gate scripts, and in this project a duplicated fact is a check that can quietly stop being able to
fail:

- **the five captured models.** Hardcoded in three gates as an identical tuple. ⚠ Two of those
  gates grade `len(models) == len(CAPTURED)`, but a third graded only `bool(models)` — so a list
  that fell behind would silently grade four models and still print PASS. `captured_models()`
  derives it from what is actually staged and **refuses to run below a floor**, because a gate whose
  scope collapses to zero and still says PASS is the failure mode this phase names most often.
- **the provenance line.** Ten copies of one sentence that has to keep saying the same thing.
- **the child-process runner.** Four hand-written copies with four different stderr truncations.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

#: Stamped into every gate's JSON. Every number in Spike B carries this caveat.
PROVENANCE = "third-party SDK re-host — feasibility-only evidence"

#: How many live captures the POC produced. A gate that finds fewer is looking at a broken staging,
#: not at a smaller corpus, and must say so rather than grade what it happens to see.
EXPECTED_CAPTURES = 5

CAPTURE_SUFFIX = ".extraction.json"


def captured_models(fixtures: Path, minimum: int = EXPECTED_CAPTURES) -> list[str]:
    """The models with a live SketchUp capture — **derived from `fixtures/`, never hardcoded**.

    ⚠ Excludes the `.PRE-FIX.json` Adelphi capture, which predates the POC's §8.1/§8.2 corrections
    and is kept only as evidence that those defects existed. Grading against it would compare a
    fixed reader to a broken one.
    """
    names = sorted(
        path.name.removesuffix(CAPTURE_SUFFIX)
        for path in fixtures.glob(f"*{CAPTURE_SUFFIX}")
        if ".PRE-FIX" not in path.name
    )
    if len(names) < minimum:
        raise SystemExit(
            f"only {len(names)} live capture(s) under {fixtures}, expected at least {minimum}.\n"
            "Stage _private/ first — see its MANIFEST.md. Grading a short list would report PASS "
            "over models that were never compared."
        )
    return names


def run_child(script: str, work: Path, name: str, arguments: list[str]) -> dict[str, Any]:
    """Run one measurement in its own interpreter and return its JSON line, or its failure.

    A child on purpose, wherever the thing being measured could take the harness down with it — a
    crash has to be a recorded result, not the end of the run.
    """
    runner = work / f"_{name}.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(script, encoding="utf-8")
    run = subprocess.run([sys.executable, str(runner), *arguments], capture_output=True, text=True)
    if run.returncode != 0:
        return {"error": f"exit {run.returncode}: {run.stderr.strip()[-1500:]}"}
    lines = [line for line in run.stdout.splitlines() if line.startswith("{")]
    return json.loads(lines[-1]) if lines else {"error": "no result line"}


def write_result(out: Path, payload: dict[str, Any]) -> None:
    """Every gate's `--out`, with the provenance stamped on.

    ⚠ Every Spike-B script takes an explicit `--out`: `byte_identity.py` once inherited another
    tool's default baseline directory and wrote client HBJSON into the committed repo
    (CONSTRAINTS §9).
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"provenance": PROVENANCE, **payload}, indent=1), encoding="utf-8")
