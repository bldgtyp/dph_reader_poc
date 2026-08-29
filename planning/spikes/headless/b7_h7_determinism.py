# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H7: determinism. Claim (d).**

*Does the headless collector read the same file the same way twice?*

This is a different claim from H4's, and keeping them apart is the point: H4 asks whether the
headless reader agrees with the live one, H7 asks whether it agrees with **itself**. Only H7 is
about the reader's own stability, and a service that re-reads a watched folder depends on it —
pholio's whole change-detection model is "the capture changed" meaning "the model changed".

⚠ **Run from two different working directories, into two different `--out` paths**, and give the
model by an **absolute** path on one leg and a **relative** one on the other. That is not
ceremony: this phase's own rules worry about embedded filesystem paths, and
`Sketchup::Model#path` — the value that made `model.file_name` untrustworthy in the first place —
is exactly the kind of thing that leaks a working directory into a capture. So determinism gets
tested against precisely the thing that would break it.

⚠ **The comparison is BYTE equality, deliberately.** Nothing in the headless path mints an id or
iterates a `set`, so unlike H6 there is no canonicalisation to apply and none is wanted: if two
reads of one unchanged file differ at all, something is nondeterministic and everything above this
gate is standing on it.

★ **A third leg, and it is the one that says what claim (d) actually covers.** Legs A and B each
read one model in a fresh process, so they share a process *history* as well as a file — and a gate
built only on those two would pass while hiding a real limit. Leg C reads a **different model
first**, in the same process, and then the model under test.

⚠ **It differs, and only in `entity_id`.** `SUEntityGetID` is scoped to the process, not to the
model: after thirteen other models, every one of Adelphi's 128 ids has moved and the capture is 384
bytes longer. The contract already calls that field session-scoped and a debugging aid only (§2),
so this is the contract being right rather than the reader being wrong — but it means claim (d) is
**"byte-identical for a given process history, and identical field-for-field otherwise"**, and a
watcher that hashes captures to detect change must exclude `entity_id` or re-read in a fresh
process. Recorded as a contract-v3 candidate. Leg C reports both comparisons so the scope is
measured rather than asserted.

    uv run b7_h7_determinism.py --corpus _private/corpus --work _private/out/determinism \\
        --out _private/out/b7_determinism.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_leg(collector: Path, model: Path, cwd: Path, out: Path, relative: bool) -> dict[str, Any]:
    """One capture, from one working directory, into one output path.

    `relative` gives the model as a path relative to `cwd` — the leg that would expose a reader
    resolving or recording anything about where it was launched from.
    """
    cwd.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    target = os.path.relpath(model, cwd) if relative else str(model.resolve())
    run = subprocess.run(
        # ⚠ `--no-gate`: this gate grades the READ, and one of the sixteen staged models is a
        # designPH 1.0.30 that the version gate refuses (H9). Determinism is a property of the
        # reader, so it is measured on the reader.
        [
            sys.executable, str(collector.resolve()), "--no-gate",
            "--model", target, "--out", str(out.resolve()),
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0 or not out.exists():
        return {"error": run.stderr.strip()[-1500:] or "no capture written"}
    payload = out.read_bytes()
    return {
        "cwd": str(cwd),
        "model_argument": target,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


#: Reads a *different* model first, then the model under test, in one process — so the second read
#: carries a process history. Everything else about it matches the CLI exactly.
WITH_HISTORY = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from collector import SDK, Tables, capture, load_ruby_marshal, write_capture

sdk = SDK(read_only=True)
tables = Tables(load_ruby_marshal(Path(sys.argv[2])))
capture(Path(sys.argv[3]), sdk, tables)          # the history
document, _, _ = capture(Path(sys.argv[4]), sdk, tables)
write_capture(document, Path(sys.argv[5]))
sdk.terminate()
"""

#: The contract's own session-scoped field (§2). Removed for the second of leg C's two comparisons.
SESSION_SCOPED = "entity_id"


def without_session_ids(payload: bytes) -> str:
    """Hash a capture with `entity_id` stripped — everything else compared as found."""
    document = json.loads(payload.decode("utf-8"))
    for section in ("faces", "edges", "windows"):
        for record in document.get(section, []):
            record.pop(SESSION_SCOPED, None)
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def first_difference(a: bytes, b: bytes) -> str:
    """Where two captures first differ, with a little context. The shape before the failure."""
    for index, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            window = slice(max(0, index - 60), index + 60)
            return (
                f"byte {index}: …{a[window].decode('utf-8', 'replace')}… "
                f"vs …{b[window].decode('utf-8', 'replace')}…"
            )
    return f"one capture is a prefix of the other ({len(a)} vs {len(b)} bytes)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True, help="scratch root for the two legs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()

    collector = Path(__file__).parent / "collector.py"
    first_root = args.work / "leg-a"
    # ⚠ A deeper, differently-named tree on the second leg, so a relative path recorded anywhere
    # would come out a different length as well as a different value.
    second_root = args.work / "leg-b" / "nested" / "deeper"

    # Leg C's "history" model is deliberately a different one from every model under test, and a
    # small one, so the leg costs a fraction of a second per model.
    history_model = args.corpus / "designph_test_COPY.skp"
    runner = args.work / "_with_history.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(WITH_HISTORY, encoding="utf-8")

    models: dict[str, Any] = {}
    for model in sorted(args.corpus.glob("*.skp")):
        a = run_leg(collector, model, first_root, first_root / f"{model.stem}.a.json", relative=False)
        b = run_leg(
            collector, model, second_root, second_root / "out" / f"{model.stem}.b.json", relative=True
        )
        row: dict[str, Any] = {"leg_a": a, "leg_b": b}
        if "error" in a or "error" in b:
            row["identical"] = False
            row["difference"] = a.get("error") or b.get("error")
        else:
            row["identical"] = a["sha256"] == b["sha256"]
            if not row["identical"]:
                row["difference"] = first_difference(
                    (first_root / f"{model.stem}.a.json").read_bytes(),
                    (second_root / "out" / f"{model.stem}.b.json").read_bytes(),
                )
        # -- leg C: the same model, read after another one in the same process -----
        if history_model.exists() and history_model != model and "error" not in a:
            third = args.work / "leg-c" / f"{model.stem}.c.json"
            third.parent.mkdir(parents=True, exist_ok=True)
            run = subprocess.run(
                [
                    sys.executable, str(runner),
                    str(Path(__file__).parent.resolve()), str(args.repo_root.resolve()),
                    str(history_model.resolve()), str(model.resolve()), str(third.resolve()),
                ],
                capture_output=True, text=True,
            )
            if run.returncode != 0 or not third.exists():
                row["leg_c"] = {"error": run.stderr.strip()[-800:] or "no capture written"}
            else:
                fresh = (first_root / f"{model.stem}.a.json").read_bytes()
                after = third.read_bytes()
                row["leg_c"] = {
                    "byte_identical_to_leg_a": fresh == after,
                    "identical_ignoring_session_ids": (
                        without_session_ids(fresh) == without_session_ids(after)
                    ),
                    "bytes": len(after),
                }

        models[model.name] = row
        history = row.get("leg_c")
        if history is None:
            note = "leg C skipped — this IS the history model"
        elif "error" in history:
            note = f"leg C failed: {history['error'].splitlines()[-1]}"
        elif history["byte_identical_to_leg_a"]:
            note = "after another model in-process: byte-identical"
        else:
            note = (
                "after another model in-process: differs, identical ignoring entity_id: "
                f"{history['identical_ignoring_session_ids']}"
            )
        print(
            f"{'✅' if row['identical'] else '❌'} {model.name}: "
            f"{a.get('sha256', '?')[:16]} vs {b.get('sha256', '?')[:16]} "
            f"({a.get('bytes', '?')} bytes) · {note}"
        )
        if not row["identical"]:
            print(f"     ⚠ {row.get('difference')}")

    identical = sum(1 for row in models.values() if row["identical"])
    # ⚠ Leg C is allowed to differ — but only in `entity_id`. Anything else moving with process
    # history would be a real nondeterminism, and this is what says so.
    history_rows = [row["leg_c"] for row in models.values() if "leg_c" in row]
    history_clean = sum(1 for row in history_rows if row.get("identical_ignoring_session_ids"))
    history_byte_identical = sum(1 for row in history_rows if row.get("byte_identical_to_leg_a"))
    passed = (
        bool(models)
        and identical == len(models)
        and history_clean == len(history_rows)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "provenance": "third-party SDK re-host — feasibility-only evidence",
                "method": (
                    "two working directories, two --out paths, the model given absolutely on one "
                    "leg and relatively on the other; byte equality, no canonicalisation"
                ),
                "leg_c_method": (
                    "a different model read first in the same process, so the capture under test "
                    "carries a process history; entity_id is expected to move and nothing else is"
                ),
                "models": models,
            },
            indent=1,
        )
    )
    print(
        f"\nVERDICT H7: {'PASS' if passed else 'FAIL'} — {identical}/{len(models)} models capture "
        f"byte-identically from two different working directories and two different output paths; "
        f"after another model in the same process {history_byte_identical}/{len(history_rows)} stay "
        f"byte-identical and {history_clean}/{len(history_rows)} are identical once the contract's "
        f"session-scoped `entity_id` is excluded → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
