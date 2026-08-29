# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H3: reconciliation against the offline baselines**, via the POC's own harness.

Runs `poc/tools/check_extraction.py` **unchanged** over the headless captures. That tool is the
phase's evidential instrument: Phases 0 and 1 counted every designPH record in the corpus offline,
key by key, so "did the walk find everything?" has a real answer rather than a feeling. Nothing here
re-implements any of it — this wrapper exists to produce one verdict line and, more importantly, to
say out loud which models the harness **cannot grade**.

⚠ **Two of the sixteen staged models have no offline baseline** — `2618 Lavoie` (staged purely as
the 146 MB scale probe) and the designPH 1.0.30 sample. The harness reports them as FAIL, and that
is the harness being right: it refuses to grade a model it has no ground truth for. Counting that
as a Spike-B failure would be scoring the *absence of evidence* as *evidence of absence*, so they
are reported separately as **ungradeable** and the pass is stated over the 14 that can be graded.

⚠ **A firing check gets explained before it gets touched.** The reconciler failed on three of four
real captures during the POC and the data was right every time; its three false-alarm classes are
already fixed (dict-carriers vs area-group carriers, placements vs entities, `descName` override
pairs). If it fires again here, suspect the *comparison* first.

    uv run b3_h3_reconcile.py --captures _private/out/captures \\
        --baseline _private/baselines/corpus_baseline.json --out _private/out/b3_reconcile.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

#: The harness's own line for a model it has no baseline for. Matched exactly rather than by
#: guessing at the model name, so a genuine failure can never be mistaken for this one.
NO_BASELINE = "has an offline baseline to reconcile against"

HEADER = re.compile(r"^  == (?P<name>.+?) ==  (?P<verdict>PASS|FAIL)\s*$")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()

    harness = args.repo_root / "poc" / "tools" / "check_extraction.py"
    captures = sorted(args.captures.glob("*.extraction.json"))
    if not captures:
        print(f"VERDICT H3: FAIL — no captures under {args.captures}")
        return 1

    run = subprocess.run(
        [sys.executable, str(harness), "--baseline", str(args.baseline), *map(str, captures)],
        capture_output=True,
        text=True,
    )
    report = run.stdout

    graded: dict[str, str] = {}
    ungradeable: list[str] = []
    current: str | None = None
    for line in report.splitlines():
        header = HEADER.match(line)
        if header:
            current = header["name"]
            graded[current] = header["verdict"]
            continue
        if NO_BASELINE in line and line.strip().startswith("FAIL") and current:
            ungradeable.append(current)
            graded.pop(current, None)

    failed = sorted(name for name, verdict in graded.items() if verdict == "FAIL")
    passed = bool(graded) and not failed

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "provenance": "third-party SDK re-host — feasibility-only evidence",
                "harness": str(harness.relative_to(args.repo_root)),
                "graded": graded,
                "ungradeable_no_offline_baseline": sorted(ungradeable),
                "report": report,
            },
            indent=1,
        )
    )

    for name in sorted(graded):
        print(f"{'✅' if graded[name] == 'PASS' else '❌'} {name}: {graded[name]}")
    for name in sorted(ungradeable):
        print(f"⚪ {name}: UNGRADEABLE — no offline baseline, so this model can grade nothing")
    print(
        f"\nVERDICT H3: {'PASS' if passed else 'FAIL'} — {len(graded) - len(failed)}/{len(graded)} "
        f"gradeable models reconcile against the offline baselines under the unchanged harness; "
        f"{len(ungradeable)} model(s) have no baseline and are excluded by name → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
