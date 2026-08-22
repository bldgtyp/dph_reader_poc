# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- server.rb
#
# A minimal static file server on 127.0.0.1, serving the extension tree to the
# `HtmlDialog` for the dialog's lifetime.
#
# ⚠ THIS FILE IS LOAD-BEARING AND SHOULD NOT BE "IMPROVED".
#
# Its shape is dictated by four silent-failure traps found the hard way in the
# Phase 3 spike (`00_Context/CONSTRAINTS.md` §3). Every one of them hangs
# SketchUp with no error message, and two of them look identical from the
# outside. It was promoted here verbatim apart from renaming; before changing
# anything, read `00_Context/SKETCHUP_RUNTIME.md` §4-§5 and diff against
# `planning/spikes/pyodide/ext/dph_plus_spike/main.rb`.
#
# Why a server at all: a `file://` page cannot fetch its own assets. `fetch`,
# `XMLHttpRequest` *and* the dynamic `import()` Pyodide uses for
# `pyodide.asm.mjs` are all refused with the same CORS rule, and the third
# cannot be shimmed at any level. Confirmed inside SketchUp, 2026-08-19.
#
# Why hand-rolled rather than WEBrick: WEBrick left Ruby's default gems at 3.0
# and there is no guarantee about what a given SketchUp build ships, while
# `TCPServer` is core. It also keeps full control of the response headers,
# which is what cross-origin isolation (and therefore any future
# `SharedArrayBuffer` requirement) needs.
#
# Scope: binds to 127.0.0.1 only, on an OS-assigned port, behind a random
# 32-hex path token, and refuses any path that escapes the served root.
#
# SketchUp 2022 is Ruby 2.7: no endless methods, no pattern matching, no
# `Hash#except`. Syntax-check with `ruby -c` before installing.
# ---------------------------------------------------------------------------
require "socket"
require "io/wait"

module DphPlusPoc
  module StaticServer

    CONTENT_TYPES = {
      ".html" => "text/html; charset=utf-8",
      ".js"   => "text/javascript; charset=utf-8",
      ".mjs"  => "text/javascript; charset=utf-8",
      ".json" => "application/json",
      ".wasm" => "application/wasm",
      ".zip"  => "application/zip",
      ".py"   => "text/plain; charset=utf-8",
      ".whl"  => "application/octet-stream",
      ".ts"   => "text/plain; charset=utf-8"
    }.freeze

    # How often the main thread hands the GVL over, and for how long. The
    # slice is larger while a request is in flight -- a 9.6 MB wasm wants
    # throughput, an idle dialog wants a responsive SketchUp.
    YIELD_INTERVAL = 0.02
    BUSY_SLICE     = 0.010
    IDLE_SLICE     = 0.001

    # How long a connected client gets to send its request line.
    REQUEST_TIMEOUT = 5.0

    LOG_PREFIX = "[dph+]".freeze

    # Returns [base_url, stop_lambda, request_count_lambda].
    #
    # ⚠ **Two things are true at once, and getting either wrong hangs SketchUp.**
    #
    #  1. **The I/O must not be on the main thread.** SketchUp drives CEF from
    #     the app's main run loop, so CEF needs that thread to drain a socket.
    #     A response bigger than the send buffer therefore blocks the main
    #     thread waiting for a reader that cannot run -- a hard deadlock, and
    #     the reason the spike's first four (small) requests succeeded and the
    #     fifth never appeared at all.
    #  2. **A Ruby thread on its own never runs.** SketchUp only schedules
    #     Ruby while Ruby is executing, so a thread parked in `accept` is
    #     starved indefinitely -- while `TCPServer.new` has already bound and
    #     listened, so the client waits on a queued connection and nothing
    #     reports an error.
    #
    # Hence: a worker thread does every blocking operation, and a
    # `UI.start_timer` on the main thread exists purely to `sleep`, which
    # releases the GVL and is what lets the worker be scheduled at all.
    def self.start(root)
      root  = File.expand_path(root)
      token = (1..32).map { "0123456789abcdef"[rand(16)] }.join
      server = TCPServer.new("127.0.0.1", 0)
      port = server.addr[1]

      state = {
        :served => 0,
        :busy   => 0,
        :log    => [],
        :lock   => Mutex.new
      }

      acceptor = Thread.new do
        begin
          loop do
            session = server.accept
            # One thread per connection: a client that connects and then
            # says nothing must not block the next request behind it.
            Thread.new(session) { |s| serve(s, root, token, state) }
          end
        rescue StandardError => error
          note(state, "accept loop ended: #{error.class}")
        end
      end

      flush = lambda do
        lines = state[:lock].synchronize { state[:log].slice!(0, state[:log].length) }
        lines.each { |line| puts "#{LOG_PREFIX} #{line}" }
      end

      pump = UI.start_timer(YIELD_INTERVAL, true) do
        # The whole point of this callback is the sleep: it hands the GVL to
        # the worker threads. Without it they never run.
        busy = state[:lock].synchronize { state[:busy] }
        sleep(busy > 0 ? BUSY_SLICE : IDLE_SLICE)
        # SketchUp's API is not thread-safe, so the workers only *record*
        # their log lines. Printing them is the main thread's job.
        flush.call
      end

      stop = lambda do
        # Flush before killing the pump, or the last lines are lost -- which
        # would most likely be the error explaining why we are stopping.
        flush.call
        UI.stop_timer(pump) if pump
        acceptor.kill if acceptor
        begin
          server.close
        rescue StandardError
          nil
        end
        puts "#{LOG_PREFIX} server stopped after " \
             "#{state[:lock].synchronize { state[:served] }} request(s)"
      end

      [
        "http://127.0.0.1:#{port}/#{token}",
        stop,
        lambda { state[:lock].synchronize { state[:served] } }
      ]
    end

    # Runs on a worker thread. Nothing here may touch the SketchUp API --
    # only sockets, `File`, and `state` under its mutex.
    def self.serve(session, root, token, state)
      sequence = state[:lock].synchronize do
        state[:served] += 1
        state[:busy] += 1
        state[:served]
      end

      unless session.wait_readable(REQUEST_TIMEOUT)
        note(state, "request ##{sequence}: client sent nothing in #{REQUEST_TIMEOUT}s")
        return
      end

      request = session.gets
      return if request.nil?
      path = request.split(" ")[1].to_s.split("?").first.to_s
      # Drain the request headers; CEF will not read the response otherwise.
      while (line = session.gets) && line.strip != ""
      end

      # The browser asks for this at the domain root, outside the token, on
      # every page load. "No content" is the right answer -- but it is still
      # logged, because the sequence number has already been taken and **a gap
      # in a numbered log is indistinguishable from a silently dropped
      # request**, which is the whole reason for numbering them (POC-1 §7.2).
      if path == "/favicon.ico"
        respond(session, 204, "text/plain", "")
        note(state, "request ##{sequence}: 204 #{path}")
        return
      end

      prefix = "/#{token}/"
      unless path.start_with?(prefix)
        note(state, "request ##{sequence}: 403 #{path}")
        respond(session, 403, "text/plain", "forbidden")
        return
      end

      relative = unescape(path[prefix.length..-1].to_s)
      absolute = File.expand_path(File.join(root, relative))
      unless absolute.start_with?(root + File::SEPARATOR) && File.file?(absolute)
        note(state, "request ##{sequence}: 404 #{relative}")
        respond(session, 404, "text/plain", "not found")
        return
      end

      body = File.binread(absolute)
      respond(session, 200, CONTENT_TYPES[File.extname(absolute).downcase] ||
                            "application/octet-stream", body)
      note(state, "request ##{sequence}: 200 #{relative} (#{body.bytesize} bytes)")
    rescue StandardError => error
      note(state, "request ##{sequence} failed: #{error.class}: #{error.message}")
      begin
        respond(session, 500, "text/plain", error.message)
      rescue StandardError
        nil
      end
    ensure
      state[:lock].synchronize { state[:busy] -= 1 }
      begin
        session.close
      rescue StandardError
        nil
      end
    end

    def self.note(state, line)
      state[:lock].synchronize { state[:log] << line }
    end

    def self.unescape(text)
      text.gsub(/%([0-9A-Fa-f]{2})/) { $1.hex.chr }
    end

    # The two Cross-Origin-* headers give the page cross-origin isolation, so
    # it could reach for `SharedArrayBuffer` if a future Pyodide feature needs
    # it. A `file://` page can never set them -- a second reason the server is
    # the safer architecture, independent of the CORS block.
    def self.respond(session, status, type, body)
      headers = [
        "HTTP/1.1 #{status}",
        "Content-Type: #{type}",
        "Content-Length: #{body.bytesize}",
        "Cross-Origin-Opener-Policy: same-origin",
        "Cross-Origin-Embedder-Policy: require-corp",
        "Cache-Control: no-store",
        "Connection: close"
      ]
      session.write(headers.join("\r\n") + "\r\n\r\n")
      session.write(body)
    end
  end
end
