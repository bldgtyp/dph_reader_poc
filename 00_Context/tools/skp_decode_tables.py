#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Decode designPH's model-level Marshal tables straight out of a `.skp`, with no SketchUp.

    uv run 00_Context/tools/skp_decode_tables.py MODEL.skp
    uv run 00_Context/tools/skp_decode_tables.py MODEL.skp frames_ud glazing_ud
    uv run 00_Context/tools/skp_decode_tables.py MODEL.skp --all --rows 20

Companion to `skp_attr_dump.py`, which lists *which* keys hold Marshal blobs. This one decodes them
and prints the `:TOKENS` header plus a sample of data rows — which is how the `frames_ud` /
`glazing_ud` schemas were finally read (`DESIGNPH_DATA_MODEL.md` §7.0.1), after a year of the
project assuming frame data was not in the model at all.

⚠ **READ-ONLY, and it never constructs anything.** It uses `planning/spikes/phase1/ruby_marshal.py`
rather than `Marshal.load`, so an unknown designPH class becomes an inert record of its name instead
of being instantiated. A corpus `.skp` cannot run code through this tool.

⚠ **COPIES ONLY** (hard rule 3). It only reads, but a corpus original should never be in the path of
a tool that is being iterated on.

⚠ **`tracker_data` contains usernames and a dated run history** (§7.0.2). It decodes like any other
table; think before pasting the output anywhere.

Why the regex hunt rather than a proper parse: `model.dat` is SketchUp's own binary format, not
documented and not ours to reverse-engineer beyond locating a key we already know the name of. The
blob is self-delimiting base64 (`BAh…`), so finding the key name and taking the next base64 run is
enough — and if it is ever not, the decode fails loudly rather than returning something plausible.
`DESIGNPH_FILE_FORMATS.md` §4.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MARSHAL_READER = REPO / "planning" / "spikes" / "phase1" / "ruby_marshal.py"

#: Everything the corpus has ever been seen to carry. `--all` scans for these; naming keys on the
#: command line overrides it. `layer_table_*` is a family, handled separately.
KNOWN_TABLES = [
    "assemblies_calc", "assemblies_ud", "connections_ud", "frames_ud",
    "glazing_ud", "ihg_ud", "tfa_calc_ud", "tracker_data", "vent_ud",
]

#: base64 of Marshal 4.8's `\x04\x08` marker. A run this long is not a coincidence.
BLOB = re.compile(rb"BAh[A-Za-z0-9+/=\r\n]{40,}", re.DOTALL)


def marshal_reader() -> Any:
    """Load the construct-nothing Marshal reader as a module."""
    if not MARSHAL_READER.exists():
        raise SystemExit(f"marshal reader not found at {MARSHAL_READER}")
    spec = importlib.util.spec_from_file_location("ruby_marshal", MARSHAL_READER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # ⚠ Register before exec: `ruby_marshal` uses @dataclass, which looks its own module up in
    # `sys.modules` and raises an unhelpful AttributeError when it is not there yet.
    sys.modules["ruby_marshal"] = module
    spec.loader.exec_module(module)
    return module


def model_dat(skp: Path) -> bytes:
    """A `.skp` is a zip; the attributes live in `model.dat` inside it."""
    with zipfile.ZipFile(skp) as archive:
        return archive.read("model.dat")


def decode(blob: bytes, key: str, reader: Any) -> list[list[Any]] | None:
    """Find `key` in the raw bytes and decode the Marshal payload that follows it."""
    for match in re.finditer(re.escape(key.encode()), blob, re.DOTALL):
        found = BLOB.search(blob[match.end(): match.end() + 4_000_000])
        if not found:
            continue
        try:
            value = reader.loads(base64.b64decode(found.group(0)))
        except Exception as error:  # noqa: BLE001 — an undecodable blob is a result, not a crash
            print(f"  {key}: undecodable — {type(error).__name__}: {error}")
            return None
        return value if isinstance(value, list) else None
    return None


def describe(key: str, rows: list[Any], sample: int) -> None:
    tokens = next(
        (r for r in rows if isinstance(r, list) and len(r) > 1 and str(r[1]) == "TOKENS"), None
    )
    data = [r for r in rows if isinstance(r, list) and not (r and str(r[0]) == "#")]
    # ⚠ Rows are pre-allocated and mostly blank — designPH writes the shape first. Count non-blank
    # descriptions, never records (§7.0).
    named = [r for r in data if len(r) > 1 and str(r[1]).strip()]
    print(f"\n=== {key} — {len(data)} rows, {len(named)} with a non-blank desc ===")
    if tokens:
        print(f"  TOKENS: {[str(x) for x in tokens[2]]}")
    for row in named[:sample] or data[:sample]:
        print("   ", [str(x)[:40] for x in row])
    if len(named) > sample:
        print(f"    …{len(named) - sample} more named row(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("skp", type=Path)
    parser.add_argument("keys", nargs="*", help=f"tables to decode (default: {', '.join(KNOWN_TABLES)})")
    parser.add_argument("--all", action="store_true", help="also scan for layer_table_NNud")
    parser.add_argument("--rows", type=int, default=4, help="sample rows to print per table")
    args = parser.parse_args()

    if not args.skp.exists():
        raise SystemExit(f"no such file: {args.skp}")
    reader = marshal_reader()
    blob = model_dat(args.skp)

    keys = args.keys or list(KNOWN_TABLES)
    if args.all:
        keys += sorted(set(m.decode() for m in re.findall(rb"layer_table_\d+ud", blob, re.DOTALL)))

    print(f"{args.skp.name}  ({len(blob):,} bytes of model.dat)")
    for key in keys:
        rows = decode(blob, key, reader)
        if rows is None:
            print(f"\n=== {key} — absent ===")
        else:
            describe(key, rows, args.rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
