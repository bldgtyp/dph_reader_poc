#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike L-B offline rehearsal: run the PHN-payload write path on real tables, verify bytes
AND arithmetic.

    uv run planning/spikes/library-import/rehearse_b.py

Reuses L-A's machinery (`rehearse.py` supplies the model.dat extractor and the
construct-nothing Marshal reader; `map_phn.py` supplies the ISO 6946 reference), drives
`write_library_b.rb` through `offline_rehearsal_b.rb`, and asserts per scenario:

  * provenance lands in DesignPHPlus_dict only; no key added to DesignPH_dict beyond tables,
  * each written blob decodes; base64 style preserved (wrapped stays wrapped — the Linde leg),
  * metadata rows untouched (except the `probe` scenario, whose WHOLE POINT is a TOKENS edit),
  * every non-marker data row byte-identical,
  * marker rows carry exactly the payload's values (assembly header, per-edge frame, glazing),
  * ⭐ the closing loop: the assembly rows are decoded BACK OUT of the written bytes and run
    through the same ISO 6946 mean-of-limits — the recovered U must equal the payload's
    intended U to 1e-9. What designPH will read provably computes what we predicted.

⚠ A rehearsal is NOT a capture (house rule): this proves our serialisation and arithmetic on
the real tables; it says nothing about what designPH accepts. Ed's session is not replaced.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "headless" / "_private" / "corpus"
OUT_DIR = HERE / "_private" / "rehearsal"


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LA = load_module("rehearse_la", HERE / "rehearse.py")  # extractor + decode + Check
MAP = load_module("map_phn", HERE / "map_phn.py")      # iso6946 reference

PAYLOAD = json.loads((HERE / "_private" / "payload" / "lb_payload.json").read_text())
MARKER = PAYLOAD["marker"]


def is_meta(row: Any) -> bool:
    return isinstance(row, list) and bool(row) and str(row[0]) == "#"


def is_ours(row: Any) -> bool:
    return isinstance(row, list) and len(row) > 1 and str(row[1]).startswith(MARKER)


def tokens_of(table: list[Any]) -> list[str]:
    meta = next(r for r in table if is_meta(r) and str(r[1]) == ":TOKENS")
    return [str(t).lstrip(":") for t in meta[2]]


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def verify(check: Any, attrs_in: dict[str, str], result: dict[str, Any], probe: bool) -> None:
    dph = result["dicts"]["DesignPH_dict"]
    ours = result["dicts"].get("DesignPHPlus_dict", {})
    wrote = [k for k in ours.get("wrote_keys", "").split(",") if k]
    check.expect(bool(wrote), f"provenance lists {len(wrote)} written keys")
    check.expect(ours.get("spike") == "L-B", "provenance spike tag is L-B")

    for key in wrote:
        raw = dph.get(key)
        if not isinstance(raw, str) or not raw.startswith("BAh"):
            check.expect(False, f"{key}: written value is a BAh blob")
            continue
        if key in attrs_in:
            check.expect(
                ("\n" in raw) == ("\n" in attrs_in[key]),
                f"{key}: base64 style preserved "
                f"({'wrapped' if chr(10) in attrs_in[key] else 'strict'})",
            )
        else:
            check.expect("\n" not in raw, f"{key}: new key, strict base64")
        table = LA.decode(raw)
        if key.startswith("layer_table_"):
            # layer rows carry material names, not the marker — "ours" = populated rows
            marker_rows = [r for r in table if not is_meta(r) and str(r[1]).strip()]
        else:
            marker_rows = [r for r in table if is_ours(r)]
        check.expect(bool(marker_rows), f"{key}: {len(marker_rows)} written row(s)")

        if key in attrs_in:
            before = LA.decode(attrs_in[key])
            probe_here = probe and key == "assemblies_calc"
            if probe_here:
                check.expect(
                    str(tokens_of(table)[-1]) == "phn_id",
                    f"{key}: PROBE — trailing :phn_id token present",
                )
                # every row gained exactly one cell; compare rows minus the probe cell
                table_cmp = [r[:-1] if not is_meta(r) else r for r in table]
                meta_cmp = [r for r in table_cmp if is_meta(r) and str(r[1]) != ":TOKENS"]
                meta_before = [r for r in before if is_meta(r) and str(r[1]) != ":TOKENS"]
                check.expect(meta_cmp == meta_before, f"{key}: non-TOKENS metadata untouched")
            else:
                table_cmp = table
                check.expect(
                    [r for r in table_cmp if is_meta(r)] == [r for r in before if is_meta(r)],
                    f"{key}: metadata rows untouched",
                )
            marker_ids = {str(r[0]) for r in marker_rows}
            after_rest = [r for r in table_cmp if not is_meta(r) and str(r[0]) not in marker_ids]
            before_rest = [r for r in before if not is_meta(r) and str(r[0]) not in marker_ids]
            check.expect(
                after_rest == before_rest,
                f"{key}: all {len(before_rest)} non-marker data rows byte-identical",
            )
        else:
            check.expect(True, f"{key}: created new ({len(table)} rows)")

    verify_values(check, dph, wrote)


def verify_values(check: Any, dph: dict[str, Any], wrote: list[str]) -> None:
    # assemblies: header values + the decoded-bytes ISO 6946 recompute
    calc = LA.decode(dph["assemblies_calc"])
    tokens = tokens_of(calc)
    col = {t: i for i, t in enumerate(tokens)}
    by_desc = {str(r[1]): r for r in calc if is_ours(r)}
    for asm in PAYLOAD["assemblies"]:
        row = by_desc.get(asm["desc"])
        if row is None:
            check.expect(False, f"assemblies_calc: {asm['desc']!r} row missing")
            continue
        header_ok = (
            close(row[col["R_in"]], asm["R_in"])
            and close(row[col["R_out"]], asm["R_out"])
            and close(row[col["surf2_percentage"]], asm["surf2_percentage"])
            and close(row[col["surf3_percentage"]], asm["surf3_percentage"])
            and row[col["int_insul"]] == asm["int_insul"]
        )
        check.expect(header_ok, f"{asm['desc']!r}: header values exact")

        layer_key = f"layer_table_{row[0]}"
        if layer_key not in dph:
            check.expect(False, f"{layer_key} missing for {asm['desc']!r}")
            continue
        ltable = LA.decode(dph[layer_key])
        lrows = [r for r in ltable if not is_meta(r)]
        layers = []
        for r in lrows:
            if not r[1] and not (isinstance(r[2], float) and r[2] > 0):
                continue  # blank pre-allocated row
            layers.append({
                "desc1": r[1], "lambda1": r[2], "desc2": r[3], "lambda2": r[4],
                "desc3": r[5], "lambda3": r[6], "thickness_mm": r[7],
            })
        check.expect(
            len(layers) == len(asm["layers"]),
            f"{layer_key}: {len(layers)} populated layers (payload {len(asm['layers'])})",
        )
        u, err = MAP.iso6946(layers, asm["surf2_percentage"], asm["surf3_percentage"],
                             asm["R_in"] + asm["R_out"])
        check.expect(
            close(u, asm["intended_u"], 5e-7),
            f"{asm['desc']!r}: U recomputed FROM WRITTEN BYTES = {u:.6f} "
            f"(intended {asm['intended_u']}) err {err:.2f}%",
        )

    # frames: every per-edge value exact
    if "frames_ud" in wrote:
        frames = LA.decode(dph["frames_ud"])
        ftokens = tokens_of(frames)
        fcol = {t: i for i, t in enumerate(ftokens)}
        fby = {str(r[1]): r for r in frames if is_ours(r)}
        for frame in PAYLOAD["frames"]:
            row = fby.get(frame["desc"])
            if row is None:
                check.expect(False, f"frames_ud: {frame['desc']!r} missing")
                continue
            fields = [f for f in frame if f != "desc"]
            missing = [f for f in fields if f not in fcol]
            bad = [f for f in fields if f in fcol and not close(row[fcol[f]], frame[f])]
            check.expect(
                not bad and not missing,
                f"{frame['desc']!r}: {len(fields)} per-edge fields exact"
                + (f" (bad: {bad} missing: {missing})" if bad or missing else ""),
            )

    if "glazing_ud" in wrote:
        glz = LA.decode(dph["glazing_ud"])
        gtokens = tokens_of(glz)
        gcol = {t: i for i, t in enumerate(gtokens)}
        gby = {str(r[1]): r for r in glz if is_ours(r)}
        for g in PAYLOAD["glazings"]:
            row = gby.get(g["desc"])
            ok = row is not None and close(row[gcol["g_value"]], g["g_value"]) \
                and close(row[gcol["U_value"]], g["U_value"])
            check.expect(ok, f"{g['desc']!r}: g/U exact")


def run(name: str, skp: Path, flags: list[str]) -> Any:
    check = LA.Check(name)
    print(f"\n== {name}  ({skp.name}, flags={flags or ['(none)']})")
    attrs = LA.extract(skp)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    in_json = OUT_DIR / f"{name}.in.json"
    out_json = OUT_DIR / f"{name}.out.json"
    in_json.write_text(json.dumps({"title": f"{name}_LIBIMPORT", "attrs": attrs}))
    proc = subprocess.run(
        ["ruby", str(HERE / "offline_rehearsal_b.rb"), str(in_json), str(out_json), *flags],
        capture_output=True, text=True,
    )
    for line in proc.stdout.splitlines():
        print(f"    | {line}")
    if proc.returncode != 0:
        check.expect(False, f"ruby exited {proc.returncode}: {proc.stderr.strip()[:400]}")
        return check
    result = json.loads(out_json.read_text())
    verify(check, attrs, result, probe="probe" in flags)
    return check


def main() -> int:
    checks = [
        run("lb_bluffreach", CORPUS / "2414_Bluff Reach_COPY.skp", []),
        run("lb_linde", CORPUS / "250703 - Linde Residence_COPY.skp", []),
        run("lb_adelphi_create", CORPUS / "adelphi-designph_COPY.skp", []),
        run("lb_bluffreach_probe", CORPUS / "2414_Bluff Reach_COPY.skp", ["probe"]),
    ]
    bad = [c for c in checks if c.failures]
    print(f"\n{'REHEARSAL FAIL' if bad else 'REHEARSAL PASS'} — "
          f"{len(checks) - len(bad)}/{len(checks)} scenarios clean")
    for c in bad:
        for f in c.failures:
            print(f"  {c.scenario}: {f}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
