"""The one entry point into the translator.

**Fixed by `planning/POC/POC-1_runtime-shell.md` §4.1 and not to be reinvented per phase:**

    dph_translator.entry.translate_json(payload: str) -> str

JSON string in, JSON string out -- `{"hbjson": str, "report": obj, "verdict": obj}` serialised.
No proxies cross the wasm boundary in either direction, and the same serialisation format spans
Ruby, JS and Python, so one bug in one place is the worst that can happen.

`translate_json` wraps the typed `translate.translate()`; tests call the typed one, the runtime
calls this. A failure is **returned**, never raised: an exception crossing the Pyodide boundary
loses its traceback, and the dialog needs a verdict either way.
"""

from __future__ import annotations

import json
from typing import Any

from . import __version__
from .build import Translation, translate
from .contract import ContractError, parse
from .report import failure

__all__ = ["translate_json", "__version__"]


def _error(label: str, message: str) -> str:
    return json.dumps({"hbjson": "", "report": {"error": message}, "verdict": failure(label, message)})


def translate_json(payload: str) -> str:
    """Translate one extraction document. Always returns a well-formed result string."""
    try:
        document: Any = json.loads(payload)
    except ValueError as error:
        return _error("payload is JSON", str(error))

    try:
        extraction = parse(document)
    except ContractError as error:
        return _error("payload matches the contract", str(error))

    try:
        result: Translation = translate(extraction)
    except Exception as error:  # noqa: BLE001 -- the dialog needs a verdict, not a traceback
        return _error("translation runs", f"{type(error).__name__}: {error}")

    return json.dumps(result.to_dict())
