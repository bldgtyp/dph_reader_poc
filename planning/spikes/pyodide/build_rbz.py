# /// script
# requires-python = ">=3.11"
# ///
"""Phase 3 — assemble the spike extension into an installable `.rbz`.

An `.rbz` is a plain zip with a different extension; SketchUp's *Extensions > Install Extension…*
unpacks it into the user's `Plugins/` folder. This script does three jobs:

  1. syntax-checks every `.rb` (Ruby 2.7 is what SketchUp 2022 runs — see `AGENTS.md`)
  2. trims the vendored runtime to what the browser actually loads
  3. reports the bundle size against Phase 2 §2.5's ≈8 MB budget, which was quoted from
     *compressed download* sizes and is not the same number as a zip of the unpacked tree

Usage:
    uv run planning/spikes/pyodide/build_rbz.py
    uv run planning/spikes/pyodide/build_rbz.py --install    # also copy into SketchUp 2022
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EXT = HERE / "ext"
VENDOR = HERE / "vendor"
DIST = HERE / "dist"
NAME = "dph_plus_spike"
SKETCHUP_PLUGINS = Path.home() / "Library/Application Support/SketchUp 2022/SketchUp/Plugins"

#: Files inside `pyodide-core` the dialog never loads. `python.exe` alone is 1.4 MB of Windows CLI
#: shim, and the `.d.ts` files are TypeScript declarations for people writing against the API.
#: Dropping them is safe because the only entry point used is `pyodide.js` → `pyodide.asm.mjs`.
RUNTIME_SKIP = {
    "python",
    "python.bat",
    "python.exe",
    "python_cli_entry.mjs",
    "pyodide.d.ts",
    "ffi.d.ts",
    "package.json",
}


def syntax_check() -> None:
    """`ruby -c` every file. A syntax error only surfaces at SketchUp load time otherwise."""
    for path in sorted(EXT.rglob("*.rb")):
        result = subprocess.run(["ruby", "-c", str(path)], capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout + result.stderr, file=sys.stderr)
            raise SystemExit(f"ruby -c failed: {path.relative_to(HERE)}")
    print(f"  ruby -c: {len(list(EXT.rglob('*.rb')))} files OK")


def stage_vendor(destination: Path) -> tuple[int, int]:
    """Copy the trimmed runtime and the wheels into the extension tree. Returns (files, bytes)."""
    if destination.exists():
        shutil.rmtree(destination)
    runtime = destination / "pyodide"
    runtime.mkdir(parents=True)
    files = 0
    size = 0
    for source in sorted((VENDOR / "pyodide").iterdir()):
        if not source.is_file() or source.name in RUNTIME_SKIP:
            continue
        shutil.copy2(source, runtime / source.name)
        files += 1
        size += source.stat().st_size

    wheels = destination / "wheels"
    wheels.mkdir(parents=True)
    for source in sorted((VENDOR / "wheels").glob("*.whl")):
        shutil.copy2(source, wheels / source.name)
        files += 1
        size += source.stat().st_size

    # The dialog reads the pinned wheel list out of this rather than repeating it.
    shutil.copy2(VENDOR / "manifest.json", destination / "manifest.json")
    files += 1
    return files, size


def build(install: bool) -> int:
    if not (VENDOR / "pyodide" / "pyodide.js").exists():
        raise SystemExit("vendor tree missing — run vendor_payload.py first")

    syntax_check()
    staged, staged_bytes = stage_vendor(EXT / NAME / "vendor")
    print(f"  vendor staged: {staged} files, {staged_bytes / 1e6:.2f} MB uncompressed")

    DIST.mkdir(exist_ok=True)
    archive = DIST / f"{NAME}.rbz"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(EXT.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                bundle.write(path, path.relative_to(EXT))

    print(f"  built {archive.relative_to(REPO)} — {archive.stat().st_size / 1e6:.2f} MB")
    print("        (Phase 2 §2.5 budgeted ≈8.1 MB from compressed download sizes)")

    if install:
        # Install by copy rather than through SketchUp's installer: the loader stub has to land
        # directly in Plugins/ and the tree beside it, which is exactly what the zip already is.
        if not SKETCHUP_PLUGINS.exists():
            raise SystemExit(f"no SketchUp Plugins folder at {SKETCHUP_PLUGINS}")
        target = SKETCHUP_PLUGINS / NAME
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(EXT / NAME, target)
        shutil.copy2(EXT / f"{NAME}.rb", SKETCHUP_PLUGINS / f"{NAME}.rb")
        print(f"  installed into {SKETCHUP_PLUGINS}")
        print("  restart SketchUp, then: Extensions > DesignPH-PLUS Spike")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install", action="store_true", help="also copy the extension into SketchUp 2022"
    )
    return build(parser.parse_args().install)


if __name__ == "__main__":
    sys.exit(main())
