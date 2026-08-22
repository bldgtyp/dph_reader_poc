# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- main.rb
#
# Menu, dialog + server lifecycle, and the Ruby half of the bridge.
#
# READ-ONLY. Nothing here writes to the model, and nothing writes to
# `DesignPH_dict` (hard rules 2 and 3).
#
# The pipeline this file drives (`planning/POC/00_POC_OVERVIEW.md` §3):
#
#     collector.rb  --extraction JSON-->  HtmlDialog (Pyodide 0.24.1)
#                                              |
#                                         dph_translator
#                                              |
#     <name>.hbjson + <name>.report.json  <----+
#
# Three properties are non-negotiable and each was paid for in Phase 3:
#
#   * the page is served over `http://127.0.0.1`, never `file://` (hard rule 8)
#   * the server's blocking I/O is on a worker thread pumped by a sleeping
#     `UI.start_timer` (hard rule 9) -- see `server.rb`
#   * every session ends in a PASSED/FAILED verdict with a per-check list. A
#     run nobody can grade at a glance has not reported anything.
#
# SketchUp 2022 is Ruby 2.7: no endless methods, no pattern matching, no
# `Hash#except`. Syntax-check with `ruby -c` before installing.
# ---------------------------------------------------------------------------
require "sketchup.rb"
require "json"

require File.join(File.dirname(__FILE__), "server")
require File.join(File.dirname(__FILE__), "collector")
require File.join(File.dirname(__FILE__), "gate")

module DphPlusPoc

  # `EXT_DIR` is also the static server's document root: `html/`, `vendor/` and
  # `fixtures/` all sit under it, and `index.html` reaches its assets with
  # `../vendor/...`.
  EXT_DIR   = File.dirname(__FILE__).freeze
  HTML_DIR  = File.join(EXT_DIR, "html").freeze
  BUILD_INFO = File.join(EXT_DIR, "build_info.json").freeze

  PREFERENCES_KEY = "com.bldgtyp.dphplus.poc".freeze

  # Seconds after `show` at which "the dialog never reached the server" becomes
  # a reportable fact. Without it a blank dialog and a dead socket look the same.
  SILENT_DIALOG_AFTER = 6.0

  # ---------------------------------------------------------------------
  # Preferences
  # ---------------------------------------------------------------------

  # Diagnostics toggle: also write `<name>.extraction.json` beside the outputs.
  # POC-5's corpus sweep depends on being able to capture the collector's own
  # output, not just the translated result.
  def self.save_extraction?
    Sketchup.read_default(PREFERENCES_KEY, "save_extraction", false) ? true : false
  end

  def self.toggle_save_extraction
    Sketchup.write_default(PREFERENCES_KEY, "save_extraction", !save_extraction?)
  end

  # ---------------------------------------------------------------------
  # The session -- one dialog, one server, one action
  # ---------------------------------------------------------------------
  #
  # A class rather than module state so that a second run cannot inherit half
  # of the first run's results. `run` replaces the current session outright.
  class Session

    ACTIONS = ["self_test", "translate"].freeze

    attr_reader :action

    def initialize(action)
      raise ArgumentError, "unknown action #{action}" unless ACTIONS.include?(action)
      @action = action
      @log = []
      @dialog = nil
      @stop_server = nil
      @extraction_json = nil
      @stub_extraction = false
      @finished = false
      # Facts the gates observed on the way past. They travel into the written
      # report, because a note nobody kept is a note nobody read.
      @host_notes = []
    end

    def start
      @dialog = UI::HtmlDialog.new(
        :dialog_title    => "DesignPH-PLUS POC -- #{@action == 'self_test' ? 'Runtime self-test' : 'Export HBJSON'}",
        :preferences_key => PREFERENCES_KEY,
        :width           => 820,
        :height          => 640,
        :resizable       => true,
        :style           => UI::HtmlDialog::STYLE_DIALOG
      )

      # JS -> Ruby. Three callbacks and no more: a log sink, a readiness ping,
      # and one result channel carrying a JSON string (bridge rules, §4).
      @dialog.add_action_callback("on_log") { |_context, line| record(line); nil }
      @dialog.add_action_callback("on_ready") { |_context, _payload| dispatch_action; nil }
      @dialog.add_action_callback("on_result") { |_context, json| receive(json); nil }
      @dialog.add_action_callback("on_echo") { |_context, json| echo(json); nil }

      base, @stop_server, requests = StaticServer.start(EXT_DIR)
      url = "#{base}/html/index.html"
      record("serving #{EXT_DIR}")
      @dialog.set_url(url)

      # If nothing has been asked for by now, the dialog never reached the
      # server -- a different failure from the server never answering, and the
      # two are indistinguishable from a blank dialog.
      UI.start_timer(SILENT_DIALOG_AFTER, false) do
        if requests.call.zero?
          puts "[dph+] WARNING: #{SILENT_DIALOG_AFTER.to_i} s after opening, the dialog has requested nothing."
          puts "[dph+]   The server is up (Diagnostics > Server only proves that independently)."
          puts "[dph+]   So HtmlDialog did not load #{url}"
        end
      end

      @dialog.set_on_closed { shutdown }
      @dialog.show
      @dialog
    end

    private

    def record(line)
      @log << line
      puts "[dph+] #{line}"
    end

    def shutdown
      @stop_server.call if @stop_server
      @stop_server = nil
    end

    # Ruby -> JS. One shape for every action: `{action, payload}` where
    # `payload` is either `null` or a JSON **string** -- never a nested object,
    # never a proxy. `JSON.generate` of a String yields a quoted JS string
    # literal, so the seam is the same string on both sides.
    def send_to_dialog(action, payload_json)
      message = { "action" => action, "payload" => payload_json }
      script = "DphPlus.dispatch(#{JSON.generate(message)})"
      record("-> dialog: #{action} (#{payload_json ? payload_json.bytesize : 0} bytes)")
      begin
        @dialog.execute_script(script)
      rescue StandardError => error
        # A failure here IS the finding: it means `execute_script` could not
        # carry the payload.
        finish_with_error("execute_script(#{action}) failed: #{error.message}")
      end
    end

    def dispatch_action
      if @action == "self_test"
        send_to_dialog("self_test", nil)
        return
      end

      extraction = walk_model
      return if extraction.nil?

      # The post-walk half of the version gate. `DphPlusPoc.run` already refused
      # anything whose stamp says 3.x, before the collector ever saw the model;
      # what only the census can decide is the no-stamp row (`gate.rb`).
      version = Gate.version(model_stamps, Gate.evidence(extraction))
      return refuse(version.reason) if version.refused?
      note(version.note)

      extraction_json = JSON.generate(extraction)
      # The breakdown is a block: it re-serialises every section, and on the
      # ordinary path — 334-501 KB across the whole corpus — it is never run.
      size = Gate.payload(extraction_json.bytesize) { Gate.breakdown(extraction) }
      return refuse(size.reason) if size.refused?
      note(size.note)

      @stub_extraction = Collector.stub?(extraction)
      # Held only when it will actually be written. A real POC-2 walk of a large model is
      # megabytes; keeping a second copy alive for the session buys nothing when the
      # diagnostics checkbox is off, which is its default.
      @extraction_json = extraction_json if DphPlusPoc.save_extraction?
      send_to_dialog("translate", extraction_json)
    end

    # The read, with the two things the plain call cannot do: a progress hook
    # (⚠ set but not visible — see `progress_reporter`) and a rescue.
    # **A collector that raises must land as a verdict**
    # (POC-4 §2) — an exception escaping an `HtmlDialog` action callback is
    # swallowed by SketchUp and the dialog simply sits there.
    def walk_model
      started = Time.now
      Sketchup.status_text = "DesignPH-PLUS: reading the model…"
      extraction = Collector.extract(
        Sketchup.active_model, DphPlusPoc.collector_signature,
        Writer.stem_for(Sketchup.active_model), progress_reporter
      )
      counts = extraction["counts"] || {}
      record(format("walked %d faces / %d classified / %d edges / %d windows in %d ms",
                    counts["faces_walked"].to_i, counts["faces_classified"].to_i,
                    counts["edges_tagged"].to_i, counts["windows_found"].to_i,
                    ((Time.now - started) * 1000).round))
      extraction
    rescue StandardError => error
      record("collector backtrace: #{error.backtrace.first(3).join(' | ')}") if error.backtrace
      finish_with_error("the collector could not read this model.\n\n#{error.class}: #{error.message}")
      nil
    ensure
      Sketchup.status_text = ""
    end

    # ⛔ **THIS IS NOT VISIBLE TODAY, AND NO PROGRESS INDICATOR CAN BE.** Measured
    # in SketchUp 22.0.353 on 2026-08-21, run D: Ed never saw it, on a walk that
    # took 10.9 s.
    #
    # Two independent reasons, and the second is the one that matters:
    #
    #   1. `Sketchup.status_text=` writes to the bottom-left of the **main
    #      SketchUp window** — which the `HtmlDialog` and the Ruby Console sit
    #      on top of. The user is looking at the dialog. Wrong surface.
    #   2. ⚠ **The walk is a synchronous loop on the main thread, so nothing
    #      repaints — not the status bar, and not the dialog either.** That is
    #      the same mechanism as hard rule 9, seen from the UI side: SketchUp
    #      drives both its own chrome and CEF from the main run loop, and a
    #      tight Ruby loop never lets that loop turn over. It is why the dialog
    #      goes blank for the length of the walk, and again for the save panel.
    #
    # So this sets a value nobody sees. It is kept because it costs one write
    # per 250 entities and becomes correct the moment the walk yields — which
    # is the real fix, and it is v1's: **chunk the walk across `UI.start_timer`
    # callbacks** so the run loop turns over between chunks. That needs the
    # recursion in `collector.rb` turned into an explicit stack.
    #
    # ⚠ Do not "fix" this by asserting harder in the tests. The offline suite
    # asserted that these strings were *set*, which they are, and called that
    # a working progress signal. That is the fourth time this phase that an
    # assertion on a call stood in for an assertion on a surface.
    #
    # Throttled to ~5 Hz, so that when it does become visible it is not a
    # per-entity status-bar write.
    def progress_reporter
      # ⚠ `nil`, not `Time.now`. Seeding it with the clock throttles away the
      # *first* tick, which is the only one that matters on a short walk — the
      # count never appears at all and the signal reads as broken.
      last = nil
      lambda do |visited|
        now = Time.now
        next if last && now - last < 0.2
        last = now
        Sketchup.status_text = "DesignPH-PLUS: reading the model… #{visited} entities"
      end
    end

    def note(text)
      return if text.nil?
      @host_notes << text
      record("note: #{text}")
    end

    def model_stamps
      Gate.stamps(Sketchup.active_model)
    rescue StandardError
      []
    end

    # A refusal is not a failure: nothing went wrong, we declined. It gets its
    # own headline so a user reading the message box is not sent hunting for a
    # bug that does not exist.
    def refuse(reason)
      return if @finished
      @finished = true
      puts "[dph+] REFUSED"
      reason.split("\n").each { |line| puts "[dph+] #{line}" }
      # ⚠ The banner FIRST, then the message box. Two reasons, and both were paid for:
      # `UI.messagebox` blanks the dialog while it is up (CEF cannot repaint from a blocked main
      # thread), so a banner written afterwards is written to a window nobody is looking at; and
      # the dialog is what remains on screen once the box is dismissed. Leaving it on `booting…`
      # is what the first live refusal actually did.
      if @dialog
        begin
          @dialog.execute_script("DphPlus.showRefusal(#{JSON.generate(reason)})")
        rescue StandardError => error
          record("could not show the refusal in the dialog: #{error.message}")
        end
      end
      UI.messagebox("DesignPH-PLUS POC: nothing exported\n\n#{reason}")
    end

    # The bridge probe's Ruby half: measure what arrived and hand it straight
    # back. Checksums rather than lengths, because a bridge that silently
    # truncates is more dangerous than one that errors -- and truncation is the
    # documented risk of `execute_script`.
    def echo(json)
      message = JSON.parse(json)
      body = message["body"].to_s
      reply = { "id" => message["id"], "size" => body.length, "sum" => Session.checksum(body) }
    rescue StandardError => error
      reply = { "id" => nil, "error" => error.message }
    ensure
      @dialog.execute_script("DphPlus.receiveEcho(#{JSON.generate(reply)})")
    end

    # djb2 truncated to a signed 32-bit integer. Must match `checksum` in
    # `app.js` byte for byte; agrees for the Basic Multilingual Plane, which is
    # all the probe's ASCII filler needs.
    def self.checksum(text)
      hash = 5381
      text.each_char do |char|
        hash = (hash << 5) + hash + char.ord
        hash &= 0xFFFFFFFF
        hash -= 0x100000000 if hash >= 0x80000000
      end
      hash
    end

    # JS -> Ruby. `json` is `{action, ok, payload, runtime, error}`, where `payload` is the
    # translator's own output string, forwarded verbatim -- JS never rebuilds it, so a large model
    # crosses the bridge once. `runtime` carries the boot measurements only JS can see; they are
    # merged into the report here rather than into the translator's output there.
    def receive(json)
      message = JSON.parse(json)
      record("<- dialog: #{message['action']} ok=#{message['ok']}")
      if message["ok"]
        result = JSON.parse(message["payload"].to_s)
        result["runtime"] = message["runtime"]
        # A translation's report is written to its own file beside the HBJSON, so the runtime
        # numbers have to be in there too -- otherwise the artefact that travels loses them.
        if result.key?("report")
          result["report"] = result["report"].merge(
            "runtime" => message["runtime"],
            # Gate observations — "no version stamp; proceeding on 194 tagged faces" is exactly
            # the kind of fact that decides whether a surprising output is a bug. Ruby is the
            # only side that sees it, so Ruby is the only side that can file it.
            "host_notes" => @host_notes
          )
        end
        finish(message["action"], result)
      else
        finish_with_error(message["error"].to_s)
      end
    rescue StandardError => error
      finish_with_error("could not read the dialog's result: #{error.class}: #{error.message}")
    end

    #: How much of a failure reaches the message box. ⚠ Not one line: the error
    #: class and message are on the *second* line of a collector failure, and a
    #: Python traceback's first line is the useless `Traceback (most recent call
    #: last):`. Not all of it either — a 40-line modal is one the user dismisses
    #: without reading. The console always gets the whole thing.
    ERROR_LINES = 8

    def finish_with_error(text)
      return if @finished
      @finished = true
      puts "[dph+] FAILED"
      text.split("\n").each { |line| puts "[dph+] #{line}" }
      lines = text.split("\n")
      excerpt = lines.first(ERROR_LINES).join("\n")
      excerpt += "\n… #{lines.size - ERROR_LINES} more line(s) in the Ruby Console" if
        lines.size > ERROR_LINES
      UI.messagebox("DesignPH-PLUS POC: FAILED\n\n#{excerpt}")
    end

    def finish(action, result)
      return if @finished
      @finished = true
      verdict = result["verdict"] || {}
      passed = verdict["passed"] ? true : false
      if action == "self_test"
        path = Writer.write_beside_model(
          JSON.pretty_generate(result.merge("host" => host_info, "ruby_log" => @log)),
          "self_test", ".json"
        )
        announce(passed, verdict, "Self-test report: #{path}")
      else
        announce(passed, verdict, save_outputs(result), result["report"])
      end
    end

    # `UI.savepanel` returns the *stem* the user chose; the three artefacts are
    # written beside it with fixed extensions so a report can never be orphaned
    # from the HBJSON it describes.
    def save_outputs(result)
      suggested = "#{Writer.stem_for(Sketchup.active_model)}.hbjson"
      chosen = UI.savepanel("Save HBJSON", Writer.default_directory, suggested)
      return "not saved -- the save dialog was cancelled" if chosen.nil?

      base = chosen.sub(/\.hbjson\z/i, "")
      written = []
      written << Writer.write(base + ".hbjson", result["hbjson"].to_s)
      written << Writer.write(base + ".report.json", JSON.pretty_generate(result["report"] || {}))
      if DphPlusPoc.save_extraction? && @extraction_json
        written << Writer.write(base + ".extraction.json", @extraction_json)
      end
      written.each { |file| record("wrote #{file}") }
      written.join("\n")
    rescue StandardError => error
      # A write failure has to name the path and the OS error (POC-4 §2). "Could
      # not save" alone is unactionable, and the translation itself succeeded —
      # the result is still on screen in the dialog.
      record("write failed: #{error.class}: #{error.message}")
      "NOT WRITTEN — #{error.class}: #{error.message}\n\nThe translation itself succeeded; " \
      "the report is in the dialog window."
    end

    def announce(passed, verdict, detail, report = nil)
      # The translator's own three-state headline (`PASSED WITH OMISSIONS` is
      # the common and correct outcome on a real model) rather than a boolean
      # relabelled — POC-3 §9.
      headline = verdict["headline"] || (passed ? "PASSED" : "FAILED")
      checks = (verdict["checks"] || []).map do |check|
        "#{check['ok'] ? '  ok    ' : '  FAIL  '}#{check['label']}"
      end
      sections = [checks.join("\n")]
      sections << counts_block(report) if report
      sections << @host_notes.map { |text| "note: #{text}" }.join("\n") unless @host_notes.empty?
      sections << "⚠ STUB COLLECTOR (POC-1): the open model was not read." if @stub_extraction
      sections << detail
      puts "[dph+] #{headline}"
      checks.each { |line| puts "[dph+] #{line}" }
      UI.messagebox("DesignPH-PLUS POC: #{headline}\n\n#{sections.reject(&:empty?).join("\n\n")}")
    end

    # Translated vs reported, per kind. Every entity is one or the other and
    # never both — that disjointness is the report's completeness invariant, so
    # these three lines are the whole story at a glance.
    def counts_block(report)
      summary = (report || {})["summary"] || {}
      lines = %w[faces apertures thermal_bridges].map do |kind|
        row = summary[kind] || {}
        format("  %-16s %4d in  %4d translated  %4d reported",
               kind, row["in"].to_i, row["translated"].to_i, row["reported"].to_i)
      end
      lines << format("  %-16s %8.1f m² covered, %.1f m² lost", "TFA",
                      summary["tfa_m2_covered"].to_f, summary["tfa_m2_lost"].to_f)
      lines.join("\n")
    end

    def host_info
      {
        "sketchup" => Sketchup.version,
        "platform" => (Object.const_defined?(:RUBY_PLATFORM) ? RUBY_PLATFORM : "?"),
        "ruby" => RUBY_VERSION,
        # Both sizes come from the build that produced this tree -- never recomputed here. A
        # second walk of the same folder would answer a slightly different question (Ruby's
        # `Dir.glob` skips dotfiles, Python's `rglob` does not) and the report would then carry a
        # footprint the build never produced.
        "installed_bytes" => DphPlusPoc.build_info["installed_bytes"],
        "rbz_bytes" => DphPlusPoc.build_info["rbz_bytes"],
        "built_at" => DphPlusPoc.build_info["built_at"]
      }
    end
  end

  # ---------------------------------------------------------------------
  # Writing files
  # ---------------------------------------------------------------------
  # ⚠ **Nothing here may derive a path from `Sketchup::Model#path`.**
  #
  # It is the location the model was last *saved*, on whatever machine saved it.
  # Measured across the five corpus copies, two came back as somebody else's
  # machine — `/Users/johnmitchell/Dropbox/…` and
  # `C:\Users\greg\OneDrive\…`. Writing "beside the model" therefore put one
  # capture in `~/Documents` under the entire Windows path as a single
  # filename, and lost the other to `ENOENT`
  # (`00_Context/SKETCHUP_RUNTIME.md` §8.2).
  #
  # So: the **directory** is the one the user picks in the save panel, offered
  # from a fixed default. The **name** is only ever a suggestion the user sees
  # and can change, and it is sanitised down to a bare stem before it is shown.
  module Writer

    # Where the save panel opens. A fixed, always-writable location beats a
    # clever one: the alternative is a guess derived from a value that is wrong
    # on 40 % of the corpus.
    DEFAULT_DIRECTORY = File.expand_path("~/Desktop").freeze

    #: Characters allowed through to a filename. An allow-list, because the
    #: strings arriving here have already included a Windows drive path.
    UNSAFE = /[^A-Za-z0-9 ._-]/.freeze

    #: `File.basename` collapses these to something that is not a name.
    NOT_A_NAME = ["/", ".", ".."].freeze

    def self.default_directory
      DEFAULT_DIRECTORY
    end

    # A filename stem from any string, including one that is secretly a path.
    # Never raises, never returns empty, never returns a separator.
    def self.safe_stem(raw)
      text = File.basename(raw.to_s.tr("\\", "/"))
      text = "" if NOT_A_NAME.include?(text)
      text = text.sub(/\.skp\z/i, "").gsub(UNSAFE, "_").strip
      text.empty? ? "untitled" : text
    end

    # ⚠ `model.title`, not `model.path` — a title, not a location. It is still
    # run through `safe_stem` because on a model last saved elsewhere it can
    # carry a whole foreign path.
    def self.stem_for(model)
      safe_stem(model.title)
    rescue StandardError
      "untitled"
    end

    # Write, atomically: a reader sees the previous file or the new one, never a
    # half-written one, and a failure part-way leaves no debris. The temp file
    # is in the destination directory so the rename cannot cross a filesystem.
    def self.write(path, contents)
      temp = "#{path}.tmp#{Process.pid}"
      begin
        File.open(temp, "w:UTF-8") { |file| file.write(contents) }
        File.rename(temp, path)
      rescue StandardError
        File.delete(temp) if File.file?(temp)
        raise
      end
      path
    end

    def self.write_beside_model(contents, kind, extension)
      stamp = Time.now.strftime("%y%m%d_%H%M%S")
      name = "#{stem_for(Sketchup.active_model)}__#{kind}_#{stamp}#{extension}"
      write(File.join(default_directory, name), contents)
    end
  end

  # ---------------------------------------------------------------------
  # Build metadata
  # ---------------------------------------------------------------------

  # Written by `tools/build_rbz.py`. Absent when the tree was copied by hand,
  # which is a legitimate state -- report the absence rather than failing.
  def self.build_info
    return @build_info if defined?(@build_info) && @build_info
    @build_info = File.file?(BUILD_INFO) ? JSON.parse(File.read(BUILD_INFO)) : {}
  rescue StandardError => error
    @build_info = { "error" => "#{error.class}: #{error.message}" }
  end

  # Stamps every extraction with the build that produced it, so a captured
  # fixture can always be traced back to a translator and a payload version --
  # POC-5 diffs re-runs of the same model against each other.
  def self.collector_signature
    info = build_info
    "dph_plus_poc collector #{info['translator_sha256'].to_s[0, 12]} " \
      "(built #{info['built_at'] || 'in place'})"
  end

  # ---------------------------------------------------------------------
  # Menu actions
  # ---------------------------------------------------------------------

  # ⚠ **The version gate's first half runs here, before anything else.**
  #
  # Not for speed, though it is instant: a designPH 3.x model must be refused
  # *before* `collector.rb` — written against the 2.x schema — walks a schema it
  # has never seen. Whatever that walk produced would be neither a translation
  # nor a report, and an exception from inside it is a worse answer than a
  # sentence naming the version. The other half of the table needs the census
  # and runs after the walk (`gate.rb`).
  def self.run(action)
    if action == "translate"
      decision = begin
        Gate.version(Gate.stamps(Sketchup.active_model))
      rescue StandardError => error
        # Not being able to read the model dictionary is itself reportable; it
        # is never a reason to proceed as if the check had passed.
        Gate::Decision.new(false, "Could not read this model: #{error.class}: #{error.message}", nil)
      end
      if decision.refused?
        puts "[dph+] REFUSED (pre-walk)"
        UI.messagebox("DesignPH-PLUS POC: nothing exported\n\n#{decision.reason}")
        return nil
      end
    end
    @session = Session.new(action)
    @session.start
  end

  # Start the server with no dialog at all, so "is the server reachable?" can
  # be answered independently of "will HtmlDialog load it?". Those two look
  # identical from a blank dialog, and separating them is what the spike's
  # first run could not do.
  def self.serve_only(seconds = 120)
    @serve_only_stop.call if defined?(@serve_only_stop) && @serve_only_stop
    base, @serve_only_stop, requests = StaticServer.start(EXT_DIR)
    url = "#{base}/html/index.html"
    puts "\n" + ("=" * 68)
    puts "Static server up for #{seconds.to_i} s. Open this in a browser:"
    puts "\n  #{url}\n"
    puts "Expect the POC page, and a `request #1: 200 html/index.html` line"
    puts "below. If the browser hangs instead, the timer pump is not running"
    puts "and nothing else in this extension can work."
    puts "=" * 68
    UI.start_timer(seconds, false) do
      puts "[dph+] serve-only window closed after #{requests.call} request(s)"
      @serve_only_stop.call if @serve_only_stop
      @serve_only_stop = nil
    end
    url
  end

  # ---------------------------------------------------------------------
  # Menu. Guarded: SketchUp re-runs this file when the extension is toggled
  # in Extension Manager, and unguarded menu building duplicates the items.
  # ---------------------------------------------------------------------
  unless defined?(@ui_built)
    menu = UI.menu("Extensions").add_submenu("DesignPH-PLUS POC")
    menu.add_item("Export HBJSON…") { run("translate") }
    menu.add_separator
    diagnostics = menu.add_submenu("Diagnostics")
    diagnostics.add_item("Runtime self-test") { run("self_test") }
    diagnostics.add_item("Server only (open in browser)") { serve_only }
    save_item = diagnostics.add_item("Save extraction JSON") { toggle_save_extraction }
    diagnostics.set_validation_proc(save_item) { save_extraction? ? MF_CHECKED : MF_UNCHECKED }
    @ui_built = true
  end

end
