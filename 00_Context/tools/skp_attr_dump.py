#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Dump SketchUp AttributeDictionary data straight out of a .skp, without SketchUp.

Reverse-engineered reader for the length-prefixed attribute records inside `model.dat`.
Validated against SketchUp 2022-era files only. See ../DESIGNPH_FILE_FORMATS.md section 4.

CAVEAT: `model.dat` accumulates historical state, so key counts here can exceed the number
of live entities. For authoritative current state use the Ruby API (BT Attribute Inspector).
Treat this as reconnaissance.

Usage
-----
    uv run skp_attr_dump.py MODEL.skp                  # summary of every dictionary
    uv run skp_attr_dump.py MODEL.skp -d DesignPH_dict # one dictionary, with values
    uv run skp_attr_dump.py MODEL.skp -d DesignPH_dict --json out.json
    uv run skp_attr_dump.py MODEL.skp --marshal        # list base64 Marshal blob keys
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

# Record opcodes. Little-endian throughout.
OP_DICT = b"\xb4\x36"  # dictionary name
OP_KEY = b"\xb6\x36"  # attribute key name
OP_WRAP = b"\xa4\x38"  # value wrapper; total_len == 0 means nil
OP_STR = b"\xad\x38"
OP_INT = b"\xa7\x38"
OP_FLOAT = b"\xa9\x38"
OP_BOOL = b"\xaa\x38"

MAX_NAME_LEN = 200  # sanity bound; real keys are far shorter


@dataclass(frozen=True)
class Marker:
    """A dictionary-name or key-name record found in the stream."""

    offset: int
    kind: str  # "dict" | "key"
    name: str
    value_at: int  # byte offset just past the name


def read_model_dat(path: Path) -> bytes:
    """Return the raw model stream.

    SketchUp 2014+ wraps the model in a zip; older versions are a flat binary.
    """
    try:
        with zipfile.ZipFile(path) as z:
            return z.read("model.dat")
    except (zipfile.BadZipFile, KeyError):
        return path.read_bytes()  # pre-2014 flat format


def find_markers(buf: bytes) -> list[Marker]:
    """Locate every dictionary-name and key-name record, in file order.

    NOTE the re.DOTALL. The 4-byte length field is raw binary, so a name of length
    10 encodes as 0A 00 00 00 -- and without DOTALL the `.` refuses to match that
    0x0A and the record is silently skipped. That bug hid three real keys on the
    first pass through these files.
    """
    markers: list[Marker] = []
    for opcode, kind in ((OP_DICT, "dict"), (OP_KEY, "key")):
        pattern = re.escape(opcode) + rb"(....)"
        for m in re.finditer(pattern, buf, re.DOTALL):
            (length,) = struct.unpack("<I", m.group(1))
            if not 0 < length < MAX_NAME_LEN:
                continue
            raw = buf[m.end() : m.end() + length]
            if len(raw) != length or not all(0x20 <= b < 0x7F for b in raw):
                continue
            markers.append(Marker(m.start(), kind, raw.decode("ascii"), m.end() + length))
    markers.sort(key=lambda mk: mk.offset)
    return markers


def read_value(buf: bytes, pos: int) -> tuple[str, object]:
    """Decode the value record at `pos`. Returns (type_name, value)."""
    if buf[pos : pos + 2] != OP_WRAP:
        return "unknown", None
    (total,) = struct.unpack("<I", buf[pos + 2 : pos + 6])
    if total == 0:
        return "nil", None

    inner = pos + 6
    opcode = buf[inner : inner + 2]
    (length,) = struct.unpack("<I", buf[inner + 2 : inner + 6])
    payload = buf[inner + 6 : inner + 6 + length]

    if opcode == OP_STR:
        return "str", payload.decode("utf-8", "replace")
    if opcode == OP_INT and len(payload) >= 4:
        return "int", struct.unpack("<i", payload[:4])[0]
    if opcode == OP_FLOAT and len(payload) >= 8:
        return "float", struct.unpack("<d", payload[:8])[0]
    if opcode == OP_BOOL and payload:
        return "bool", bool(payload[0])
    return f"raw:{opcode.hex()}", payload[:16].hex()


def collect(buf: bytes) -> dict[str, list[tuple[str, str, object]]]:
    """Group (key, type, value) triples under the dictionary that precedes them."""
    out: dict[str, list[tuple[str, str, object]]] = collections.defaultdict(list)
    current: str | None = None
    for mk in find_markers(buf):
        if mk.kind == "dict":
            current = mk.name
        elif current is not None:
            type_name, value = read_value(buf, mk.value_at)
            out[current].append((mk.name, type_name, value))
    return out


def truncate(value: object, limit: int = 46) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skp", type=Path)
    ap.add_argument("-d", "--dict", help="show values for this dictionary only")
    ap.add_argument("--marshal", action="store_true", help="list keys holding base64 Marshal blobs")
    ap.add_argument("--json", type=Path, help="write the full result to this path")
    args = ap.parse_args()

    if not args.skp.exists():
        print(f"no such file: {args.skp}", file=sys.stderr)
        return 1

    buf = read_model_dat(args.skp)
    grouped = collect(buf)

    if args.marshal:
        # designPH serialises Ruby object graphs as base64(Marshal.dump(...)),
        # which always begins \x04\x08 -> "BAh".
        print(f"{'dictionary':<22} {'key':<22} bytes")
        for dict_name, entries in sorted(grouped.items()):
            for key, type_name, value in entries:
                if type_name == "str" and isinstance(value, str) and value.startswith("BAh"):
                    print(f"{dict_name:<22} {key:<22} {len(value)}")
        return 0

    if args.dict:
        entries = grouped.get(args.dict)
        if not entries:
            print(f"dictionary {args.dict!r} not found. Present: {', '.join(sorted(grouped))}")
            return 1
        by_key: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for key, type_name, value in entries:
            by_key[key][(type_name, truncate(value))] += 1
        print(f"{args.dict} -- {len(by_key)} distinct keys, {len(entries)} records\n")
        for key in sorted(by_key, key=lambda k: -sum(by_key[k].values())):
            print(f"{key}  (n={sum(by_key[key].values())})")
            for (type_name, shown), count in by_key[key].most_common(8):
                print(f"    {count:5d}  [{type_name}] {shown}")
            print()
    else:
        print(f"{'dictionary':<28} records  distinct keys")
        for dict_name, entries in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
            distinct = len({key for key, _, _ in entries})
            print(f"{dict_name:<28} {len(entries):7d}  {distinct}")

    if args.json:
        payload = {
            d: [{"key": k, "type": t, "value": v} for k, t, v in entries]
            for d, entries in grouped.items()
        }
        args.json.write_text(json.dumps(payload, indent=2, default=str))
        print(f"\nwrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
