# SketchUp as a Host Environment

What SketchUp actually gives an extension, and what it takes away. Everything here is **observed on
SketchUp Pro 2022 (22.0.353), macOS arm64 (`arm64-darwin20`)** unless marked otherwise, most of it
during Phase 3 (`planning/RESULTS/PHASE-3_results.md`).

Companion notes: [`PYODIDE_RUNTIME.md`](PYODIDE_RUNTIME.md) for what runs *inside* the dialog,
[`CONSTRAINTS.md`](CONSTRAINTS.md) for the short list of things that will stop you.

---

## 1. Two runtimes, one process

A SketchUp extension is **two languages in one process**, and almost every trap in this document
comes from the boundary between them.

| | Ruby side | Dialog side |
|---|---|---|
| Language | Ruby **2.7** (pinned to the SketchUp release) | JavaScript in **Chromium 88** (CEF 88.2.4) |
| Sees | the model, the filesystem, the menus | the DOM, `fetch`, WebAssembly |
| Cannot | render HTML, run WASM | touch the model or the filesystem |
| Talks by | `dialog.execute_script(js)` | `sketchup.<callback>(string)` |

Neither direction returns a value. A round trip has to be assembled by hand — see §5.

## 2. Ruby version and its consequences

**SketchUp 2022 ships Ruby 2.7.** The Ruby version is pinned to the SketchUp release and is not
configurable.

Not available, and each one parses fine in your head before failing at load time:

- endless methods — `def x = y` (Ruby 3.0)
- pattern matching — `case ... in` (3.0)
- `Hash#except` (3.0)
- rightward assignment, `Data.define`, and anything else 3.x

**Syntax-check every file before installing it:** `ruby -c FILE.rb`. macOS ships Ruby 2.6 at
`/usr/bin/ruby`, which is *stricter* than 2.7 — good enough as a gate, and it will not accept
anything 2.7 rejects.

## 3. Extension packaging

```
Plugins/
  my_extension.rb          ← loader stub. ONLY .rb files directly here are auto-loaded
  my_extension/            ← subfolders are NOT scanned
    main.rb
    html/
    vendor/
```

- SketchUp executes every `.rb` **directly inside** `Plugins/` at startup. Subfolders are ignored,
  so the convention is a stub plus a same-named folder, bridged by `SketchupExtension`. That is also
  what makes the extension appear in the Extension Manager so a user can disable it. designPH itself
  uses exactly this shape (`designPH.rb` + `designPH/`).
- An `.rbz` is a **plain zip** with a different extension. *Extensions → Install Extension…* unpacks
  it into `Plugins/`. Building one is `zipfile.ZipFile(..., ZIP_DEFLATED)`; installing by hand is a
  `cp -r` of the same tree.
- **Guard the menu-building code.** SketchUp re-runs the file when the extension is toggled in the
  Extension Manager, and unguarded `UI.menu(...).add_item` duplicates every entry.

  ```ruby
  unless defined?(@ui_built)
    # ... build menus ...
    @ui_built = true
  end
  ```

- The menu is registered as `UI.menu("Plugins")` but appears to the user under **Extensions**.
- **Persistent preferences** are `Sketchup.read_default(section, key, fallback)` /
  `Sketchup.write_default(section, key, value)`. The section is a reverse-DNS string of your
  choosing; the same string is also the `HtmlDialog`'s `:preferences_key`, which is what makes the
  dialog remember its size and position between runs.
- **A checkable menu item** needs a validation proc, not a stored boolean in the label:

  ```ruby
  item = menu.add_item("Save extraction JSON") { toggle_save_extraction }
  menu.set_validation_proc(item) { save_extraction? ? MF_CHECKED : MF_UNCHECKED }
  ```

  The proc is called each time the menu is opened, so the tick always reflects current state.
  `MF_CHECKED` / `MF_UNCHECKED` are globals SketchUp defines; a stub environment must define them
  or the file will not load.

Paths on macOS:

```
~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/
/Applications/SketchUp 2022/SketchUp.app/
```

## 4. `HtmlDialog` — the embedded browser

`UI::HtmlDialog` (SketchUp 2017+) is **Chromium Embedded Framework**, and its version is *not* the
Chrome on the user's machine. It is frozen at whatever CEF shipped with that SketchUp release.

### 4.1 Reading the engine version — do this before trusting any web API

```bash
plutil -p "/Applications/SketchUp 2022/SketchUp.app/Contents/Frameworks/\
Chromium Embedded Framework.framework/Resources/Info.plist"
```

| Key | Value on SketchUp 2022 |
|---|---|
| `CFBundleShortVersionString` | `88.2.4.0` |
| `SCMRevision` | `…refs/branch-heads/**4324**@{#2103}` |

Branch 4324 is **Chromium 88** — January 2021. Everything since Chromium 89 is unavailable:
top-level `await`, `.at()`, `Object.hasOwn`, `structuredClone`, class `static {}` blocks, RegExp
match indices, WebAssembly reference types, wasm SIMD.

⚠ **Only SketchUp 2022 has been measured.** Every SketchUp release ships a newer CEF, but the CEF
in 2021, 2023, 2024, 2025 and 2026 is **unknown and must be read the same way** before any claim is
made about it. Do not interpolate.

### 4.2 A matching Chromium can be downloaded and automated

This is the single biggest productivity finding of Phase 3. Rather than asking a human to click
through SketchUp for every hypothesis, fetch the same Chromium and drive it headlessly:

```bash
curl -sL -o chrome88.zip \
  https://commondatastorage.googleapis.com/chromium-browser-snapshots/Mac/827102/chrome-mac.zip
unzip -q chrome88.zip
./chrome-mac/Chromium.app/Contents/MacOS/Chromium --version   # → Chromium 88.0.4324.0
```

Drive it over the DevTools Protocol (`--remote-debugging-port`, plus `--remote-allow-origins=*`).
**Use `--headless`, not `--headless=new`** — the new mode only exists from Chrome 109.
`planning/spikes/pyodide/verify_in_chrome.py` does all of this.

### 4.3 `file://` is a dead end — confirmed inside SketchUp

`HtmlDialog#set_file` loads the page from `file://`, and **a `file://` page cannot fetch its own
assets**:

| Mechanism | On `file://` | Can it be shimmed? |
|---|---|---|
| `<script src="…">` classic | **works** | — |
| `fetch()` | blocked, `origin 'null'` | yes — and the shim does not help, see next row |
| `XMLHttpRequest` | blocked, same CORS rule | it *is* the shim; it fails identically |
| dynamic `import()` | blocked | **no.** Not a `fetch` call; not interceptable at any level |

The error is always the same shape:

```
Access to fetch at 'file:///…' from origin 'null' has been blocked by CORS policy: Cross origin
requests are only supported for protocol schemes: chrome, chrome-extension, chrome-untrusted,
data, http, https, isolated-app.
```

Classic scripts loading is what makes this confusing: the page comes up and your globals are
defined, so the first symptom is a `TypeError` about a *module*, which reads like a missing file.

`--allow-file-access-from-files` makes all of it work in desktop Chromium, which identifies the
exact capability — and **SketchUp's CEF does not grant it** (verified in SketchUp, 2026-08-19).

### 4.4 Therefore: serve over loopback

The working architecture is a static HTTP server inside the extension:

- `TCPServer.new("127.0.0.1", 0)` — loopback only, OS-assigned port
- a random path token in the URL, so nothing else on the machine can read the tree
- `dialog.set_url("http://127.0.0.1:<port>/<token>/html/index.html")`
- shut down in `dialog.set_on_closed`

It is not a workaround, it is strictly better: it is also **the only way to set response headers**,
which is what `Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy:
require-corp` need — and those are what `SharedArrayBuffer` needs.

**Do not use WEBrick.** It left Ruby's default gems at 3.0 and there is no guarantee what a given
SketchUp build ships. `TCPServer` is core.

Reference implementation: `planning/spikes/pyodide/ext/dph_plus_spike/main.rb`, with an offline test
at `planning/spikes/pyodide/test_static_server.rb` that loads the real `main.rb` against a stub
SketchUp API.

## 5. ⚠ The main thread — three rules, and each one alone breaks something

Rules 1 and 2 cost two full debugging rounds. **Both halves are required.** Rule 3 is the same
mechanism showing up a third time, in a place nobody was looking.

### Rule 1 — a Ruby `Thread` never runs on its own

SketchUp runs the Ruby VM on its main thread and schedules Ruby **only while Ruby is executing**.
Once your method returns and SketchUp goes back to its C++ event loop, the main Ruby thread still
holds the GVL, so a background thread parked in `accept` is starved indefinitely.

The symptom is not an error. `TCPServer.new` has already done `bind` and `listen`, so the kernel
queues the connection and the client waits forever. You get a blank dialog.

### Rule 2 — blocking I/O must not be on the main thread

SketchUp drives CEF from the app's main run loop, so **CEF needs the main thread to drain a socket**.
Write a response body larger than the socket send buffer from a `UI.start_timer` callback and you
deadlock: your write waits for a reader that cannot run. Beachball.

The tell is a size pattern — every small asset served, and no log line at all for the first big one.

### The shape that works

```ruby
# A worker thread does every blocking operation...
acceptor = Thread.new do
  loop { Thread.new(server.accept) { |s| serve(s) } }
end

# ...and the timer exists ONLY to sleep, which releases the GVL so the worker
# can be scheduled. Adaptive: a longer slice while a request is in flight.
pump = UI.start_timer(0.02, true) do
  sleep(busy? ? 0.010 : 0.001)
  flush_log   # workers queue lines; the main thread prints them
end
```

⚠ **Worker threads must never touch the SketchUp API — `puts` included.** The API is not
thread-safe. Queue log lines under a mutex and print them from the timer.

⚠ **Flush the queue in your stop lambda before killing the timer,** or the last lines are lost —
which will be exactly the error explaining why you are stopping.

Cost: SketchUp feels sluggish while the dialog is open. Acceptable, bounded, and it stops on close.

### Rule 3 — ⛔ nothing repaints while the main thread is busy

*(Measured 2026-08-21, POC-4 run D. `planning/POC/RESULTS/POC-4_results.md` §6.7.)*

Rules 1 and 2 are about work that *cannot proceed*. Rule 3 is about work that proceeds perfectly
while the user is shown nothing at all, which is why it took a live run and a user's question to
find. **SketchUp drives its own chrome *and* CEF from the main run loop.** Any synchronous Ruby
loop therefore freezes:

- the **status bar** (`Sketchup.status_text=` sets the value; nothing draws it),
- the **`HtmlDialog`** (it goes blank, then returns intact),
- and every other piece of SketchUp's UI.

Measured: a **10.9 s** collector walk over 2,556,183 face visits, with `status_text` written every
250 entities throttled to 5 Hz. The user saw **nothing** — the dialog blank from the first entity
until after the save panel closed.

⚠ **So there is no such thing as a progress indicator for main-thread work.** Not in the status
bar, not in the dialog, not anywhere. Choosing a different surface does not help, because the
surface is not the problem.

**The fix is structural and it is the same shape as the rule above: chunk the work across
`UI.start_timer` callbacks so the run loop turns over between chunks.** Each callback does a bounded
slice and returns. A recursive walk has to become an explicit stack first — which is the real cost,
and the reason it is a v1 item rather than a POC one.

⚠ **And the testing corollary, which is the part that generalises.** A stub SketchUp has no screen,
so an offline suite can only assert that `status_text` was **set** — which it was, correctly, every
single time. The test was green and the feature could not work. *Asserting the call is not asserting
the surface* (§9.1).

## 6. The Ruby ↔ JS bridge

```
Ruby → JS   dialog.execute_script("someFunction(#{JSON.generate(payload)})")
JS   → Ruby sketchup.my_callback(JSON.stringify(payload))
                # registered with dialog.add_action_callback("my_callback") { |ctx, str| ... }
```

Neither returns a value. For a round trip, keep a pending-resolver map on the JS side and have Ruby
answer by calling back into a known function.

### ⚠ An exception inside an `add_action_callback` block is SWALLOWED

The single most dangerous property of the bridge, and it produces no output anywhere:

```ruby
dialog.add_action_callback("on_ready") { |_ctx, _payload| do_the_whole_export }   # ✗
```

If `do_the_whole_export` raises, SketchUp discards the exception. No console line, no dialog, no
message box — the callback simply never completes, and the extension looks like it is still
thinking. It is indistinguishable from a hang, from a dead socket, and from a page that never
loaded, which are three different bugs with three different fixes.

**Rescue inside every callback and turn the error into a visible verdict:**

```ruby
dialog.add_action_callback("on_ready") do |_ctx, _payload|
  begin
    do_the_whole_export
  rescue StandardError => error
    report_failure("#{error.class}: #{error.message}", error.backtrace)
  end
  nil          # return nil explicitly; the value is discarded either way
end
```

⚠ **Report more than `error.message`.** The class is usually the diagnostic (`Errno::ENOENT` vs
`NoMethodError` are different problems), and a Python traceback arriving over the bridge has
`Traceback (most recent call last):` as its *first* line — so a message box showing only line 1
shows the user nothing. Log the whole thing to the console and put a bounded excerpt on screen.

### Measured capacity (SketchUp 2022, macOS)

| Payload | JS → Ruby | Ruby → JS |
|---|---|---|
| 1 KB | ok, 2 ms | ok |
| 10 KB | ok, 7 ms | ok |
| 100 KB | ok, 27 ms | ok |
| 1 MB | ok, 206 ms | ok |
| **4 MB** | **ok, 818 ms** | **ok** |

Checksum-verified in both directions (djb2, truncated to signed 32-bit). **No limit was found at
4 MB**; larger sizes were not attempted because a failure at 16 MB would be indistinguishable from a
crash. A real designPH model's geometry is far below this — Adelphi's 82 classified faces are
**19.4 KB**, about 0.5% of the verified ceiling.

⚠ Checksums agree across Ruby/JS only for the Basic Multilingual Plane: JS `charCodeAt` iterates
UTF-16 code units, Ruby `ord` iterates codepoints. Astral characters would disagree.

⚠ **Do not push megabytes across the bridge while the dialog is loading something else.** An early
build ran a 5 MB probe immediately before Pyodide fetched its 9 MB of assets, and the two competed.

### Page-ready handshake

`execute_script` issued straight after `dialog.show` can land **before the page's own scripts have
run**. Let the page announce itself instead:

```javascript
if (host && host.spike_ready) host.spike_ready("");   // page → Ruby, once loaded
```

## 7. Reading the model — API traps

Confirmed live during Phase 1 (`planning/RESULTS/PHASE-1_results.md`) and the POC's first real
export (2026-08-21, `planning/POC/RESULTS/`).

- **`entity.attribute_dictionaries` returns `nil`**, not an empty collection, when an entity has
  none. Easy `NoMethodError`.
- ⚠ **`face.area` is net of glued-component openings, and `face.loops` does not show them.**
  Exact 16-of-16 confirmation on Adelphi: every window host face reports a smaller `area` than its
  own boundary encloses, while only 2 of them report `loops.size > 1`. A polygon built from
  `outer_loop`/`inner_loops` is therefore **gross** and `face.area` is **net**, and both are right.
  Full detail and the consequences: `DESIGNPH_DATA_MODEL.md` §5.0.
- ⚠ **`ComponentInstance#transformation` is relative to the PARENT, not the world.** Comparing one
  against world-space face geometry put Adelphi's windows 1.2–3.3 m off their own host planes. Use
  `accumulated_parent_transform * instance.transformation`. `DESIGNPH_DATA_MODEL.md` §9.3.
- ⚠ **A component definition's geometry may be entirely nested.**
  `definition.entities.grep(Sketchup::Face)` returns `[]` for all 46 designPH windows on Adelphi —
  the panes live in sub-groups. Walk definitions recursively, never flat. §9.1.
- ⚠ **A recursive walk visits placements × faces.** Adelphi: **1,023,558** faces visited against
  ~8000 unique ones, and ~3.7 s of wall clock. Correct, but say so if the number is ever shown to a
  user. `DESIGNPH_DATA_MODEL.md` §8.6.1.
- **Recursion and transformations.** A face inside a group is stored in the group's *local*
  coordinates. Carry the accumulated `Geom::Transformation` or every nested face lands in the wrong
  place and every scaled group lies about its size.

  ```ruby
  when Sketchup::Group            then walk(e.entities, transform * e.transformation)
  when Sketchup::ComponentInstance then walk(e.definition.entities, transform * e.transformation)
  ```

- **Internal units are always inches**, whatever the model displays. Multiply by `0.0254` for
  metres. `Length#to_f` gives inches; `face.area` gives in².
- ⚠ **Walking `Sketchup::Face` is not walking the model.** designPH puts thermal bridges on
  **`Sketchup::Edge`** — PHPP measures them as lengths — so a face-only traversal silently drops
  them: 99 of 293 tagged entities on a real project. When a live count comes in under the offline
  record count, ask which *entity type* is missing.
- **A `ComponentInstance` carries its own dictionaries *and* inherits its definition's.** Both
  matter; keep them separate rather than merging.
- ✅ **`entity.persistent_id` really is stable across sessions — measured, not assumed**
  (2026-08-21, POC-4 run B). The same model exported twice, in two SketchUp sessions with a quit and
  relaunch between them, produced extraction files that were **identical byte for byte** — 215,373
  bytes, all 82 faces and 46 windows, every path-qualified id unchanged. Nothing in the reading is
  per-run.

  ⚠ **`entityID` is the one that is not.** It is session-scoped and will differ between two runs of
  the same model; it is a debugging aid and must never key anything that outlives the session.
  Carrying both, and being explicit about which is which, is what let the claim be *tested* rather
  than believed.

  ⚠ **An id is only as stable as its path.** These ids are path-qualified — the persistent ids of
  every enclosing group/component, joined — which is what makes one definition placed twice into two
  distinct envelope surfaces. It also means a user *re-nesting* geometry changes the id of everything
  inside it, even though nothing about the surface changed. Stable across sessions ≠ stable across
  edits.
- **`glued_to` resolves window hosts reliably** — 46 of 46 on Adelphi, and **239 of 239 across the
  whole five-model corpus** (2026-08-21). Zero unresolved hosts anywhere.
- ⚠ **`definition.behavior.cuts_opening?` is a capability, not a fact about the host.** It is `true`
  on all 46 designPH windows, yet only **1 of 16** host faces has an inner loop. It means "this
  component is able to cut", not "this host has a hole".
  ⚠ **And the obvious replacement is also wrong.** `face.loops.size > 1` tests for a *modelled*
  hole, and a glued opening creates none — it is true on only **2 of Adelphi's 16 real window
  hosts**. **`glued_to` is the only thing that identifies a host** (2026-08-21;
  `DESIGNPH_DATA_MODEL.md` §5.0).
- **Type-check every attribute read.** `areaGroupID` is a `String` on 1359 of 1441 faces in the
  primary corpus model. Nothing about `DesignPH_dict` value types is guaranteed.
- ⚠ **Tagged edges nest as deeply as faces do.** All **99** of Bluff Reach's thermal-bridge edges sit
  **two levels down** inside groups; a walk that visited only the top level would return zero of them
  and report success. The recursion has to cover edges, not just faces (contract E-1, answered
  2026-08-21).
- ⚠ **A face can carry a `DesignPH_dict` and no area group at all.** Bluff Reach: **576** faces carry
  the dictionary, **194** carry a group — the rest hold only `descNameAuto` or a cached
  `Material`/`BackMaterial`. "Tagged" and "classified" are three different populations with
  "carries an area-group key" in between, and conflating any two of them breaks a reconciliation
  (`DESIGNPH_FILE_FORMATS.md` §4.3).

## 8. Writing output

⚠ **Not like this** — kept because it is the obvious approach and it is wrong:

```ruby
dir  = model.path.empty? ? File.expand_path("~/Desktop") : File.dirname(model.path)   # ✗
base = model.path.empty? ? "untitled" : File.basename(model.path, ".skp")             # ✗
```

`model.path` is the location the model was last **saved**, on whatever machine saved it (§8.2). On a
file authored elsewhere `File.dirname` points at a directory that does not exist here — or, for a
Windows path on macOS, at nothing at all, because there are no separators to split and the whole
path becomes one filename. Write to a **known** directory, or to one the user chose through a save
dialog, and never to one derived from the model.

### The save panel

```ruby
chosen = UI.savepanel("Save HBJSON", default_directory, suggested_filename)
return if chosen.nil?          # ⚠ nil means the user CANCELLED — a normal outcome, not an error
```

- It returns the **full path** the user chose, or `nil` on cancel. Cancelling must not be reported
  as a failure, and must not fall back to writing somewhere else.
- The **directory** it opens in is the only trustworthy source of an output location. A fixed,
  always-writable default (`~/Desktop`) beats a clever one derived from a value that is wrong on
  40 % of real models.
- The **filename** is a suggestion the user sees and can change, so a bad one is cosmetic rather
  than dangerous — but sanitise it anyway. `Model#title` is a title, not a path, yet on a model last
  saved elsewhere it can still carry a whole foreign path. Reduce to a bare stem: swap `\\` for
  `/`, take `File.basename`, drop a trailing `.skp`, replace anything outside `[A-Za-z0-9 ._-]`,
  and fall back to `"untitled"` when nothing survives.

### Write atomically

A reader must see the previous file or the new one, never a half-written one — and a failure
part-way must leave no debris:

```ruby
temp = "#{path}.tmp#{Process.pid}"
begin
  File.open(temp, "w:UTF-8") { |file| file.write(contents) }   # name the encoding; do not
  File.rename(temp, path)                                      # inherit it from the locale
rescue StandardError
  File.delete(temp) if File.file?(temp)
  raise
end
```

⚠ The temp file goes in the **destination directory**, not `/tmp`, so the rename cannot cross a
filesystem — a cross-device `rename` fails, and the failure arrives after the write has succeeded,
which is the worst moment for it.

⚠ **A write failure must name the path and the OS error.** "Could not save" is unactionable;
`Errno::ENOENT … /Users/…/does-not-exist/model.hbjson` is a user fixing their own problem. And when
the translation itself succeeded, say that too — the result is still on screen even though nothing
reached disk.

## 8.1 ⚠ macOS SketchUp is multi-document, and `Sketchup.open_file` opens a **new window**

*(2026-08-21. Caught in review before it cost a session, but it would have.)*

On Windows `Sketchup.open_file(path)` replaces the current model. **On macOS it opens another
document window**, and `Sketchup.active_model` follows whichever window is frontmost — which may not
be the one just opened, and may not have become frontmost by the time the next line of Ruby runs.

The failure mode is the worst available: a loop that opens five models and collects `active_model`
after each writes **five files, named after five different models, all containing the first model's
data**, with no error anywhere. Nothing about the output looks wrong.

Two defences, and use both:

- **Prefer "collect whatever is open".** Have the human open each model and run a one-liner. It is
  more clicks and no ambiguity.
- **If you must batch, verify.** After `open_file`, assert
  `File.expand_path(Sketchup.active_model.path) == File.expand_path(path)` and **stop** if it does
  not. Never carry on and never guess.

`poc/ext/tests/run_collector_console.rb` implements both (`Dph.here` and `Dph.sweep`).

### 8.2 ⚠ `Sketchup::Model#path` is not the path of the file you opened

*(Measured 2026-08-21 across the five corpus copies, and it cost one capture.)*

On **two of five** models `model.path` came back as the location the model was last saved to **on
somebody else's machine**:

| model | last saved by | `model.path` returned |
|---|---|---|
| `adelphi-designph_COPY` | SketchUp 22.0.353 | ✅ the opened copy |
| `250708_COPY` | 22.0.353 | ✅ the opened copy |
| `2414_Bluff Reach_COPY` | 23.1.341 | ✅ the opened copy |
| `250703 - Linde…_COPY` | **25.0.660 (Windows)** | `C:\Users\greg\OneDrive\…\Linde Residence - 2.0 kBTU - 7.3.25.skp` |
| `2523 Wellington_COPY` | **26.1.188** | `/Users/johnmitchell/Dropbox/…/2523 Weiilington.skp` |

Both strings are embedded verbatim in the `.skp`'s `model.dat` (which also stores the source path of
every imported component — that is where `/Users/darnautu/AppData/Local/Temp/Component.skp` comes
from). ⚠ The affected two are the two saved by SketchUp 24+/26 while the others were 22 and 23, but
**n=5 is a correlation, not a mechanism** — do not build a version rule on it. Build on not trusting
`model.path`.

Two consequences, and the second is the one that matters:

1. **Never derive an output path from it.** The capture script wrote to
   `model.path.sub(".skp", ".extraction.json")`. macOS finds no separators in a Windows path, so the
   *entire* path became one filename in SketchUp's working directory (`~/Documents`); the other
   raised `ENOENT` and the capture was lost outright.
2. ⚠ **A guard built on it fails silently, in both directions.** The COPIES-ONLY check tested
   `path.start_with?(File.expand_path("~/Dropbox"))`. `/Users/johnmitchell/Dropbox/…` does not start
   with *this* machine's `~/Dropbox`, so hard rule 3 was not being enforced at all — and the reverse
   is equally possible, refusing a legitimate copy whose stale path happens to sit under the user's
   own Dropbox. Match `/Dropbox/` for any user, and treat it as advisory rather than as a guarantee.

`model.title` is the obvious substitute and is **not verified** — it may share the same source. The
capture script instead writes to a fixed directory and, when `model.path` does not point into it,
**stops and asks which copy is open**, listing them. Naming it is the assertion the API cannot make,
and the name is passed through to the collector so the extraction's `model.file_name` stops carrying
one that identifies nothing.

⚠ **Do not replace the guard with a smarter negative test.** That was tried twice within an hour and
failed both ways: matching this machine's `~/Dropbox` let the stale `/Users/johnmitchell/Dropbox/…`
straight through, and widening it to `/Dropbox/` for any user then **refused a legitimate copy on the
Desktop**. A negative test on an untrustworthy value is worthless whichever way you point it. Ask a
positive question — *is this verifiably the file I expect?* — and hand the residue to the human.

## 9. ⚠ Reporting to the user — three surfaces, and they disagree by default

A SketchUp extension has three places to say what happened, and **POC-4 produced four separate
defects that were all the same defect**: the surfaces drifted apart, and the *transient* one was
right while the *persistent* one was wrong or silent. Worth designing for up front.

| Surface | Lives for | Good for | Fails by |
|---|---|---|---|
| **Ruby Console** | the session | the full record — every line, every backtrace | nobody has it open |
| **`HtmlDialog`** | until closed | the grade, the counts, the reasons — the thing that stays on screen | going blank (§5 rule 3); never being told |
| **`UI.messagebox`** | until dismissed | forcing attention once | it is gone a second later, and it blanks the dialog while up |

**The rules that fell out of getting it wrong four times:**

1. **One source of truth for the grade.** Not a boolean rendered independently in two places. POC's
   verdict is `{passed, headline, checks[]}` and *both* the dialog and the message box render
   `headline` — because the moment one renders `passed` and the other renders `headline`, a run with
   omissions shows green `PASSED` in the window and `PASSED WITH OMISSIONS` in the box.
2. **Every terminal path must reach the persistent surface.** Success, failure *and refusal*. A
   refusal that only reaches the message box leaves the dialog reading `booting…` forever — a
   session that has finished its work still claiming to be starting.
3. **Write the dialog BEFORE the message box.** The box is modal on the main thread and blanks the
   dialog while it is up (§5 rule 3), so a banner written afterwards is written to a window nobody
   is looking at.
4. **A refusal is not a failure.** Give it its own state and its own words — nothing went wrong, we
   declined. Rendering it as `FAILED` sends the user hunting for a bug that does not exist.
5. **Never `alert`/`confirm`/`prompt` inside the dialog** — it blocks every subsequent browser event
   and the extension goes dark (§10).

### 9.1 ⚠ Asserting the call is not asserting the surface

The reason all four defects were *green in CI* the whole time:

| What was asserted | What was actually true |
|---|---|
| `verdict.passed` was correct | the banner rendered the wrong one of three states |
| the harness graded `verdict.passed` too | it had rendered the wrong banner on **every CI run since the fixture was written** |
| the message box carried the refusal | the dialog was left on `booting…` |
| `status_text` was **set** — and it was | nothing was ever displayed (§5 rule 3) |

**When the claim is "the user sees X", the assertion has to read X off the surface** — out of the
DOM, out of the recorded message-box text — *and be shown to fail on the code that got it wrong*
before it is trusted. A stub SketchUp has no screen at all, so an offline suite can never close the
last one of these; that is what the human runs are for.

## 10. Interactive-development notes

- **Load, don't paste.** The Ruby Console mangles long multi-line pastes. Use
  `load '/absolute/path/script.rb'` and have the script write its output to a file.
- **Extensions load at startup only.** Reinstalling requires a SketchUp restart.
- ⚠ **Never trigger `alert`/`confirm`/`prompt` in an `HtmlDialog`.** A modal dialog blocks all
  further browser events and the extension stops receiving commands.
- ⚠ **`UI.messagebox` blanks the `HtmlDialog` while it is up.** The message box is modal on the main
  thread, and CEF is painted *from* that thread (§5), so the dialog cannot repaint until the box is
  dismissed — it goes white, then comes back intact. Not a defect, and alarming the first time. Do
  not conclude the page has crashed; and do not rely on the dialog being readable *behind* a modal.
- ⛔ **NO PROGRESS INDICATOR CAN UPDATE DURING MAIN-THREAD WORK — not the status bar, not the
  dialog.** The rule above is the special case; this is the general one, and it is hard rule 9 seen
  from the UI side instead of the I/O side. SketchUp drives its own chrome *and* CEF from the main
  run loop, so any synchronous Ruby loop freezes both until it returns.

  Measured in SketchUp 22.0.353 (2026-08-21, POC-4 run D): a 10.9 s collector walk over 2,556,183
  face visits. `Sketchup.status_text=` was written every 250 entities throttled to 5 Hz, and the
  user **saw nothing at all** — the dialog sat blank from the moment the walk began until after the
  save panel closed. Two independent reasons, and only the second is interesting:

  1. `Sketchup.status_text=` writes to the bottom-left of the **main SketchUp window**, which the
     dialog and the Ruby Console sit on top of. Wrong surface: the user is looking at the dialog.
  2. Nothing repaints anyway, because the main thread never yields.

  ⚠ **The corollary for testing is the sharp part.** A stub has no screen, so an offline suite can
  only assert that the status string was *set* — which it was, correctly, every time. Asserting the
  call is not asserting the surface, and a green test said "the progress signal works" while the
  feature could not work at all.

  **The fix is structural, not cosmetic: chunk long work across `UI.start_timer` callbacks** so the
  run loop turns over between chunks — the same shape as §5's rule, for the same reason. A
  recursive walk has to become an explicit stack first.
- ⚠ **`load`-ing a file whose constants the installed extension already defined emits a warning per
  constant.** Thirty lines of `already initialized constant` can bury the one message worth reading.
  Wrap the reload: `original = $VERBOSE; $VERBOSE = nil; load path; ensure; $VERBOSE = original`.
  The redefinition is intended — it is how you iterate without reinstalling — the warning is not.
- **The BT Attribute Inspector** (`~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/
  bt_inspector/`) is a read-only viewer for live model state. The offline `.skp` parser sees
  *historical* state too and cannot tell the difference.

## 11. Open questions

| Question | Why it matters |
|---|---|
| CEF version in SketchUp 2021, 2023, 2024, 2025, 2026 | Sets the Pyodide ceiling (`PYODIDE_RUNTIME.md` §2). Read the plist on each |
| Windows behaviour | Untested. CEF is CEF, but `file://` handling and path semantics are exactly what differs |
| Whether `HtmlDialog` on Windows accepts a loopback `set_url` | The whole architecture depends on it |
| Bridge ceiling above 4 MB | Never probed. Real extraction payloads are 215–262 KB compact (334–501 KB pretty-printed); the largest HBJSON produced is 686 KB (Bluff Reach) |
| **Does a chunked walk actually restore repainting?** | §5 rule 3's fix is *reasoned*, not measured. Nobody has yet run a `UI.start_timer`-chunked traversal and confirmed the status bar and dialog update between slices. It follows from the mechanism, but so did several things that turned out to be wrong |
| What a chunked walk costs | Turning the recursion into an explicit stack, plus per-slice overhead, against a walk that is already 60–79 % of the run |
| Windows: does `Sketchup.status_text=` behave the same? | The status bar is in a different place in the window chrome, and the whole §5 rule 3 finding is macOS-only so far |
| What actually makes `Model#path` go stale | §8.2 correlates it with SketchUp 24+/26 having written the file, on n=5. Not a mechanism, and not worth relying on — the rule is to distrust the value |

## 12. Measured, inside SketchUp 2022 — the numbers to compare against

*(2026-08-21, SketchUp **22.0.353**, macOS arm64-darwin20, Ruby **2.7.2**. Full record:
`planning/POC/RESULTS/POC-1_results.md`.)*

| | SketchUp 2022 | Headless Chromium 88 snapshot |
|---|--:|--:|
| Pyodide ready | 1397 ms | 1783 ms |
| 9 archives staged | 1590 ms | 1806 ms |
| Payload unpacked (`zipfile`) | 1705 ms | 2035 ms |
| **Cold start to `import honeybee_ph`** | **2577 ms** | 3216 ms |
| Peak WASM heap | 28.8 MB | 28.8 MB |
| JS heap | 68.9 MB | — |
| Bridge, 1 MB round trip | 201 ms | — |
| Collector walk, Adelphi (1.02 M face visits) | 3656 ms | — |
| Collector walk, Bluff Reach (2.56 M face visits) | 9704 ms | — |
| Collector walk, Linde (2466 face visits, 25 layer tables) | 100 ms | — |
| Translate 82 faces → 324 KB HBJSON | ~4.2 s incl. bridge | — |

### The wired export path, four live runs *(POC-4, 2026-08-21)*

The numbers above are the runtime shell. These are the whole product path — menu click to files on
disk — and they are what a user actually waits for:

| | Adelphi (run A) | Adelphi (run B) | Bluff Reach (run D) |
|---|--:|--:|--:|
| Pyodide boot, cold | 2573 ms | 2589 ms | 2574 ms |
| **Collector walk** | **4180 ms** | 4101 ms | **10 950 ms** |
| Face visits | 1 023 558 | 1 023 558 | 2 556 183 |
| Extraction JSON | 215 373 B | 215 373 B | 261 833 B |
| Translate (bridge in, HBJSON out) | 180 ms | 180 ms | 340 ms |
| HBJSON | 323 779 B | 323 779 B | 686 479 B |
| **Total, click to message box** | **~7.0 s** | ~6.9 s | **~13.9 s** |

Four observations that only a real run gives you:

- ⚠ **The walk dominates, by an order of magnitude.** Boot is a fixed ~2.6 s and translation is
  under half a second even on the largest model in the corpus; **the Ruby walk is 60–79 % of the
  wall clock.** Every optimisation instinct points at Pyodide, and Pyodide is not the problem.
- ⚠ **Walk time tracks placements, not envelope size.** Bluff Reach has 2.4× Adelphi's classified
  faces and 2.5× its face *visits*, and takes 2.6× as long — the visits are what predict it. Linde
  walks 2466 faces in 100 ms while carrying 25 layer tables and 47 windows.
- **Boot is remarkably stable**: 2542–2589 ms across four cold starts, spread 47 ms.
- **The run is reproducible end to end.** Runs A and B are the same model in two sessions: the
  extractions are **byte-identical** and the walk times differ by 79 ms (1.9 %).

⚠ **And for 4 to 11 of those seconds the UI is frozen and shows nothing** — §5 rule 3. The
performance number the user reports will be "it hung", not "it took 13.9 s".

⚠ **Walk time tracks placements, not model size or complexity.** Linde walks 2466 faces in 100 ms
and carries 25 layer tables and 47 windows; Bluff Reach walks 2.56 million in 9.7 s. A user staring
at a 10-second pause is looking at component instancing, not at their envelope.

⚠ **SketchUp's own CEF boots *faster* than the headless Chromium 88 snapshot** — 2.58 s against
3.22 s, consistently. Presumably headless startup plus CDP overhead. The practical consequence is
worth stating: **the offline harness is a pessimistic proxy, not an optimistic one**, so a timing
that passes there will pass in SketchUp. That is the safe direction to be wrong in, and it is the
opposite of what one would guess.

Ruby 2.7.2 accepted every file that `ruby -c` had only checked against the system 2.6.10 — the
conservative direction, now confirmed rather than assumed.
