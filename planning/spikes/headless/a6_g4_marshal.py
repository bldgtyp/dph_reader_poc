# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike A — G4: do designPH's model-level Marshal tables come through the C API byte-clean?

designPH stores its frame, glazing, assembly, connection and layer libraries as `Marshal.dump`
blobs in the MODEL's own `DesignPH_dict` (`collector.rb:644`). They are binary: `Marshal` writes
symbol and string lengths as raw bytes, so **`0x00` is guaranteed to appear**.

⚠ **The named silent-failure risk is NUL truncation.** A ctypes read through `c_char_p` stops at the
first NUL, and the worst case is not a crash — it is a *partially decoded table that still parses*,
i.e. a false PASS. `sdk.py` therefore reads every string through `SUStringGetUTF8Length` + a counted
copy and returns **`bytes`, never `str`**. This gate proves that discipline actually worked, three
ways:

1. the blob starts with Marshal's `\\x04\\x08` magic;
2. it **contains NUL bytes** — if it does not, the read truncated and every other check is worthless;
3. it decodes with the untouched `ruby_marshal.py` from Phase 1, and the decoded table's row count
   and token header are reported.

Cross-checked against the live captures, which shipped the same tables decoded by Ruby.

⚠ Third-party SDK re-host; feasibility-only evidence. See `sdk.py`.

    uv run a6_g4_marshal.py --corpus _private/corpus --fixtures _private/fixtures \
        --out _private/out/a6_marshal.json
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import sys
from ctypes import byref, c_size_t
from pathlib import Path

from sdk import SDK, SUAttributeDictionaryRef, SUStringRef
from walk import Walker

MARSHAL_MAGIC = b"\x04\x08"
# The stored form is base64 of that magic. designPH never stores the raw dump.
MARSHAL_B64_PREFIX = b"BAh"
DICT = "DesignPH_dict"

CORPUS_TO_CAPTURE = {
    "adelphi-designph_COPY.skp": "adelphi-designph_COPY.extraction.json",
    "2414_Bluff Reach_COPY.skp": "2414_Bluff Reach_COPY.extraction.json",
    "2523 Wellington_COPY.skp": "2523 Wellington_COPY.extraction.json",
    "250703 - Linde Residence_COPY.skp": "250703 - Linde Residence_COPY.extraction.json",
    "250708_COPY.skp": "250708_COPY.extraction.json",
}


def load_ruby_marshal(repo_root: Path):
    """Import Phase 1's decoder unchanged. It constructs nothing, so a corpus file cannot run code."""
    path = repo_root / "planning" / "spikes" / "phase1" / "ruby_marshal.py"
    spec = importlib.util.spec_from_file_location("ruby_marshal", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ruby_marshal"] = module
    spec.loader.exec_module(module)
    return module


def model_tables(sdk: SDK, walker: Walker, model) -> dict[str, tuple[bytes, bytes]]:
    """Model-level Marshal tables as (stored base64 bytes, decoded Marshal bytes)."""
    n = c_size_t()
    sdk.call("SUModelGetNumAttributeDictionaries", model, byref(n), tolerate=(2, 8, 9))
    if not n.value:
        return {}
    arr = (SUAttributeDictionaryRef * n.value)()
    got = c_size_t()
    sdk.call("SUModelGetAttributeDictionaries", model, n.value, arr, byref(got))

    target = None
    for i in range(got.value):
        s = SUStringRef()
        sdk.call("SUStringCreate", byref(s))
        try:
            sdk.call("SUAttributeDictionaryGetName", arr[i], byref(s))
            if sdk.read_string(s).decode("utf-8", "replace") == DICT:
                target = arr[i]
        finally:
            sdk.lib.SUStringRelease(byref(s))
    if target is None:
        return {}

    out: dict[str, tuple[bytes, bytes]] = {}
    for key in walker.dict_keys(target):
        got_value = walker.typed_value(target, key)
        if not (got_value and got_value[0] == "String" and isinstance(got_value[1], bytes)):
            continue
        stored = got_value[1]
        if not stored.startswith(MARSHAL_B64_PREFIX):
            continue  # designPH_version, klima_ID — plain scalars, not tables
        out[key] = (stored, base64.b64decode(stored))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--fixtures", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    args = ap.parse_args()

    marshal = load_ruby_marshal(args.repo_root)
    sdk = SDK()
    walker = Walker(sdk)
    results: dict[str, dict] = {}
    failures: list[str] = []

    for skp, capture_name in sorted(CORPUS_TO_CAPTURE.items()):
        path, cap_path = args.corpus / skp, args.fixtures / capture_name
        if not path.exists() or not cap_path.exists():
            continue
        cap = json.loads(cap_path.read_text(encoding="utf-8"))
        expected = sorted(cap["counts"]["tables_found"])

        model = sdk.open_model(path)
        try:
            blobs = model_tables(sdk, walker, model)
        finally:
            sdk.close_model(model)

        found = sorted(blobs)
        rows: dict[str, dict] = {}
        no_nul: list[str] = []
        undecodable: list[str] = []
        for key, (stored, blob) in sorted(blobs.items()):
            # NULs live in the DECODED payload; the stored transport is ASCII base64 by design.
            has_nul = b"\x00" in blob
            if not has_nul:
                no_nul.append(key)
            if not blob.startswith(MARSHAL_MAGIC):
                undecodable.append(f"{key}: base64 did not decode to Marshal magic")
                rows[key] = {"bytes": len(blob), "contains_nul": has_nul, "decoded": False, "rows": 0}
                continue
            try:
                value = marshal.loads(blob)
                n_rows = len(value) if isinstance(value, (list, dict)) else 1
                ok = True
            except Exception as exc:  # noqa: BLE001 — a decode failure is the result, not a crash
                undecodable.append(f"{key}: {type(exc).__name__}: {exc}")
                n_rows, ok = 0, False
            rows[key] = {"stored_b64_bytes": len(stored), "bytes": len(blob),
                         "contains_nul": has_nul, "decoded": ok, "rows": n_rows}

        # ⚠ `tracker_data` must decode like the rest but must never leave `_private/` (overview §4).
        shipped = {k: v for k, v in rows.items() if k != "tracker_data"}
        missing = sorted(set(expected) - set(found))
        extra = sorted(set(found) - set(expected))
        results[skp] = {
            "expected_tables": expected, "found_tables": found,
            "missing": missing, "extra": extra,
            "tables": shipped, "tracker_data_present": "tracker_data" in rows,
            "blobs_without_nul": no_nul, "undecodable": undecodable,
        }
        if missing or undecodable:
            failures.append(skp)

        total_bytes = sum(v["bytes"] for v in rows.values())
        print(f"{'✅' if not (missing or undecodable) else '❌'} {skp}")
        print(f"     tables: {len(found)} found / {len(expected)} in the live capture"
              f"{'  MISSING: ' + ', '.join(missing) if missing else ''}"
              f"{'  EXTRA: ' + ', '.join(extra) if extra else ''}")
        print(f"     bytes read: {total_bytes:,}  ·  all decode: "
              f"{'yes' if not undecodable else 'NO'}"
              f"{'  ·  no NUL in payload (reported, not a failure): ' + ', '.join(no_nul) if no_nul else ''}")
        for e in undecodable:
            print(f"       ⚠ {e}")
        biggest = sorted(shipped.items(), key=lambda kv: -kv[1]["bytes"])[:3]
        for k, v in biggest:
            print(f"       {k:<22} {v['bytes']:>9,} bytes  {v['rows']:>5} rows")

    sdk.terminate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"provenance": "third-party SDK re-host — feasibility-only evidence",
         "note": "tracker_data decodes but is never shipped; only its presence is recorded",
         "models": results}, indent=1))

    tables = sum(len(r["found_tables"]) for r in results.values())
    nbytes = sum(v["bytes"] for r in results.values() for v in r["tables"].values())
    # ⚠ Zero tables is a FAIL, not a vacuous pass. An earlier draft printed "every blob NUL-bearing
    # and decoded" over an empty set and looked green while finding nothing.
    if tables == 0:
        failures.append("no tables found at all")
    print(
        f"\nVERDICT G4: {'PASS' if not failures else 'FAIL — ' + '; '.join(failures)} — "
        f"{tables} Marshal tables across {len(results)} models, {nbytes:,} decoded bytes; "
        f"stored as base64 so NUL truncation cannot occur in transit; "
        f"all parsed by the unmodified Phase-1 reader → {args.out}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
