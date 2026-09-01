#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Stage the Spike L-B copies (⚠ client data — everything lands in gitignored `_private/`).

    uv run planning/spikes/library-import/prep_copies_b.py

Same contract as L-A's `prep_copies.py` (copies of the headless staged copies, `LIBIMPORT`
in every name, refuse-to-overwrite), but APPENDS an L-B section to `_private/MANIFEST.md`
instead of rewriting it — the L-A table is evidence and stays.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "headless" / "_private" / "corpus"
DEST = HERE / "_private" / "copies"

#: destination name -> (source, purpose)
COPIES = {
    "2414_BluffReach_LIBIMPORT-lb.skp": (
        "2414_Bluff Reach_COPY.skp",
        "L-B primary: full PHN payload write (8 assemblies + 9 frames + 2 glazings), "
        "calculator grading, one assignment, PPP export under stable 2.2.29",
    ),
    "250703_Linde_LIBIMPORT-lb.skp": (
        "250703 - Linde Residence_COPY.skp",
        "L-B second model (n>1 rule): wrapped-base64 frames_ud/glazing_ud style must be "
        "preserved; PHN data written into the designPH model of the SAME building",
    ),
    "2414_BluffReach_LIBIMPORT-xc.skp": (
        "2414_Bluff Reach_COPY.skp",
        "L-B extra-column probe: DPHLB.write!(:probe) appends a foreign :phn_id column to "
        "assemblies_calc — does designPH still read the table, and does the column survive "
        "its save? (the update-key question)",
    ),
}

MARKER_LINE = "## `copies/` — the L-B working copies"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    for name, (src_name, purpose) in COPIES.items():
        src = SRC / src_name
        dst = DEST / name
        if not src.exists():
            raise SystemExit(f"source missing: {src} — stage the headless corpus first")
        if dst.exists():
            print(f"kept    {name} (exists — never overwrite a staged copy)")
        else:
            shutil.copy2(src, dst)
            print(f"staged  {name}")
        rows.append(
            f"| `{name}` | {dst.stat().st_size:,} | `{sha256(dst)[:16]}` | `{src_name}` | {purpose} |"
        )

    manifest = HERE / "_private" / "MANIFEST.md"
    text = manifest.read_text() if manifest.exists() else "# MANIFEST\n"
    section = f"""
{MARKER_LINE} (staged {date.today().isoformat()} by `prep_copies_b.py`)

Same rules as the L-A table above. Ed's sessions **Save As** (`*-post.skp`); pristine copies
are the diff baselines. Payload: `payload/lb_payload.json`; expectations:
`payload/lb_expectations.md`; PHN source: `phn/linde_phn_library.json`.

| file | bytes | sha256[:16] | source (headless `_private/corpus/`) | purpose |
|---|---:|---|---|---|
{chr(10).join(rows)}
"""
    if MARKER_LINE in text:
        print("manifest: L-B section already present — not rewritten (delete it to refresh)")
    else:
        manifest.write_text(text.rstrip() + "\n" + section)
        print(f"manifest -> {manifest} (L-B section appended)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
