# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H5: the unchanged translator, to the POC's own numbers.**

Feeds every headless capture to `poc/py/dph_translator` and grades the result against the POC's
acceptance table. **Nothing in the translator is modified.** If a headless capture makes it
misbehave, that is a *finding about the capture*, recorded — never a patch applied (HEADLESS-B §7).

Two gradings, and they answer different questions:

**1. The acceptance table, on the five models the POC measured.** 545/545 classified faces,
239/239 windows, 99/99 thermal bridges, and TFA 368.5 / 1491.9 / 448.2 m² on the three models that
carry group-1 faces. These numbers are the POC's product; reproducing them from a capture no
SketchUp was involved in is what H5 is for.

**2. Live vs headless, report against report.** The stronger claim, and the cheaper one: the same
translator run twice, once on each capture of the same model, must produce the same summary. That
catches a difference the acceptance totals would round away.

▶ **And then all 16 staged models** (HEADLESS-B §2.2), which is coverage the POC never had:
⭐ **`2536 Holmes`'s 42 named thermal-bridge edges** — the only second bridge model in existence,
and "confirmed on one model is confirmed on nothing" is this repo's most-repeated lesson;
⭐ the 146 MB `2618 Lavoie`; ⭐ the designPH **1.0.30** generation. Those eleven have no live
capture, so they are **recorded, not graded** — they can prove the translator does not fall over,
which is a different claim from proving it is right.

⚠ Runs on the POC's own interpreter (`poc/py/.venv`), which holds exactly the eight vendored
wheels. `make venv` builds it.

    uv run b5_h5_translate.py --captures _private/out/captures --fixtures _private/fixtures \\
        --out-dir _private/out/translated --out _private/out/b5_translate.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

#: The POC's acceptance table (`planning/POC/RESULTS/POC-4_results.md`), per model. Read as
#: "the translator must still say exactly this". ⚠ Restated here rather than derived because it is
#: the *prior* result being reproduced — a number computed from the input under test could not
#: disagree with it.
#: ⚠ Which model carries which TFA is read from the POC's results, not inferred from a run:
#: Adelphi 368.5 (`POC-4_ed-runbook.md`), Bluff Reach 1491.9 (same file), Wellington 448.2 —
#: the third of `POC-3_results.md`'s "368.5 / 1491.9 / 448.2". Linde and `250708` derive **none**,
#: which is a result and not a gap: only group-1 faces make TFA and they carry none.
ACCEPTANCE: dict[str, dict[str, Any]] = {
    "adelphi-designph_COPY": {"faces": 82, "apertures": 46, "bridges": 0, "tfa_m2": 368.5},
    "2414_Bluff Reach_COPY": {"faces": 194, "apertures": 40, "bridges": 99, "tfa_m2": 1491.9},
    "2523 Wellington_COPY": {"faces": 103, "apertures": 57, "bridges": 0, "tfa_m2": 448.2},
    "250703 - Linde Residence_COPY": {"faces": 74, "apertures": 47, "bridges": 0, "tfa_m2": 0.0},
    "250708_COPY": {"faces": 92, "apertures": 49, "bridges": 0, "tfa_m2": 0.0},
}

#: TFA is quoted to one decimal in the results docs; anything inside this is the same number.
TFA_TOLERANCE_M2 = 0.05

#: Summary keys that legitimately differ between two runs. The first two are H4's named buckets one
#: layer up; `hbjson_bytes` is a different thing entirely and belongs to H6:
#:
#: ⚠ **`hbjson_bytes` is not an equality test and cannot be made into one.** honeybee-energy orders
#: four of its lists out of a `set`, so two runs of the same translator on the same input emit the
#: same constructions in a different sequence — and because their names are different *lengths*
#: (`Roof_02` vs `Wall_01B`), the byte count moves too. Measured on Adelphi: 570 differences, of
#: which 371 are `uuid4` churn on `properties.ph.*.identifier`/`display_name` and the rest are that
#: reordering. Both are documented, measured-harmless per-export effects
#: (`00_Context/HONEYBEE_STACK.md` §4), and canonical equivalence is H6's job.
DEVICE_FIELDS = {"generated_by", "model", "hbjson_bytes"}

RUNNER = """
import json, sys
from pathlib import Path
from dph_translator.entry import translate_json

payload = Path(sys.argv[1]).read_text(encoding="utf-8")
result = json.loads(translate_json(payload))
Path(sys.argv[2]).write_text(json.dumps(result), encoding="utf-8")
print(json.dumps({"verdict": result["verdict"], "summary": result.get("report", {}).get("summary", {}),
                  "hbjson_bytes": len(result.get("hbjson", ""))}))
"""


def translate(python: Path, capture: Path, out: Path, runner: Path) -> dict[str, Any]:
    """Run the untouched translator in the POC's own interpreter. A failure is data, not a crash."""
    out.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(
        [str(python), str(runner), str(capture), str(out)], capture_output=True, text=True
    )
    if run.returncode != 0:
        return {"error": run.stderr.strip()[-2000:]}
    return json.loads(run.stdout.strip().splitlines()[-1])


def grade(name: str, result: dict[str, Any]) -> list[str]:
    """The acceptance table, per model. Returns the failures."""
    expected = ACCEPTANCE.get(name)
    if expected is None or "error" in result:
        return [f"translation failed: {result.get('error', '?')}"] if "error" in result else []
    summary = result["summary"]
    problems: list[str] = []
    for label, key, want in (
        ("classified faces", "faces", expected["faces"]),
        ("apertures", "apertures", expected["apertures"]),
        ("thermal bridges", "thermal_bridges", expected["bridges"]),
    ):
        got = summary.get(key, {})
        if got.get("in") != want or got.get("translated") != want:
            problems.append(
                f"{label}: {got.get('translated')}/{got.get('in')} translated, expected {want}/{want}"
            )
    if expected["tfa_m2"] is not None:
        covered = summary.get("tfa_m2_covered")
        if covered is None or abs(covered - expected["tfa_m2"]) > TFA_TOLERANCE_M2:
            problems.append(f"TFA: {covered} m², expected {expected['tfa_m2']} m²")
    return problems


def normalise(summary: dict[str, Any]) -> dict[str, Any]:
    """Drop the per-export churn, and **only** that.

    honeybee gives a freshly constructed object with no identity of its own a `uuid4`, so the
    default site honeybee mints when designPH's climate id does not resolve carries a different
    `display_name` on every run of the same input. That is churn, not a difference between captures.

    ⚠ Nothing else is normalised. `klima_id`, `klima_standort` and `resolved` all stay — those are
    the fields that would say the two readers disagreed about the climate.
    """
    out = dict(summary)
    site = out.get("site")
    if isinstance(site, dict) and isinstance(site.get("hb_default_site"), dict):
        default = dict(site["hb_default_site"])
        default.pop("display_name", None)
        out["site"] = {**site, "hb_default_site": default}
    return out


def compare_summaries(headless: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """The same translator, two captures of one model. Device fields and known churn excepted."""
    mine, theirs = normalise(headless), normalise(live)
    differences: list[str] = []
    for key in sorted(set(mine) | set(theirs)):
        if key in DEVICE_FIELDS:
            continue
        if mine.get(key) != theirs.get(key):
            differences.append(f"summary.{key}: headless {mine.get(key)!r} vs live {theirs.get(key)!r}")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True, help="where translations are written")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()

    python = args.repo_root / "poc" / "py" / ".venv" / "bin" / "python"
    if not python.exists():
        print(f"VERDICT H5: FAIL — the POC interpreter is missing at {python}; run `cd poc && make venv`")
        return 1

    runner = args.out_dir / "_run_translator.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(RUNNER, encoding="utf-8")

    models: dict[str, Any] = {}
    for capture in sorted(args.captures.glob("*.extraction.json")):
        name = capture.name.removesuffix(".extraction.json")
        result = translate(python, capture, args.out_dir / f"{name}.headless.hbjson.json", runner)
        row: dict[str, Any] = {
            "verdict": result.get("verdict", {}).get("headline"),
            "hbjson_bytes": result.get("hbjson_bytes"),
            "summary": result.get("summary", {}),
            "acceptance_problems": grade(name, result),
            "error": result.get("error"),
        }

        live_capture = args.fixtures / f"{name}.extraction.json"
        if live_capture.exists():
            live = translate(python, live_capture, args.out_dir / f"{name}.live.hbjson.json", runner)
            # ⚠ H6 compares two OUTPUTS, so an INPUT difference has to be removed from the input —
            # not scrubbed out of the output afterwards. `model.file_name` is the one field where
            # the two readers deliberately disagree (H4's named bucket: the headless reader uses the
            # file it opened, the live one inherited `Sketchup::Model#path`), and honeybee threads
            # it into the model, the room and the building segment, as a substring of derived
            # identifiers. Chasing those in the output is how a canonicaliser grows until it can no
            # longer fail. So one field is aligned here, in a THIRD capture written beside the other
            # two, and the alignment is recorded per model.
            aligned_name = json.loads(live_capture.read_text(encoding="utf-8"))["model"]["file_name"]
            aligned_capture = args.out_dir / f"{name}.headless-aligned.extraction.json"
            document = json.loads(capture.read_text(encoding="utf-8"))
            row["name_alignment"] = {
                "headless": document["model"]["file_name"],
                "live": aligned_name,
                "aligned": document["model"]["file_name"] != aligned_name,
            }
            document["model"]["file_name"] = aligned_name
            aligned_capture.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
            translate(
                python, aligned_capture, args.out_dir / f"{name}.headless-aligned.hbjson.json", runner
            )
            row["live_verdict"] = live.get("verdict", {}).get("headline")
            row["summary_differences"] = compare_summaries(
                result.get("summary", {}), live.get("summary", {})
            )
            if row["verdict"] != row["live_verdict"]:
                row["acceptance_problems"].append(
                    f"verdict differs: headless {row['verdict']!r} vs live {row['live_verdict']!r}"
                )
            row["acceptance_problems"].extend(row["summary_differences"])
        models[name] = row

        graded = name in ACCEPTANCE
        flag = "❌" if row["acceptance_problems"] or row["error"] else ("✅" if graded else "⚪")
        summary = row["summary"]
        print(
            f"{flag} {name}: {row['verdict']} · faces "
            f"{summary.get('faces', {}).get('translated')}/{summary.get('faces', {}).get('in')} · "
            f"apertures {summary.get('apertures', {}).get('translated')}/"
            f"{summary.get('apertures', {}).get('in')} · bridges "
            f"{summary.get('thermal_bridges', {}).get('translated')}/"
            f"{summary.get('thermal_bridges', {}).get('in')} · TFA "
            f"{summary.get('tfa_m2_covered')} m²"
        )
        for problem in row["acceptance_problems"][:6]:
            print(f"     ⚠ {problem}")
        if row["error"]:
            print(f"     ⚠ {row['error'].splitlines()[-1] if row['error'] else ''}")

    # -- the corpus totals the POC quotes ----------------------------------
    def total(key: str) -> int:
        return sum(
            models[n]["summary"].get(key, {}).get("translated", 0)
            for n in ACCEPTANCE
            if n in models
        )

    totals = {
        "faces": (total("faces"), sum(v["faces"] for v in ACCEPTANCE.values())),
        "apertures": (total("apertures"), sum(v["apertures"] for v in ACCEPTANCE.values())),
        "thermal_bridges": (total("thermal_bridges"), sum(v["bridges"] for v in ACCEPTANCE.values())),
    }
    graded_failures = sorted(
        n for n in ACCEPTANCE if n in models and (models[n]["acceptance_problems"] or models[n]["error"])
    )
    crashed = sorted(n for n, row in models.items() if row["error"])
    passed = (
        all(n in models for n in ACCEPTANCE)
        and not graded_failures
        and not crashed
        and all(got == want for got, want in totals.values())
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "provenance": "third-party SDK re-host — feasibility-only evidence",
                "acceptance": ACCEPTANCE,
                "corpus_totals": {k: {"got": g, "expected": w} for k, (g, w) in totals.items()},
                "models": models,
            },
            indent=1,
        )
    )
    print(
        f"\nVERDICT H5: {'PASS' if passed else 'FAIL'} — corpus totals "
        f"{totals['faces'][0]}/{totals['faces'][1]} faces · "
        f"{totals['apertures'][0]}/{totals['apertures'][1]} windows · "
        f"{totals['thermal_bridges'][0]}/{totals['thermal_bridges'][1]} bridges on the five graded "
        f"models; {len(models)} captures translated, {len(crashed)} failed → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
