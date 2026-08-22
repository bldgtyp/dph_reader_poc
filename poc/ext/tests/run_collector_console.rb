# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- capture extraction JSON from model COPIES.
#
# Paste into SketchUp's Ruby Console (Window > Ruby Console):
#
#     load "/Users/em/Desktop/dph_plus_testing/poc/ext/tests/run_collector_console.rb"
#
# Then, with a model copy open:
#
#     Dph.here                 # collect the model that is open right now
#     Dph.here("<name>")       # ...filing it under an explicit name
#     Dph.status               # which copies are captured and which are left
#
# ⚠ **`Dph.here` is the supported path. Open each model yourself, run it, repeat.**
#
# ⚠ **The capture always lands in MODEL_DIR.** `Sketchup::Model#path` is NOT the path of the
# file you opened -- see the note below. When it does not point into MODEL_DIR the run stops and
# lists the copies so you can say which one is open. Naming it is the assertion the API cannot
# make.
#
# There is a `Dph.sweep` that opens a folder of models in turn, and on macOS it may not work:
# SketchUp is a multi-document app there, `Sketchup.open_file` opens a NEW WINDOW rather than
# replacing the current model, and `Sketchup.active_model` follows the frontmost window --
# which may not be the one just opened, and may not have become frontmost yet. The failure
# mode is the bad kind: five extraction files, named after five different models, all
# containing the *first* model's data. So `sweep` verifies that the active model's own path
# actually changed to the file it asked for, and **stops** if it did not. It never guesses.
#
# ⚠ **COPIES ONLY.** Hard rule 3: never open a corpus original for POC work. `here` proceeds
# silently only when `model.path` is verifiably a file in MODEL_DIR; otherwise it STOPS and asks
# you to name the copy, because no negative test on `model.path` can tell a stale path from an
# open original. What IS guaranteed regardless is that collection never writes to the model.
#
# ⚠ **READ-ONLY, and it proves it.** `model.modified?` is recorded before and after each
# collection. A `true` after a `false` means something wrote to the model, and the run stops
# there rather than writing a fixture nobody can trust.
#
# It does NOT need the extension installed or a dialog open -- the collector is a plain module,
# loaded here straight from the repo. That also means you can re-`load` this file after an edit
# without reinstalling anything.
# ---------------------------------------------------------------------------
require "json"

module Dph

  MODEL_DIR = File.expand_path("~/Desktop/dph_poc_copies").freeze

  # ⚠ **`Sketchup::Model#path` is not the path of the file you opened.**
  #
  # Measured 2026-08-21 across the five corpus copies: on two of them it came
  # back as the path where the model was last saved **on somebody else's
  # machine** -- `/Users/johnmitchell/Dropbox/.../2523 Weiilington.skp` and
  # `C:\Users\greg\OneDrive\...\Linde Residence - 2.0 kBTU - 7.3.25.skp`. Both
  # strings are embedded verbatim in the `.skp`'s `model.dat`; neither is where
  # Ed's copy lives. The two affected models are the two last saved by SketchUp
  # 24+ and 26 (the other three were 22 and 23), but n=5 is a correlation and
  # not a mechanism -- do not rely on the version rule, rely on not trusting
  # `model.path`.
  #
  # Two things followed, and the second is the dangerous one:
  #
  #   1. The extraction was written to `model.path.sub(".skp", ".json")`. On
  #      Windows-derived paths macOS has no separators to split, so the *entire*
  #      path became one filename in SketchUp's cwd (`~/Documents`); on the
  #      other it raised ENOENT and the capture was lost.
  #   2. **The COPIES-ONLY guard tested the same value and silently failed
  #      open.** `/Users/johnmitchell/Dropbox/...` does not start with this
  #      machine's `~/Dropbox`, so hard rule 3 was not being enforced at all --
  #      and the reverse is just as possible, refusing a legitimate copy whose
  #      stale path happens to sit under the user's own Dropbox.
  #
  # So: **the destination is always `MODEL_DIR`**, never derived from the model.
  #
  # ⚠ And the guard cannot be built on `model.path` either — that was tried twice within an hour
  # and failed in both directions. Matching `~/Dropbox` let Wellington's stale
  # `/Users/johnmitchell/Dropbox/...` straight through; widening to `/Dropbox/` for any user then
  # **refused a legitimate copy sitting on the Desktop**. A negative test on an untrustworthy value
  # is worthless whichever way you point it. `here` uses a positive test — is this verifiably the
  # copy? — and asks the human when the answer is no.
  FORBIDDEN_FRAGMENT = "/Dropbox/".freeze

  def self.collector_path
    File.join(File.dirname(__FILE__), "..", "dph_plus_poc", "collector.rb")
  end

  # Reload rather than assume: this is usually run while iterating on the collector, and a stale
  # copy in memory would produce a fixture that matches no code.
  # `$VERBOSE = nil` around the reload because the installed extension has already defined the
  # same constants, and Ruby warns once per constant on redefinition -- thirty lines of noise that
  # can bury the one message worth reading. The redefinition is intended; the warning is not.
  def self.load_collector
    original = $VERBOSE
    $VERBOSE = nil
    load collector_path
  ensure
    $VERBOSE = original
  end

  # ⚠ **Only for a path the CALLER supplies** -- `sweep`'s directory argument. Never for
  # `model.path`. A negative test ("this does not look forbidden") on an untrustworthy value is
  # worthless in both directions, and both directions happened here within one hour: first it
  # passed Wellington's stale `/Users/johnmitchell/Dropbox/...` because that is not *this*
  # machine's `~/Dropbox`, then, widened to match any user's, it **refused a legitimate copy on
  # the Desktop** on the strength of a path the model had no business claiming.
  #
  # `here` uses a positive test instead: is the path verifiably the copy we expect? If it is not,
  # the answer is unknown, and the human resolves it by naming the model.
  def self.forbidden?(path)
    path.to_s.include?(FORBIDDEN_FRAGMENT)
  end

  # Is `model.path` verifiably a file in MODEL_DIR? Positive, so a stale or foreign path answers
  # `false` rather than sneaking through some prefix test.
  def self.trusted_path?(path)
    File.dirname(File.expand_path(path.to_s.tr("\\", "/"))) == MODEL_DIR
  end

  # `[stem, already_captured?]` for every copy on disk — the menu offered when the open model
  # cannot be identified, and the progress list `status` prints.
  def self.candidates
    Dir.glob(File.join(MODEL_DIR, "*.skp")).sort.map do |skp|
      stem = File.basename(skp, ".skp")
      [stem, File.exist?(File.join(MODEL_DIR, "#{stem}.extraction.json"))]
    end
  end

  # What is left to do. `model.path` cannot answer it, but the folder can.
  def self.status
    rows = candidates
    puts "\n#{MODEL_DIR}"
    rows.each { |stem, captured| puts "  #{captured ? '✓' : '·'} #{stem}" }
    remaining = rows.reject(&:last).map(&:first)
    puts remaining.empty? ? "\n  all #{rows.size} captured." : "\n  #{remaining.size} to go."
    remaining
  end

  # The name to file this capture under. `model.path` is untrustworthy, so the
  # basename is a *suggestion* -- pass an explicit one when it looks wrong:
  #
  #     Dph.here("2523 Wellington_COPY")
  #
  # It never leaves MODEL_DIR, and `.skp`-in-the-middle (a Windows path arriving
  # as one long filename) is stripped so a bad suggestion still lands somewhere
  # sane.
  def self.destination_for(path, override)
    stem = override || File.basename(path.to_s.tr("\\", "/"), ".skp")
    stem = stem.gsub(/[^A-Za-z0-9 ._-]/, "_")
    File.join(MODEL_DIR, "#{stem}.extraction.json")
  end

  # -------------------------------------------------------------------
  # The supported path: collect whatever is open right now.
  # -------------------------------------------------------------------
  def self.here(name = nil)
    load_collector
    model = Sketchup.active_model
    path = model.path.to_s

    # The one question that matters, and the API cannot answer it: is the open model a COPY?
    #
    # When `model.path` points into MODEL_DIR, that is a positive identification and we proceed.
    # Otherwise the path is either stale (fine — the real file IS a copy) or a genuinely open
    # original (not fine), and **nothing here can tell those apart**. So it stops and asks for the
    # one fact the human has and SketchUp does not: which copy this is. Naming it is the
    # assertion, and it is cheap — the runbook already has each model opened by hand.
    unless trusted_path?(path)
      if name.nil?
        puts "\n✗ Cannot identify this model."
        puts "  model.path is #{path.inspect}"
        puts "  — not a file in #{MODEL_DIR}, and model.path is the location the model was last"
        puts "    SAVED, which on a file authored elsewhere is somebody else's machine. It cannot"
        puts "    be used to tell a copy from an original."
        puts ""
        puts "  If this IS one of the copies, say which. The ones in #{MODEL_DIR}:"
        # ⚠ The real names, not an example. An earlier version of this message hardcoded one
        # model's name and printed it while a different model was open, which reads as an
        # instruction rather than as a placeholder.
        candidates.each do |stem, captured|
          puts "      Dph.here(#{stem.inspect})#{captured ? '   (already captured)' : ''}"
        end
        puts "  If you really did open an original, close it and open the copy (hard rule 3)."
        return nil
      end
      puts "\n⚠ model.path is #{path.inspect} — stale, ignored."
      puts "  Filing under the name you gave. Reading the model that is open now."
    end

    destination = destination_for(path, name)
    puts "\n#{File.basename(destination, '.extraction.json')}"
    result = collect(model, destination)
    puts result["error"] ? "  ✗ #{result['error']}" : "  ✓ done"
    remaining = status
    if remaining.empty?
      puts "\nQuit SketchUp and tell me. I run:"
      puts "  uv run poc/tools/check_extraction.py ~/Desktop/dph_poc_copies/*.extraction.json"
    end
    result
  end

  # -------------------------------------------------------------------
  # The batch path. Verifies, and refuses to guess.
  # -------------------------------------------------------------------
  def self.sweep(directory = MODEL_DIR)
    directory = File.expand_path(directory)
    if forbidden?(directory)
      puts "✗ REFUSED: #{directory} holds corpus originals. Copy them first (hard rule 3)."
      return
    end
    models = Dir.glob(File.join(directory, "*.skp")).sort
    if models.empty?
      puts "No .skp files in #{directory}"
      return
    end

    load_collector
    puts "\n" + ("=" * 72)
    puts "designPH extraction sweep -- #{models.size} model(s) in #{directory}"
    puts "⚠ If this stops on the first model, that is macOS multi-document behaviour."
    puts "  Fall back to: open each copy by hand, then `Dph.here`."
    puts "=" * 72

    results = []
    models.each do |path|
      puts "\n#{File.basename(path)}"
      Sketchup.open_file(path)
      model = Sketchup.active_model
      # The whole reason this method is not the supported path. Without this check the sweep
      # would happily write five files that all describe the first model.
      unless File.expand_path(model.path.to_s) == File.expand_path(path)
        puts "  ✗ STOP: after open_file, the active model is #{model.path.inspect},"
        puts "    not #{path.inspect}. SketchUp did not switch documents."
        puts "    Use `Dph.here` per model instead — no data has been written."
        return results
      end
      results << collect(model, destination_for(path, nil))
    end
    summarise(results)
    results
  end

  # -------------------------------------------------------------------
  # `destination` is the .extraction.json path, resolved by the caller — never
  # derived from the model here. See the header for what that cost.
  def self.collect(model, destination)
    name = File.basename(destination, ".extraction.json")
    before = model.modified?

    started = Time.now
    payload = DphPlusPoc::Collector.extract(
      model, "dph_plus_poc collector console-run #{Time.now.strftime('%Y-%m-%d')}", name
    )
    elapsed = ((Time.now - started) * 1000).round

    if model.modified? && !before
      puts "  ✗ STOP: the model was modified during collection. The collector must be read-only."
      return { "model" => name, "error" => "model.modified? changed false -> true" }
    end

    File.write(destination, JSON.pretty_generate(payload))
    counts = payload["counts"]
    printf("  %d walked / %d tagged / %d classified / %d edges / %d windows  (%d ms)\n",
           counts["faces_walked"], counts["faces_tagged"], counts["faces_classified"],
           counts["edges_tagged"], counts["windows_found"], elapsed)
    puts "  tables: #{counts['tables_found'].join(', ')}" unless counts["tables_found"].empty?
    puts "  -> #{File.basename(destination)}"
    counts.merge("model" => name, "ms" => elapsed)
  rescue StandardError => error
    puts "  ✗ #{error.class}: #{error.message}"
    puts "    #{error.backtrace.first(3).join("\n    ")}"
    { "model" => name, "error" => "#{error.class}: #{error.message}" }
  end

  # End with a verdict. A run nobody can grade at a glance has not reported anything.
  def self.summarise(results)
    failed = results.select { |r| r["error"] }
    puts "\n" + ("=" * 72)
    puts failed.empty? ? "ALL #{results.size} MODEL(S) COLLECTED" :
                         "#{failed.size} OF #{results.size} FAILED"
    failed.each { |r| puts "  #{r['model']}: #{r['error']}" }
    puts "=" * 72
  end
end

puts "Dph loaded. Open a model COPY, then run:  Dph.here"
