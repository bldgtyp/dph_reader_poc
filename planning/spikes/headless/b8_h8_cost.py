# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H8: cost, recorded not gated.** Wall time, peak memory, and concurrency.

Numbers only, no threshold — a server budget will eventually want them, and Spike C's host choice
depends on the concurrency answers. But three of the four measurements below are things Spike A
could not make, and each exists because the obvious version of it is wrong:

⚠ **Peak RSS needs ONE PROCESS PER MODEL.** Spike A's capability sweep read all 16 models in a
single process and reported 851 MB, and that is a *process* high-water mark — "the run peaked here",
not "Lavoie costs this". `ru_maxrss` never comes down, so any figure taken from a shared process
attributes every model's peak to whichever model happened to run last.

⚠ **Cost tracks unique ENTITY count, not file size.** Adelphi is 3.2 MB and 1441 tagged entities
behind 1,023,558 face placements; `2618 Lavoie` is **146 MB** and reads faster than Bluff Reach's
10.8 MB. Bracketing on file size would predict the wrong thing, so the brackets here are Lavoie
(largest file) and `250708` (fastest), not the two the plan originally named.

➕ **Concurrency is measured, not assumed**, because a folder watcher will want to know before
Spike C picks a host. Three separate questions, and they have different answers:

1. **Two models open at once in one process** — does the SDK allow it, and does either read change?
   Compared byte-for-byte against the one-at-a-time captures, because "it did not crash" is not
   "it read the same thing".
2. **Two processes in parallel** — the boring answer a worker pool would actually use.
3. **Two threads in one process** — ⚠ run inside a subprocess on purpose. `SUInitialize`'s thread
   safety is undocumented here, and a reader that segfaults must produce *data* rather than take
   the harness down with it.

    uv run b8_h8_cost.py --corpus _private/corpus --captures _private/out/captures \\
        --work _private/out/cost --out _private/out/b8_cost.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from collector import comparable_digest
from harness import run_child

#: Every child measurement opens the same way. Written once: an earlier version repeated these four
#: lines and the RSS block in three embedded scripts, and a change to `capture()`'s signature had to
#: be found in three string literals with no import to follow and no linter that sees them.
PREAMBLE = """
import json, resource, sys, threading, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from collector import SDK, HeadlessCollector, Tables, capture, load_ruby_marshal, write_capture

sdk = SDK(read_only=True)
tables = Tables(load_ruby_marshal(Path(sys.argv[2])))
started = time.perf_counter()
"""

#: ⚠ macOS reports `ru_maxrss` in **bytes**, Linux in **kibibytes**. Encoded once: three copies of a
#: 1024x platform correction, in a figure reported as a headline cost, is one Linux run away from
#: three different units in one JSON file.
PEAK_RSS = """
sdk.terminate()
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
scale = 1024 * 1024 if sys.platform == "darwin" else 1024
REPORT["seconds"] = round(time.perf_counter() - started, 3)
REPORT["peak_rss_mb"] = round(peak / scale, 1)
print(json.dumps(REPORT))
"""

#: Reads one model and reports its OWN peak RSS. Run as a child so the figure belongs to one model.
SINGLE = PREAMBLE + """
result = capture(Path(sys.argv[3]), sdk, tables, apply_gate=False)
size = write_capture(result.document, Path(sys.argv[4]))
REPORT = {"read_seconds": round(result.seconds, 3), "bytes": size,
          "counts": result.document["counts"], "notices": result.notices}
""" + PEAK_RSS

#: Both models open **at the same time**, then read. If the SDK objected to a second open model this
#: is where it would say so.
BOTH_OPEN = PREAMBLE + """
first, second = Path(sys.argv[3]), Path(sys.argv[4])
a = sdk.open_model(first)
b = sdk.open_model(second)
try:
    write_capture(HeadlessCollector(sdk, tables).extract(a, first.stem), Path(sys.argv[5]))
    write_capture(HeadlessCollector(sdk, tables).extract(b, second.stem), Path(sys.argv[6]))
finally:
    sdk.close_model(a)
    sdk.close_model(b)
REPORT = {}
""" + PEAK_RSS

#: Two threads, one process, one `SUInitialize`. ⚠ Deliberately in a child: if this is unsafe it
#: crashes, and a crash must be a recorded result rather than the end of the run.
THREADED = PREAMBLE + """
root = Path(sys.argv[2])
paths = [Path(sys.argv[3]), Path(sys.argv[4])]
outs = [Path(sys.argv[5]), Path(sys.argv[6])]
errors = []

def read(path, out):
    try:
        model = sdk.open_model(path)
        try:
            write_capture(HeadlessCollector(sdk, Tables(load_ruby_marshal(root))).extract(
                model, path.stem), out)
        finally:
            sdk.close_model(model)
    except BaseException as error:
        errors.append(f"{type(error).__name__}: {error}")

threads = [threading.Thread(target=read, args=(p, o)) for p, o in zip(paths, outs)]
for t in threads: t.start()
for t in threads: t.join()
REPORT = {"errors": errors}
""" + PEAK_RSS


def digest(path: Path) -> str | None:
    """A capture's comparable hash, or `None` when the file is missing.

    ⚠ `collector.comparable_digest` excludes `entity_id` — the contract's session-scoped field,
    which is scoped to the **process** rather than the model. A raw byte comparison across two
    process histories reports a mismatch on 100 % of models and means nothing by it, which is exactly
    what the first version of this check did on the plain two-processes-in-parallel case, where
    nothing concurrent was happening at all.
    """
    if not path.exists():
        return None
    return comparable_digest(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True, help="the one-at-a-time captures")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()

    here = str(Path(__file__).parent.resolve())
    root = str(args.repo_root.resolve())
    args.work.mkdir(parents=True, exist_ok=True)

    # -- per-model cost, one process each ---------------------------------
    models: dict[str, Any] = {}
    for model in sorted(args.corpus.glob("*.skp")):
        out = args.work / f"{model.stem}.single.json"
        result = run_child(SINGLE, args.work, "single", [here, root, str(model.resolve()), str(out)])
        result["file_mb"] = round(model.stat().st_size / 1_048_576, 1)
        counts = result.get("counts", {})
        result["entities"] = counts.get("faces_tagged", 0) + counts.get("edges_tagged", 0)
        result["seconds"] = result.get("read_seconds", result.get("seconds", 0.0))
        models[model.name] = result
        if "error" in result:
            print(f"❌ {model.name}: {result['error'].splitlines()[-1]}")
            continue
        print(
            f"   {model.name:<42} {result['file_mb']:>6.1f} MB  {result['seconds']:>6.2f} s  "
            f"{result['peak_rss_mb']:>7.1f} MB peak  {counts.get('faces_walked', 0):>9} placements"
        )

    # -- concurrency -------------------------------------------------------
    # ⚠ Derived from what was just measured, not two names. The docstring says the brackets should
    # be the largest file and the fastest read; hardcoding them meant a renamed or unstaged file
    # left `concurrency` empty and the printout silent, inside a PASS.
    measured = [(name, row) for name, row in models.items() if "error" not in row]
    pair: list[Path] = []
    if len(measured) >= 2:
        largest = max(measured, key=lambda item: item[1]["file_mb"])[0]
        fastest = min(
            (item for item in measured if item[0] != largest), key=lambda item: item[1]["seconds"]
        )[0]
        pair = [args.corpus / largest, args.corpus / fastest]
    concurrency: dict[str, Any] = {}
    if len(pair) == 2 and all(path.exists() for path in pair):
        outs = [args.work / f"{path.stem}.both.json" for path in pair]
        both = run_child(
            BOTH_OPEN, args.work, "both",
            [here, root, *(str(p.resolve()) for p in pair), *(str(o.resolve()) for o in outs)],
        )
        # ⚠ "It did not crash" is not "it read the same thing". Compare against the sequential
        # captures, which H4 already graded against the live ones.
        both["matches_sequential_capture"] = {
            path.name: digest(out) == digest(args.captures / f"{path.stem}.extraction.json")
            for path, out in zip(pair, outs, strict=True)
        }
        concurrency["two_models_open_in_one_process"] = both

        started = time.perf_counter()
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str((Path(__file__).parent / "collector.py").resolve()),
                    # ⚠ `--no-gate` — H8 measures the cost of READING, and the version gate would
                    # refuse one of the staged models before it read anything (H9).
                    "--no-gate",
                    "--model", str(path.resolve()),
                    "--out", str((args.work / f"{path.stem}.parallel.json").resolve()),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for path in pair
        ]
        codes = [process.wait() for process in processes]
        concurrency["two_processes_in_parallel"] = {
            "seconds": round(time.perf_counter() - started, 3),
            "exit_codes": codes,
            "matches_sequential_capture": {
                path.name: digest(args.work / f"{path.stem}.parallel.json")
                == digest(args.captures / f"{path.stem}.extraction.json")
                for path in pair
            },
        }

        thread_outs = [args.work / f"{path.stem}.threaded.json" for path in pair]
        concurrency["two_threads_in_one_process"] = run_child(
            THREADED, args.work, "threaded",
            [here, root, *(str(p.resolve()) for p in pair),
             *(str(o.resolve()) for o in thread_outs)],
        )
        concurrency["two_threads_in_one_process"]["matches_sequential_capture"] = {
            path.name: digest(out) == digest(args.captures / f"{path.stem}.extraction.json")
            for path, out in zip(pair, thread_outs, strict=True)
        }

    print("\n  concurrency")
    for label, row in concurrency.items():
        matches = row.get("matches_sequential_capture", {})
        state = "error: " + row["error"].splitlines()[-1] if "error" in row else (
            f"{row.get('seconds')} s"
            + (f", {row['peak_rss_mb']} MB peak" if "peak_rss_mb" in row else "")
            + (f", errors {row['errors']}" if row.get("errors") else "")
        )
        agree = "captures match the sequential ones (entity_id aside)" if matches and all(
            matches.values()
        ) else (
            f"⚠ MISMATCH {matches}" if matches else "not compared"
        )
        print(f"   {label:<34} {state} — {agree}")

    # ⚠ Cost is recorded, but *agreement* is not a cost measurement: "does a threaded read corrupt
    # the capture" is a yes/no with a wrong answer, and it was previously printed on a non-VERDICT
    # line inside a function that returned 0 unconditionally. Two threads silently producing a wrong
    # capture would have been a green Spike B.
    disagreements = sorted(
        f"{label}: {name}"
        for label, row in concurrency.items()
        for name, agrees in (row.get("matches_sequential_capture") or {}).items()
        if not agrees
    )
    concurrency_ran = [label for label, row in concurrency.items() if "error" not in row]
    concurrency_ok = (
        len(concurrency_ran) == 3 and not disagreements and not any(
            row.get("errors") for row in concurrency.values()
        )
    )

    ok = [row for row in models.values() if "error" not in row]
    slowest = max(ok, key=lambda row: row["seconds"], default=None)
    heaviest = max(ok, key=lambda row: row["peak_rss_mb"], default=None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "provenance": "third-party SDK re-host — feasibility-only evidence",
                "note": "recorded, not gated — H8 sets no threshold",
                "models": models,
                "concurrency": concurrency,
                "concurrency_disagreements": disagreements,
            },
            indent=1,
        )
    )
    print(
        f"VERDICT H8-concurrency: {'PASS' if concurrency_ok else 'FAIL'} — "
        f"{len(concurrency_ran)}/3 modes ran and every capture they produced matches the "
        f"sequential one (entity_id aside); {len(disagreements)} disagreement(s) {disagreements}"
    )
    print(
        f"VERDICT H8: RECORDED — {len(ok)}/{len(models)} models measured one process each; "
        f"slowest {slowest['seconds'] if slowest else '?'} s, "
        f"heaviest {heaviest['peak_rss_mb'] if heaviest else '?'} MB peak RSS, "
        f"total {sum(row['seconds'] for row in ok):.1f} s → {args.out}"
    )
    return 0 if concurrency_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
