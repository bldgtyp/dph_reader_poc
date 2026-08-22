# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Phase 3 — which Pyodide releases can SketchUp's Chromium actually parse?

SketchUp 2022 ships **CEF 88.2.4 = Chromium 88** (January 2021), read off
`SketchUp.app/Contents/Frameworks/Chromium Embedded Framework.framework`. Pyodide 314.0.5's loader
uses 66 ES2022 static initialization blocks, which Chromium 88 rejects with
`SyntaxError: Unexpected token '{'` — the exact error the first successful SketchUp run produced.

This script scans each Pyodide release's loader for syntax that postdates a given Chromium, so the
question "is there a version that would work" gets an answer from the files themselves rather than
from release notes. It reads one file per version off jsDelivr (~1–3 MB each), never the 350 MB
distribution.

**Syntax is necessary, not sufficient.** A release that parses can still fail on a WebAssembly
feature or a missing runtime API; those are noted per version but not detected here. Treat a pass as
"worth testing in SketchUp", never as "will work".

Usage:
    uv run planning/spikes/pyodide/probe_pyodide_syntax.py
    uv run planning/spikes/pyodide/probe_pyodide_syntax.py --versions 0.21.3 0.26.4 --chromium 88
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Any

import httpx

CDN = "https://cdn.jsdelivr.net/pyodide/v{version}/full/{filename}"

#: Loader filenames change across the line: `.mjs` is the ES-module build, `.js` the classic one.
#: Both are tried, because which exists depends on the release.
LOADERS = ("pyodide.asm.mjs", "pyodide.asm.js")

#: Release line samples, oldest first. One per minor is enough to bracket the answer.
DEFAULT_VERSIONS = (
    "0.20.0",
    "0.21.3",
    "0.22.1",
    "0.23.4",
    "0.24.1",
    "0.25.1",
    "0.26.4",
    "0.27.7",
    "0.28.3",
    "314.0.5",
)


@dataclass(frozen=True)
class Feature:
    """One JS syntax feature, the Chromium that shipped it, and how to spot it."""

    label: str
    chromium: int
    pattern: str


#: Syntax only — a parse error takes the whole file down, which is the failure mode being chased.
#: Runtime-only additions (`Object.hasOwn`, `.at()`) are listed separately because they fail later
#: and could in principle be polyfilled.
SYNTAX: tuple[Feature, ...] = (
    Feature("class fields", 72, r"^\s*#?[a-zA-Z_]\w*\s*=\s*[^=]"),
    Feature("optional chaining `?.`", 80, r"\?\."),
    Feature("nullish coalescing `??`", 80, r"\?\?[^=]"),
    Feature("logical assignment `??= ||= &&=`", 85, r"(\?\?=|\|\|=|&&=)"),
    Feature("private class fields `#x`", 74, r"[^\w#]#[a-zA-Z_]\w*\s*[=;(]"),
    Feature("RegExp match indices `/d`", 90, r"/[gimsuy]*d[gimsuy]*\s*[,;)\]]"),
    Feature("static initialization block `static {`", 94, r"static\s*\{"),
)

RUNTIME: tuple[Feature, ...] = (
    Feature("`String/Array.prototype.at()`", 92, r"\.at\("),
    Feature("`Object.hasOwn`", 93, r"Object\.hasOwn"),
    Feature("`structuredClone`", 98, r"structuredClone"),
    Feature("`Array.prototype.findLast`", 97, r"\.findLast\("),
)


def fetch_loader(client: httpx.Client, version: str) -> tuple[str, str] | None:
    """Return (filename, source) for a release's loader, or None if jsDelivr has neither."""
    for filename in LOADERS:
        response = client.get(CDN.format(version=version, filename=filename), timeout=120.0)
        if response.status_code == 200:
            return filename, response.text
    return None


def scan(source: str, features: tuple[Feature, ...]) -> list[tuple[Feature, int]]:
    return [(f, len(re.findall(f.pattern, source, re.M))) for f in features]


def probe(versions: tuple[str, ...], target: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with httpx.Client(follow_redirects=True) as client:
        for version in versions:
            found = fetch_loader(client, version)
            if found is None:
                print(f"  {version:10s}  (no loader on jsDelivr)")
                continue
            filename, source = found
            syntax = [(f, n) for f, n in scan(source, SYNTAX) if n and f.chromium > target]
            runtime = [(f, n) for f, n in scan(source, RUNTIME) if n and f.chromium > target]
            needed = max([f.chromium for f, _ in syntax], default=0)

            verdict = "PARSES" if not syntax else f"needs Chromium {needed}"
            print(f"  {version:10s}  {filename:18s}  {len(source) / 1e6:5.2f} MB   {verdict}")
            for feature, count in syntax:
                print(f"                 ✗ syntax  {feature.label} (Chromium {feature.chromium}) ×{count}")
            for feature, count in runtime:
                print(f"                 ⚠ runtime {feature.label} (Chromium {feature.chromium}) ×{count}")
            results.append(
                {
                    "version": version,
                    "loader": filename,
                    "parses_on_target": not syntax,
                    "min_chromium_syntax": needed or None,
                    "runtime_gaps": [f.label for f, _ in runtime],
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", nargs="+", default=list(DEFAULT_VERSIONS))
    parser.add_argument(
        "--chromium", type=int, default=88, help="target engine (SketchUp 2022 = Chromium 88)"
    )
    args = parser.parse_args()

    print(f"target: Chromium {args.chromium}\n")
    results = probe(tuple(args.versions), args.chromium)

    ok = [r for r in results if r["parses_on_target"]]
    print()
    if ok:
        print(f"  parses on Chromium {args.chromium}: " + ", ".join(r["version"] for r in ok))
        print("  ⚠ syntax only — WebAssembly features and runtime APIs are NOT checked here.")
    else:
        print(f"  no probed release parses on Chromium {args.chromium}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
