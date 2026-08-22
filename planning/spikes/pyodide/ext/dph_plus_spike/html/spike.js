/* Phase 3 — the JS half of the Pyodide spike.
 *
 * Host-agnostic, exactly like `spike.py`: this same file runs under SketchUp's `HtmlDialog` (via
 * `index.html`) and under desktop Chrome (via `harness/harness.html`). The host supplies a tiny
 * adapter — where to send results, how to log — and nothing else. A step that passes in Chrome and
 * fails in SketchUp therefore isolates the difference to the host, which is the whole point of the
 * phase.
 *
 * Assets are read through a two-rung ladder, because the phase's top risk is that `HtmlDialog`
 * will not let a `file://` page fetch its own assets:
 *
 *   1. plain `fetch()`        — works over http(s), and over file:// where local file access is on
 *   2. `XMLHttpRequest` shim  — some hosts allow file:// XHR where they refuse file:// fetch
 *
 * Which rung carried the load is recorded in `SPIKE.fetchStrategy`, because "it worked" is not a
 * useful result here; "it worked, on rung 2" is. Stock desktop Chromium refuses *both* on file://
 * and refuses the dynamic `import()` Pyodide uses as well, which no shim can reach — see
 * `RESULTS/PHASE-3_results.md` §3.2. The ladder is kept because CEF is not desktop Chromium and
 * the point of the spike is to find out where SketchUp actually sits.
 */

(function (global) {
  "use strict";

  var SPIKE = {};
  global.SPIKE = SPIKE;

  // ------------------------------------------------------------------------------------------
  // Logging
  // ------------------------------------------------------------------------------------------

  SPIKE.logLines = [];
  SPIKE.onLog = null; // host adapter sets this

  function log(message) {
    var line = "[" + (performance.now() / 1000).toFixed(2) + "s] " + message;
    SPIKE.logLines.push(line);
    if (global.console && console.log) console.log(line);
    if (SPIKE.onLog) {
      try {
        SPIKE.onLog(line);
      } catch (error) {
        /* a broken log sink must never fail the spike */
      }
    }
  }
  SPIKE.log = log;

  // ------------------------------------------------------------------------------------------
  // Rung 1 and 2 — fetching bytes when the page may be on file://
  // ------------------------------------------------------------------------------------------

  /** How the last successful binary read was performed. One of "fetch", "xhr", "host". */
  SPIKE.fetchStrategy = null;

  function xhrBinary(url) {
    return new Promise(function (resolve, reject) {
      var request = new XMLHttpRequest();
      request.open("GET", url, true);
      request.responseType = "arraybuffer";
      request.onload = function () {
        // A file:// XHR reports status 0 on success — there is no HTTP status to report.
        if (request.status === 0 || (request.status >= 200 && request.status < 300)) {
          resolve(request.response);
        } else {
          reject(new Error("XHR " + request.status + " for " + url));
        }
      };
      request.onerror = function () {
        reject(new Error("XHR failed for " + url));
      };
      request.send(null);
    });
  }

  /**
   * Read `url` as an ArrayBuffer.
   *
   * Plain `fetch` — the ladder lives in the shim below, which `boot` installs before anything is
   * read, so this call gets the XHR fallback for free rather than repeating it.
   */
  SPIKE.readBinary = function (url) {
    return fetch(url).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status + " for " + url);
      SPIKE.fetchStrategy = SPIKE.fetchStrategy || "fetch";
      return response.arrayBuffer();
    });
  };

  /** Read `vendor/manifest.json` — the one place the pinned wheel list lives. */
  SPIKE.readManifest = function (url) {
    SPIKE.installFetchShim();
    return SPIKE.readBinary(url).then(function (buffer) {
      return JSON.parse(new TextDecoder().decode(buffer));
    });
  };

  /**
   * Make `globalThis.fetch` fall back to XHR for anything it refuses.
   *
   * Load-bearing: Pyodide fetches `pyodide.asm.wasm` and `python_stdlib.zip` through its *own*
   * calls to `fetch`, so `SPIKE.readBinary` never sees them. Without this shim, a host that blocks
   * `file://` fetch kills the spike inside `loadPyodide()` before any of our code runs.
   */
  SPIKE.installFetchShim = function () {
    if (SPIKE._shimInstalled) return;
    var nativeFetch = global.fetch.bind(global);
    global.fetch = function (input, init) {
      var url = typeof input === "string" ? input : input && input.url;
      return nativeFetch(input, init).catch(function (error) {
        log("fetch shim: routing " + url + " through XHR (" + error.message + ")");
        return xhrBinary(url).then(function (buffer) {
          SPIKE.fetchStrategy = "xhr";
          return new Response(buffer, { status: 200, headers: { "Content-Type": "application/wasm" } });
        });
      });
    };
    SPIKE._shimInstalled = true;
  };

  // ------------------------------------------------------------------------------------------
  // Step 1 + 2 — boot Pyodide and install the payload
  // ------------------------------------------------------------------------------------------

  /**
   * Install the payload by unpacking it with Python's own `zipfile`.
   *
   * Every wheel here is `py3-none-any`, so unpacking **is** installing — there is nothing for a
   * resolver to resolve. Phase 2 planned to go through `micropip` and keep this in reserve; Finding
   * 35 turned that around. `micropip` is coupled to the Pyodide release and cannot run on the 0.24.1
   * that SketchUp's Chromium 88 forces, so the reserve is now the mechanism and `micropip` is not
   * shipped at all. `pyodide-core` contains no packages either way (Phase 2 §2.5), so something like
   * this was always going to be needed.
   */
  function unpackWheels(pyodide, wheelPaths) {
    return pyodide.runPythonAsync(
      [
        "import sysconfig, zipfile, sys",
        "target = sysconfig.get_paths()['purelib']",
        "for path in " + JSON.stringify(wheelPaths) + ":",
        "    with zipfile.ZipFile(path) as archive:",
        "        archive.extractall(target)",
        "sys.path_importer_cache.clear()",
        "import importlib; importlib.invalidate_caches()",
        "target",
      ].join("\n")
    );
  }

  /**
   * Boot the runtime and install everything.
   *
   * `config`:
   *   indexURL    — directory holding `pyodide.js` and friends, with trailing slash
   *   wheelURLs   — [{name, url}] to unpack onto Pyodide's filesystem
   *   spikePyURL  — URL of `spike.py`
   */
  SPIKE.boot = function (config) {
    var timings = {};
    var started = performance.now();
    var pyodide = null;

    function mark(label) {
      timings[label] = Math.round(performance.now() - started);
    }

    SPIKE.installFetchShim();
    log("loading pyodide from " + config.indexURL);

    return global
      .loadPyodide({ indexURL: config.indexURL })
      .then(function (instance) {
        pyodide = instance;
        SPIKE.pyodide = instance;
        mark("pyodide_ready_ms");
        log("pyodide ready in " + timings.pyodide_ready_ms + " ms");

        // Fetch every wheel into the emscripten filesystem before touching Python. Doing all the
        // I/O first keeps the two failure modes — "could not read the file" and "could not install
        // the wheel" — from being reported as one.
        pyodide.FS.mkdirTree("/wheels");
        return config.wheelURLs.reduce(function (chain, wheel) {
          return chain.then(function (paths) {
            return SPIKE.readBinary(wheel.url).then(function (buffer) {
              var path = "/wheels/" + wheel.name;
              pyodide.FS.writeFile(path, new Uint8Array(buffer));
              paths.push(path);
              return paths;
            });
          });
        }, Promise.resolve([]));
      })
      .then(function (paths) {
        mark("wheels_fetched_ms");
        log(paths.length + " wheels staged via " + SPIKE.fetchStrategy);

        SPIKE.installStrategy = "zipfile";
        return unpackWheels(pyodide, paths).then(function () {
          return paths;
        });
      })
      .then(function () {
        mark("wheels_installed_ms");
        log("payload installed via " + SPIKE.installStrategy);
        return SPIKE.readBinary(config.spikePyURL);
      })
      .then(function (buffer) {
        pyodide.FS.writeFile("/spike.py", new Uint8Array(buffer));
        return pyodide.runPythonAsync("import sys; sys.path.insert(0, '/'); import spike; 'ok'");
      })
      .then(function () {
        mark("spike_imported_ms");
        return SPIKE.call("run_all");
      })
      .then(function (result) {
        mark("steps_2_3_ms");
        result.timings = timings;
        result.fetch_strategy = SPIKE.fetchStrategy;
        result.install_strategy = SPIKE.installStrategy;
        result.memory = SPIKE.memory();
        log("boot complete in " + timings.steps_2_3_ms + " ms");
        return result;
      });
  };

  /**
   * Call a `spike.py` entry point with JSON-safe arguments and get a plain JS object back.
   *
   * Everything crosses as a JSON string rather than as a proxied Python object. Proxies leak (they
   * need explicit `.destroy()`) and, more importantly, a JSON string is the same on both sides of
   * the Ruby bridge too — so one serialisation format spans Ruby, JS and Python.
   */
  SPIKE.call = function (functionName, argument) {
    var source = [
      "import json, spike",
      "json.dumps(spike." + functionName + "(" + (argument === undefined ? "" : "json.loads(_spike_arg)") + "))",
    ].join("\n");
    if (argument !== undefined) {
      SPIKE.pyodide.globals.set("_spike_arg", JSON.stringify(argument));
    }
    return SPIKE.pyodide.runPythonAsync(source).then(function (text) {
      return JSON.parse(text);
    });
  };

  /** Step 4 — build a Room from face vertices that came across the bridge. */
  SPIKE.runStep4 = function (payload) {
    var started = performance.now();
    return SPIKE.call("step4_build_model_from_faces", payload).then(function (result) {
      result.wall_clock_ms = Math.round(performance.now() - started);
      result.payload_bytes = JSON.stringify(payload).length;
      result.memory = SPIKE.memory();
      return result;
    });
  };

  // ------------------------------------------------------------------------------------------
  // Measurement
  // ------------------------------------------------------------------------------------------

  /**
   * Memory, in MB. Two different numbers, both wanted:
   *   `wasm_heap` — Pyodide's linear memory, which is what a big model actually grows
   *   `js_heap`   — Chromium's `performance.memory`, absent outside Chromium and behind a flag in
   *                 some builds. Its absence is itself worth recording.
   */
  SPIKE.memory = function () {
    var report = {};
    try {
      var buffer = SPIKE.pyodide && SPIKE.pyodide._module && SPIKE.pyodide._module.HEAP8;
      if (buffer) report.wasm_heap_mb = +(buffer.length / 1048576).toFixed(1);
    } catch (error) {
      report.wasm_heap_mb = null;
    }
    if (performance.memory) {
      report.js_heap_mb = +(performance.memory.usedJSHeapSize / 1048576).toFixed(1);
      report.js_heap_limit_mb = +(performance.memory.jsHeapSizeLimit / 1048576).toFixed(1);
    } else {
      report.js_heap_mb = null; // not a Chromium build, or the API is disabled
    }
    return report;
  };

  /**
   * Bridge capacity probe. Builds JSON payloads of escalating size and hands each to `send`,
   * which the host wires to whatever its bridge is. Returns the largest size that survived a
   * round trip intact.
   *
   * Deliberately checks a checksum rather than just "did not throw": a bridge that silently
   * truncates is far more dangerous than one that errors, and truncation is a documented risk of
   * `execute_script` payloads.
   */
  SPIKE.probeBridge = function (send, sizes) {
    sizes = sizes || [1e3, 1e4, 1e5, 1e6, 4e6, 1.6e7];
    var results = [];
    return sizes
      .reduce(function (chain, size) {
        return chain.then(function () {
          var filler = new Array(Math.max(1, Math.round(size / 10))).join("0123456789");
          var message = { size: filler.length, sum: checksum(filler), body: filler };
          var started = performance.now();
          return Promise.resolve(send(message))
            .then(function (echo) {
              results.push({
                bytes: filler.length,
                ok: !!echo && echo.sum === message.sum && echo.size === message.size,
                ms: Math.round(performance.now() - started),
                echo_size: echo ? echo.size : null,
              });
            })
            .catch(function (error) {
              results.push({ bytes: filler.length, ok: false, error: String(error.message || error) });
            });
        });
      }, Promise.resolve())
      .then(function () {
        var passed = results.filter(function (r) {
          return r.ok;
        });
        return {
          attempts: results,
          max_ok_bytes: passed.length ? passed[passed.length - 1].bytes : 0,
        };
      });
  };

  /** Cheap, order-sensitive checksum — enough to catch truncation and re-ordering. */
  function checksum(text) {
    var hash = 5381;
    for (var i = 0; i < text.length; i++) {
      hash = ((hash << 5) + hash + text.charCodeAt(i)) | 0;
    }
    return hash;
  }
  SPIKE.checksum = checksum;
})(typeof window !== "undefined" ? window : globalThis);
