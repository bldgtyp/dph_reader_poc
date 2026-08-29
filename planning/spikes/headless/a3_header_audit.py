# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike A — check every ctypes declaration in `sdk.py` against the SDK's own shipped headers.

**Why this exists, and it is not hypothetical.** `sdk.py`'s first draft declared

    SUModelGetVersion(SUModelRef, int* version)      # inferred from the doxygen NAME

because a function called `GetVersion` sitting next to an enum called `SUModelVersion` reads
overwhelmingly like an enum getter. The real signature is

    SU_RESULT SUModelGetVersion(SUModelRef model, int* major, int* minor, int* build)

so the call wrote through two out-pointers that were never passed. On Adelphi it **survived and
returned a plausible-looking 22** — which is even the right major version for its writer — and it
**segfaulted on the next model**. A wrong signature that produces a believable number on the first
model in the corpus is exactly this repo's most-repeated failure shape, one layer down in the stack.

A second one was silently wrong and had not yet been called: `SUEntityGetType` returns
`enum SURefType` **directly**; it is not an out-param call and not even `SU_RESULT`.

So: a published *name* is not a *signature*, and the only authority is the header. This script makes
that check mechanical, and it is cheap enough to run before every gate.

    uv run a3_header_audit.py --headers _private/sdk/.../Headers --out _private/out/a3_header_audit.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_HEADERS = (
    Path(__file__).parent / "_private" / "sdk" / "sketchup_importer" / "SketchUpAPI.framework" / "Headers"
)

# `("SUFoo", [ArgA, ArgB], restype),` rows in sdk.py's signature table.
SDK_ROW = re.compile(r'\("(SU[A-Za-z0-9_]+)",\s*(\[[^\]]*\])\s*,', re.S)
# `SU_RESULT SUFoo(args);` and `SU_EXPORT <ret> SUFoo(args);` in the headers.
HDR_RESULT = re.compile(r"SU_RESULT\s+(SU[A-Za-z0-9_]+)\s*\(([^;]*?)\)\s*;", re.S)
HDR_EXPORT = re.compile(r"SU_EXPORT\s+([A-Za-z_][\w\s*]*?)\s+(SU[A-Za-z0-9_]+)\s*\(([^;]*?)\)\s*;", re.S)


def strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", " ", re.sub(r"/\*.*?\*/", " ", text, flags=re.S))


def split_params(params: str) -> list[str]:
    params = re.sub(r"\s+", " ", params).strip()
    if not params or params == "void":
        return []
    return [p.strip() for p in params.split(",")]


def parse_headers(headers: Path) -> dict[str, dict[str, object]]:
    if not headers.is_dir():
        raise SystemExit(f"headers not found: {headers}")
    src = strip_comments("\n".join(p.read_text(errors="replace") for p in sorted(headers.rglob("*.h"))))
    out: dict[str, dict[str, object]] = {}
    for m in HDR_RESULT.finditer(src):
        out[m.group(1)] = {"returns": "SU_RESULT", "params": split_params(m.group(2))}
    for m in HDR_EXPORT.finditer(src):
        ret = re.sub(r"\s+", " ", m.group(1)).strip()
        out.setdefault(m.group(2), {"returns": ret, "params": split_params(m.group(3))})
    return out


def parse_sdk_module(path: Path) -> dict[str, int]:
    """Declared arity per function, read from the source text so the framework need not be loadable."""
    text = path.read_text()
    start = text.index("sig = [")
    end = text.index("]", text.index("for name, args, res in sig"))
    declared: dict[str, int] = {}
    for m in SDK_ROW.finditer(text[start:end]):
        args = m.group(2).strip()
        declared[m.group(1)] = 0 if args == "[]" else args.count(",") + 1
    if not declared:
        raise SystemExit("parsed no declarations out of sdk.py — the signature table moved; fix this script")
    return declared


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--headers", type=Path, default=DEFAULT_HEADERS)
    ap.add_argument("--sdk-module", type=Path, default=Path(__file__).parent / "sdk.py")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    hdr = parse_headers(args.headers)
    declared = parse_sdk_module(args.sdk_module)
    print(f"headers  : {len(hdr)} functions parsed from {args.headers}")
    print(f"sdk.py   : {len(declared)} declarations\n")

    mismatches, unknown = [], []
    for name, arity in sorted(declared.items()):
        real = hdr.get(name)
        if real is None:
            unknown.append(name)
            print(f"  ?      {name}: not declared in the shipped headers")
            continue
        params = real["params"]
        if len(params) != arity:
            mismatches.append({"name": name, "declared": arity, "header": len(params), "params": params})
            print(f"  ✗ FAIL {name}: sdk.py declares {arity} args, header says {len(params)}")
            print(f"           {', '.join(params)}  ->  {real['returns']}")

    if not mismatches:
        print("  all declared arities match the shipped headers")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "headers": str(args.headers), "header_functions": len(hdr),
        "declared": len(declared), "mismatches": mismatches, "not_in_headers": unknown,
    }, indent=1))

    print(
        f"\nVERDICT a3: {'PASS' if not mismatches else 'FAIL'} — "
        f"{len(declared)} declarations checked against {len(hdr)} header functions, "
        f"{len(mismatches)} arity mismatch(es)"
        + (f", {len(unknown)} not found in headers" if unknown else "")
        + f" → {args.out}"
    )
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
