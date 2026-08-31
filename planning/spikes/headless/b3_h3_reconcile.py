# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H3: reconciliation against the offline baselines**, via the POC's own harness.

Runs `pocs/01_sketchup-export/tools/check_extraction.py` **unchanged** over the headless captures. That tool is the
phase's evidential instrument: Phases 0 and 1 counted every designPH record in the corpus offline,
key by key, so "did the walk find everything?" has a real answer rather than a feeling. Nothing here
re-implements any of it — this wrapper exists to produce one verdict line and, more importantly, to
say out loud which models the harness **cannot grade**.

⚠ **Some staged models have no offline baseline** — `2618 Lavoie` is staged purely as the 146 MB
scale probe. The harness would report them as FAIL, and that is the harness being right: it refuses
to grade a model it has no ground truth for. Counting that as a Spike-B failure would be scoring the
*absence of evidence* as *evidence of absence*.

★ **So the partition happens BEFORE the subprocess, from the baseline itself.** The harness is only
handed captures it can grade, and the rest are reported as ungradeable from the partition. An
earlier version passed all of them and then un-failed two by matching a substring of the harness's
own sentence — which (a) makes a wording change in a POC file this phase must not modify silently
reclassify a real failure, and (b) removed whichever model's header was current, so the phrase
appearing anywhere in a genuinely failing report would drop that model from grading with the
verdict still green.

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
from typing import Any

from harness import write_result
from sdk import load_module


#: `check_extraction.py`'s own model↔baseline matcher, imported rather than re-implemented: it
#: normalises the `_COPY` / ` copy` / `-copy` suffixes the staged corpus actually uses, and a
#: narrower local copy silently answers "no baseline" for a name it does not know.
def baseline_covers(match_baseline: Any, baseline: dict[str, Any], capture: Path) -> bool:
    document = json.loads(capture.read_text(encoding="utf-8"))
    return match_baseline(document["model"]["file_name"], baseline) is not None


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

    harness_path = args.repo_root / "pocs" / "01_sketchup-export" / "tools" / "check_extraction.py"
    captures = sorted(args.captures.glob("*.extraction.json"))
    if not captures:
        print(f"VERDICT H3: FAIL — no captures under {args.captures}")
        return 1

    check_extraction = load_module(harness_path, "check_extraction")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    gradeable = [
        c for c in captures if baseline_covers(check_extraction.match_baseline, baseline, c)
    ]
    ungradeable = sorted(
        c.name.removesuffix(".extraction.json") for c in captures if c not in gradeable
    )

    run = subprocess.run(
        [sys.executable, str(harness_path), "--baseline", str(args.baseline), *map(str, gradeable)],
        capture_output=True,
        text=True,
    )
    report = run.stdout

    graded: dict[str, str] = {}
    for line in report.splitlines():
        header = HEADER.match(line)
        if header:
            graded[header["name"]] = header["verdict"]

    failed = sorted(name for name, verdict in graded.items() if verdict == "FAIL")
    # ⚠ The harness's exit status counts too. An earlier version discarded it and graded only the
    # prose it printed — the same shape as the POC banner that stayed green for the life of its
    # harness by rendering a different field from the one it checked.
    passed = (
        bool(graded)
        and not failed
        and len(graded) == len(gradeable)
        and run.returncode == 0
    )

    write_result(
        args.out,
        {
            "harness": str(harness_path.relative_to(args.repo_root)),
            "harness_exit_code": run.returncode,
            "graded": graded,
            "ungradeable_no_offline_baseline": ungradeable,
            "report": report,
        },
    )

    for name in sorted(graded):
        print(f"{'✅' if graded[name] == 'PASS' else '❌'} {name}: {graded[name]}")
    for name in ungradeable:
        print(f"⚪ {name}: UNGRADEABLE — no offline baseline, so this model can grade nothing")
    print(
        f"\nVERDICT H3: {'PASS' if passed else 'FAIL'} — {len(graded) - len(failed)}/{len(graded)} "
        f"gradeable models reconcile against the offline baselines under the unchanged harness; "
        f"{len(ungradeable)} model(s) have no baseline and are excluded by name → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
