# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — **H2: contract-v2 emission**, on all 16 staged models.

Does the headless collector emit the frozen contract verbatim — same keys, same shapes, same units,
`libraries` hoisted to model level — with no schema drift, nothing leaking that must not leave, and
the size rule active?

▶ **Sixteen models, not five** (HEADLESS-B §2.2). H2 compares a capture against the *contract*, not
against a live capture, so it does not need ground truth — and running the whole staged corpus buys
coverage the POC never had: **`2536 Holmes`'s 42 named thermal-bridge edges** (the only second
bridge model in existence), the **146 MB** `2618 Lavoie` scale probe, and the **designPH 1.0.30**
generation, which is structurally different from anything the contract was written against.

What this gate asserts, and why each one is a check rather than an intention:

1. ⛔ **The reader cannot save.** `SUEntityGetAttributeDictionary` is a get-or-CREATE and it is the
   only complete way to test for a dictionary, so reading *mutates the in-memory model*. Hard rule 2
   survives only because nothing ever writes the file back — and §2.2 asks for that to be
   **structural**: the reader must be *incapable* of saving, not merely not save. So this asserts
   that resolving a writer raises, and that the binding's declared symbol set contains none.
2. **The document is contract-v2 shaped**: exact top-level keys, exact per-record field sets,
   `contract_version == 2`, and the census invariant
   `len(unclassified.tagged_faces) + len(faces) == counts.faces_tagged`.
3. **Nothing that must not leave, leaves.** `tracker_data` is listed in `counts.tables_found` and
   never shipped; no embedded filesystem path appears anywhere in the payload. Asserted by scanning
   the serialised document, not by trusting the writer.
4. **The size rule is live.** Anything over 1 MB is logged with a named cause — the rule that
   earned its keep on the very first capture it applied to and produced contract v2.

⚠ Third-party SDK re-host; feasibility-only evidence. See `sdk.py`.

    uv run b2_h2_emission.py --corpus _private/corpus --out-dir _private/out/captures \\
        --out _private/out/b2_emission.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import gate
from a7_capability_probe import WRITE_SYMBOLS
from collector import (
    CONTRACT_VERSION,
    RECORD_SECTIONS,
    SDK,
    SHIP_TABLE_PREFIXES,
    SHIP_TABLES,
    Tables,
    capture,
    load_ruby_marshal,
    write_capture,
)
from harness import write_result

#: Contract §1. Exact — an extra key is drift just as surely as a missing one.
ENVELOPE_KEYS = {
    "contract_version", "generated_by", "model", "counts",
    "faces", "edges", "windows", "libraries", "tables", "unclassified",
}
MODEL_KEYS = {"file_name", "designph_versions", "klima_id", "klima_standort", "units_note"}
COUNTS_KEYS = {
    "faces_walked", "faces_tagged", "faces_classified",
    "edges_tagged", "windows_found", "tables_found",
}
FACE_KEYS = {
    "id", "entity_id", "area_group", "temp_zone", "assembly_ref", "desc_name", "tfa_rf",
    "outer_loop", "inner_loops", "area_m2", "both_generations",
}
EDGE_KEYS = {
    "id", "entity_id", "area_group", "connection_ref", "desc_name",
    "length_m", "start", "end", "both_generations",
}
WINDOW_KEYS = {
    "id", "entity_id", "designph_name", "definition_name", "instance_name",
    "dynamic_attributes", "transformation", "panel_outer_loop",
    "host_face_id", "host_resolution", "host_has_inner_loops",
}
UNCLASSIFIED_FACE_KEYS = {"id", "area_group", "tag"}
LIBRARY_KEYS = {"frame_types", "glazing_types"}

#: Model-level blobs that are **named** in `counts.tables_found` and never shipped (contract §5).
#: `tracker_data` is designPH's own telemetry and is the one that must never leave the machine.
NEVER_SHIPPED = ("tracker_data", "tfa_calc", "tfa_calc_ud", "frames_ud", "glazing_ud")

#: ⚠ `WRITE_SYMBOLS` is imported from `a7_capability_probe`, not restated. This gate's whole claim
#: is *coverage of the write surface*, so a hand-copied list that fell behind the probe's would keep
#: printing a green never-save verdict over a shrunken denominator — a check that quietly stops
#: being able to fail, in the block carrying the phase's ⛔ invariant.

#: An embedded filesystem path is client data and a determinism hazard at once — the same value
#: that made `Sketchup::Model#path` untrustworthy. Scanned for in the serialised payload.
PATH_PATTERNS = (
    re.compile(r"/Users/"),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"/home/"),
    re.compile(r"\\\\\\\\[A-Za-z0-9_-]+\\\\"),
)

LOG_PAYLOAD_BYTES = 1_000_000


def check_shape(document: dict[str, Any]) -> list[str]:
    """Every contract-v2 shape rule, as a list of failures. Empty is the pass."""
    problems: list[str] = []

    def keys(where: str, got: Any, expected: set[str]) -> None:
        if not isinstance(got, dict):
            problems.append(f"{where}: not an object ({type(got).__name__})")
            return
        if set(got) != expected:
            missing = sorted(expected - set(got))
            extra = sorted(set(got) - expected)
            problems.append(f"{where}: missing {missing}, unexpected {extra}")

    keys("envelope", document, ENVELOPE_KEYS)
    if document.get("contract_version") != CONTRACT_VERSION:
        problems.append(f"contract_version is {document.get('contract_version')!r}, not {CONTRACT_VERSION}")
    if "STUB" in str(document.get("generated_by", "")):
        problems.append("generated_by claims STUB — this is not a real capture")

    keys("model", document.get("model"), MODEL_KEYS)
    keys("counts", document.get("counts"), COUNTS_KEYS)
    keys("libraries", document.get("libraries"), LIBRARY_KEYS)

    for section, expected in zip(
        RECORD_SECTIONS, (FACE_KEYS, EDGE_KEYS, WINDOW_KEYS), strict=True
    ):
        records = document.get(section)
        if not isinstance(records, list):
            problems.append(f"{section}: not an array")
            continue
        odd = {frozenset(r) for r in records if isinstance(r, dict) and set(r) != expected}
        # ⚠ `sorted`, not set order: which three drifted shapes get reported must not vary between
        # runs of a gate whose sibling exists to assert determinism.
        for shape in sorted(odd, key=sorted)[:3]:
            problems.append(
                f"{section}: a record is missing {sorted(expected - shape)} / has extra "
                f"{sorted(set(shape) - expected)}"
            )

    unclassified = document.get("unclassified", {})
    if set(unclassified) != {"tagged_faces", "untagged_by_tag"}:
        problems.append(f"unclassified: keys are {sorted(unclassified)}")
    for record in unclassified.get("tagged_faces", []):
        if set(record) != UNCLASSIFIED_FACE_KEYS:
            # One report names the drift; 2392 copies of it would not add anything.
            problems.append(f"unclassified.tagged_faces: keys are {sorted(record)}")
            break

    # Contract §6.1's invariant. It is the one thing that proves the report can NAME every tagged
    # entity the translation omits, which is what hard rule 4 asks for.
    counts = document.get("counts", {})
    accounted = len(document.get("faces", [])) + len(unclassified.get("tagged_faces", []))
    if accounted != counts.get("faces_tagged"):
        problems.append(
            f"census: faces {len(document.get('faces', []))} + tagged-unclassified "
            f"{len(unclassified.get('tagged_faces', []))} = {accounted}, but faces_tagged is "
            f"{counts.get('faces_tagged')}"
        )

    # Contract §5: a table absent from the model is OMITTED, never null and never {}.
    for name, table in (document.get("tables") or {}).items():
        if not (name in SHIP_TABLES or name.startswith(SHIP_TABLE_PREFIXES)):
            problems.append(f"tables: {name} is shipped but is not on the contract's ship list")
        if table is None or table == {}:
            problems.append(f"tables.{name}: empty — absence must be omission, not a null")
    return problems


def check_leakage(document: dict[str, Any], payload: str) -> list[str]:
    """Nothing that must not leave, leaves. Asserted on the serialised bytes, not on intent."""
    problems: list[str] = []
    for name in NEVER_SHIPPED:
        if name in (document.get("tables") or {}):
            problems.append(f"{name} is SHIPPED — it may be named in tables_found and nothing more")
    for pattern in PATH_PATTERNS:
        found = pattern.search(payload)
        if found:
            problems.append(f"an embedded filesystem path appears in the payload: {found.group(0)!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True, help="where the captures are written")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()

    sdk = SDK(read_only=True)

    # -- 1. the structural never-save property -----------------------------
    # Two facts, not four: which writers the binary actually exports, and which of those this handle
    # will hand back. `refused` is the complement of `resolved`, and "declared by the binding" is the
    # same property from the other side (`_ReadOnlyLib` resolves a name iff it is in `declared`), so
    # they were four names for two measurements in the block carrying the phase's ⛔ invariant.
    exported = sorted(set(WRITE_SYMBOLS) - set(sdk.missing(list(WRITE_SYMBOLS))))
    resolved = []
    for symbol in exported:
        try:
            getattr(sdk.lib, symbol)
            resolved.append(symbol)
        except PermissionError:
            pass
    save_proof = {
        "write_symbols_exported_by_the_binary": exported,
        "resolved_by_the_read_only_handle": resolved,
        "declared_by_the_binding": sorted(set(exported) & sdk.declared),
    }
    print(
        f"{'✅' if not resolved else '❌'} never-save: {len(exported)} writers exported by the "
        f"binary, {len(exported) - len(resolved)} refused by the handle, "
        f"{len(save_proof['declared_by_the_binding'])} declared by the binding"
    )

    tables = Tables(load_ruby_marshal(args.repo_root))
    models: dict[str, Any] = {}
    try:
        for path in sorted(args.corpus.glob("*.skp")):
            # ⚠ Read ungated on purpose — H2 grades the READ, over all 16 staged models. But a model
            # the version gate refuses must not land in the directory the later gates glob: H9's
            # headline claim is "on a refusal nothing is emitted", and the phase's own pipeline
            # emitting one would contradict it. Refused captures go to `quarantine/`.
            result = capture(path, sdk, tables, apply_gate=False)
            document, notices, seconds = result.document, result.notices, result.seconds
            assert document is not None  # apply_gate=False never refuses
            refused = gate.version(
                document["model"]["designph_versions"], gate.evidence(document)
            ).refused
            out = (args.out_dir / "quarantine" if refused else args.out_dir) / (
                f"{path.stem}.extraction.json"
            )
            size = write_capture(document, out)
            payload = json.dumps(document, separators=(",", ":"))

            problems = check_shape(document) + check_leakage(document, payload)
            counts = document["counts"]
            sizes = {
                section: len(json.dumps(document[section]))
                for section in (*RECORD_SECTIONS, "libraries", "tables", "unclassified")
            }
            oversize = [f"{k} {v} bytes" for k, v in sizes.items() if v > LOG_PAYLOAD_BYTES]
            models[path.name] = {
                "bytes": size,
                "quarantined_by_the_version_gate": refused,
                "seconds": round(seconds, 2),
                "counts": counts,
                "designph_versions": document["model"]["designph_versions"],
                "problems": problems,
                "notices": notices,
                "over_1mb_sections": oversize,
            }
            flag = "✅" if not problems else "❌"
            print(
                f"{flag} {'⚪ ' if refused else ''}{path.name}: {counts['faces_classified']} classified · "
                f"{counts['edges_tagged']} edges · {counts['windows_found']} windows · "
                f"{len(document['tables'])} tables · {size} bytes · {seconds:.2f} s"
            )
            for problem in problems:
                print(f"     ⚠ {problem}")
            if size > LOG_PAYLOAD_BYTES:
                # The rule that produced contract v2. It logs; it never silently chunks.
                print(f"     ⚠ payload is {size} bytes (>1 MB): {oversize or 'no single section over 1 MB'}")
    finally:
        sdk.terminate()

    write_result(args.out, {"never_save": save_proof, "models": models})

    failures = sum(1 for row in models.values() if row["problems"])
    passed = bool(models) and not failures and not resolved
    print(
        f"\nVERDICT H2: {'PASS' if passed else 'FAIL'} — {len(models)} models emitted contract v2, "
        f"{failures} with shape or leakage problems; the read-only handle refused "
        f"{len(exported) - len(resolved)}/{len(exported)} writers the binary exports → {args.out}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
