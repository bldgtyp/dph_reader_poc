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
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

#: Reads one model and reports its OWN peak RSS. Run as a child so the figure belongs to one model.
#: ⚠ macOS reports `ru_maxrss` in bytes; Linux reports kibibytes. Normalised here rather than in the
#: caller, where the platform is no longer visible.
SINGLE = """
import json, resource, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from collector import SDK, Tables, capture, load_ruby_marshal, write_capture

sdk = SDK(read_only=True)
tables = Tables(load_ruby_marshal(Path(sys.argv[2])))
started = time.perf_counter()
document, notices, seconds = capture(Path(sys.argv[3]), sdk, tables)
size = write_capture(document, Path(sys.argv[4]))
sdk.terminate()
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
scale = 1024 * 1024 if sys.platform == "darwin" else 1024
print(json.dumps({
    "seconds": round(seconds, 3),
    "total_seconds": round(time.perf_counter() - started, 3),
    "peak_rss_mb": round(peak / scale, 1),
    "bytes": size,
    "counts": document["counts"],
    "notices": notices,
}))
"""

#: Both models open **at the same time**, then read. If the SDK objected to a second open model this
#: is where it would say so.
BOTH_OPEN = """
import json, resource, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from collector import SDK, HeadlessCollector, Tables, load_ruby_marshal, write_capture

sdk = SDK(read_only=True)
tables = Tables(load_ruby_marshal(Path(sys.argv[2])))
first, second = Path(sys.argv[3]), Path(sys.argv[4])
started = time.perf_counter()
a = sdk.open_model(first)
b = sdk.open_model(second)
try:
    write_capture(HeadlessCollector(sdk, tables).extract(a, first.stem), Path(sys.argv[5]))
    write_capture(HeadlessCollector(sdk, tables).extract(b, second.stem), Path(sys.argv[6]))
finally:
    sdk.close_model(a)
    sdk.close_model(b)
sdk.terminate()
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
scale = 1024 * 1024 if sys.platform == "darwin" else 1024
print(json.dumps({"seconds": round(time.perf_counter() - started, 3),
                  "peak_rss_mb": round(peak / scale, 1)}))
"""

#: Two threads, one process, one `SUInitialize`. ⚠ Deliberately in a child: if this is unsafe it
#: crashes, and a crash must be a recorded result rather than the end of the run.
THREADED = """
import json, resource, sys, threading, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from collector import SDK, HeadlessCollector, Tables, load_ruby_marshal, write_capture

sdk = SDK(read_only=True)
root = Path(sys.argv[2])
paths = [Path(sys.argv[3]), Path(sys.argv[4])]
outs = [Path(sys.argv[5]), Path(sys.argv[6])]
errors = []

def read(path, out):
    try:
        tables = Tables(load_ruby_marshal(root))
        model = sdk.open_model(path)
        try:
            write_capture(HeadlessCollector(sdk, tables).extract(model, path.stem), out)
        finally:
            sdk.close_model(model)
    except BaseException as error:
        errors.append(f"{type(error).__name__}: {error}")

started = time.perf_counter()
threads = [threading.Thread(target=read, args=(p, o)) for p, o in zip(paths, outs)]
for t in threads: t.start()
for t in threads: t.join()
sdk.terminate()
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
scale = 1024 * 1024 if sys.platform == "darwin" else 1024
print(json.dumps({"seconds": round(time.perf_counter() - started, 3),
                  "peak_rss_mb": round(peak / scale, 1), "errors": errors}))
"""


def child(script: str, work: Path, name: str, arguments: list[str]) -> dict[str, Any]:
    """Run one measurement in its own interpreter and return its JSON line, or its failure."""
    runner = work / f"_{name}.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(script, encoding="utf-8")
    run = subprocess.run(
        [sys.executable, str(runner), *arguments], capture_output=True, text=True
    )
    if run.returncode != 0:
        return {"error": f"exit {run.returncode}: {run.stderr.strip()[-800:]}"}
    lines = [line for line in run.stdout.splitlines() if line.startswith("{")]
    return json.loads(lines[-1]) if lines else {"error": "no result line"}


def digest(path: Path) -> str | None:
    """A capture's hash **with `entity_id` removed**, which is the only comparable form.

    ⚠ `entity_id` is `SUEntityGetID`, and the contract calls it session-scoped, a debugging aid
    only (§2). It is scoped to the *process*, not to the model: reading thirteen other models first
    shifts every one of Adelphi's 128 ids, and the capture grows 384 bytes. So a raw byte
    comparison across two different process histories reports a mismatch on 100 % of models and
    means nothing by it — which is exactly what the first version of this check did, on the
    plain two-processes-in-parallel case where nothing concurrent was happening at all.

    Everything else is compared byte-for-byte.
    """
    if not path.exists():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    for section in ("faces", "edges", "windows"):
        for record in document.get(section, []):
            record.pop("entity_id", None)
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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
        result = child(SINGLE, args.work, "single", [here, root, str(model.resolve()), str(out)])
        result["file_mb"] = round(model.stat().st_size / 1_048_576, 1)
        counts = result.get("counts", {})
        result["entities"] = counts.get("faces_tagged", 0) + counts.get("edges_tagged", 0)
        models[model.name] = result
        if "error" in result:
            print(f"❌ {model.name}: {result['error'].splitlines()[-1]}")
            continue
        print(
            f"   {model.name:<42} {result['file_mb']:>6.1f} MB  {result['seconds']:>6.2f} s  "
            f"{result['peak_rss_mb']:>7.1f} MB peak  {counts.get('faces_walked', 0):>9} placements"
        )

    # -- concurrency -------------------------------------------------------
    pair = [
        args.corpus / "adelphi-designph_COPY.skp",
        args.corpus / "2618_Lavoie_SCALEPROBE_COPY.skp",
    ]
    concurrency: dict[str, Any] = {}
    if all(path.exists() for path in pair):
        outs = [args.work / f"{path.stem}.both.json" for path in pair]
        both = child(
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
        concurrency["two_threads_in_one_process"] = child(
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
            },
            indent=1,
        )
    )
    print(
        f"\nVERDICT H8: RECORDED — {len(ok)}/{len(models)} models measured one process each; "
        f"slowest {slowest['seconds'] if slowest else '?'} s, "
        f"heaviest {heaviest['peak_rss_mb'] if heaviest else '?'} MB peak RSS, "
        f"total {sum(row['seconds'] for row in ok):.1f} s → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
