# ---------------------------------------------------------------------------
# Phase 3 -- exercise `main.rb`'s static server outside SketchUp.
#
#     ruby planning/spikes/pyodide/test_static_server.rb
#
# The first SketchUp run failed with a blank dialog and a port that refused
# connections, and there was no way to tell a broken server from a dialog that
# would not load one. This closes that gap: it loads the real `main.rb` against
# a stub SketchUp API and drives the real `StaticServer` over a real socket, so
# the request path, the path token, the MIME types and the headers are all
# checked here rather than in Ed's SketchUp session.
#
# What it CANNOT check is the thing that broke: `UI.start_timer` is stubbed with
# a plain Ruby `Thread`, which works properly in stock Ruby. In SketchUp it is
# the reverse -- threads starve and the timer works -- which is exactly why the
# real code uses the timer. Treat a pass here as "the HTTP is correct", not as
# "it will serve inside SketchUp".
# ---------------------------------------------------------------------------
require "net/http"
require "tmpdir"

# A worker or pump thread that dies quietly would take the whole server with it
# in SketchUp, where the symptom is another hang. Make it loud here instead.
Thread.abort_on_exception = true

# -- stub SketchUp, just enough for `main.rb` to load -------------------------

stub_dir = Dir.mktmpdir("dphplus-stub")
File.write(File.join(stub_dir, "sketchup.rb"), "")
$LOAD_PATH.unshift(stub_dir)

module UI
  # A plain Ruby Thread stands in for SketchUp's main-thread timer. Correct
  # here, wrong in SketchUp -- see the header.
  def self.start_timer(interval, repeat = false, &block)
    Thread.new do
      loop do
        sleep(interval)
        block.call
        break unless repeat
      end
    end
  end

  def self.stop_timer(handle)
    handle.kill if handle.respond_to?(:kill)
  end

  def self.menu(_name)
    Menu.new
  end

  def self.messagebox(text)
    puts "[messagebox] #{text}"
  end

  class Menu
    def add_submenu(_name)
      self
    end

    def add_item(_name)
      nil
    end

    def add_separator; end
  end
end

module Sketchup
  def self.version
    "22.0.0 (stub)"
  end
end

load File.join(__dir__, "ext", "dph_plus_spike", "main.rb")

# -- drive it ----------------------------------------------------------------

EXT_ROOT = File.join(__dir__, "ext", "dph_plus_spike")
base, stop = BT::DPHPlusSpike::StaticServer.start(EXT_ROOT)
puts "serving #{EXT_ROOT}\n     at #{base}\n\n"

failures = 0

def check(label, condition, detail = nil)
  puts format("  %-4s %s%s", condition ? "ok" : "FAIL", label, detail ? "  (#{detail})" : "")
  condition
end

def get(url)
  Net::HTTP.get_response(URI(url))
end

# The workers cannot print for themselves -- they hand lines to the pump. Watch
# for one arriving, because a silent server is how both SketchUp hangs looked.
$stdout_lines_seen = false
module Kernel
  alias_method :original_puts, :puts
  def puts(*args)
    $stdout_lines_seen = true if args.first.to_s.include?("request #")
    original_puts(*args)
  end
end

begin
  page = get("#{base}/html/index.html")
  failures += 1 unless check("index.html is served", page.code == "200", "HTTP #{page.code}")
  failures += 1 unless check("...as text/html", page["content-type"].to_s.start_with?("text/html"))
  failures += 1 unless check("...and is the real page", page.body.include?("startSpike"))

  # Cross-origin isolation is the whole reason to prefer a server over file://.
  failures += 1 unless check("COOP header set", page["cross-origin-opener-policy"] == "same-origin")
  failures += 1 unless check("COEP header set", page["cross-origin-embedder-policy"] == "require-corp")

  wasm = get("#{base}/vendor/pyodide/pyodide.asm.wasm")
  failures += 1 unless check("wasm is served", wasm.code == "200", "HTTP #{wasm.code}")
  failures += 1 unless check("...as application/wasm", wasm["content-type"] == "application/wasm")
  failures += 1 unless check("...intact", wasm.body.bytesize > 1_000_000, "#{wasm.body.bytesize} bytes")

  manifest = get("#{base}/vendor/manifest.json")
  failures += 1 unless check("manifest is served", manifest.code == "200", "HTTP #{manifest.code}")

  missing = get("#{base}/html/nope.html")
  failures += 1 unless check("missing file is 404", missing.code == "404", "HTTP #{missing.code}")

  # The path token is the only thing keeping anything else on the machine out.
  wrong_token = base.sub(%r{/[0-9a-f]{32}\z}, "/" + ("0" * 32))
  forbidden = get("#{wrong_token}/html/index.html")
  failures += 1 unless check("wrong token is 403", forbidden.code == "403", "HTTP #{forbidden.code}")

  # `File.expand_path` has to collapse the `..` before the root check, or the
  # token would be the only thing between a caller and the whole filesystem.
  escape = get("#{base}/../../../../etc/passwd")
  failures += 1 unless check("path escape is refused", %w[403 404].include?(escape.code),
                             "HTTP #{escape.code}")
  # The whole sequence above can finish inside one pump interval. Wait for a
  # tick so the log flush is actually exercised -- `stop` used to kill the pump
  # with lines still queued, which in SketchUp meant losing the error that
  # explained the failure.
  sleep 0.2
  failures += 1 unless check("worker log reached the main thread", $stdout_lines_seen)
ensure
  stop.call
  FileUtils.rm_rf(stub_dir) if defined?(FileUtils)
end

puts "\n#{failures.zero? ? 'ALL CHECKS PASSED' : "#{failures} CHECK(S) FAILED"}"
exit(failures.zero? ? 0 : 1)
