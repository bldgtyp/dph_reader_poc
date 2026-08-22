# /// script
# requires-python = ">=3.11"
# dependencies = ["websocket-client>=1.7"]
# ///
"""DesignPH-PLUS POC — drive the built extension page in headless **Chromium 88**.

**This does not test SketchUp.** It tests the same *engine*: SketchUp 2022's `HtmlDialog` is CEF
88.2.4, i.e. Chromium 88 (January 2021), read off the framework's `Info.plist`
(`00_Context/SKETCHUP_RUNTIME.md` §4.1). Running the real page against a matching snapshot converts
"ask Ed to click and report back" into a local loop, and is how the Pyodide version ceiling was
found. It is the agent's own gate: green here before Ed is asked for anything.

⚠ **The browser version is part of the verification.** Pointing this at the modern Chrome on the
machine is a false green — every API Chromium 88 lacks would work. The run therefore *refuses* any
major version but 88 unless `--allow-any-version` is passed, and always prints what it drove.

Get the engine (~120 MB, cached outside the repo):

    mkdir -p ~/.cache/dph-plus && cd ~/.cache/dph-plus
    curl -sL -o chrome88.zip \\
      https://commondatastorage.googleapis.com/chromium-browser-snapshots/Mac/827102/chrome-mac.zip
    unzip -q chrome88.zip -d chromium-88

Usage:
    uv run poc/tools/verify_in_chrome.py
    uv run poc/tools/verify_in_chrome.py --headed --chrome /path/to/Chromium
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import websocket

HERE = Path(__file__).resolve().parent
POC = HERE.parent
REPO = POC.parent
EXTENSION_ROOT = POC / "ext" / "dph_plus_poc"
STUB_EXTRACTION = EXTENSION_ROOT / "fixtures" / "stub_extraction.json"
DEFAULT_CHROME = Path.home() / ".cache/dph-plus/chromium-88/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
DEFAULT_OUT = REPO / "planning" / "POC" / "RESULTS" / "baselines"

#: The engine SketchUp 2022 embeds. Anything else is not a verification of this project.
REQUIRED_MAJOR = 88

#: `--headless=new` only exists from Chrome 109; an old build needs the original flag.
LEGACY_HEADLESS_BELOW = 109

#: Deliberately minimal. No `--allow-file-access-from-files`, no `--disable-web-security`: a run
#: that needed those would prove nothing about SketchUp, which sets neither.
CHROME_FLAGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-gpu",
    # CDP refuses websocket handshakes from an unlisted origin; the driver connects from an
    # ephemeral localhost port, so there is no stable origin to list.
    "--remote-allow-origins=*",
]

#: A stand-in for SketchUp's injected `sketchup` object. It implements the same four callbacks
#: `main.rb` registers, with the same protocol, so `index.html` and `app.js` run unmodified — the
#: house rule that one code path serves every host. It drives both menu actions in sequence.
#:
#: What it proves: the wiring, the Pyodide boot on a Chromium 88 engine, the payload install, the
#: translator seam. What it cannot prove: `HtmlDialog`'s own payload limits and its threading —
#: which is exactly what Ed's SketchUp run is for.
SKETCHUP_STUB = """
window.__DPH_DRIVER = { results: {} };
window.sketchup = {
  on_log: function () {},
  on_ready: function () {
    window.DphPlus.dispatch({ action: 'self_test', payload: null });
  },
  on_echo: function (json) {
    var message = JSON.parse(json);
    window.DphPlus.receiveEcho({
      id: message.id,
      size: message.body.length,
      sum: window.DphPlus.checksum(message.body)
    });
  },
  on_result: function (json) {
    // Same shape Ruby sees: `payload` is the translator's own string, forwarded verbatim, and
    // `runtime` carries the boot measurements the page alone can see.
    var reply = JSON.parse(json);
    var result = reply.ok ? JSON.parse(reply.payload) : reply;
    result.ok = reply.ok;
    result.runtime = reply.runtime;
    window.__DPH_DRIVER.results[reply.action] = result;
    if (reply.action === 'self_test' && reply.ok) {
      window.DphPlus.dispatch({ action: 'translate', payload: %(extraction)s });
    } else {
      window.__DPH_DRIVER.done = true;
    }
  }
};
"""

#: What the page actually SHOWS, read back out of the DOM once the run has finished.
#:
#: ⚠ **This exists because grading the verdict object is not grading the page.** Adelphi's first
#: real export displayed a green `PASSED` while the message box beside it said `PASSED WITH
#: OMISSIONS` and 40 assemblies had gone unresolved — `showVerdict` was rendering `verdict.passed`,
#: a boolean, when the verdict has had three states since POC-3 §9.
#:
#: This harness could not have caught it, and the reason is worth keeping: it checked
#: `verdict.passed` too. **The stub fixture has produced `PASSED WITH OMISSIONS` from the day it was
#: written** — so every CI run since then rendered the wrong banner, headlessly, with nobody
#: reading it. The failing case was on screen the whole time and no assertion looked at the screen.
RENDERED = """
(function () {
  var verdict = document.getElementById('verdict');
  var summary = document.getElementById('summary');
  return {
    banner: verdict ? verdict.textContent.split('\\n')[0].trim() : null,
    banner_class: verdict ? verdict.className : null,
    summary_text: summary ? summary.textContent.replace(/\\s+/g, ' ').trim() : '',
    summary_rows: summary ? summary.querySelectorAll('tr').length : 0
  };
})()
"""

#: `app.js` reports through the host rather than by returning a promise, so the driver polls the
#: stub's completion flag. A Pyodide boot that fails inside `loadPyodide` does not always reject —
#: a wasm `CompileError` can leave the promise pending forever — so the deadline is what turns a
#: hang into a reportable negative result.
DRIVER_WAIT = """
new Promise(function (resolve) {
  var deadline = Date.now() + %(timeout)d;
  (function poll() {
    if (window.__DPH_DRIVER && window.__DPH_DRIVER.done) {
      return resolve(window.__DPH_DRIVER.results);
    }
    if (Date.now() > deadline) {
      var log = window.DphPlus ? window.DphPlus.logLines : [];
      return resolve({ fatal: 'the page never reported', log: log });
    }
    setTimeout(poll, 250);
  })();
});
"""


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def serve(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def chrome_major(binary: Path) -> int:
    try:
        output = subprocess.run([str(binary), "--version"], capture_output=True, text=True).stdout
        return int(re.search(r"(\d+)\.", output).group(1))
    except Exception:  # noqa: BLE001 — an unknown version just means the modern flag
        return 999


def page_websocket(debug_port: int, timeout: float = 30.0) -> str:
    """Poll Chrome's debugging endpoint until the extension page target appears."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json") as response:
                for target in json.load(response):
                    if target["type"] == "page" and target.get("url", "").endswith(".html"):
                        return target["webSocketDebuggerUrl"]
        except Exception:  # noqa: BLE001 — Chrome is simply not up yet
            pass
        time.sleep(0.25)
    raise SystemExit("Chrome never exposed the page over CDP")


class CDP:
    """The three lines of Chrome DevTools Protocol this verification actually needs."""

    def __init__(self, url: str, timeout: float) -> None:
        self.socket = websocket.create_connection(url, timeout=timeout)
        self.next_id = 0
        self.console: list[str] = []

    def send(self, method: str, **params: Any) -> dict[str, Any]:
        self.next_id += 1
        message_id = self.next_id
        self.socket.send(json.dumps({"id": message_id, "method": method, "params": params}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("method") == "Runtime.consoleAPICalled":
                self.console.append(
                    " ".join(str(a.get("value", a.get("description", ""))) for a in message["params"]["args"])
                )
            elif message.get("method") == "Log.entryAdded":
                entry = message["params"]["entry"]
                self.console.append(
                    "[browser:{}] {} {}".format(entry["level"], entry["text"], entry.get("url", ""))
                )
            elif message.get("method") == "Runtime.exceptionThrown":
                detail = message["params"]["exceptionDetails"]
                self.console.append("UNCAUGHT: {} {}".format(detail.get("text"), detail.get("url")))
            elif message.get("id") == message_id:
                return message

    def evaluate(self, expression: str) -> Any:
        reply = self.send("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "error" in reply:
            raise RuntimeError(str(reply["error"]))
        outcome = reply["result"]
        if "exceptionDetails" in outcome:
            raise RuntimeError(json.dumps(outcome["exceptionDetails"])[:800])
        return outcome["result"].get("value")

    def close(self) -> None:
        try:
            self.socket.close()
        except Exception:  # noqa: BLE001 — closing a dead socket is not a finding
            pass


def check_staged_payload() -> None:
    """Refuse to verify a tree the build tools have not brought up to date.

    Serving a stale staged copy makes the run report on code the `.rbz` does not contain — the
    exact failure `build_rbz.py --check` exists to remove.
    """
    if not (EXTENSION_ROOT / "vendor" / "manifest.json").exists():
        raise SystemExit("extension vendor tree not staged — run build_rbz.py first")
    result = subprocess.run(
        [sys.executable, str(HERE / "build_rbz.py"), "--check"], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise SystemExit(result.stdout + result.stderr)
    print(f"  {result.stdout.strip()}")


def run(
    binary: Path, major: int, extraction: Path, headed: bool, timeout: float, boot_timeout: float
) -> dict[str, Any]:
    port = free_port()
    server = serve(EXTENSION_ROOT, port)
    url = f"http://127.0.0.1:{port}/html/index.html"
    debug_port = free_port()
    profile = Path(tempfile.mkdtemp(prefix="dphplus-chrome-"))
    command = [
        str(binary),
        *CHROME_FLAGS,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={profile}",
    ]
    if not headed:
        command.append("--headless" if major < LEGACY_HEADLESS_BELOW else "--headless=new")
    command.append(url)

    print(f"  serving the staged extension at {url}")
    chrome = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = None
    started = time.time()
    try:
        client = CDP(page_websocket(debug_port), timeout=timeout)
        client.send("Runtime.enable")
        client.send("Log.enable")
        client.send("Page.enable")
        # The page auto-starts as soon as the stub host answers, so the stub has to be in place
        # before any of the page's own scripts run — hence a reload after injecting it.
        client.send(
            "Page.addScriptToEvaluateOnNewDocument",
            source=SKETCHUP_STUB % {"extraction": json.dumps(extraction.read_text())},
        )
        client.send("Page.reload")
        # The reload tears down the execution context the evaluate would bind to, and older builds
        # report that as a hard CDP error rather than queueing. Retry until the new one exists.
        deadline = time.time() + 30
        while True:
            try:
                results = client.evaluate(DRIVER_WAIT % {"timeout": int(boot_timeout * 1000)})
                break
            except RuntimeError as error:
                if "context was destroyed" not in str(error) or time.time() > deadline:
                    raise
                time.sleep(0.5)
        return {
            "results": results or {},
            "rendered": client.evaluate(RENDERED) or {},
            "seconds": round(time.time() - started, 1),
            "console": client.console,
        }
    except Exception as error:  # noqa: BLE001 — a driver failure is a recordable result
        return {
            "results": {"fatal": str(error)},
            "rendered": {},
            "seconds": round(time.time() - started, 1),
            "console": client.console if client else [],
        }
    finally:
        if client:
            client.close()
        chrome.terminate()
        try:
            chrome.wait(timeout=10)
        except subprocess.TimeoutExpired:
            chrome.kill()
        server.shutdown()
        shutil.rmtree(profile, ignore_errors=True)


def summarise(outcome: dict[str, Any], major: int) -> bool:
    """Print the verdict. End with a grade, never with whatever the last line happened to be."""
    results = outcome["results"]
    self_test = results.get("self_test", {})
    translate = results.get("translate", {})
    rendered = outcome.get("rendered") or {}
    headline = translate.get("verdict", {}).get("headline")
    checks = [
        (f"engine is Chromium {REQUIRED_MAJOR}", major == REQUIRED_MAJOR, str(major)),
        (
            "self-test passed",
            bool(self_test.get("verdict", {}).get("passed")),
            json.dumps(self_test.get("verdict", {}).get("checks", []))[:120],
        ),
        (
            "translation passed",
            bool(translate.get("verdict", {}).get("passed")),
            # `summary.faces` is `{in, translated, reported}` — an earlier flat `faces_translated`
            # key printed `None` here for as long as it was wrong, which is what a detail string
            # nobody grades gets you.
            "{} of {} faces".format(
                translate.get("report", {}).get("summary", {}).get("faces", {}).get("translated"),
                translate.get("report", {}).get("summary", {}).get("faces", {}).get("in"),
            ),
        ),
        (
            "HBJSON produced",
            bool(translate.get("hbjson")),
            "{} bytes".format(len(str(translate.get("hbjson", "")))),
        ),
        # ⚠ What the page SHOWS, not what the result object says. See `RENDERED`.
        (
            "banner shows the verdict's own headline",
            bool(headline) and rendered.get("banner") == headline,
            "banner {!r} vs headline {!r}".format(rendered.get("banner"), headline),
        ),
        (
            "report summary rendered",
            rendered.get("summary_rows", 0) >= 4 and "apertures" in rendered.get("summary_text", ""),
            "{} table rows".format(rendered.get("summary_rows", 0)),
        ),
    ]
    passed = all(ok for _, ok, _ in checks)

    print(
        "\n  ================ {} ================  ({} s)".format(
            "PASSED" if passed else "FAILED", outcome["seconds"]
        )
    )
    for label, ok, detail in checks:
        print("  {}{}  ({})".format("ok    " if ok else "FAIL  ", label, detail))

    timings = self_test.get("runtime", {}).get("timings", {})
    if timings:
        print("\n  pyodide ready : {} ms".format(timings.get("pyodide_ready_ms")))
        print("  payload staged: {} ms".format(timings.get("payload_staged_ms")))
        print("  wheels unpack : {} ms".format(timings.get("wheel_unpack_ms")))
        print("  imports done  : {} ms   <- cold start".format(timings.get("boot_ms")))
        print("  wasm heap     : {} MB".format(self_test.get("runtime", {}).get("wasm_heap_mb")))
        print("  bridge echo   : {} bytes max".format(self_test.get("bridge", {}).get("max_ok_bytes")))
    if not passed:
        if results.get("fatal"):
            print("\n  fatal: {}".format(results["fatal"]))
        for line in outcome["console"][-15:]:
            print(f"       | {line}")
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chrome", type=Path, default=DEFAULT_CHROME, help="browser binary; must be the Chromium 88 snapshot"
    )
    parser.add_argument(
        "--allow-any-version",
        action="store_true",
        help="drive a browser that is not Chromium 88 (NOT a verification)",
    )
    parser.add_argument(
        "--extraction",
        type=Path,
        default=STUB_EXTRACTION,
        help="extraction JSON to translate. POC-4 points this at a captured real fixture to "
        "compare output across CPython, Chromium 88 and SketchUp for the SAME input",
    )
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--boot-timeout", type=float, default=180.0, help="seconds before a hung boot is failed"
    )
    parser.add_argument(
        "--hbjson-out",
        type=Path,
        default=None,
        help="write the produced HBJSON here, in full and as bytes. POC-4's byte-identity check "
        "compares this against the same extraction translated under CPython 3.11",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--tag", default="", help="suffix for the baseline filename")
    args = parser.parse_args()

    if not args.chrome.exists():
        raise SystemExit(
            f"browser not found at {args.chrome}\nsee this file's docstring for the one-line download"
        )
    major = chrome_major(args.chrome)
    print(f"browser: {args.chrome} (major {major})")
    if major != REQUIRED_MAJOR and not args.allow_any_version:
        raise SystemExit(
            f"refusing to run: SketchUp 2022 is Chromium {REQUIRED_MAJOR}, this binary is "
            f"{major}. A pass on a modern engine is a false green."
        )

    check_staged_payload()
    if not args.extraction.exists():
        raise SystemExit(f"no extraction JSON at {args.extraction}")
    print(f"  extraction: {args.extraction}")
    outcome = run(args.chrome, major, args.extraction, args.headed, args.timeout, args.boot_timeout)
    passed = summarise(outcome, major)

    translate = outcome["results"].get("translate")
    if args.hbjson_out and isinstance(translate, dict) and translate.get("hbjson"):
        # ⚠ Bytes, and UTF-8 named explicitly. The whole point of the artefact is a hash, and
        # `write_text` would take its encoding from the locale — which would make the comparison a
        # statement about the machine rather than about the two runtimes.
        args.hbjson_out.parent.mkdir(parents=True, exist_ok=True)
        args.hbjson_out.write_bytes(str(translate["hbjson"]).encode("utf-8"))
        print(f"  hbjson: {args.hbjson_out} ({args.hbjson_out.stat().st_size} bytes)")

    # The HBJSON is already sized in the report; keeping a whole model in a planning baseline would
    # bloat the repo for nothing.
    if isinstance(translate, dict) and "hbjson" in translate:
        translate["hbjson_sample"] = str(translate.pop("hbjson"))[:400]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    destination = args.out_dir / f"poc1_chromium{major}{args.tag}.json"
    destination.write_text(
        json.dumps({"passed": passed, "chromium_major": major, **outcome}, indent=2) + "\n"
    )
    print(f"\n  written: {destination.relative_to(REPO)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
