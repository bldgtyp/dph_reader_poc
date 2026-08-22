# /// script
# requires-python = ">=3.11"
# ///
"""DesignPH-PLUS POC — assemble the extension into an installable `.rbz`.

An `.rbz` is a plain zip with a different extension; SketchUp's *Extensions > Install Extension…*
unpacks it into the user's `Plugins/` folder. Promoted from `planning/spikes/pyodide/build_rbz.py`
with one addition: the translator now ships too, and staleness is made structurally impossible.

Five jobs:

  1. syntax-check every `.rb` (SketchUp 2022 runs Ruby 2.7 — `AGENTS.md`)
  2. zip `poc/py/dph_translator/` into the payload, so the runtime installs it by the **same
     `zipfile` unpack** as the eight wheels — one mechanism, no packaging change at integration
  3. trim the vendored runtime to what the browser actually loads, and stage it
  4. record `build_info.json` inside the extension: sizes, the Pyodide pin, and the translator's
     source hash. The dialog reads it, so the self-test verdict carries real numbers rather than
     prose
  5. report **both** sizes. A compressed download size is not a bundle size: Phase 2 budgeted
     ≈8.1 MB from tarball sizes and the install footprint was 15.3 MB. The user feels the second one

`--check` recomputes the translator's source hash and compares it against what is staged. That is
the "tests passed on code the `.rbz` doesn't contain" failure mode, removed rather than watched for
(POC-1 §4.1).

Usage:
    uv run poc/tools/build_rbz.py
    uv run poc/tools/build_rbz.py --check       # is the staged payload current?
    uv run poc/tools/build_rbz.py --install     # also copy into SketchUp 2022
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
POC = HERE.parent
REPO = POC.parent
EXT = POC / "ext"
VENDOR = POC / "vendor"
DIST = POC / "dist"
TRANSLATOR = POC / "py" / "dph_translator"
NAME = "dph_plus_poc"
STAGED_VENDOR = EXT / NAME / "vendor"
BUILD_INFO = EXT / NAME / "build_info.json"
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

#: Never ship these, whatever a lint or test run leaves lying around. `__pycache__` is the real
#: offender: running the suite against `html/boot.py` writes a `.pyc` beside it, and a
#: "does not start with a dot" filter puts 12 KB of stale bytecode into the `.rbz` — inflating the
#: two size numbers this tool exists to report.
ARCHIVE_SKIP_DIRS = {"__pycache__", ".git", ".ruff_cache", ".pytest_cache"}
ARCHIVE_SKIP_SUFFIXES = {".pyc", ".pyo"}

#: A fixed timestamp makes the translator zip byte-reproducible, so its hash tracks the *source*
#: and not the clock.
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

#: Deflate level. Measured on this tree: level 9 takes 1.94 s and saves 40 KB (0.6 %) over level 6's
#: 0.54 s — because 18 of the 20 MB is already-compressed payload (`python_stdlib.zip`, the `.wasm`,
#: eight `.whl`). Max compression buys nothing here and the build runs on every `make ci`.
COMPRESS_LEVEL = 6

#: The `.rbz` size is recorded inside the `.rbz`, so writing it changes it. Rebuild until the
#: recorded number matches the file — it converges in two or three passes.
MAX_SIZE_PASSES = 6


def syntax_check() -> int:
    """`ruby -c` every file. A syntax error only surfaces at SketchUp load time otherwise."""
    files = sorted(EXT.rglob("*.rb"))
    for path in files:
        result = subprocess.run(["ruby", "-c", str(path)], capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout + result.stderr, file=sys.stderr)
            raise SystemExit(f"ruby -c failed: {path.relative_to(POC)}")
    return len(files)


def translator_sources() -> list[Path]:
    return sorted(p for p in TRANSLATOR.rglob("*.py") if "__pycache__" not in p.parts)


def translator_hash() -> str:
    """Hash of the translator's source, path-qualified so a rename is a change."""
    digest = hashlib.sha256()
    for path in translator_sources():
        digest.update(str(path.relative_to(TRANSLATOR)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def stage_translator(destination: Path) -> tuple[int, int]:
    """Zip the translator package for `zipfile` unpack into Pyodide's site-packages."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    sources = translator_sources()
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=COMPRESS_LEVEL) as bundle:
        for path in sources:
            arcname = str(Path(TRANSLATOR.name) / path.relative_to(TRANSLATOR))
            info = zipfile.ZipInfo(arcname, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, path.read_bytes())
    return len(sources), destination.stat().st_size


def stage_vendor(destination: Path) -> tuple[int, int]:
    """Copy the trimmed runtime, the wheels and the translator into the extension tree."""
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

    modules, translator_bytes = stage_translator(destination / "dph_translator.zip")
    print(f"  translator staged: {modules} modules, {translator_bytes / 1e3:.1f} KB")
    files += 1
    size += translator_bytes

    # The dialog reads the pinned wheel list out of this rather than repeating it.
    shutil.copy2(VENDOR / "manifest.json", destination / "manifest.json")
    return files + 1, size


def write_build_info(rbz_bytes: int, installed_bytes: int) -> None:
    manifest = json.loads((STAGED_VENDOR / "manifest.json").read_text())
    BUILD_INFO.write_text(
        json.dumps(
            {
                "built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "pyodide_version": manifest["pyodide_version"],
                "translator_sha256": translator_hash(),
                "installed_bytes": installed_bytes,
                "rbz_bytes": rbz_bytes,
            },
            indent=2,
        )
        + "\n"
    )


def shippable(path: Path, root: Path) -> bool:
    """Is this a file the extension should carry?"""
    if not path.is_file() or path.name.startswith("."):
        return False
    if path.suffix in ARCHIVE_SKIP_SUFFIXES:
        return False
    return not ARCHIVE_SKIP_DIRS.intersection(path.relative_to(root).parts)


def write_archive() -> int:
    DIST.mkdir(exist_ok=True)
    archive = DIST / f"{NAME}.rbz"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=COMPRESS_LEVEL) as bundle:
        for path in sorted(EXT.rglob("*")):
            if shippable(path, EXT):
                bundle.write(path, path.relative_to(EXT))
    return archive.stat().st_size


def installed_size() -> int:
    """What lands in the user's Plugins folder — the same file set the archive carries."""
    return sum(p.stat().st_size for p in (EXT / NAME).rglob("*") if shippable(p, EXT))


def check_staged() -> int:
    """Is the staged payload built from the translator source that is on disk right now?"""
    if not BUILD_INFO.exists():
        print("  ✗ extension not built — run build_rbz.py", file=sys.stderr)
        return 1
    recorded = json.loads(BUILD_INFO.read_text()).get("translator_sha256")
    current = translator_hash()
    if recorded != current:
        print(
            f"  ✗ staged translator is stale: built from {str(recorded)[:12]}, source is now {current[:12]}",
            file=sys.stderr,
        )
        return 1
    print(f"  ✓ staged translator matches poc/py/dph_translator ({current[:12]})")
    return 0


def build(install: bool) -> int:
    if not (VENDOR / "pyodide" / "pyodide.js").exists():
        raise SystemExit("vendor tree missing — run vendor_payload.py first")

    print(f"  ruby -c: {syntax_check()} files OK")
    staged, staged_bytes = stage_vendor(STAGED_VENDOR)
    print(f"  vendor staged: {staged} files, {staged_bytes / 1e6:.2f} MB uncompressed")

    # The recorded size is inside the artifact it describes, so iterate to a fixed point.
    rbz_bytes = 0
    for _pass in range(MAX_SIZE_PASSES):
        write_build_info(rbz_bytes, installed_size())
        actual = write_archive()
        if actual == rbz_bytes:
            break
        rbz_bytes = actual
    else:
        print(f"  ! rbz_bytes did not converge in {MAX_SIZE_PASSES} passes", file=sys.stderr)

    print("  built {} — {:.2f} MB".format((DIST / (NAME + ".rbz")).relative_to(REPO), rbz_bytes / 1e6))
    print(f"        installed footprint: {installed_size() / 1e6:.2f} MB — the number the user feels")
    print("        (Phase 3's micropip-free final: 6.66 MB .rbz, 20.7 MB installed)")

    if install:
        # Install by copy rather than through SketchUp's installer: the loader stub has to land
        # directly in Plugins/ and the tree beside it, which is exactly what the zip already is.
        if not SKETCHUP_PLUGINS.exists():
            raise SystemExit(f"no SketchUp Plugins folder at {SKETCHUP_PLUGINS}")
        target = SKETCHUP_PLUGINS / NAME
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            EXT / NAME, target, ignore=shutil.ignore_patterns(*ARCHIVE_SKIP_DIRS, "*.pyc", "*.pyo")
        )
        shutil.copy2(EXT / f"{NAME}.rb", SKETCHUP_PLUGINS / f"{NAME}.rb")
        print(f"  installed into {SKETCHUP_PLUGINS}")
        print("  restart SketchUp, then: Extensions > DesignPH-PLUS POC")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the staged payload is current")
    parser.add_argument("--install", action="store_true", help="also copy the extension into SketchUp 2022")
    args = parser.parse_args()
    return check_staged() if args.check else build(args.install)


if __name__ == "__main__":
    sys.exit(main())
