# /// script
# requires-python = ">=3.11"
# dependencies = ["websocket-client>=1.7"]
# ///
"""Phase 3 — run the spike in desktop Chrome, headless, and record what happened.

**This does not test SketchUp.** `HtmlDialog` is Chromium (CEF), so Chrome is the closest thing to
it that can be automated here, and it separates two questions the phase would otherwise have to
answer at once:

  * *does our code work at all* — answered here, repeatably, before Ed installs anything
  * *does `HtmlDialog` let it work* — answerable only in SketchUp, and the only question left over

The `file` mode is the one that matters. It loads the page over `file://` with no permissive flags,
which is the same origin situation `HtmlDialog#set_file` creates, and therefore exercises the
phase's top risk: whether Pyodide can fetch its own `.wasm` from a local page. The `http` mode
serves the identical tree from `127.0.0.1` and is the control — plus a preview of the fallback
architecture (a WEBrick server inside the extension) if `file://` turns out to be a dead end.

Usage:
    uv run planning/spikes/pyodide/verify_in_chrome.py                    # both modes
    uv run planning/spikes/pyodide/verify_in_chrome.py --mode file --headed
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
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import websocket

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EXTENSION_ROOT = HERE / "ext" / "dph_plus_spike"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

#: `--headless=new` only exists from Chrome 109. An old build needs the original flag, which is how
#: a Chromium 88 snapshot — the engine SketchUp 2022 actually embeds — can be driven here.
LEGACY_HEADLESS_BELOW = 109
DEFAULT_OUT = REPO / "planning" / "01_sketchup-export" / "feasibility" / "RESULTS" / "baselines"

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
#: `main.rb` registers, with the same protocol, so `index.html` runs unmodified. What this proves is
#: the *wiring* — that `spike_ready` fires, that `startSpike` is reachable, that the bridge round
#: trip resolves. It cannot prove anything about `HtmlDialog`'s payload limits, which is why the
#: sizes it echoes are small and why Ed's run is still required.
SKETCHUP_STUB = """
window.sketchup = {
  spike_log: function () {},
  spike_ready: function () {
    var faces = [];
    for (var i = 0; i < %(faces)d; i++) {
      var x = (i %% 40) * 3.0, y = Math.floor(i / 40) * 3.0;
      faces.push({
        id: 'stub_face_' + i,
        area_group: i %% 3 === 0 ? '8' : 10,
        vertices: [[x, y, 0], [x + 2.8, y, 0], [x + 2.8, y + 2.8, 0], [x, y + 2.8, 0]]
      });
    }
    startSpike({
      strategy: 'stub',
      faces: { model_name: 'Stub_Model', units: 'Meters', faces: faces }
    });
  },
  spike_bridge_echo: function (json) {
    var message = JSON.parse(json);
    window.SPIKE_HOST.resolve(message.id, {
      id: message.id, size: message.body.length, sum: SPIKE.checksum(message.body)
    });
  },
  spike_bridge_down_result: function () {},
  spike_probe_down: function () {},
  spike_result: function (json) { window.__SPIKE_DONE = json; }
};
"""


@dataclass
class Outcome:
    mode: str
    ok: bool
    seconds: float
    result: dict[str, Any]
    console: list[str]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def serve(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def page_websocket(debug_port: int, timeout: float = 30.0) -> str:
    """Poll Chrome's debugging endpoint until the harness page target appears."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json") as response:
                for target in json.load(response):
                    if target["type"] == "page" and target.get("url", "").endswith((".html", ".html?manual")):
                        return target["webSocketDebuggerUrl"]
        except Exception:  # noqa: BLE001 — Chrome is simply not up yet
            pass
        time.sleep(0.25)
    raise SystemExit("Chrome never exposed the harness page over CDP")


class CDP:
    """The three lines of Chrome DevTools Protocol this spike actually needs."""

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
                self.console.append(f"[browser:{entry['level']}] {entry['text']} {entry.get('url', '')}")
            elif message.get("method") == "Runtime.exceptionThrown":
                detail = message["params"]["exceptionDetails"]
                self.console.append("UNCAUGHT: " + json.dumps(detail.get("text")) + " " + str(detail.get("url")))
            elif message.get("id") == message_id:
                return message

    def evaluate(self, expression: str) -> Any:
        reply = self.send(
            "Runtime.evaluate",
            expression=expression,
            awaitPromise=True,
            returnByValue=True,
        )
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


def chrome_major(binary: Path) -> int:
    """Major version of a Chrome/Chromium binary, so the right headless flag is used."""
    try:
        output = subprocess.run([str(binary), "--version"], capture_output=True, text=True).stdout
        return int(re.search(r"(\d+)\.", output).group(1))
    except Exception:  # noqa: BLE001 — an unknown version just means the modern flag
        return 999


def run_mode(
    mode: str, faces: int, headed: bool, timeout: float, binary: Path, boot_timeout: float
) -> Outcome:
    if not binary.exists():
        raise SystemExit(f"browser not found at {binary}")

    server = None
    if mode == "file-permissive":
        # NOT what SketchUp does. This run exists to name the exact capability a `file://` host
        # would have to grant, so the SketchUp result can be read as "HtmlDialog does/does not
        # enable local file access" rather than as an unexplained failure.
        command_extra = ["--allow-file-access-from-files"]
    else:
        command_extra = []

    if mode == "extension":
        # This mode serves the *staged* copy inside the extension tree, not `vendor/`. Re-vendoring
        # without rebuilding leaves the two on different Pyodide releases, and the symptom is a
        # failure that looks like the runtime under test rather than a stale file.
        staged = EXTENSION_ROOT / "vendor" / "manifest.json"
        source = HERE / "vendor" / "manifest.json"
        if not staged.exists():
            raise SystemExit("extension vendor tree not staged — run build_rbz.py first")
        if json.loads(staged.read_text())["pyodide_version"] != json.loads(source.read_text())["pyodide_version"]:
            raise SystemExit(
                "staged extension payload is a different Pyodide than vendor/ — run build_rbz.py"
            )
        port = free_port()
        server = serve(EXTENSION_ROOT, port)
        url = f"http://127.0.0.1:{port}/html/index.html"
    elif mode == "http":
        port = free_port()
        server = serve(HERE, port)
        url = f"http://127.0.0.1:{port}/harness/harness.html?manual"
    else:
        url = (HERE / "harness" / "harness.html").as_uri() + "?manual"

    debug_port = free_port()
    profile = Path(tempfile.mkdtemp(prefix="dphplus-chrome-"))
    command = [
        str(binary),
        *CHROME_FLAGS,
        *command_extra,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={profile}",
    ]
    if not headed:
        command.append("--headless" if chrome_major(binary) < LEGACY_HEADLESS_BELOW else "--headless=new")
    command.append(url)

    print(f"  {mode}: {url}")
    chrome = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = None
    started = time.time()
    try:
        client = CDP(page_websocket(debug_port), timeout=timeout)
        client.send("Runtime.enable")
        client.send("Log.enable")
        if mode == "extension":
            # The page auto-starts as soon as the stub host answers, so the stub has to be in
            # place before any of the page's own scripts run — hence a reload after injecting it.
            client.send("Page.enable")
            client.send(
                "Page.addScriptToEvaluateOnNewDocument",
                source=SKETCHUP_STUB % {"faces": faces},
            )
            client.send("Page.reload")
            # The reload tears down the execution context the evaluate would bind to, and older
            # builds report that as a hard CDP error rather than queueing. Retry until the new
            # context exists.
            deadline = time.time() + 30
            while True:
                try:
                    result = client.evaluate(EXTENSION_WAIT)
                    break
                except RuntimeError as error:
                    if "context was destroyed" not in str(error) or time.time() > deadline:
                        raise
                    time.sleep(0.5)
            # `index.html` hands the whole HBJSON to the host so Ruby can write it to disk. Keeping
            # it here would put a multi-megabyte model into a planning-repo baseline for no gain —
            # its size is already recorded as `step4.hbjson_bytes`.
            if isinstance(result, dict) and "hbjson" in result:
                result["hbjson_sample"] = result.pop("hbjson")[:400]
        else:
            wait_for_harness(client)
            # A Pyodide boot that fails inside `loadPyodide` does not always reject — a wasm
            # `CompileError` can leave the promise pending forever, which turns a clear negative
            # result into a 10-minute timeout. Race it, and report what the log had reached.
            result = client.evaluate(HARNESS_WAIT % {"faces": faces, "timeout": int(boot_timeout * 1000)})
        elapsed = time.time() - started
        ok = bool(result) and "fatal" not in result and result.get("boot", {}).get("step2", {}).get("ok")
        return Outcome(mode, bool(ok), round(elapsed, 1), result or {}, client.console)
    except Exception as error:  # noqa: BLE001 — a driver failure is a recordable result
        console = client.console if client else []
        return Outcome(mode, False, round(time.time() - started, 1), {"driver_error": str(error)}, console)
    finally:
        if client:
            client.close()
        chrome.terminate()
        try:
            chrome.wait(timeout=10)
        except subprocess.TimeoutExpired:
            chrome.kill()
        if server:
            server.shutdown()
        shutil.rmtree(profile, ignore_errors=True)


#: Bounds a harness run, so a Pyodide boot that hangs rather than rejects still yields a result.
HARNESS_WAIT = """
Promise.race([
  window.runSpike(%(faces)d),
  new Promise(function (resolve) {
    setTimeout(function () {
      resolve({ fatal: 'boot did not settle within %(timeout)d ms', log: SPIKE.logLines });
    }, %(timeout)d);
  })
]);
"""

#: `index.html` reports through the host rather than by returning a promise, so the driver waits on
#: the stub's completion flag instead.
EXTENSION_WAIT = """
new Promise(function (resolve) {
  var deadline = Date.now() + 600000;
  (function poll() {
    if (window.__SPIKE_DONE) return resolve(JSON.parse(window.__SPIKE_DONE));
    if (Date.now() > deadline) return resolve({ fatal: 'extension page never reported' });
    setTimeout(poll, 250);
  })();
});
"""

def wait_for_harness(client: CDP, timeout: float = 20.0) -> None:
    """Block until the page's scripts have run, and say precisely what is missing if they have not.

    Worth the extra code: the interesting failure mode on `file://` is that a `<script src>` never
    loads, and the symptom of that — `window.runSpike is not a function` — names the wrong culprit.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if client.evaluate("typeof window.runSpike === 'function'"):
            return
        time.sleep(0.25)
    snapshot = client.evaluate(
        "JSON.stringify({"
        "  spike_js: typeof window.SPIKE,"
        "  pyodide_js: typeof window.loadPyodide,"
        "  scripts: [].map.call(document.scripts, function (s) { return s.src; }),"
        "  ready: document.readyState"
        "})"
    )
    raise RuntimeError("harness never initialised: " + str(snapshot))


def summarise(outcome: Outcome) -> None:
    result = outcome.result
    boot = result.get("boot", {})
    print(f"\n  == {outcome.mode} ==  {'PASS' if outcome.ok else 'FAIL'}  ({outcome.seconds}s wall clock)")
    if not outcome.ok:
        print(f"     {result.get('fatal') or result.get('driver_error')}")
        for line in outcome.console[-12:]:
            print(f"       | {line}")
        return
    timings = boot.get("timings", {})
    print(f"     asset reads via      : {boot.get('fetch_strategy')}")
    print(f"     wheels installed via : {boot.get('install_strategy')}")
    print(f"     pyodide ready        : {timings.get('pyodide_ready_ms')} ms")
    print(f"     wheels staged        : {timings.get('wheels_fetched_ms')} ms")
    print(f"     wheels installed     : {timings.get('wheels_installed_ms')} ms")
    print(f"     import honeybee done : {timings.get('steps_2_3_ms')} ms  <- cold start")
    print(f"     warm re-run          : {result.get('warm_rerun_ms')} ms")
    print(f"     memory               : {boot.get('memory')}")
    step4 = result.get("step4", {})
    print(
        f"     step 4               : {step4.get('faces_translated')}/{step4.get('faces_in')} faces, "
        f"payload {step4.get('payload_bytes', 0) / 1e6:.2f} MB in, "
        f"HBJSON {step4.get('hbjson_bytes', 0) / 1e6:.2f} MB out, "
        f"{step4.get('wall_clock_ms')} ms"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["file", "file-permissive", "http", "extension", "all"],
        default="all",
    )
    parser.add_argument("--faces", type=int, default=1441, help="synthetic face count for step 4")
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--chrome",
        type=Path,
        default=CHROME,
        help="browser binary. Point at a Chromium 88 snapshot to reproduce SketchUp 2022's engine",
    )
    parser.add_argument("--tag", default="", help="suffix for the baseline filenames")
    parser.add_argument(
        "--boot-timeout", type=float, default=120.0, help="seconds before a hung boot is failed"
    )
    args = parser.parse_args()

    if not (HERE / "vendor" / "pyodide" / "pyodide.js").exists():
        raise SystemExit("vendor tree missing — run vendor_payload.py first")

    modes = ["file", "file-permissive", "http", "extension"] if args.mode == "all" else [args.mode]
    print(f"browser: {args.chrome} (major {chrome_major(args.chrome)})")
    outcomes = [
        run_mode(mode, args.faces, args.headed, args.timeout, args.chrome, args.boot_timeout)
        for mode in modes
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for outcome in outcomes:
        summarise(outcome)
        destination = args.out_dir / f"phase3_chrome_{outcome.mode}{args.tag}.json"
        destination.write_text(
            json.dumps(
                {
                    "mode": outcome.mode,
                    "ok": outcome.ok,
                    "wall_clock_s": outcome.seconds,
                    "result": outcome.result,
                    "console": outcome.console,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"     written              : {destination.relative_to(REPO)}")

    return 0 if all(o.ok for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
