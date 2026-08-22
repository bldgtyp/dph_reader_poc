/* DesignPH-PLUS POC — the JS half of the runtime.
 *
 * Responsibilities, and nothing else:
 *
 *   1. boot Pyodide 0.24.1 and install the payload (8 wheels + the translator zip) by `zipfile`
 *      unpack — `micropip` is deliberately not shipped, it cannot run on 0.24.1
 *   2. hand control to Ruby once the runtime is up (`sketchup.on_ready`)
 *   3. carry one action at a time across the seam and answer on `sketchup.on_result`
 *   4. end every session in a verdict banner
 *
 * ⚠ TARGET IS CHROMIUM 88. ES5-shaped on purpose: `var`, `function`, promise chains. No
 * `async`/`await` at top level, no class fields, no `.at()`, no `Object.hasOwn`.
 *
 * ⚠ NO `alert`/`confirm`/`prompt`, ever. A modal dialog inside `HtmlDialog` blocks every
 * subsequent event and the extension goes dark (`CONSTRAINTS.md` §3).
 *
 * The seam is fixed by `planning/POC/POC-1_runtime-shell.md` §4.1 and must not be reinvented per
 * phase: **`dph_translator.entry.translate_json(payload: str) -> str`**, JSON string in, JSON
 * string out. No proxies cross the boundary in either direction — they leak (explicit `.destroy()`)
 * and a JSON string is the same value on the Ruby side of the bridge too, so one serialisation
 * format spans Ruby, JS and Python.
 *
 * There is no `fetch` → XHR fallback ladder here, unlike the Phase 3 spike. The spike carried one
 * because `file://` was still under test; it is now a settled dead end (hard rule 8) and the page
 * is only ever served over `http://127.0.0.1`, where plain `fetch` works.
 */

(function (global) {
  "use strict";

  var DphPlus = {};
  global.DphPlus = DphPlus;

  var config = null;
  var pyodide = null;
  var host = null;
  var timings = {};
  var bootStarted = 0;
  var payloadInfo = {};
  var ready = false;

  DphPlus.logLines = [];

  DphPlus.attach = function (options) {
    config = options;
    host = options.host;
  };

  // ----------------------------------------------------------------------------------------
  // Logging and the verdict banner
  // ----------------------------------------------------------------------------------------

  function log(message) {
    var line = "[" + (performance.now() / 1000).toFixed(2) + "s] " + message;
    DphPlus.logLines.push(line);
    if (global.console && console.log) console.log(line);
    if (config && config.logElement) {
      config.logElement.textContent += "\n" + line;
      config.logElement.scrollTop = config.logElement.scrollHeight;
    }
    // A broken log sink must never fail the run.
    try {
      if (host && host.on_log) host.on_log(line);
    } catch (error) {
      /* ignored on purpose */
    }
  }
  DphPlus.log = log;

  /**
   * Render `{passed, headline, checks:[{label, ok, detail}]}`.
   *
   * A hard requirement, not decoration (Phase 3 Finding 41): an early spike build left a 20-line
   * Python traceback as the last thing on screen after a *successful* run. A run nobody can grade
   * at a glance has not reported anything.
   *
   * ⚠ **Use `headline`, not `passed`.** The verdict has THREE states, not two (POC-3 §9), and
   * `PASSED WITH OMISSIONS` is the ordinary outcome on a real model. Rendering the boolean printed
   * a green `PASSED` on Adelphi's first live export while the message box beside it said `PASSED
   * WITH OMISSIONS` and 40 assemblies had gone unresolved — the two surfaces disagreeing, with the
   * one that stays on screen giving the more flattering answer. `headline` is what Ruby writes to
   * the message box, so reading it here is also what keeps them from drifting apart again.
   */
  function showVerdict(verdict) {
    if (!config || !config.verdictElement) return;
    var checks = verdict.checks || [];
    var lines = [verdict.headline || (verdict.passed ? "PASSED" : "FAILED")];
    for (var i = 0; i < checks.length; i++) {
      var check = checks[i];
      lines.push((check.ok ? "  ok    " : "  FAIL  ") + check.label +
                 (check.detail ? "  (" + check.detail + ")" : ""));
    }
    config.verdictElement.textContent = lines.join("\n");
    // Green still means "nothing failed"; the omissions are carried by the words and by the
    // report table's `reported` column, which is styled to stand out when it is non-zero.
    config.verdictElement.className = verdict.passed ? "pass" : "fail";
    for (var j = 0; j < lines.length; j++) log(lines[j]);
  }

  /**
   * Ruby refused before there was anything to translate — an unsupported designPH version, a model
   * with no designPH data, an oversized payload.
   *
   * ⚠ **A refusal has to reach the DIALOG, not just the message box.** On the first live run of the
   * "not a designPH model" path the message box said its piece, the user dismissed it, and the
   * dialog was left reading `booting…` forever — a window that had finished its work still
   * claiming to be starting. That is Finding 41's failure mode exactly: *a run nobody can grade at
   * a glance has not reported anything*, and the surface that stays on screen is the one that has
   * to carry the grade.
   *
   * Its own state, deliberately: a refusal is not a failure. Nothing went wrong — we declined.
   */
  DphPlus.showRefusal = function (message) {
    if (!config || !config.verdictElement) return;
    config.verdictElement.textContent = "NOTHING EXPORTED\n\n" + String(message);
    config.verdictElement.className = "refused";
    if (config.summaryElement) config.summaryElement.textContent = "";
    log("REFUSED: " + String(message).split("\n")[0]);
  };

  // ----------------------------------------------------------------------------------------
  // The report summary
  // ----------------------------------------------------------------------------------------

  /**
   * Render the report beside the verdict: counts per kind, TFA coverage, assembly tiers, and the
   * first few reported entries with their reasons.
   *
   * This is the visible half of hard rule 4 — "report, don't guess". The written `.report.json`
   * has always carried every omission; nothing on screen said so, and a user who does not open the
   * file cannot tell `PASSED` from `PASSED WITH OMISSIONS` by looking. The reported column is
   * therefore styled to stand out when it is non-zero and greyed when it is not.
   *
   * ⚠ Every value goes in through `textContent`, never `innerHTML`. Face names, tag names and
   * assembly names are all user data out of a `.skp`, and one of them containing markup must be
   * unremarkable rather than interesting.
   */
  function cell(row, text, className) {
    var td = document.createElement("td");
    td.textContent = text;
    if (className) td.className = className;
    row.appendChild(td);
    return td;
  }

  function countRow(table, label, counts) {
    var values = counts || {};
    var row = table.insertRow();
    cell(row, label, "label");
    cell(row, String(values["in"] || 0));
    cell(row, String(values.translated || 0));
    cell(row, String(values.reported || 0), values.reported ? "reported" : "zero");
  }

  function headerRow(table) {
    var row = table.insertRow();
    ["", "in", "translated", "reported"].forEach(function (label, index) {
      var th = document.createElement("th");
      th.textContent = label;
      if (index === 0) th.className = "label";
      row.appendChild(th);
    });
  }

  //: How many reported entries are listed on screen. The report file holds up to 200 per kind and
  //: says how many it truncated; this is a prompt to open it, not a replacement for it.
  var SUMMARY_ENTRIES = 8;

  function reportedEntries(report) {
    var entries = report.entries || {};
    var listed = [];
    for (var kind in entries) {
      if (!Object.prototype.hasOwnProperty.call(entries, kind)) continue;
      var items = entries[kind].listed || [];
      for (var i = 0; i < items.length; i++) {
        if (items[i].outcome === "reported-not-translated") listed.push(items[i]);
      }
    }
    return listed;
  }

  function showSummary(report) {
    if (!config || !config.summaryElement) return;
    var root = config.summaryElement;
    root.textContent = "";
    if (!report || !report.summary) return;
    var summary = report.summary;

    var table = document.createElement("table");
    headerRow(table);
    countRow(table, "faces", summary.faces);
    countRow(table, "apertures", summary.apertures);
    countRow(table, "thermal bridges", summary.thermal_bridges);
    root.appendChild(table);

    var facts = [];
    // TFA is a headline number and is stated whether or not anything went wrong — a model that
    // derives none (two of the five in the corpus, correctly) must look different from one that
    // lost it.
    facts.push("TFA " + (summary.tfa_m2_covered || 0) + " m² covered, " +
               (summary.tfa_m2_lost || 0) + " m² lost");
    var tiers = summary.assembly_tiers || {};
    var tierText = [];
    for (var tier in tiers) {
      if (Object.prototype.hasOwnProperty.call(tiers, tier)) tierText.push(tier + "×" + tiers[tier]);
    }
    if (tierText.length) facts.push("assembly tiers " + tierText.join(", "));
    if (report.host_notes && report.host_notes.length) {
      facts = facts.concat(report.host_notes);
    }
    var line = document.createElement("div");
    line.textContent = facts.join("  ·  ");
    root.appendChild(line);

    var reported = reportedEntries(report);
    if (!reported.length) return;
    var list = document.createElement("ul");
    list.className = "reasons";
    for (var j = 0; j < Math.min(reported.length, SUMMARY_ENTRIES); j++) {
      var item = document.createElement("li");
      item.textContent = reported[j].kind + " " + reported[j].id + " — " +
                         (reported[j].reason || "no reason given");
      list.appendChild(item);
    }
    if (reported.length > SUMMARY_ENTRIES) {
      var more = document.createElement("li");
      more.className = "more";
      more.textContent = "…and " + (reported.length - SUMMARY_ENTRIES) +
                         " more, all of them in the .report.json";
      list.appendChild(more);
    }
    root.appendChild(list);
  }

  function failureVerdict(label, error) {
    return {
      passed: false,
      checks: [{ label: label, ok: false, detail: String((error && error.message) || error) }]
    };
  }

  // ----------------------------------------------------------------------------------------
  // Boot
  // ----------------------------------------------------------------------------------------

  function mark(label) {
    timings[label] = Math.round(performance.now() - bootStarted);
  }

  function readBinary(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status + " for " + url);
      return response.arrayBuffer();
    });
  }

  function readJSON(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status + " for " + url);
      return response.json();
    });
  }

  /**
   * Install everything by unpacking it with Python's own `zipfile`.
   *
   * Every wheel is `py3-none-any`, so unpacking **is** installing — there is nothing for a
   * resolver to resolve. `micropip` is coupled to the Pyodide release and cannot run on the 0.24.1
   * that Chromium 88 forces (it raises `ImportError: cannot import name 'lockfileBaseUrl'` before
   * doing anything), so it is not shipped at all. The translator zip goes in by the identical
   * path — one mechanism, so POC-3 needs no packaging change at integration.
   */
  function unpackAll(paths) {
    return pyodide.runPythonAsync(
      [
        "import os, sysconfig, zipfile, sys",
        "target = sysconfig.get_paths()['purelib']",
        "for path in " + JSON.stringify(paths) + ":",
        "    with zipfile.ZipFile(path) as archive:",
        "        archive.extractall(target)",
        // The archive bytes are dead once unpacked; 1.5 MB of wheels would otherwise sit in MEMFS
        // alongside their own contents for the whole session.
        "    os.remove(path)",
        "sys.path_importer_cache.clear()",
        "import importlib; importlib.invalidate_caches()",
        "target"
      ].join("\n")
    );
  }

  /** Fetch every archive into the emscripten FS first, so "could not read it" and "could not
   *  install it" are never reported as one failure. */
  function stage(archives) {
    pyodide.FS.mkdirTree("/payload");
    return archives.reduce(function (chain, archive) {
      return chain.then(function (paths) {
        return readBinary(archive.url).then(function (buffer) {
          var path = "/payload/" + archive.name;
          pyodide.FS.writeFile(path, new Uint8Array(buffer));
          paths.push(path);
          return paths;
        });
      });
    }, Promise.resolve([]));
  }

  function boot() {
    bootStarted = performance.now();
    log("loading pyodide from " + config.indexURL);

    return readJSON(config.manifestURL)
      .then(function (manifest) {
        payloadInfo = { pyodide: manifest.pyodide_version, wheels: manifest.wheel_order };
        return global.loadPyodide({ indexURL: config.indexURL }).then(function (instance) {
          pyodide = instance;
          DphPlus.pyodide = instance;
          mark("pyodide_ready_ms");
          log("pyodide ready in " + timings.pyodide_ready_ms + " ms");
          var archives = manifest.wheel_order.map(function (name) {
            return { name: name, url: config.wheelBaseURL + name };
          });
          archives.push({ name: "dph_translator.zip", url: config.translatorURL });
          return stage(archives);
        });
      })
      .then(function (paths) {
        mark("payload_staged_ms");
        log(paths.length + " archives staged");
        return unpackAll(paths);
      })
      .then(function () {
        mark("wheel_unpack_ms");
        log("payload unpacked into Pyodide's site-packages");
        return readBinary(config.bootPyURL);
      })
      .then(function (buffer) {
        pyodide.FS.writeFile("/boot.py", new Uint8Array(buffer));
        return pyodide.runPythonAsync("import sys; sys.path.insert(0, '/'); import boot; 'ok'");
      })
      .then(function () {
        // `boot.import_stack()` owns the import ORDER — `honeybee_ph` must come last, because its
        // `_extend_` hooks graft `.properties.ph` onto honeybee's own classes.
        return callPython("boot.import_stack()");
      })
      .then(function (stack) {
        mark("import_ms");
        if (!stack.ok) throw new Error("import failed: " + JSON.stringify(stack.failed));
        mark("boot_ms");
        log("boot complete in " + timings.boot_ms + " ms");
        return stack;
      });
  }

  // ----------------------------------------------------------------------------------------
  // The Python seam
  // ----------------------------------------------------------------------------------------

  /** Evaluate a Python expression that returns a JSON string, and parse it. */
  function callPython(expression) {
    return pyodide.runPythonAsync(expression).then(function (text) {
      return JSON.parse(text);
    });
  }

  /**
   * The one entry point into the translator (POC-1 §4.1). The payload crosses as a Python global
   * rather than interpolated into source: a multi-megabyte string literal would have to be escaped,
   * and an escaping bug is exactly the kind of silent corruption the bridge checksums exist to catch.
   */
  function translate(payloadJSON) {
    pyodide.globals.set("_dph_payload", payloadJSON);
    return pyodide
      .runPythonAsync("import dph_translator.entry as _entry\n_entry.translate_json(_dph_payload)")
      .then(function (text) {
        // Release the extraction. POC-2's walk of a real model is megabytes, and leaving it bound
        // in Pyodide's globals would pin a second copy in the wasm heap for the dialog's life.
        pyodide.globals.set("_dph_payload", "");
        return { text: text, parsed: JSON.parse(text) };
      });
  }

  // ----------------------------------------------------------------------------------------
  // The Ruby bridge probe
  // ----------------------------------------------------------------------------------------

  /**
   * Cheap, order-sensitive checksum — djb2 truncated to a signed 32-bit integer. Must match
   * `Session#checksum` in `main.rb` byte for byte. It agrees only for the Basic Multilingual
   * Plane (JS iterates UTF-16 code units, Ruby iterates codepoints); the probe's filler is ASCII
   * digits, so that never arises.
   */
  function checksum(text) {
    var hash = 5381;
    for (var i = 0; i < text.length; i++) hash = ((hash << 5) + hash + text.charCodeAt(i)) | 0;
    return hash;
  }
  DphPlus.checksum = checksum;

  var pendingEchoes = {};
  var nextEchoId = 0;

  /** Ruby answers here. `HtmlDialog` gives each side a one-way call, so a round trip is assembled
   *  by hand: JS parks a resolver, Ruby calls back into this. */
  DphPlus.receiveEcho = function (reply) {
    var resolve = pendingEchoes[reply.id];
    delete pendingEchoes[reply.id];
    if (resolve) resolve(reply);
  };

  function echoOnce(bytes) {
    if (!host || !host.on_echo) return Promise.resolve({ bytes: bytes, ok: false, error: "no host" });
    var body = new Array(Math.max(1, Math.round(bytes / 10)) + 1).join("0123456789");
    var id = ++nextEchoId;
    var started = performance.now();
    return new Promise(function (resolve) {
      pendingEchoes[id] = resolve;
      setTimeout(function () {
        if (pendingEchoes[id]) {
          delete pendingEchoes[id];
          resolve({ id: id, timeout: true });
        }
      }, 30000);
      host.on_echo(JSON.stringify({ id: id, size: body.length, sum: checksum(body), body: body }));
    }).then(function (reply) {
      return {
        bytes: body.length,
        ok: !!reply && reply.size === body.length && reply.sum === checksum(body),
        ms: Math.round(performance.now() - started)
      };
    });
  }

  /**
   * Round-trip escalating payloads and report the largest that survived intact.
   *
   * Checks a checksum rather than "did not throw": a bridge that silently truncates is far more
   * dangerous than one that errors, and truncation is the documented risk of `execute_script`.
   * Phase 3 already measured the ceiling at ≥4 MB each way; this is a regression check on the
   * restructured bridge, not a re-measurement, so it stops at 1 MB.
   */
  function echoProbe() {
    var sizes = [1e3, 1e5, 1e6];
    var results = [];
    return sizes
      .reduce(function (chain, size) {
        return chain.then(function () {
          return echoOnce(size).then(function (outcome) { results.push(outcome); });
        });
      }, Promise.resolve())
      .then(function () {
        var passed = results.filter(function (r) { return r.ok; });
        return {
          attempts: results,
          max_ok_bytes: passed.length ? passed[passed.length - 1].bytes : 0
        };
      });
  }

  // ----------------------------------------------------------------------------------------
  // Actions
  // ----------------------------------------------------------------------------------------

  function measurements() {
    var report = { timings: timings, payload: payloadInfo };
    try {
      var heap = pyodide && pyodide._module && pyodide._module.HEAP8;
      if (heap) report.wasm_heap_mb = +(heap.length / 1048576).toFixed(1);
    } catch (error) {
      report.wasm_heap_mb = null;
    }
    // `performance.memory` is Chromium-only and behind a flag in some builds; its absence is
    // itself worth recording rather than papering over.
    report.js_heap_mb = performance.memory
      ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(1)
      : null;
    return report;
  }

  function runSelfTest() {
    return echoProbe().then(function (bridge) {
      return callPython("boot.self_test()").then(function (result) {
        // Boot measurements ride in the envelope (see `answer`), not here — one place, so the
        // self-test report and a translation report carry the same numbers under the same key.
        result.bridge = bridge;
        // Python graded its own checks; the bridge is the one thing only this side can see.
        result.verdict.checks.push({
          label: "bridge round trip",
          ok: bridge.max_ok_bytes > 0,
          detail: bridge.max_ok_bytes + " bytes"
        });
        result.verdict.passed = result.verdict.checks.every(function (check) { return check.ok; });
        showVerdict(result.verdict);
        return { text: JSON.stringify(result), parsed: result };
      });
    });
  }

  /**
   * Translate, and hand the translator's own string onward **verbatim**.
   *
   * The HBJSON is never re-serialised on this side. It is parsed once — the banner needs the
   * verdict — but `resultText` is what travels to Ruby, so a POC-3-sized model crosses
   * `execute_script` once rather than being parsed and rebuilt on the way. Runtime measurements
   * ride in their own envelope field; Ruby merges them into the report it writes, which keeps this
   * function out of the translator's output entirely.
   */
  function runTranslate(payloadJSON) {
    if (!payloadJSON) throw new Error("translate dispatched with no payload");
    return translate(payloadJSON).then(function (outcome) {
      showVerdict(outcome.parsed.verdict);
      // A rendering fault in the summary must never fail a translation that succeeded. The
      // HBJSON is already built and about to cross to Ruby; losing it to a DOM error would be
      // the report killing the thing it reports on.
      try {
        showSummary(outcome.parsed.report);
      } catch (error) {
        log("could not render the report summary: " + error);
      }
      return outcome;
    });
  }

  function perform(message) {
    if (message.action === "self_test") return runSelfTest();
    if (message.action === "translate") return runTranslate(message.payload);
    return Promise.reject(new Error("unknown action: " + message.action));
  }

  function answer(action, ok, outcome, error) {
    var reply = { action: action, ok: ok };
    if (ok) {
      reply.payload = outcome.text;
      reply.runtime = measurements();
    } else {
      reply.error = String((error && error.stack) || error);
      showVerdict(failureVerdict(action, error));
    }
    if (host && host.on_result) {
      host.on_result(JSON.stringify(reply));
    } else {
      // Standalone (headless harness) path — nothing to report to, so park it where a driver
      // can poll for it.
      global.__DPH_RESULT = reply;
    }
  }

  /**
   * Ruby → JS. `message` is `{action, payload}`, `payload` a JSON string or null.
   *
   * Ruby only dispatches from its `on_ready` callback, which this side fires after `boot()` has
   * resolved — so `ready` is a guard against a future caller, not a queue. An action that arrives
   * early is refused loudly rather than buffered: a silently deferred translate would report
   * against a runtime that may never come up.
   */
  DphPlus.dispatch = function (message) {
    if (!ready) {
      answer(message.action, false, null, new Error("dispatched before the runtime was ready"));
      return;
    }
    log("action: " + message.action +
        (message.payload ? " (" + message.payload.length + " chars)" : ""));
    Promise.resolve()
      .then(function () { return perform(message); })
      .then(function (outcome) { answer(message.action, true, outcome, null); })
      .catch(function (error) { answer(message.action, false, null, error); });
  };

  DphPlus.start = function () {
    boot()
      .then(function () {
        ready = true;
        // Readiness has to be announced from this side: an `execute_script` issued straight after
        // `HtmlDialog#show` can land before these scripts have run.
        if (host && host.on_ready) {
          host.on_ready("");
        } else {
          // Standalone page load: nothing will ever dispatch an action, so nothing else will
          // write a verdict. Leaving the banner on "booting…" would show a run that SUCCEEDED
          // looking like one still in progress — Finding 41's failure mode in miniature, and the
          // reason "end with a verdict" is a rule rather than a nicety (POC-1 §7.2).
          log("no `sketchup` host object — open this through the extension, not directly");
          showVerdict({
            passed: true,
            checks: [
              { label: "runtime boot", ok: true, detail: "standalone page load" },
              { label: "no SketchUp host", ok: true,
                detail: "nothing dispatched; open through the extension to translate a model" }
            ]
          });
        }
      })
      .catch(function (error) {
        ready = false;
        showVerdict(failureVerdict("runtime boot", error));
        answer("boot", false, null, error);
      });
  };
})(typeof window !== "undefined" ? window : globalThis);
