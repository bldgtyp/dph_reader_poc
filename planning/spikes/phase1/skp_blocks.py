#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Group a `.skp`'s attribute records into one block per attribute dictionary instance.

`00_Context/tools/skp_attr_dump.py` reads every attribute record in a model and tallies them by
key. That is enough to count how often a key appears and is what the Phase 0 baseline used -- but
it cannot say which keys sit on the *same* entity, so Phase 0 had to infer the
`areaGroupID` -> `tempZoneID` pairing from population arithmetic rather than observe it.

The records are laid out in file order as: a dictionary-name record, then that dictionary's keys,
then the next dictionary-name record. So the run of key records between two dictionary-name markers
*is* one entity's dictionary. Grouping on that boundary recovers per-entity co-occurrence, which is
what Phase 1 sections 1.1 and 1.3 need.

CAVEAT, and it is the whole reason this does not close Phase 1 on its own: `model.dat` accumulates
historical state. A block is one dictionary instance that was written at some point -- not
necessarily one *live* entity. Co-occurrence *within* a block is real (those keys were written
together on one entity); the population of blocks is not a census of the current model. For live
state use the BT Attribute Inspector.

The binary parsing itself is not reimplemented here. It is imported from `skp_attr_dump.py`, which
is the canonical reader -- notably its `re.DOTALL`, without which any 10-character key name is
silently dropped.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

_DUMPER_PATH = Path(__file__).resolve().parents[3] / "00_Context" / "tools" / "skp_attr_dump.py"


def _load_dumper() -> Any:
    """Import `skp_attr_dump.py` by path -- it is a script, not an installed module."""
    spec = importlib.util.spec_from_file_location("skp_attr_dump", _DUMPER_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - path is repo-fixed
        raise ImportError(f"cannot load the canonical reader at {_DUMPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["skp_attr_dump"] = module  # dataclasses needs the module registered
    spec.loader.exec_module(module)
    return module


_dumper = _load_dumper()
read_model_dat = _dumper.read_model_dat


@dataclass(frozen=True)
class Block:
    """One attribute dictionary instance: the keys written together on one entity."""

    dict_name: str
    offset: int
    values: dict[str, Any]
    types: dict[str, str]

    @property
    def keys(self) -> frozenset[str]:
        """Every key present, whether or not it holds a value."""
        return frozenset(self.values)

    def non_nil(self, key: str) -> bool:
        """True when the key is present *and* carries a value.

        designPH writes nil placeholders freely, so presence alone means nothing --
        see CLAUDE.md, "a `*Auto` key that is present but nil is not evidence of anything".
        """
        return self.values.get(key) is not None


def read_blocks(path: Path, dict_name: str | None = None) -> list[Block]:
    """Read `path` and return its attribute-dictionary blocks in file order.

    Pass `dict_name` to keep only blocks of that dictionary (`"DesignPH_dict"`).
    """
    buf = read_model_dat(path)
    blocks: list[Block] = []
    current: Block | None = None

    for marker in _dumper.find_markers(buf):
        if marker.kind == "dict":
            if current is not None:
                blocks.append(current)
            current = Block(marker.name, marker.offset, {}, {})
        elif current is not None:
            type_name, value = _dumper.read_value(buf, marker.value_at)
            # A repeated key inside one block would mean the boundary is wrong; keep the first.
            current.values.setdefault(marker.name, value)
            current.types.setdefault(marker.name, type_name)

    if current is not None:
        blocks.append(current)

    if dict_name is not None:
        return [b for b in blocks if b.dict_name == dict_name]
    return blocks


def face_blocks(blocks: list[Block], face_keys: frozenset[str]) -> Iterator[Block]:
    """Yield the blocks that look like face-level data rather than model-level data.

    A model-level block carries the library tables (`assemblies_ud`, `layer_table_*`,
    `designPH_version`); a face-level block carries none of them. Discriminating on the
    key set rather than on a count keeps this honest when a model holds more than one
    model-level block -- Wellington holds two, one per designPH version that touched it.
    """
    for block in blocks:
        if block.keys & face_keys:
            yield block


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        found = read_blocks(Path(arg), "DesignPH_dict")
        print(f"{arg}: {len(found)} DesignPH_dict blocks")
