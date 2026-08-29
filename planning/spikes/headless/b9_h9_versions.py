# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H9: what does the reader do with a designPH version it does not know?** ⭐ NEW (§2.2)

The corpus spans **designPH 1.0.30 → 2.4.0 BETA**, and 1.0.30 is structurally different: a `Shader`
key no 2.x model has, `tfa_calc` without the `_ud` suffix, `Klima_Standort` with a capital K
(`DESIGNPH_DATA_MODEL.md` §13.1). A reader that meets it must **say so**, not half-read it — hard
rule 4 applied to the version axis rather than the entity axis.

**The right answer was left open by the plan, deliberately, and this gate settles it.** Either the
reader reads the model and names what it could not resolve, or it refuses by name and says why.
⛔ **Silently producing a partial capture is the failure**, whichever way it goes.

⚠ **The precedent is exact and it is this repo's:** the offline parser returned a clean **zero** on
the 1.0.30 file and that stood for ten days (`DESIGNPH_FILE_FORMATS.md` §4.1). A plausible answer
with no error is the shape to avoid, so this gate does not ask "did it work?" — it asks **"did it
say?"**, and it compares what the reader *found* against what the offline corpus baseline knows is
there.

Three checks per model:

1. **The gate's decision**, from `gate.py` — the POC's `gate.rb` ported, so the extension and a
   headless service cannot silently diverge about which files they will read. A refusal must name
   the stamp it saw.
2. **On a model the gate ALLOWS**, the capture must not be quietly thin: every table the offline
   baseline records as present must appear in `counts.tables_found`, and unresolved model-level keys
   are named. A capture that reads 42 faces and drops a table without saying so is the failure mode.
3. **On a model the gate REFUSES, nothing may be emitted at all** — and that is checked by
   running `collector.py` itself, not by asking `gate.py` what it would have said. The gate being
   right is a different claim from the reader applying it.

    uv run b9_h9_versions.py --corpus _private/corpus --captures _private/out/captures \\
        --baseline _private/baselines/corpus_baseline.json --out _private/out/b9_versions.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import gate
from collector import MODEL_KLIMA_ID, MODEL_KLIMA_NAME, MODEL_VERSION_KEY
from harness import write_result
from sdk import load_module

#: The two models this gate exists for, and why each is here. Everything else in the corpus is 2.1
#: to 2.2 and exercises nothing on this axis.
UNDER_TEST = {
    "BLDGTYP-sample-pre2014_COPY.skp": (
        "designPH 1.0.30 — a generation below anything the contract was written against"
    ),
    "designph_test_COPY.skp": (
        "designPH 2.4.0 BETA — a beta stamp above every released version in the corpus"
    ),
}

#: Model-level keys that are not tables and are read into `model` (contract §1) — **taken from the
#: collector**, not retyped. This set is what the gate subtracts to find unread blob keys, so a
#: hand-copy that fell behind would report a key the reader had learned to read as a silent partial
#: capture: firing on healthy data, which is the same defect `baseline_blob_keys` was written about.
KNOWN_MODEL_KEYS = {MODEL_VERSION_KEY, MODEL_KLIMA_ID, MODEL_KLIMA_NAME}


def baseline_model_keys(
    match_baseline: Any, baseline: dict[str, Any], stem: str
) -> dict[str, dict[str, Any]] | None:
    """The model-level keys the OFFLINE reader recorded, or `None` when this model has no baseline.

    ⚠ `None` and `{}` are different answers and conflating them is how a check stops being able to
    fail: the 1.0.30 sample has **no Phase-0 baseline at all**, so "the capture named every key the
    baseline records" would be vacuously true for it.

    ⚠ The offline reader sees the file's historical union, so this is an upper bound: a key here and
    not in the capture may be history. It is still the right comparison, because the failure being
    guarded against is a capture that is *thin* and does not say so.
    """
    found = match_baseline(stem, baseline)
    return dict(found[1].get("model_keys") or {}) if found else None


def baseline_blob_keys(keys: dict[str, dict[str, Any]] | None) -> list[str]:
    """Which baseline model keys could be Marshal tables — the STRING-typed ones, minus the scalars.

    ⚠ Derived from the baseline's own recorded value types rather than an ignore-list. `Dashboard`
    is a **bool** and therefore cannot be a `BAh…` blob; the contract already says so
    ("non-blob model keys — `Dashboard`, `designPH_version`, `klima_ID`, … — are not tables at
    all"), and the first version of this check flagged it as a silent partial capture on the 2.4.0
    BETA model. A check that fires on healthy data is testing the wrong property.
    """
    if not keys:
        return []
    return sorted(
        name
        for name, record in keys.items()
        if name not in KNOWN_MODEL_KEYS and "str" in (record.get("types") or [])
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    match_baseline = load_module(
        args.repo_root / "poc" / "tools" / "check_extraction.py", "check_extraction"
    ).match_baseline
    models: dict[str, Any] = {}
    problems_total = 0

    for name, why in UNDER_TEST.items():
        skp = args.corpus / name
        # ⚠ A model the gate refuses is quarantined by H2, so look in both places — and say which.
        capture_path = args.captures / f"{skp.stem}.extraction.json"
        quarantined = args.captures / "quarantine" / f"{skp.stem}.extraction.json"
        if not capture_path.exists() and quarantined.exists():
            capture_path = quarantined
        if not capture_path.exists():
            print(f"  SKIP {name} — no capture; run b2_h2_emission.py first")
            continue
        document = json.loads(capture_path.read_text(encoding="utf-8"))

        # ★ The reader's OWN behaviour, through its CLI, into a path that must not appear.
        refusal_target = args.out.parent / f"{skp.stem}.MUST-NOT-EXIST.json"
        refusal_target.unlink(missing_ok=True)
        run = subprocess.run(
            [
                sys.executable, str(Path(__file__).parent / "collector.py"),
                "--model", str(skp.resolve()), "--out", str(refusal_target.resolve()),
            ],
            capture_output=True, text=True,
        )
        reader = {
            "exit_code": run.returncode,
            "wrote_a_capture": refusal_target.exists(),
            "said": run.stdout.strip().splitlines()[:6],
        }
        refusal_target.unlink(missing_ok=True)

        stamps = document["model"]["designph_versions"]
        found = gate.evidence(document)
        pre = gate.version(stamps, None)
        post = gate.version(stamps, found)

        problems: list[str] = []
        offline_keys = baseline_model_keys(match_baseline, baseline, skp.stem)
        blob_keys = baseline_blob_keys(offline_keys)
        unread = [k for k in blob_keys if k not in document["counts"]["tables_found"]]

        if post.refused:
            # ⚠ A refusal must NAME what it saw. A refusal that does not is the same failure as a
            # silent partial read, one step earlier.
            if not all(str(stamp) in (post.reason or "") for stamp in stamps):
                problems.append("the refusal does not name the version stamp it saw")
            if reader["wrote_a_capture"]:
                problems.append("⛔ the reader wrote a capture for a model the gate refuses")
            if reader["exit_code"] == 0:
                problems.append("the reader exited 0 on a refusal — a caller could not tell")
        else:
            # Allowed → the capture must not be quietly thin.
            if unread:
                problems.append(
                    f"the offline baseline records the blob key(s) {unread} and the capture names "
                    "none of them"
                )
            if not found:
                problems.append("allowed with no designPH evidence at all — that should be a refusal")
            if offline_keys is None:
                problems.append(
                    "allowed, and there is no offline baseline to check the capture's completeness "
                    "against — the read cannot be shown to be complete"
                )
        models[name] = {
            "why": why,
            "stamps": stamps,
            "major": [gate.major(stamp) for stamp in stamps],
            "pre_walk": {"allow": pre.allow, "reason": pre.reason, "note": pre.note},
            "post_walk": {"allow": post.allow, "reason": post.reason, "note": post.note},
            "evidence": found,
            "reader_cli": reader,
            "capture_read_from": str(capture_path.parent.name),
            "counts": document["counts"],
            "offline_model_keys": sorted(offline_keys) if offline_keys is not None else None,
            "offline_blob_keys": blob_keys,
            "blob_keys_not_named_by_the_capture": unread,
            "problems": problems,
        }
        problems_total += len(problems)

        verdict = "REFUSED" if post.refused else "ALLOWED"
        print(
            f"{'✅' if not problems else '❌'} {name}: {stamps} → {verdict} "
            f"(the reader exited {reader['exit_code']} and wrote "
            f"{'a capture' if reader['wrote_a_capture'] else 'nothing'})"
        )
        print(f"     {why}")
        if post.reason:
            print(f"     reason: {post.reason.splitlines()[0]} …")
            for line in post.reason.splitlines()[1:4]:
                if line.strip():
                    print(f"             {line.strip()}")
        if post.note:
            print(f"     note: {post.note}")
        if not post.refused:
            print(
                f"     read: {document['counts']['faces_classified']} classified faces · "
                f"{document['counts']['edges_tagged']} edges · "
                f"{document['counts']['windows_found']} windows · "
                f"tables named {document['counts']['tables_found']}"
            )
            print(f"     evidence: {', '.join(found) or 'none'}")
        for problem in problems:
            print(f"     ⚠ {problem}")

    passed = len(models) == len(UNDER_TEST) and not problems_total
    write_result(
        args.out, {"gate": "poc/ext/dph_plus_poc/gate.rb, ported as gate.py", "models": models}
    )
    refusals = sum(1 for row in models.values() if not row["post_walk"]["allow"])
    print(
        f"\nVERDICT H9: {'PASS' if passed else 'FAIL'} — {len(models)} unknown-version models "
        f"tested, {refusals} refused by name and {len(models) - refusals} read with every "
        f"model-level key accounted for; {problems_total} silent partial capture(s) → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
