# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- exercise the loopback server outside SketchUp.
#
#     ruby poc/ext/tests/test_static_server.rb
#
# The Phase 3 spike's first SketchUp run failed with a blank dialog and a port
# that refused connections, and there was no way to tell a broken server from a
# dialog that would not load one. This closes that gap: it loads the real
# `main.rb` against a stub SketchUp API -- which also catches a menu or constant
# error at load time -- and drives the real `StaticServer` over a real socket,
# so the request path, the path token, the MIME types and the headers are all
# checked here rather than in Ed's SketchUp session.
#
# ⚠ What it CANNOT check is the thing that broke: `UI.start_timer` is stubbed
# with a plain Ruby `Thread`, which works properly in stock Ruby. In SketchUp it
# is the reverse -- threads starve and the timer works -- which is exactly why
# the real code uses the timer. Treat a pass here as "the HTTP is correct", not
# as "it will serve inside SketchUp".
#
# The collector has its own suite next door: `test_collector.rb`.
# ---------------------------------------------------------------------------
require "fileutils"
require "net/http"
require_relative "sketchup_stub"

# A worker or pump thread that dies quietly would take the whole server with it
# in SketchUp, where the symptom is another hang. Make it loud here instead.
Thread.abort_on_exception = true

load File.join(__dir__, "..", "dph_plus_poc", "main.rb")

# -- drive it ----------------------------------------------------------------

EXT_ROOT = File.expand_path(File.join(__dir__, "..", "dph_plus_poc"))
base, stop, request_count = DphPlusPoc::StaticServer.start(EXT_ROOT)
puts "serving #{EXT_ROOT}\n     at #{base}\n\n"

# `check` owns the tally. Returning the outcome for the caller to re-test invited a new check to
# be added without its `failures +=`, which prints a FAIL line and still exits 0.
$failures = 0

def check(label, condition, detail = nil)
  $failures += 1 unless condition
  puts format("  %-4s %s%s", condition ? "ok" : "FAIL", label, detail ? "  (#{detail})" : "")
  condition
end

def get(url)
  Net::HTTP.get_response(URI(url))
end

begin
  page = get("#{base}/html/index.html")
  check("index.html is served", page.code == "200", "HTTP #{page.code}")
  check("...as text/html", page["content-type"].to_s.start_with?("text/html"))
  check("...and is the real page", page.body.include?("DphPlus.attach"))

  # Cross-origin isolation is the whole reason to prefer a server over file://.
  check("COOP header set", page["cross-origin-opener-policy"] == "same-origin")
  check("COEP header set", page["cross-origin-embedder-policy"] == "require-corp")

  app = get("#{base}/html/app.js")
  check("app.js is served", app.code == "200", "HTTP #{app.code}")
  check("...as text/javascript", app["content-type"].to_s.start_with?("text/javascript"))

  fixture = get("#{base}/fixtures/stub_extraction.json")
  check("the stub extraction is served", fixture.code == "200", "HTTP #{fixture.code}")
  check("...as application/json", fixture["content-type"] == "application/json")

  # The vendored runtime is only present after `build_rbz.py` has staged it. Its
  # absence is a legitimate state (a fresh checkout), so report it rather than
  # failing a check that is really about the payload, not the server.
  if File.file?(File.join(EXT_ROOT, "vendor", "pyodide", "pyodide.asm.wasm"))
    wasm = get("#{base}/vendor/pyodide/pyodide.asm.wasm")
    check("wasm is served", wasm.code == "200", "HTTP #{wasm.code}")
    check("...as application/wasm", wasm["content-type"] == "application/wasm")
    check("...intact", wasm.body.bytesize > 1_000_000, "#{wasm.body.bytesize} bytes")
    manifest = get("#{base}/vendor/manifest.json")
    check("manifest is served", manifest.code == "200", "HTTP #{manifest.code}")
  else
    puts "  --   vendor payload not staged; skipping wasm checks (run build_rbz.py)"
  end

  missing = get("#{base}/html/nope.html")
  check("missing file is 404", missing.code == "404", "HTTP #{missing.code}")

  # The path token is the only thing keeping anything else on the machine out.
  wrong_token = base.sub(%r{/[0-9a-f]{32}\z}, "/" + ("0" * 32))
  forbidden = get("#{wrong_token}/html/index.html")
  check("wrong token is 403", forbidden.code == "403", "HTTP #{forbidden.code}")

  # `File.expand_path` has to collapse the `..` before the root check, or the
  # token would be the only thing between a caller and the whole filesystem.
  escape = get("#{base}/../../../../etc/passwd")
  check("path escape is refused", %w[403 404].include?(escape.code), "HTTP #{escape.code}")

  # The bridge checksum has to agree with `app.js` byte for byte, or a silent
  # truncation would read as a pass. These two values were computed by the JS
  # implementation and are pinned here as a cross-language contract.
  check("checksum agrees with app.js (empty)", DphPlusPoc::Session.checksum("") == 5381)
  check("checksum agrees with app.js ('0123456789')",
        DphPlusPoc::Session.checksum("0123456789") == 995_771_986)

  # The whole sequence above can finish inside one pump interval. Wait for a tick so the log flush
  # is actually exercised -- `stop` used to kill the pump with lines still queued, which in SketchUp
  # meant losing the error that explained the failure. The request counter is the server's own
  # record of what its workers did, which is the fact this is really asserting: they ran at all.
  sleep 0.2
  check("workers ran and were counted", request_count.call >= 6, "#{request_count.call} requests")
ensure
  stop.call
  FileUtils.rm_rf(STUB_LOAD_DIR)
end

puts "\n#{$failures.zero? ? 'ALL CHECKS PASSED' : "#{$failures} CHECK(S) FAILED"}"
exit($failures.zero? ? 0 : 1)
