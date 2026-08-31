# DesignPH-PLUS POC — the verification gate.
#
#     make ci        everything the agent can prove without SketchUp
#     make ed        build + install, ready for a SketchUp session
#
# ⚠ `make ci` is not "it works". It is "it works on the same *engine*". The one thing no target
# here can reach is `HtmlDialog` itself — its threading and its payload limits — which is why
# every phase still ends with an Ed run from a staged runbook.

PY := $(CURDIR)/py/.venv/bin/python

.PHONY: ci ed venv test lint typecheck ruby-test validate vendor build verify identity clean

## Everything provable offline, in dependency order.
ci: lint typecheck test ruby-test validate build verify

## Python 3.11 — Pyodide 0.24.1's CPython, exactly.
##
## The wheel pins come from `py/pyproject.toml` and nowhere else; `tools/vendor_payload.py` reads
## the same list, so the test venv and the shipped `.rbz` cannot drift apart.
##
## `--no-deps` throughout: honeybee-core *declares* honeybee-schema → pydantic → pydantic-core
## (Rust, no pure wheel) and never imports it outside its `cli/` modules. Resolving the declared
## closure fails; the imports it actually makes are pure.
venv:
	cd py && uv venv --python 3.11 .venv
	cd py && VIRTUAL_ENV=.venv uv pip install --no-deps -r pyproject.toml
	cd py && VIRTUAL_ENV=.venv uv pip install --no-deps -e .
	cd py && VIRTUAL_ENV=.venv uv pip install pytest ruff mypy

test:
	cd py && $(PY) -m pytest

## `ruff.toml` sits at `pocs/01_sketchup-export/` so the tool scripts are held to the same standard as the package.
lint:
	$(PY) -m ruff check py tools ext/dph_plus_poc/html/boot.py
	$(PY) -m ruff format --check py tools ext/dph_plus_poc/html/boot.py

## All four Ruby suites run the real code against a stub SketchUp API — see `ext/tests/sketchup_stub.rb`
## for what that can and cannot prove. The server suite catches load-time errors and every HTTP
## property but not the threading; the collector suite catches every rule that loses data silently
## but is not evidence about designPH; the gate suite covers both refusal tables, including the
## designPH 3.x row nobody has a file for; the integration suite drives a whole export and reads the
## message boxes back, which is how "failures surface visibly" becomes testable. The corpus
## reconciliation is what carries evidential weight, and it needs real models:
## `ext/tests/run_collector_console.rb` then `tools/check_extraction.py`.
ruby-test:
	ruby ext/tests/test_static_server.rb
	ruby ext/tests/test_collector.rb
	ruby ext/tests/test_gate.rb
	ruby ext/tests/test_integration.rb

typecheck:
	cd py && $(PY) -m mypy

## Validates translator output against published honeybee-schema, in a SEPARATE interpreter: the
## translator's venv holds exactly the eight vendored wheels, and `honeybee-schema` is deliberately
## not one of them. The gate is scoped to geometry/PH errors — `properties.energy.*` failures are
## upstream drift we cannot fix from here. See the tool's docstring.
validate:
	uv run tools/validate_output.py

vendor:
	uv run tools/vendor_payload.py

build:
	uv run tools/build_rbz.py

## Drives the built page in a real Chromium 88 — the engine SketchUp 2022 embeds. Refuses any
## other major version; a pass on a modern engine is a false green.
verify:
	uv run tools/verify_in_chrome.py

## POC-4's byte-identity check: the SAME extraction translated under CPython 3.11 and under
## Chromium 88 must produce byte-identical HBJSON, on every captured fixture. Deliberately NOT part
## of `ci` — it boots Pyodide once per fixture (~5 minutes for the corpus) and it needs
## `_private/fixtures/`, which is gitignored client data. Run it per phase, not per edit.
identity: build
	uv run tools/byte_identity.py

ed: build
	uv run tools/build_rbz.py --install

clean:
	rm -rf dist ext/dph_plus_poc/vendor ext/dph_plus_poc/build_info.json
