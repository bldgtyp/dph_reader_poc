#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Stage the Spike L-A copies (⚠ client data — everything lands in gitignored `_private/`).

    uv run planning/spikes/library-import/prep_copies.py

Copies the already-staged headless corpus copies (themselves copies — hard rule 3 twice over)
into `_private/copies/` under names that carry the `LIBIMPORT` marker `write_library.rb`'s guard
requires, and (re)writes `_private/MANIFEST.md`. Refuses to overwrite an existing copy — a copy
Ed has already written into is evidence, not scratch.
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
    "2414_BluffReach_LIBIMPORT-a.skp": (
        "2414_Bluff Reach_COPY.skp",
        "timing (a): written in the designPH-DISABLED prep session, saved as `-a-written.skp`; "
        "the designPH session opens the written file cold",
    ),
    "2414_BluffReach_LIBIMPORT-b.skp": (
        "2414_Bluff Reach_COPY.skp",
        "timing (b): written live, SketchUp open, designPH dialog NOT yet opened this session",
    ),
    "2414_BluffReach_LIBIMPORT-c.skp": (
        "2414_Bluff Reach_COPY.skp",
        "timing (c): written live while the designPH dialog is already open — the hot swap",
    ),
    "adelphi_LIBIMPORT-g.skp": (
        "adelphi-designph_COPY.skp",
        "O-3 generation test: native assemblies_ud INSERT, plus DPHL.write!(:both, :create) "
        "to plant the other generation beside it",
    ),
}


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
    manifest.write_text(
        f"""# MANIFEST — Spike L-A scratch (⚠ CLIENT DATA, gitignored)

STAGED: {date.today().isoformat()} by `prep_copies.py`. Everything here is a **copy of a copy**
(sources are the headless spike's staged copies). Nothing is committed; nothing containing
`tracker_data` or an embedded filesystem path leaves this folder.

## `copies/` — the LIBIMPORT working copies

Names carry `LIBIMPORT` because `write_library.rb`'s guard refuses any model title without it.
⚠ Ed's sessions **Save As** new names (`*-written.skp`, `*-post.skp` per the runbook) — the
staged copies themselves stay pristine as the diff baselines.

| file | bytes | sha256[:16] | source (headless `_private/corpus/`) | purpose |
|---|---:|---|---|---|
{chr(10).join(rows)}

## `baseline/` — PRE-state reads of the staged copies

- `<name>.tables.json` — `dump_model_tables.py` live-state model-table dump (the O-6 “before”)
- `<name>.capture.json` — headless contract-v2 capture (the O-9 “before”; excludes
  `frames_ud`/`glazing_ud` by contract — that is what the tables dump is for)

## `rehearsal/` — offline rehearsal state (`rehearse.py`)

Regenerable. ⚠ A rehearsal is NOT a capture: it proves `write_library.rb`'s logic and
serialisation, not designPH's behaviour.

## `post/` — Ed-session outputs land here

Saved `.skp`s from the runbook sessions, their `.tables.json` / `.capture.json` reads, and the
diffs. Created as the runbook runs.
""")
    print(f"manifest -> {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
