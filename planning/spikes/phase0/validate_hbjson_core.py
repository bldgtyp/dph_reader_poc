#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.11.*"
# dependencies = ["honeybee-schema==1.53.1", "pydantic<2"]
# ///
"""Phase 0 §0.4 step 1 — validate the reference HBJSON against `honeybee-schema` 1.53.1.

Pinned to the schema version the reference file declares (`"version": "1.53.1"`), and to
pydantic 1.x because honeybee-schema 1.53.x is written against the pydantic-v1 API
(`Field(regex=...)`, removed in pydantic 2).

Writes a JSON verdict so the report generator can consume it without re-installing this
dependency set.

Usage
-----
    uv run validate_hbjson_core.py MODEL.hbjson --out verdict.json
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from honeybee_schema.model import Model
from pydantic import ValidationError

# The raw error list runs to thousands of entries — pydantic 1 expands every union branch, so one
# non-conforming material reports once per candidate type. Only a sample is written out verbatim,
# but every *summary* below is computed from the full list. Nothing that a reader would take as a
# categorical claim is derived from the sample.
MAX_SAMPLED_ERRORS = 40

# Path segments that mark an error as touching geometry or the PH extension, as opposed to the
# honeybee-energy payloads. v1 writes the former and not the latter, so the distinction decides
# whether a failure here is relevant to our acceptance criteria at all.
CORE_SEGMENTS = frozenset(
    {"geometry", "boundary_condition", "faces", "apertures", "doors", "orphaned_shades", "ph"}
)


def object_path(loc: tuple) -> str:
    """Collapse an error location to the object that failed, dropping the field and union branch.

    The path is cut after the *last* list index, which is what identifies an object within a
    collection: `properties.energy.constructions.7.materials.2.density` -> `...constructions.7.materials.2`.
    """
    parts = [str(p) for p in loc]
    indices = [i for i, p in enumerate(parts) if p.isdigit()]
    return ".".join(parts[: indices[-1] + 1 if indices else len(parts)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("hbjson", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = json.loads(args.hbjson.read_text())
    verdict: dict[str, object] = {
        "validator": "honeybee-schema==1.53.1 (pydantic 1.x)",
        "file": str(args.hbjson),
        "declared_version": data.get("version"),
    }

    try:
        Model.parse_obj(data)
        verdict |= {
            "valid": True,
            "error_count": 0,
            "failing_object_count": 0,
            "failing_containers": {},
            "errors_touching_core_or_ph": 0,
            "sampled_errors": [],
        }
    except ValidationError as exc:
        errors = exc.errors()
        objects = {object_path(e["loc"]) for e in errors}
        containers = collections.Counter(re.sub(r"\.\d+", "[]", o) for o in objects)
        core_hits = [
            ".".join(str(p) for p in e["loc"])
            for e in errors
            if CORE_SEGMENTS & {str(p) for p in e["loc"]}
        ]
        verdict |= {
            "valid": False,
            # Everything below is computed from the FULL error list, not the sample.
            "error_count": len(errors),
            "failing_object_count": len(objects),
            "failing_containers": dict(containers.most_common()),
            "errors_touching_core_or_ph": len(core_hits),
            "sample_of_errors_touching_core_or_ph": core_hits[:10],
            "sampled_errors": [
                {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"], "type": e["type"]}
                for e in errors[:MAX_SAMPLED_ERRORS]
            ],
            "sampled_error_note": (
                f"sampled_errors holds the first {MAX_SAMPLED_ERRORS} of {len(errors)} raw errors, "
                "for eyeballing only. Every summary field is computed from all of them."
            ),
        }

    args.out.write_text(json.dumps(verdict, indent=2))
    print(
        f"valid={verdict['valid']}  raw errors={verdict['error_count']}  "
        f"failing objects={verdict['failing_object_count']}  "
        f"touching geometry/PH={verdict['errors_touching_core_or_ph']}  -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
