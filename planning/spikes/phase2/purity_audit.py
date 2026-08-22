# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Phase 2 — Python purity audit.

Resolves the full dependency closure of one or more root requirements, then classifies every
package in that closure as one of three things:

    (a) pure          — publishes a ``py3-none-any`` / ``py2.py3-none-any`` wheel; runs in Pyodide
                        straight off PyPI via ``micropip``.
    (b) pyodide-built — no pure wheel, but Pyodide ships its own wasm build of it.
    (c) blocker       — no pure wheel and no Pyodide build. This is the only class that kills a
                        package.

The distinction between (b) and (c) is the whole point of the phase, so the Pyodide side is read
from the *actual* ``pyodide-lock.json`` of a named release rather than from a hand-kept list.

Closure resolution is deliberately platform-independent: ``uv pip compile --universal`` gives the
union of every platform's requirements, which is a superset of what Pyodide needs and therefore
cannot under-report a blocker. Purity is then decided from PyPI's file list for the resolved
version, not from whatever wheel this machine happens to be able to install — a macOS ``pip
download`` would report ``lxml`` as a macOS binary and tell us nothing about whether a pure
alternative exists.

A package that publishes *no* wheel at all is reported as ``sdist-only`` and must be opened by hand;
an sdist proves nothing either way (plan §Method).

Usage:
    uv run planning/spikes/phase2/purity_audit.py honeybee-ph PHX \
        --pyodide 314.0.5 --pyodide 0.29.4 \
        --md planning/RESULTS/PHASE-2_dependency-audit.md \
        --json planning/RESULTS/baselines/phase2_closure.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

PYPI_JSON = "https://pypi.org/pypi/{name}/{version}/json"
PYODIDE_LOCK = "https://cdn.jsdelivr.net/pyodide/v{version}/full/pyodide-lock.json"

PURE_TAGS = ("py3-none-any", "py2.py3-none-any")

#: The Pyodide releases whose package sets decide class (b) vs class (c). Both current stable
#: lines as of 2026-08-19: 314.x runs CPython 3.14, 0.29.x runs 3.13. Override with --pyodide
#: once Phase 3 settles on the release it actually vendors.
DEFAULT_PYODIDE_VERSIONS = ("314.0.5", "0.29.4")

# Classification labels, in increasing order of severity.
PURE = "pure"
PYODIDE_BUILT = "pyodide-built"
SDIST_ONLY = "sdist-only"
BLOCKER = "blocker"


def _canonical(name: str) -> str:
    """PEP 503 normalised name — ``PH_units``, ``ph-units`` and ``PH-Units`` are one package."""
    return name.lower().replace("_", "-").replace(".", "-")


@dataclass
class Package:
    """One resolved package, with everything needed to judge it."""

    name: str
    version: str
    #: Which root requirement(s) pulled it in.
    roots: set[str] = field(default_factory=set)
    #: Environment marker from the resolution, if the dependency is conditional.
    marker: str | None = None
    classification: str = PURE
    #: Filename of the pure wheel, when there is one.
    pure_wheel: str | None = None
    pure_wheel_bytes: int = 0
    #: Platform-specific wheel tags seen on PyPI, for the record.
    platform_tags: list[str] = field(default_factory=list)
    #: Pyodide releases (of those queried) that ship a build of this package.
    pyodide_builds: list[str] = field(default_factory=list)
    note: str = ""


def resolve_closure(root: str, python_version: str) -> dict[str, tuple[str, str | None]]:
    """Return ``{canonical_name: (version, marker)}`` for the full universal closure of *root*.

    ``--universal`` resolves for every platform at once, so a Windows-only or macOS-only
    dependency still shows up. That over-reports for Pyodide, which is neither, but over-reporting
    is the safe direction: a marker-hidden blocker would be invisible.
    """
    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp) / "requirements.in"
        req.write_text(root + "\n")
        proc = subprocess.run(
            [
                "uv", "pip", "compile", "--universal", "--no-header",
                "--python-version", python_version, str(req),
            ],
            capture_output=True,
            text=True,
            check=False,  # the error message is more useful than the traceback
        )
    if proc.returncode != 0:
        raise RuntimeError(f"uv pip compile failed for {root!r}:\n{proc.stderr}")

    resolved: dict[str, tuple[str, str | None]] = {}
    for line in proc.stdout.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        spec, _, marker = line.partition(";")
        name, _, version = spec.strip().partition("==")
        resolved[_canonical(name)] = (version.strip(), marker.strip() or None)
    return resolved


def classify(client: httpx.Client, pkg: Package) -> None:
    """Decide *pkg*'s classification from PyPI's file list for its resolved version."""
    resp = client.get(PYPI_JSON.format(name=pkg.name, version=pkg.version))
    resp.raise_for_status()
    urls = resp.json()["urls"]

    wheels = [u for u in urls if u["packagetype"] == "bdist_wheel"]
    has_sdist = any(u["packagetype"] == "sdist" for u in urls)

    for wheel in wheels:
        tag = "-".join(wheel["filename"].removesuffix(".whl").split("-")[-3:])
        if tag in PURE_TAGS:
            pkg.classification = PURE
            pkg.pure_wheel = wheel["filename"]
            pkg.pure_wheel_bytes = wheel["size"]
            return
        pkg.platform_tags.append(tag)

    # No pure wheel. Deduplicate the platform tags — 20 manylinux/macos/win rows say one thing.
    pkg.platform_tags = sorted(set(pkg.platform_tags))
    if not wheels:
        pkg.classification = SDIST_ONLY
        pkg.note = "no wheel published" + ("; sdist only" if has_sdist else "; no files at all")
    else:
        pkg.classification = BLOCKER  # provisional — the Pyodide pass may downgrade it to (b)


def load_pyodide_packages(client: httpx.Client, version: str) -> set[str]:
    """Canonical names of every package in a Pyodide release's lock file."""
    resp = client.get(PYODIDE_LOCK.format(version=version))
    resp.raise_for_status()
    return {_canonical(name) for name in resp.json()["packages"]}


def audit(roots: Iterable[str], pyodide_versions: list[str], python_version: str) -> dict[str, Any]:
    packages: dict[str, Package] = {}
    closures: dict[str, list[str]] = {}

    for root in roots:
        resolved = resolve_closure(root, python_version)
        closures[root] = sorted(resolved)
        for name, (version, marker) in resolved.items():
            pkg = packages.get(name)
            if pkg is None:
                pkg = packages[name] = Package(name=name, version=version, marker=marker)
            elif pkg.version != version:  # pragma: no cover — would mean the roots disagree
                pkg.note = f"version differs between roots: {pkg.version} vs {version}"
            pkg.roots.add(root)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for pkg in packages.values():
            classify(client, pkg)

        pyodide_sets = {v: load_pyodide_packages(client, v) for v in pyodide_versions}

    for pkg in packages.values():
        pkg.pyodide_builds = [v for v, names in pyodide_sets.items() if pkg.name in names]
        if pkg.classification == BLOCKER and pkg.pyodide_builds:
            pkg.classification = PYODIDE_BUILT

    return {
        "python_version": python_version,
        "pyodide_versions": {v: sorted(names) for v, names in pyodide_sets.items()},
        "closures": closures,
        "packages": {
            name: {**asdict(pkg), "roots": sorted(pkg.roots)}
            for name, pkg in sorted(packages.items())
        },
    }


def _kb(n: int) -> str:
    return f"{n / 1024:,.0f} KB" if n else "—"


def render_markdown(result: dict[str, Any]) -> str:
    packages = result["packages"]
    # The roots are already in the result, in the order they were resolved — do not pass them
    # in alongside it, or a re-render from a saved JSON can mislabel the header.
    roots = list(result["closures"])
    order = {PURE: 0, PYODIDE_BUILT: 1, SDIST_ONLY: 2, BLOCKER: 3}
    rows = sorted(packages.values(), key=lambda p: (-order[p["classification"]], p["name"]))

    icon = {PURE: "✅", PYODIDE_BUILT: "🟡", SDIST_ONLY: "❓", BLOCKER: "❌"}

    lines = [
        "# Phase 2 — dependency closure audit",
        "",
        "Generated by [`planning/spikes/phase2/purity_audit.py`](../spikes/phase2/purity_audit.py).",
        "",
        f"- Roots: {', '.join('`' + r + '`' for r in roots)}",
        f"- Resolved for Python {result['python_version']}, `uv pip compile --universal`",
        "- Pyodide releases checked: "
        + ", ".join(f"`{v}` ({len(n)} packages)" for v, n in result["pyodide_versions"].items()),
        "",
        "| Package | Version | Pulled in by | Class | Wheel | Size | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in rows:
        wheel = "`py3-none-any`" if p["classification"] == PURE else ", ".join(
            f"`{t}`" for t in p["platform_tags"][:3]
        ) or "—"
        notes = p["note"]
        if p["pyodide_builds"]:
            built = ", ".join(f"`{v}`" for v in p["pyodide_builds"])
            notes = (notes + "; " if notes else "") + f"Pyodide build in {built}"
        lines.append(
            f"| `{p['name']}` | {p['version']} | {', '.join(p['roots'])} | "
            f"{icon[p['classification']]} {p['classification']} | {wheel} | "
            f"{_kb(p['pure_wheel_bytes'])} | {notes} |"
        )

    lines += ["", "## Per-root closure size", ""]
    lines += ["| Root | Packages | Pure | Impure | Pure-wheel bytes |", "|---|---|---|---|---|"]
    for root, names in result["closures"].items():
        subset = [packages[n] for n in names]
        pure = [p for p in subset if p["classification"] == PURE]
        total = sum(p["pure_wheel_bytes"] for p in pure)
        lines.append(
            f"| `{root}` | {len(subset)} | {len(pure)} | {len(subset) - len(pure)} | {_kb(total)} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="root requirements to resolve, e.g. honeybee-ph PHX")
    parser.add_argument(
        "--pyodide", action="append", default=None,
        help="Pyodide release to check against; repeatable "
             f"(default: {', '.join(DEFAULT_PYODIDE_VERSIONS)})",
    )
    parser.add_argument("--python-version", default="3.14", help="Python version to resolve for")
    parser.add_argument("--md", type=Path, help="write the Markdown table here")
    parser.add_argument("--json", type=Path, help="write the raw result here")
    args = parser.parse_args()

    result = audit(args.roots, args.pyodide or list(DEFAULT_PYODIDE_VERSIONS), args.python_version)

    markdown = render_markdown(result)
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(markdown)
        print(f"wrote {args.md}", file=sys.stderr)
    else:
        print(markdown)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.json}", file=sys.stderr)

    blockers = [p for p in result["packages"].values() if p["classification"] == BLOCKER]
    unknown = [p for p in result["packages"].values() if p["classification"] == SDIST_ONLY]
    for p in blockers:
        print(f"BLOCKER: {p['name']}=={p['version']} (via {', '.join(p['roots'])})", file=sys.stderr)
    for p in unknown:
        print(f"CHECK BY HAND: {p['name']}=={p['version']} — {p['note']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
