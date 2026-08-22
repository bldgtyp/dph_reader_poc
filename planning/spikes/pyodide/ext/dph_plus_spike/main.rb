# ---------------------------------------------------------------------------
# DesignPH-PLUS -- Phase 3 spike -- main.rb
#
# READ-ONLY. Nothing here writes to the model, and nothing writes to
# `DesignPH_dict` (hard rules 2 and 3).
#
# The question this file exists to answer: can Pyodide run inside SketchUp's
# `HtmlDialog`? Desktop Chrome already answered the parts that are not about
# SketchUp -- see `planning/RESULTS/PHASE-3_results.md`. Two of those answers
# shape everything below:
#
#   * over `file://`, stock Chromium blocks `fetch`, blocks `XMLHttpRequest`,
#     and blocks the dynamic `import()` Pyodide uses for `pyodide.asm.mjs`.
#     All three fail with the same CORS message. No JS shim can rescue it --
#     a module import is not interceptable.
#   * the identical tree served from `http://127.0.0.1` works, cold start
#     ~2.3 s.
#
# So this extension offers BOTH load strategies and reports which one the
# dialog accepted:
#
#   :file    -- `HtmlDialog#set_file`. Works only if CEF was built or
#               configured to allow local file access. Untested until now;
#               that is the point.
#   :server  -- a ~70-line static HTTP server on 127.0.0.1, random port,
#               random path token, shut down with the dialog. Known-good in
#               Chromium, and the only strategy that can set COOP/COEP headers
#               if `SharedArrayBuffer` is ever needed.
#
# SketchUp 2022 is Ruby 2.7: no endless methods, no pattern matching, no
# `Hash#except`. Syntax-check with `ruby -c` before installing.
# ---------------------------------------------------------------------------
require "sketchup.rb"
require "json"
require "socket"
require "io/wait"

module BT
  module DPHPlusSpike

    # `EXT_DIR` is also the static server's document root: `html/` and `vendor/` both sit under it,
    # and `index.html` reaches its assets with `../vendor/...` either way.
    EXT_DIR  = File.dirname(__FILE__).freeze
    HTML_DIR = File.join(EXT_DIR, "html").freeze

    # in -> m. SketchUp's internal unit is always inches whatever the model
    # displays, so every raw coordinate needs this before honeybee sees it.
    IN_TO_M = 0.0254

    # ---------------------------------------------------------------------
    # A minimal static file server
    # ---------------------------------------------------------------------
    #
    # Hand-rolled rather than WEBrick: WEBrick left Ruby's default gems at 3.0
    # and there is no guarantee about what a given SketchUp build ships, while
    # `TCPServer` is core. It also keeps full control of the response headers,
    # which is what a future `SharedArrayBuffer` requirement would need.
    #
    # Scope: binds to 127.0.0.1 only, on an OS-assigned port, behind a random
    # 32-hex path token, and refuses any path that escapes the served root.
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

      # Returns [base_url, stop_lambda, request_count_lambda].
      #
      # ⚠ **Two things are true at once, and getting either wrong hangs SketchUp.**
      # Both were learned the hard way; see Findings 30 and 32.
      #
      #  1. **The I/O must not be on the main thread.** SketchUp drives CEF from
      #     the app's main run loop, so CEF needs that thread to drain a socket.
      #     A response bigger than the send buffer therefore blocks the main
      #     thread waiting for a reader that cannot run -- a hard deadlock, and
      #     the reason the first four (small) requests succeeded and the fifth
      #     never appeared at all.
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
          lines.each { |line| puts "[spike] #{line}" }
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
          puts "[spike] server stopped after #{state[:lock].synchronize { state[:served] }} request(s)"
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
        # every page load. Answering "no content" keeps it out of the log.
        if path == "/favicon.ico"
          respond(session, 204, "text/plain", "")
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
      # it. A `file://` page can never set them -- risk 2 in the phase plan, and
      # a second reason the server strategy is the safer architecture.
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

    # ---------------------------------------------------------------------
    # Reading the model
    # ---------------------------------------------------------------------

    # Recurse into groups and components, carrying the accumulated
    # transformation. A face inside a group is stored in the group's LOCAL
    # coordinates; without the transform every nested face lands in the wrong
    # place and every scaled group lies about its size.
    def self.walk_faces(entities, transform, rows)
      entities.each do |entity|
        case entity
        when Sketchup::Face
          dictionary = entity.attribute_dictionary("DesignPH_dict")
          next if dictionary.nil?
          rows << face_record(entity, dictionary, transform)
        when Sketchup::Group
          walk_faces(entity.entities, transform * entity.transformation, rows)
        when Sketchup::ComponentInstance
          walk_faces(entity.definition.entities, transform * entity.transformation, rows)
        end
      end
      rows
    end

    def self.face_record(face, dictionary, transform)
      vertices = face.outer_loop.vertices.map do |vertex|
        point = vertex.position.transform(transform)
        [(point.x.to_f * IN_TO_M).round(6),
         (point.y.to_f * IN_TO_M).round(6),
         (point.z.to_f * IN_TO_M).round(6)]
      end
      {
        "id"         => "face_#{face.entityID}",
        # Coalesce, never version-key (hard rule 6). The two generations are
        # mutually exclusive per face across all 14 corpus models, and both
        # hold real data on real models whatever the version stamp.
        "area_group" => dictionary["areaGroupID"] || dictionary["areaGroupIDAuto"],
        "vertices"   => vertices,
        # Reported for the record, not used by the spike's translator.
        "has_inner_loops" => face.loops.size > 1
      }
    end

    # Faces designPH has actually classified. `areaGroupID` is a String on 1359
    # of 1441 faces in the primary corpus model -- most often `'n'`, meaning
    # "not assigned" -- so the filter has to be by value, not by presence
    # (hard rule 5).
    def self.classified?(record)
      group = record["area_group"]
      return false if group.nil?
      Integer(group.to_s, 10) > 0
    rescue ArgumentError, TypeError
      false
    end

    def self.collect_faces(model, only_classified)
      rows = walk_faces(model.entities, Geom::Transformation.new, [])
      kept = only_classified ? rows.select { |r| classified?(r) } : rows
      {
        "model_name"      => (model.title.empty? ? "Untitled" : model.title),
        "units"           => "Meters",
        "faces"           => kept,
        "tagged_total"    => rows.size,
        "classified_only" => only_classified
      }
    end

    # ---------------------------------------------------------------------
    # The bridge
    # ---------------------------------------------------------------------

    # Must match `SPIKE.checksum` in spike.js byte for byte -- djb2 truncated to
    # a signed 32-bit integer. Verified equal on both sides for empty, ASCII and
    # 100 KB inputs. It agrees only for the Basic Multilingual Plane: JS iterates
    # UTF-16 code units and Ruby iterates codepoints, so an astral character
    # would disagree. The probe's filler is ASCII digits, so it never arises.
    #
    # The probe compares checksums rather than lengths because a bridge that
    # silently truncates is more dangerous than one that errors, and truncation
    # is the documented risk of `execute_script`.
    def self.checksum(text)
      hash = 5381
      text.each_char { |char| hash = signed32((hash << 5) + hash + char.ord) }
      hash
    end

    def self.signed32(value)
      value &= 0xFFFFFFFF
      value >= 0x80000000 ? value - 0x100000000 : value
    end

    # Payload sizes the probe walks, in bytes. Stops at 4 MB deliberately: a
    # failure at 16 MB would freeze SketchUp for long enough to be mistaken for
    # a crash, and 4 MB is already double the HBJSON that 1441 faces produce.
    BRIDGE_SIZES = [1_000, 10_000, 100_000, 1_000_000, 4_000_000].freeze

    # Ruby -> JS direction of the probe. `execute_script` returns nothing, so
    # the dialog answers asynchronously on `spike_bridge_down_result`; those
    # replies land while Pyodide is still booting and are collected at the end.
    def self.probe_downstream(dialog, sizes)
      sizes.each do |size|
        body = "0123456789" * (size / 10)
        message = { "size" => body.length, "sum" => checksum(body), "body" => body }
        @downstream_sent << body.length
        begin
          dialog.execute_script("SPIKE_HOST.receiveFromRuby(#{JSON.generate(JSON.generate(message))})")
        rescue StandardError => error
          @downstream << { "sent_bytes" => body.length, "ok" => false, "error" => error.message }
        end
      end
    end

    # ---------------------------------------------------------------------
    # The run
    # ---------------------------------------------------------------------

    def self.run(strategy)
      model = Sketchup.active_model
      @results = { "strategy" => strategy.to_s, "sketchup" => Sketchup.version,
                   "platform" => (Object.const_defined?(:RUBY_PLATFORM) ? RUBY_PLATFORM : "?") }
      @log = []
      @downstream = []
      @downstream_sent = []
      @stop_server = nil

      dialog = UI::HtmlDialog.new(
        :dialog_title    => "DesignPH-PLUS -- Phase 3 spike (#{strategy})",
        :preferences_key => "com.bldgtyp.dphplus.spike",
        :width           => 760,
        :height          => 620,
        :resizable       => true,
        :style           => UI::HtmlDialog::STYLE_DIALOG
      )

      dialog.add_action_callback("spike_log") do |_context, line|
        @log << line
        puts "[spike] #{line}"
        nil
      end

      dialog.add_action_callback("spike_bridge_echo") do |_context, json|
        begin
          message = JSON.parse(json)
          reply = { "id" => message["id"], "size" => message["body"].to_s.length,
                    "sum" => checksum(message["body"].to_s) }
        rescue StandardError => error
          reply = { "id" => nil, "error" => error.message }
        end
        dialog.execute_script(
          "SPIKE_HOST.resolve(#{JSON.generate(reply['id'])}, #{JSON.generate(reply)})"
        )
        nil
      end

      dialog.add_action_callback("spike_bridge_down_result") do |_context, json|
        begin
          parsed = JSON.parse(json)
          parsed["sent_bytes"] = @downstream_pending
          @downstream << parsed
        rescue StandardError => error
          @downstream << { "error" => error.message }
        end
        nil
      end

      dialog.add_action_callback("spike_result") do |_context, json|
        finish(json)
        nil
      end

      # The page asks for this once its own Pyodide boot is finished. It used to
      # run inside `spike_ready`, which pushed ~5 MB through `execute_script`
      # immediately before the runtime started fetching its 9.6 MB of assets --
      # megabytes of bridge traffic competing with the load it was meant to
      # measure. Nothing needs it that early.
      dialog.add_action_callback("spike_probe_down") do |_context, _payload|
        probe_downstream(dialog, BRIDGE_SIZES)
        nil
      end

      # The page calls this once its own scripts have run. Everything below
      # depends on `SPIKE_HOST` existing, so it cannot be driven from `show`.
      dialog.add_action_callback("spike_ready") do |_context, _payload|
        faces = collect_faces(model, true)
        @results["faces_collected"] = faces["faces"].size
        @results["faces_tagged_total"] = faces["tagged_total"]
        # The dialog reads the pinned wheel list out of `vendor/manifest.json` itself,
        # so nothing about the Python payload is duplicated on this side.
        context = { "strategy" => strategy.to_s, "faces" => faces }
        payload = JSON.generate(context)
        @results["face_payload_bytes"] = payload.bytesize
        puts "[spike] handing #{faces['faces'].size} classified faces " \
             "(#{payload.bytesize} bytes) to the dialog"
        begin
          dialog.execute_script("startSpike(#{payload})")
        rescue StandardError => error
          # A failure here IS the finding: it means `execute_script` could not
          # carry a real model's geometry.
          @results["startSpike_error"] = error.message
          puts "[spike] execute_script(startSpike) FAILED: #{error.message}"
        end
        nil
      end

      if strategy == :server
        base, @stop_server, requests = StaticServer.start(EXT_DIR)
        url = "#{base}/html/index.html"
        puts "[spike] serving #{EXT_DIR} at #{base}"
        @results["url"] = url
        dialog.set_url(url)
        # If nothing has been asked for by now, the dialog never reached the
        # server -- a different failure from the server never answering, and the
        # two look identical from a blank dialog.
        UI.start_timer(6.0, false) do
          if requests.call.zero?
            puts "[spike] WARNING: 6 s after opening, the dialog has requested nothing."
            puts "[spike]   The server is up (menu item 3 proves that independently)."
            puts "[spike]   So HtmlDialog did not load #{url}"
          end
        end
      else
        @results["url"] = File.join(HTML_DIR, "index.html")
        dialog.set_file(File.join(HTML_DIR, "index.html"))
      end

      dialog.set_on_closed { @stop_server.call if @stop_server }
      dialog.show
      dialog
    end

    def self.finish(json)
      begin
        @results["report"] = JSON.parse(json)
      rescue StandardError => error
        @results["report_parse_error"] = error.message
        @results["report_raw_head"] = json.to_s[0, 500]
      end
      @results["downstream_bridge"] = @downstream
      @results["downstream_sent_bytes"] = @downstream_sent
      @results["ruby_log"] = @log

      hbjson = @results["report"] && @results["report"]["hbjson"]
      if hbjson
        @results["report"].delete("hbjson")
        path = write_file(hbjson, "hbjson", ".hbjson")
        @results["hbjson_path"] = path
        @results["hbjson_bytes"] = hbjson.bytesize
        puts "[spike] HBJSON written -> #{path}"
      end

      path = write_file(JSON.pretty_generate(@results), "phase3_result", ".json")
      puts "[spike] result written -> #{path}"
      # "finished" said nothing about whether it worked, and appeared over a failed run more than
      # once. Grade it here instead.
      report = @results["report"] || {}
      boot = report["boot"] || {}
      passed = report["fatal"].nil? &&
               boot.fetch("step2", {})["ok"] &&
               boot.fetch("step3", {})["ok"] &&
               (report["step4"].nil? || report["step4"]["ok"])
      headline = passed ? "PASSED" : "FAILED"
      detail = if passed && report["step4"]
                 "\n\n#{report['step4']['faces_translated']} of " \
                 "#{report['step4']['faces_in']} faces translated, " \
                 "#{report['step4']['rejected_count']} rejected."
               elsif report["fatal"]
                 "\n\n#{report['fatal'].to_s.split("\n").first}"
               else
                 ""
               end
      puts "[spike] #{headline}"
      UI.messagebox("Phase 3 spike: #{headline}#{detail}\n\nResult: #{path}")
      path
    end

    # Write next to the .skp when it has been saved, else to the Desktop --
    # the same rule the BT Attribute Inspector uses.
    def self.write_file(contents, kind, extension)
      model = Sketchup.active_model
      directory = model.path.empty? ? File.expand_path("~/Desktop") : File.dirname(model.path)
      base = model.path.empty? ? "untitled" : File.basename(model.path, ".skp")
      stamp = Time.now.strftime("%y%m%d_%H%M%S")
      path = File.join(directory, "#{base}__#{kind}_#{stamp}#{extension}")
      File.write(path, contents)
      path
    end

    # Start the server with no dialog at all, so "is the server reachable?" can
    # be answered independently of "will HtmlDialog load it?". Those two look
    # identical from a blank dialog, and separating them is what the first run
    # could not do.
    def self.serve_only(seconds = 120)
      @stop_server.call if @stop_server
      base, @stop_server, requests = StaticServer.start(EXT_DIR)
      url = "#{base}/html/index.html"
      puts "\n" + ("=" * 68)
      puts "Static server up for #{seconds.to_i} s. Open this in a browser:"
      puts "\n  #{url}\n"
      puts "Expect the spike page, and a `request #1: 200 html/index.html` line"
      puts "below. If the browser hangs instead, the timer pump is not running"
      puts "and nothing else in this spike can work."
      puts "=" * 68
      UI.start_timer(seconds, false) do
        puts "[spike] serve-only window closed after #{requests.call} request(s)"
        @stop_server.call if @stop_server
        @stop_server = nil
      end
      url
    end

    # A payload check that needs no dialog: prints what the bridge would have
    # to carry for the open model, so a bridge limit can be interpreted.
    def self.report_payload_size
      model = Sketchup.active_model
      classified = collect_faces(model, true)
      everything = collect_faces(model, false)
      puts "\n" + ("=" * 68)
      puts "designPH face payload -- #{model.title}"
      puts "=" * 68
      printf("%-34s %8d faces  %10.2f KB\n", "classified (area group > 0)",
             classified["faces"].size, JSON.generate(classified).bytesize / 1024.0)
      printf("%-34s %8d faces  %10.2f KB\n", "every face with DesignPH_dict",
             everything["faces"].size, JSON.generate(everything).bytesize / 1024.0)
      nil
    end

    # ---------------------------------------------------------------------
    # Menu. Guarded: SketchUp re-runs this file when the extension is toggled
    # in Extension Manager, and unguarded menu building duplicates the items.
    # ---------------------------------------------------------------------
    unless defined?(@ui_built)
      menu = UI.menu("Plugins").add_submenu("DesignPH-PLUS Spike")
      menu.add_item("1. Run spike -- local HTTP server (recommended)") { run(:server) }
      menu.add_item("2. Run spike -- file:// (expected to fail; run it anyway)") { run(:file) }
      menu.add_separator
      menu.add_item("3. Test the server only -- open the URL in a browser") { serve_only }
      menu.add_item("Report face payload size (no dialog)") { report_payload_size }
      @ui_built = true
    end

  end
end
