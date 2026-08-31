#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike L-A offline rehearsal: run the Ruby write path on real tables, verify every byte.

    uv run planning/spikes/library-import/rehearse.py

For each scenario this: (1) extracts the model-level designPH blobs out of a staged copy's
`model.dat` (read-only, regex route — same as `00_Context/tools/skp_decode_tables.py`);
(2) hands them to `offline_rehearsal.rb`, which stubs `Sketchup` and runs `DPHL.write!` for real;
(3) decodes the result with the construct-nothing Marshal reader and asserts:

      * every written blob is strict base64 (no newlines) and decodes cleanly,
      * metadata rows (:TOKENS included) are untouched,
      * every NON-marker data row survives byte-identical — the untouched-row invariant,
      * the marker rows carry exactly the intended values,
      * the provenance note landed in DesignPHPlus_dict, never in DesignPH_dict.

⚠ A rehearsal is NOT a capture (house rule). This de-risks Ed's session — a script crash or a
mangled table gets caught here, on this machine — but says nothing about what designPH accepts.

Output JSONs land in `_private/rehearsal/` (client library names — gitignored).
"""

from __future__ import annotations

import base64
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
CORPUS = REPO / "planning" / "spikes" / "headless" / "_private" / "corpus"
OUT_DIR = HERE / "_private" / "rehearsal"

MARKER = "ZZ-LIBIMPORT"
# \r\n included: designPH mixes strict and newline-wrapped base64, even within one model
# (Linde: frames_ud/glazing_ud wrapped, assemblies_calc strict).
BLOB = re.compile(rb"BAh[A-Za-z0-9+/=\r\n]{40,}", re.DOTALL)
KNOWN = [
    "assemblies_calc", "assemblies_ud", "connections_ud", "frames_ud",
    "glazing_ud", "ihg_ud", "tfa_calc_ud", "vent_ud",
]

INTENDED_U = 1.0 / (0.13 + 0.04 + 0.0125 / 0.25 + 0.300 / 0.035 + 0.015 / 0.13)


def marshal_reader() -> Any:
    path = REPO / "planning" / "spikes" / "phase1" / "ruby_marshal.py"
    spec = importlib.util.spec_from_file_location("ruby_marshal", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["ruby_marshal"] = module
    spec.loader.exec_module(module)
    return module


RM = marshal_reader()


def jsonable(value: Any) -> Any:
    """Symbols -> ':name' strings so decoded rows compare/print cleanly."""
    if isinstance(value, RM.Symbol):
        return f":{value}"
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    return value


def extract(skp: Path) -> dict[str, str]:
    """Model-level designPH attributes as {key: value-string}.

    ⚠ `model.dat` keeps historical state, so the first blob after a key name can be a stale or
    truncated one (it IS, on Linde's `assemblies_calc`). A rehearsal input only needs *a* valid
    table, so each candidate occurrence is decode-validated and the first clean one wins. Live
    `Sketchup#get_attribute` (Ed's session) has no such ambiguity."""
    dat = zipfile.ZipFile(skp).read("model.dat")
    attrs: dict[str, str] = {}
    keys = list(KNOWN) + sorted(
        {m.group(0).decode() for m in re.finditer(rb"layer_table_\d+ud", dat)}
    )
    for key in keys:
        for m in re.finditer(re.escape(key.encode()), dat):
            found = BLOB.search(dat[m.end(): m.end() + 4_000_000])
            if not found:
                continue
            try:
                RM.loads(base64.b64decode(found.group(0)))
            except Exception:  # noqa: BLE001 — a stale/truncated historical blob; try the next
                continue
            attrs[key] = found.group(0).decode()
            break
    # designPH_version: a plain string value (opcode AD 38 <len> <bytes>) after the key name.
    m = re.search(rb"designPH_version", dat)
    if m:
        window = dat[m.end(): m.end() + 64]
        v = re.search(rb"\xad\x38(....)", window, re.DOTALL)
        if v:
            length = int.from_bytes(v.group(1), "little")
            start = m.end() + v.end()
            attrs["designPH_version"] = dat[start: start + length].decode("ascii", "replace")
    return attrs


def decode(b64: str) -> list[Any]:
    return jsonable(RM.loads(base64.b64decode(b64)))


def is_meta(row: Any) -> bool:
    return isinstance(row, list) and bool(row) and str(row[0]) == "#"


def has_marker(row: Any) -> bool:
    return isinstance(row, list) and any(MARKER in str(v) for v in row)


class Check:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.failures: list[str] = []

    def expect(self, ok: bool, what: str) -> None:
        print(f"    {'ok ' if ok else 'FAIL'} {what}")
        if not ok:
            self.failures.append(what)


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def verify(check: Check, attrs_in: dict[str, str], result: dict[str, Any]) -> None:
    dph = result["dicts"]["DesignPH_dict"]
    ours = result["dicts"].get("DesignPHPlus_dict", {})
    wrote = [k for k in ours.get("wrote_keys", "").split(",") if k]
    check.expect(bool(wrote), f"provenance note lists written keys: {wrote}")
    check.expect(
        not any(MARKER in str(k) for k in dph),
        "no marker-named KEYS added to DesignPH_dict (values only)",
    )

    for key in wrote:
        raw = dph.get(key)
        if not isinstance(raw, str) or not raw.startswith("BAh"):
            check.expect(False, f"{key}: written value is a BAh blob")
            continue
        if key in attrs_in:  # style must match what the key already carried
            check.expect(
                ("\n" in raw) == ("\n" in attrs_in[key]),
                f"{key}: base64 style preserved ({'wrapped' if chr(10) in attrs_in[key] else 'strict'})",
            )
        else:
            check.expect("\n" not in raw, f"{key}: new key, strict base64")
        table = decode(raw)
        marker_rows = [r for r in table if has_marker(r)]
        check.expect(bool(marker_rows), f"{key}: marker row present ({len(marker_rows)})")

        if key in attrs_in:  # modified table: everything we did not touch must be identical
            before = decode(attrs_in[key])
            check.expect(
                [r for r in table if is_meta(r)] == [r for r in before if is_meta(r)],
                f"{key}: metadata rows untouched",
            )
            after_rest = [r for r in table if not is_meta(r) and not has_marker(r)]
            # the write fills a blank row (or inserts one), so the untouched rows of `before`
            # are everything except the row that gained the marker (matched by row id)
            marker_ids = {str(r[0]) for r in marker_rows}
            before_rest = [
                r for r in before if not is_meta(r) and str(r[0]) not in marker_ids
            ]
            check.expect(
                after_rest == before_rest,
                f"{key}: all {len(before_rest)} non-marker data rows byte-identical",
            )
        else:
            check.expect(True, f"{key}: created new ({len(table)} rows)")

    # value spot-checks
    for key in wrote:
        table = decode(dph[key])
        rows = [r for r in table if has_marker(r)]
        if key == "assemblies_calc":
            r = rows[0]
            check.expect(
                close(r[2], 0.13) and close(r[3], 0.04),
                f"assemblies_calc films R_in/R_out = {r[2]}/{r[3]}",
            )
        if key.startswith("layer_table_"):
            check.expect(len(rows) == 3, f"{key}: 3 marker layers")
            total = sum(r[7] for r in rows)
            check.expect(close(total, 327.5), f"{key}: thicknesses sum to 327.5 mm ({total})")
        if key == "assemblies_ud":
            r = rows[0]
            check.expect(close(r[4], round(INTENDED_U, 3)), f"assemblies_ud U = {r[4]}")
        if key == "frames_ud":
            r = rows[0]
            check.expect(
                all(close(v, 1.1) for v in r[2:6]) and all(close(v, 0.115) for v in r[6:10]),
                f"frames_ud per-edge U/width = {r[2]}/{r[6]}",
            )
        if key == "glazing_ud":
            r = rows[0]
            check.expect(
                close(r[2], 0.52) and close(r[3], 0.62), f"glazing_ud g/U = {r[2]}/{r[3]}"
            )


def run(name: str, skp: Path, flags: list[str]) -> Check:
    check = Check(name)
    print(f"\n== {name}  ({skp.name}, flags={flags or ['native']})")
    attrs = extract(skp)
    in_json = OUT_DIR / f"{name}.in.json"
    out_json = OUT_DIR / f"{name}.out.json"
    in_json.write_text(json.dumps({"title": f"{name}_LIBIMPORT", "attrs": attrs}))
    proc = subprocess.run(
        ["ruby", str(HERE / "offline_rehearsal.rb"), str(in_json), str(out_json), *flags],
        capture_output=True, text=True,
    )
    for line in proc.stdout.splitlines():
        print(f"    | {line}")
    if proc.returncode != 0:
        check.expect(False, f"ruby exited {proc.returncode}: {proc.stderr.strip()[:400]}")
        return check
    result = json.loads(out_json.read_text())
    verify(check, attrs, result)
    if "revise" in flags:
        dph = result["dicts"]["DesignPH_dict"]
        asm = next(r for r in decode(dph["assemblies_calc"]) if has_marker(r))
        check.expect(str(asm[1]).endswith(" R2"), f"revise: desc renamed ({asm[1]!r})")
        layers = decode(dph[f"layer_table_{asm[0]}"])
        wool = next(r for r in layers if "MinWool" in str(r[1]))
        check.expect(close(wool[2], 0.04), f"revise: MinWool lambda retuned ({wool[2]})")
    return check


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = [
        run("bluffreach_native", CORPUS / "2414_Bluff Reach_COPY.skp", []),
        run("adelphi_native", CORPUS / "adelphi-designph_COPY.skp", []),
        run("adelphi_both_create", CORPUS / "adelphi-designph_COPY.skp", ["both", "create"]),
        run("linde_native", CORPUS / "250703 - Linde Residence_COPY.skp", []),
        run("bluffreach_revise", CORPUS / "2414_Bluff Reach_COPY.skp", ["revise"]),
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
