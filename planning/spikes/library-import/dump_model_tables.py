#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike L-A's authoritative before/after read: the model-level `DesignPH_dict`, LIVE state.

    uv run planning/spikes/library-import/dump_model_tables.py COPY.skp --out out.json
    uv run planning/spikes/library-import/dump_model_tables.py --diff before.json after.json

Reads through the headless C-SDK binding (read-only handle — the writer symbol is never even
resolved), so unlike the offline `skp_decode_tables.py` regex route it cannot return a stale
historical blob out of `model.dat`, and unlike a contract-v2 capture it misses nothing: EVERY
model-level key is dumped, `frames_ud` and `glazing_ud` included (the capture deliberately ships
neither — `DESIGNPH_DATA_MODEL.md` §7.0).

The `--diff` mode is the O-6 grader at model level: keys added / removed / changed, and for a
changed table, which rows (by row id) and which columns.

⚠ COPIES ONLY (hard rule 3), and the SDK mutate-on-read trap means the opened file must NEVER be
saved — this tool cannot save (read-only binding), which is the point.
⚠ Output may contain `tracker_data` (usernames, run history — §7.0.2): it stays in `_private/`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
HEADLESS = HERE.parent / "headless"
sys.path.insert(0, str(HEADLESS))


def dump(skp: Path) -> dict[str, Any]:
    from collector import DICT, HeadlessCollector, Tables, load_ruby_marshal
    from sdk import SDK

    sdk = SDK(read_only=True)
    tables = Tables(load_ruby_marshal(HERE.parent.parent.parent))
    collector = HeadlessCollector(sdk, tables)
    model = sdk.open_model(skp)
    try:
        dictionary = collector._model_dictionary(model)  # noqa: SLF001 — spike reuse, by design
        scalars: dict[str, Any] = {}
        decoded: dict[str, Any] = {}
        if dictionary is not None:
            for key in collector.walker.dict_keys(dictionary):
                got = collector.walker.typed_value(dictionary, key)
                if not got:
                    continue
                kind, value = got
                if kind == "String" and isinstance(value, bytes) and value.startswith(b"BAh"):
                    decoded[key] = tables.decode(value)
                    decoded[key]["base64_style"] = "wrapped" if b"\n" in value else "strict"
                else:
                    scalars[key] = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
        return {
            "file": skp.name,
            "dict_present": dictionary is not None,
            "scalars": scalars,
            "tables": decoded,
        }
    finally:
        sdk.close_model(model)
        sdk.terminate()


def row_map(table: dict[str, Any]) -> dict[str, list[Any]]:
    return {str(r[0]): r for r in table.get("rows", []) if isinstance(r, list) and r}


def diff_tables(key: str, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if before.get("tokens") != after.get("tokens"):
        out.append(f"{key}: TOKENS changed {before.get('tokens')} -> {after.get('tokens')}")
    if before.get("base64_style") != after.get("base64_style"):
        out.append(f"{key}: base64 style {before.get('base64_style')} -> {after.get('base64_style')}")
    b_rows, a_rows = row_map(before), row_map(after)
    tokens = after.get("tokens") or before.get("tokens") or []
    for rid in sorted(set(b_rows) | set(a_rows)):
        b, a = b_rows.get(rid), a_rows.get(rid)
        if b == a:
            continue
        if b is None:
            out.append(f"{key}[{rid}]: ADDED {a}")
        elif a is None:
            out.append(f"{key}[{rid}]: REMOVED {b}")
        else:
            # rows may differ in WIDTH (the L-B probe appends a column) — guard every access
            cols = [
                f"{tokens[i] if i < len(tokens) else i}: "
                f"{(b[i] if i < len(b) else '<absent>')!r} -> "
                f"{(a[i] if i < len(a) else '<absent>')!r}"
                for i in range(max(len(b), len(a)))
                if (b[i] if i < len(b) else None) != (a[i] if i < len(a) else None)
            ]
            out.append(f"{key}[{rid}]: {'; '.join(cols)}")
    return out


def diff(before_path: Path, after_path: Path) -> int:
    before = json.loads(before_path.read_text())
    after = json.loads(after_path.read_text())
    lines: list[str] = []
    for name, b_side, a_side in (("scalar", before["scalars"], after["scalars"]),):
        for key in sorted(set(b_side) | set(a_side)):
            if b_side.get(key) != a_side.get(key):
                lines.append(f"{name} {key}: {b_side.get(key)!r} -> {a_side.get(key)!r}")
    b_tables, a_tables = before["tables"], after["tables"]
    for key in sorted(set(b_tables) | set(a_tables)):
        if key not in b_tables:
            t = a_tables[key]
            lines.append(f"table {key}: ADDED ({len(t.get('rows', []))} rows)")
        elif key not in a_tables:
            lines.append(f"table {key}: REMOVED")
        elif b_tables[key] != a_tables[key]:
            lines.extend(diff_tables(key, b_tables[key], a_tables[key]))
    print(f"{before_path.name} -> {after_path.name}: "
          f"{len(lines) or 'NO'} difference(s)")
    for line in lines:
        print(f"  {line}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, help="dump mode: where to write the JSON")
    parser.add_argument("--diff", action="store_true", help="diff two dump JSONs")
    args = parser.parse_args()

    if args.diff:
        if len(args.paths) != 2:
            raise SystemExit("--diff takes exactly two dump JSONs")
        return diff(args.paths[0], args.paths[1])

    if len(args.paths) != 1 or not args.out:
        raise SystemExit("dump mode: one COPY.skp and --out OUT.json")
    document = dump(args.paths[0])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, indent=1, default=str))
    named = {
        k: sum(1 for r in t.get("rows", []) if len(r) > 1 and str(r[1]).strip())
        for k, t in document["tables"].items()
    }
    print(f"{args.paths[0].name}: {len(document['tables'])} tables, "
          f"{len(document['scalars'])} scalars -> {args.out}")
    for key, count in sorted(named.items()):
        print(f"  {key}: {count} named row(s) [{document['tables'][key]['base64_style']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
