# Pyodide inside `HtmlDialog`

CPython compiled to WebAssembly, running in SketchUp's embedded browser. This is the **decided
runtime** for DesignPH-PLUS (PRD §7.1), proven end to end in SketchUp 2022 on 2026-08-19.

Read [`SKETCHUP_RUNTIME.md`](SKETCHUP_RUNTIME.md) first — the host's engine version and its
threading rules are what constrain everything here.

---

## 1. The short version

| | |
|---|---|
| Runtime | **Pyodide 0.24.1** — CPython **3.11.3**, Emscripten 3.1.45, wasm32 |
| Why that version | SketchUp 2022's Chromium 88. Nothing newer runs. See §2 |
| Payload | 8 pure wheels, unpacked with `zipfile`. **No `micropip`** |
| Loaded from | `http://127.0.0.1` served by the extension. **Never `file://`** |
| Cold start | **2.6 s** to `import honeybee_ph` + a round-tripped model |
| Bundle | **6.66 MB** `.rbz`, 20.7 MB installed |
| Peak WASM heap | 28.8 MB (a 1441-face model; 28.8 MB at rest too) |

## 2. ⚠ The version ceiling — the hardest constraint in the project

**The dialog's Chromium sets the newest Pyodide you can use, and the oldest SketchUp you support
sets the Chromium.** SketchUp 2022 is Chromium 88 (January 2021).

Measured against a real Chromium 88 snapshot, not inferred:

| Pyodide | Result on Chromium 88 | Mechanism |
|---|---|---|
| 314.0.5 (CPython 3.14) | ✗ `SyntaxError: Unexpected token '{'` | 66 ES2022 `static { }` blocks — Chromium **94** |
| 0.28.3 | ✗ same | 64 `static { }` blocks |
| 0.27.7 | ✗ `CompileError: invalid value type 'externref'` | WebAssembly **reference types** — Chromium **96** |
| 0.26.4 | ✗ boot never settles | not diagnosed further |
| 0.25.1 | ✗ boot never settles | not diagnosed further |
| **0.24.1** | ✅ **full stack, cold start 3.5 s** | — |
| 0.22.1 | ✅ (spot-checked) | — |

✅ **Boot time is stable in production, measured over four live SketchUp runs** (POC-4, 2026-08-21):
2542, 2573, 2574 and 2589 ms cold — a spread of **47 ms**. Pyodide is not the variable in this
system; the Ruby collector walk is, and it is 60–79 % of the wall clock
(`SKETCHUP_RUNTIME.md` §12).

Two independent gates, and syntax is only the first: `probe_pyodide_syntax.py` brackets the *parse*
break at 0.27.7/0.28.3, but 0.27.7 still dies at wasm instantiation. **A release that parses is not a
release that runs.** Always finish the check in a real engine.

Tooling for redoing this on another SketchUp version:

```bash
uv run planning/spikes/pyodide/probe_pyodide_syntax.py --chromium 88   # syntax bracket
uv run planning/spikes/pyodide/vendor_payload.py --pyodide-version 0.24.1
uv run planning/spikes/pyodide/verify_in_chrome.py --mode http --chrome <chromium-88-binary>
```

⚠ **Raising the Pyodide pin means raising the supported SketchUp floor.** That is a product decision
with a technical price, unresolved — PRD §7.4 and `planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_results.md` §3.6.

## 3. What `pyodide-core` actually contains

The shippable artifact is `pyodide-core-<version>.tar.bz2` from the GitHub release — **not** the
full distribution, which is ~350 MB of build output.

`pyodide-core-0.24.1`, 7 files:

| File | Bytes | Needed? |
|---|--:|---|
| `pyodide.asm.wasm` | 8,995,509 | yes |
| `python_stdlib.zip` | 8,882,369 | yes |
| `pyodide.asm.js` | 1,157,891 | yes |
| `pyodide-lock.json` | 84,412 | yes — fetched at boot even with no packages |
| `pyodide.js` | 17,417 | yes — the classic-script entry point |
| `pyodide.mjs` | 17,133 | no |
| `package.json` | 3,070 | no |

(314.0.5's core has 13 files, adding `.d.ts` declarations and Windows/Unix CLI shims — all
droppable. `build_rbz.py` has the skip list.)

⚠ **`pyodide-core` ships no Python packages at all.** There is no `micropip` on board, so something
has to install the payload — see §4.

## 4. Installing the payload: unpack, don't resolve

**`micropip` is not shipped, deliberately.**

Phase 2 planned to install through `micropip.install(..., deps=False)` and keep a `zipfile` unpack
"in reserve". Phase 3 inverted that:

- `micropip` is **coupled to the Pyodide release**. micropip 0.11.1 on Pyodide 0.24.1 raises
  `ImportError: cannot import name 'lockfileBaseUrl' from 'pyodide_js'` before doing any work.
- Every wheel in the payload is `py3-none-any`. **Unpacking *is* installing** — there is nothing for
  a resolver to resolve.
- Carrying it cost 0.2 MB and put a Python traceback in front of the user on every single run.

The installer, in full:

```python
import sysconfig, zipfile, sys, importlib
target = sysconfig.get_paths()['purelib']
for path in wheel_paths:                       # written into Pyodide's FS by JS
    with zipfile.ZipFile(path) as archive:
        archive.extractall(target)
sys.path_importer_cache.clear()
importlib.invalidate_caches()
```

Unpacking a wheel also lays down its `.dist-info`, so `importlib.metadata.version()` still reports
correct versions. (The honeybee/ladybug packages define **no `__version__` attribute** — read
metadata, not the module.)

`deps=False` was load-bearing under the micropip plan and is simply moot now: nothing resolves
dependencies, so `honeybee-core`'s declared `honeybee-schema` → `pydantic` → Rust `pydantic-core`
never enters the picture. See [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §2.

## 5. Boot sequence and asset order

Observed in SketchUp, served over loopback:

```
html/index.html            6,900     ← set_url target
vendor/pyodide/pyodide.js 17,417     ← classic <script src>
html/spike.js             15,410
vendor/manifest.json       5,198     ← our pinned payload list
── loadPyodide() ──
vendor/pyodide/pyodide.asm.js     1,157,891
vendor/pyodide/pyodide-lock.json     84,412
vendor/pyodide/python_stdlib.zip  8,882,369
vendor/pyodide/pyodide.asm.wasm   8,995,509
── 8 wheels, ~1.5 MB total ──
html/spike.py             14,706
```

⚠ The runtime fetches its own assets through **its own** `fetch` calls, which your code never sees.
That is why `file://` cannot be rescued by wrapping your own loader (§4.3 of the SketchUp notes).

## 6. Measured performance

**SketchUp 2022, macOS arm64, Pyodide 0.24.1** — the run of 2026-08-19 21:39.

| Stage | Time |
|---|--:|
| Pyodide runtime ready | 1.38 s |
| 8 wheels fetched over loopback | +0.23 s |
| unpacked and installed | +0.16 s |
| imports + `Room.from_box` round trip | +0.84 s |
| **total cold start** | **2.63 s** |
| warm re-run (same runtime, build another model) | **5 ms** |

Import cost is concentrated in one place:

| Module | ms |
|---|--:|
| `ladybug_geometry.geometry3d.pointvector` | 120.8 |
| `ladybug.location` | 109.5 |
| **`honeybee.room`** | **587.9** |
| `honeybee.model`, `honeybee_energy.lib.constructionsets`, `honeybee_ph` | ~0 (already pulled in) |

**Keep the dialog alive between exports.** A warm re-run is 5 ms against a 2.6 s cold start.

### Pyodide vs native CPython

Same `spike.py`, 1441 synthetic faces:

| Operation | Pyodide (modern Chrome) | CPython 3.14 | Ratio |
|---|--:|--:|--:|
| `Face3D` + `Face` × 1441 | 45 ms | 18 ms | 2.5× |
| `Model.to_dict` | 58 ms | 44 ms | 1.3× |
| `json.dumps` (2.14 MB) | 38 ms | 21 ms | 1.8× |
| **export path total** | **187 ms** | **108 ms** | **1.7×** |
| `Model.from_dict` (verification only) | 18.2 s | 9.0 s | 2.0× |

**Pyodide is ~2× slower than native, not an order of magnitude.** The HBJSON it produces is
**byte-identical** — 2,139,675 bytes both ways.

⚠ On Chromium 88 the same 1441-face `Model.from_dict` takes **36 s**. That is an *upstream*
honeybee-ph cost amplified by an old engine, on a path v1 never takes — writing is 139 ms. See
[`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §5.

### Memory

| | |
|---|--:|
| WASM heap at rest | 28.8 MB |
| WASM heap, 1441-face model | 28.8 MB (0.24.1); 74.9 MB (314.0.5) |
| JS heap | 41–82 MB |
| `jsHeapSizeLimit` reported | 3.6 GB |

No memory pressure was observed alongside a loaded SketchUp model.

## 7. Calling into Python from JS

Cross the boundary as **JSON strings**, not proxies:

```javascript
pyodide.globals.set("_arg", JSON.stringify(argument));
const text = await pyodide.runPythonAsync(
  "import json, spike\n" +
  "json.dumps(spike.some_function(json.loads(_arg)))"
);
return JSON.parse(text);
```

Proxies leak — they need an explicit `.destroy()` — and a JSON string is the same format the Ruby
bridge uses, so one serialisation spans all three languages.

⚠ **A Pyodide failure does not always reject.** A wasm `CompileError` can leave the `loadPyodide`
promise pending forever, turning a clear negative into a timeout. Race any boot against a deadline.

⚠ **Report Python errors, never let them cross the boundary as exceptions** — the traceback is lost.
Catch, format `f"{type(e).__name__}: {e}"`, and return it as data.

## 8. Licensing of the runtime itself

Pyodide and `micropip` are **MPL-2.0**; CPython is PSF. The copyleft exposure comes from the
*payload*, not the runtime — see [`HONEYBEE_STACK.md`](HONEYBEE_STACK.md) §7 and
`planning/01_sketchup-export/feasibility/RESULTS/PHASE-3_licence-question.md`.

## 9. Reproducing the setup

```bash
uv run planning/spikes/pyodide/vendor_payload.py            # pinned + sha256-verified from PyPI
uv run planning/spikes/pyodide/build_rbz.py --install       # trim, zip, copy into SketchUp
uv run planning/spikes/pyodide/verify_in_chrome.py          # 4 configurations over CDP
```

`verify_in_chrome.py --mode`: `file` (fails, by design), `file-permissive` (identifies the missing
capability), `http` (the real architecture), `extension` (the extension's own page against a stub
`sketchup` host).

⚠ `extension` mode serves the **staged** copy inside the extension tree, not `vendor/`. Re-vendor
without rebuilding and they drift; the driver now refuses rather than blaming the new runtime for a
stale one's failure.
