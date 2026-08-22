# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""DesignPH-PLUS POC — vendor the Pyodide runtime and the wheel payload.

Promoted from `planning/spikes/pyodide/vendor_payload.py`; **paths only** changed. The Pyodide
0.24.1 pin and the eight-wheel manifest are exactly what Phase 3 verified inside SketchUp.

Downloads, verifies and unpacks everything the extension needs to run **offline**:

    poc/vendor/pyodide/            unpacked `pyodide-core-<ver>.tar.bz2` (the runtime)
    poc/vendor/wheels/*.whl        the 8 wheels of PHASE-2 results §2.6
    poc/vendor/manifest.json       what was fetched, its sha256, and its size

`poc/vendor/` is the download cache; `build_rbz.py` stages a trimmed copy into
`poc/ext/dph_plus_poc/vendor/`, which is what actually ships. Both are gitignored and regenerable.

Everything is **pinned**. A payload that silently floats cannot be compared against Phase 2's
bundle budget or Phase 3's measurements. `--check` re-verifies an existing vendor tree without
downloading, which is what the build script calls.

Usage:
    uv run poc/tools/vendor_payload.py               # required payload (8 wheels)
    uv run poc/tools/vendor_payload.py --with-phx    # + the PHX write-path stretch goal
    uv run poc/tools/vendor_payload.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).resolve().parent
POC = HERE.parent
VENDOR = POC / "vendor"

#: Pyodide release line. 314.x runs CPython 3.14; this is the release Phase 2 §2.5 measured.
#: `pyodide-core` is the *shippable* tarball — 6.8 MB against the full distribution's 350 MB —
#: and it contains no packages at all, which is why the wheels are vendored and unpacked by hand.
#: **0.24.1 is the newest Pyodide that runs on SketchUp 2022**, which embeds CEF 88.2.4 =
#: **Chromium 88** (January 2021). Verified against a real Chromium 88 snapshot, not inferred:
#:
#:   0.28+   `SyntaxError: Unexpected token '{'` — ES2022 static blocks, Chromium 94
#:   0.25.1  boot never settles
#:   0.24.1  ✅ full stack, cold start 3.5 s, CPython 3.11.3 / Emscripten 3.1.45
#:
#: `--pyodide-version` overrides it; `planning/spikes/pyodide/probe_pyodide_syntax.py` brackets the
#: syntax break, and
#: `verify_in_chrome.py --chrome <chromium-88>` settles the rest. Raising this pin means raising
#: the supported SketchUp floor — see PRD §7.4.
PYODIDE_VERSION = "0.24.1"


def pyodide_core_url(version: str) -> str:
    return f"https://github.com/pyodide/pyodide/releases/download/{version}/pyodide-core-{version}.tar.bz2"


#: The payload, pinned — read from **`poc/py/pyproject.toml`, the single source of truth**.
#:
#: The pins used to be written out here as well as in the project file and the Makefile. That is the
#: "tests passed on code the `.rbz` doesn't contain" failure mode wearing a different hat: the test
#: venv would install one version while the `.rbz` shipped another, and nothing would say so. One
#: list, three consumers.
#:
#: **`micropip` is deliberately not in it** (Phase 3, Finding 35). Phase 2 planned to install
#: through it and keep a `zipfile` unpack in reserve; in practice `micropip` is coupled to the
#: Pyodide release and cannot run on the 0.24.1 that SketchUp's Chromium 88 forces — it raises
#: `ImportError: cannot import name 'lockfileBaseUrl'` before doing anything. Since every wheel here
#: is `py3-none-any`, unpacking **is** installing: there is nothing for a resolver to resolve. So the
#: reserve became the mechanism, and shipping `micropip` alongside it bought nothing but 0.2 MB and a
#: traceback in the user's face on every single run.
PYPROJECT = HERE.parent / "py" / "pyproject.toml"


def required_wheels() -> dict[str, str]:
    """The `name == version` pins from `poc/py/pyproject.toml`, in declaration order."""
    pins: dict[str, str] = {}
    for requirement in tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]:
        name, _, version = requirement.partition("==")
        if not version:
            raise SystemExit(f"{requirement!r} is not `==`-pinned; the payload must not float")
        pins[name.strip()] = version.strip()
    return pins


#: Stretch goal only (Phase 2 §2.6). Adds `PHX.from_HBJSON` → `to_WUFI_XML` / `to_METr_JSON`.
#: Never `PHX.from_WUFI_XML`, never `PHX.PHPP`.
PHX_WHEELS: dict[str, str] = {"phx": "1.56.88"}

PYPI_JSON = "https://pypi.org/pypi/{name}/{version}/json"


@dataclass
class Artifact:
    """One downloaded file, recorded so the build can re-verify it without the network."""

    name: str
    version: str
    filename: str
    url: str
    sha256: str
    bytes: int
    kind: str  # "runtime" | "wheel"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pure_wheel_url(client: httpx.Client, name: str, version: str) -> tuple[str, str, str]:
    """Return (filename, url, sha256) of the pure-Python wheel for ``name==version``.

    Purity is read off PyPI's file list rather than off whatever this laptop can install — the
    mistake Phase 2 recorded about ``pip download``. A pin with no ``*-none-any`` wheel is an error
    here, not something to paper over: the whole Pyodide case rests on there being one.
    """
    response = client.get(PYPI_JSON.format(name=name, version=version), timeout=60.0)
    response.raise_for_status()
    for entry in response.json()["urls"]:
        if entry["packagetype"] == "bdist_wheel" and entry["filename"].endswith("-none-any.whl"):
            return entry["filename"], entry["url"], entry["digests"]["sha256"]
    raise SystemExit(f"{name}=={version}: no py3-none-any wheel on PyPI — payload assumption broken")


def download(client: httpx.Client, url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with client.stream("GET", url, timeout=300.0, follow_redirects=True) as response:
        response.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in response.iter_bytes(1 << 20):
                handle.write(chunk)


def vendor_runtime(client: httpx.Client, version: str) -> Artifact:
    """Fetch and unpack `pyodide-core`, leaving its files flat in `vendor/pyodide/`."""
    tarball = VENDOR / f"pyodide-core-{version}.tar.bz2"
    if not tarball.exists():
        print(f"  fetching {tarball.name} ...", flush=True)
        download(client, pyodide_core_url(version), tarball)

    runtime = VENDOR / "pyodide"
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    with tarfile.open(tarball, "r:bz2") as archive:
        # The tarball nests everything under `pyodide/`; flatten it so the dialog's `indexURL`
        # is just `vendor/pyodide/`.
        members = [m for m in archive.getmembers() if m.isfile()]
        for member in members:
            member.name = Path(member.name).name
            archive.extract(member, runtime, filter="data")
    print(f"  unpacked {len(members)} files into vendor/pyodide/")

    return Artifact(
        name="pyodide-core",
        version=version,
        filename=tarball.name,
        url=pyodide_core_url(version),
        sha256=sha256_of(tarball),
        bytes=tarball.stat().st_size,
        kind="runtime",
    )


def vendor_wheels(client: httpx.Client, pins: dict[str, str]) -> list[Artifact]:
    wheels = VENDOR / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    artifacts: list[Artifact] = []
    for name, version in pins.items():
        filename, url, expected = pure_wheel_url(client, name, version)
        dest = wheels / filename
        if not dest.exists():
            print(f"  fetching {filename} ...", flush=True)
            download(client, url, dest)
        actual = sha256_of(dest)
        if actual != expected:
            raise SystemExit(f"{filename}: sha256 mismatch — expected {expected}, got {actual}")
        artifacts.append(Artifact(name, version, filename, url, expected, dest.stat().st_size, "wheel"))
    return artifacts


def write_manifest(artifacts: list[Artifact], with_phx: bool, version: str) -> dict[str, Any]:
    manifest = {
        "pyodide_version": version,
        "includes_phx": with_phx,
        "artifacts": [asdict(a) for a in artifacts],
        # The order the dialog unpacks them in. There is no resolver — every wheel is
        # `py3-none-any` and `zipfile` just extracts them — so nothing derives this order for us.
        "wheel_order": [a.filename for a in artifacts if a.kind == "wheel"],
    }
    (VENDOR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def report(manifest: dict[str, Any]) -> None:
    runtime = [a for a in manifest["artifacts"] if a["kind"] == "runtime"]
    wheels = [a for a in manifest["artifacts"] if a["kind"] == "wheel"]
    print("\n  payload (compressed download sizes)")
    for artifact in runtime + wheels:
        print(f"    {artifact['filename']:52s} {artifact['bytes'] / 1e6:7.2f} MB")
    total = sum(a["bytes"] for a in manifest["artifacts"])
    unpacked = sum(f.stat().st_size for f in (VENDOR / "pyodide").rglob("*") if f.is_file())
    print(f"    {'TOTAL download':52s} {total / 1e6:7.2f} MB")
    print(f"    {'(pyodide-core unpacked, what ships in the .rbz)':52s} {unpacked / 1e6:7.2f} MB")


def check(with_phx: bool) -> int:
    """Re-verify an existing vendor tree offline. Returns a process exit code."""
    manifest_path = VENDOR / "manifest.json"
    if not manifest_path.exists():
        print("vendor/manifest.json missing — run without --check first", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text())
    expected_pins = required_wheels() | (PHX_WHEELS if with_phx else {})
    problems: list[str] = []

    for artifact in manifest["artifacts"]:
        path = VENDOR / ("wheels" if artifact["kind"] == "wheel" else ".") / artifact["filename"]
        if not path.exists():
            problems.append(f"missing: {artifact['filename']}")
        elif sha256_of(path) != artifact["sha256"]:
            problems.append(f"corrupt: {artifact['filename']}")

    have = {a["name"]: a["version"] for a in manifest["artifacts"] if a["kind"] == "wheel"}
    for name, version in expected_pins.items():
        if have.get(name) != version:
            problems.append(f"pin drift: {name} wants {version}, vendored {have.get(name)}")

    for required in ("pyodide.js", "pyodide.asm.wasm", "python_stdlib.zip"):
        if not (VENDOR / "pyodide" / required).exists():
            problems.append(f"missing runtime file: {required}")

    for problem in problems:
        print(f"  ✗ {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"  ✓ vendor tree verified ({len(manifest['artifacts'])} artifacts)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-phx", action="store_true", help="also vendor the PHX write path (stretch goal)"
    )
    parser.add_argument(
        "--pyodide-version",
        default=PYODIDE_VERSION,
        help="Pyodide release to vendor (0.28+ cannot parse on SketchUp 2022's Chromium 88)",
    )
    parser.add_argument("--check", action="store_true", help="verify an existing tree, no network")
    args = parser.parse_args()

    if args.check:
        return check(args.with_phx)

    pins = required_wheels() | (PHX_WHEELS if args.with_phx else {})
    VENDOR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True) as client:
        print(f"pyodide-core {args.pyodide_version}")
        artifacts = [vendor_runtime(client, args.pyodide_version)]
        print(f"wheels ({len(pins)} pinned)")
        artifacts += vendor_wheels(client, pins)
    report(write_manifest(artifacts, args.with_phx, args.pyodide_version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
