# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- the wired export path, end to end on the Ruby side.
#
#     ruby poc/ext/tests/test_integration.rb
#
# POC-4's gate is "failures surface visibly", and that is a claim about what the
# user is shown -- so this suite drives a real `Session` against a stubbed
# `HtmlDialog` and reads the message boxes back. Every row of §2's failure table
# that does not need CEF is here:
#
#   collector raises  -> FAILED message box, nothing written
#   version refused   -> a refusal naming the stamp, no dialog opened at all
#   no designPH data  -> a refusal saying so, after the walk
#   payload too big   -> a refusal naming the largest section
#   write fails       -> the path and the OS error, and the run still reports
#   ok                -> three files, atomically, with the gate's notes in them
#
# ⚠ What it cannot prove is the same short list as always: `HtmlDialog`'s
# payload ceiling and its threading. `UI.start_timer` here is a plain Ruby
# `Thread`, which is the exact inversion of SketchUp's behaviour
# (`sketchup_stub.rb` header). Ed's §3 runbook is what closes those.
#
# Ruby 2.7. `ruby -c` before installing.
# ---------------------------------------------------------------------------
require "json"
require "tmpdir"
require_relative "sketchup_stub"

Thread.abort_on_exception = true

load File.join(__dir__, "..", "dph_plus_poc", "main.rb")

$failures = 0
$sandbox = nil

def check(label, condition, detail = nil)
  $failures += 1 unless condition
  puts format("  %-4s %s%s", condition ? "ok" : "FAIL", label, detail ? "  (#{detail})" : "")
  condition
end

def group(title)
  puts "\n#{title}"
end

# The save panel is the ONLY source of an output directory (`Writer`'s header).
# Redirecting it here is therefore not a test hack — it is the production
# contract, exercised. Nothing in this suite may write to the real Desktop.
module UI
  def self.savepanel(_title, _directory, filename)
    File.join($sandbox, filename.to_s)
  end
end

M = 1.0 / 0.0254

def square(size, z: 0.0)
  [[0, 0, z], [size, 0, z], [size, size, z], [0, size, z]]
end

# A minimal but genuinely designPH-shaped model: one classified face, a version
# stamp, a climate id.
def designph_model(version: "2.1.15", faces: 1)
  entities = Array.new(faces) do |index|
    Sketchup::Face.new(square(M), persistent_id: index + 1, dictionaries: {
      "DesignPH_dict" => {
        "areaGroupID" => 8, "tempZoneID" => "A", "assemblyID" => "01ud", "descName" => "Wall"
      }
    })
  end
  Sketchup::Model.new(
    entities: entities,
    title: "adelphi-designph_COPY",
    dictionaries: { "DesignPH_dict" => {
      "designPH_version" => version, "klima_ID" => "US0058a"
    } }
  )
end

# What the dialog hands back on `on_result`: the envelope, carrying the
# translator's own output string verbatim.
def translator_reply(hbjson: '{"type":"Model"}', headline: "PASSED WITH OMISSIONS")
  result = {
    "hbjson" => hbjson,
    "report" => {
      "summary" => {
        "faces" => { "in" => 82, "translated" => 82, "reported" => 0 },
        "apertures" => { "in" => 46, "translated" => 46, "reported" => 0 },
        "thermal_bridges" => { "in" => 0, "translated" => 0, "reported" => 0 },
        "tfa_m2_covered" => 368.5, "tfa_m2_lost" => 0.0
      }
    },
    "verdict" => {
      "passed" => true, "headline" => headline,
      "checks" => [{ "label" => "contract version", "ok" => true, "detail" => "2" }]
    }
  }
  JSON.generate({
    "action" => "translate", "ok" => true,
    "payload" => JSON.generate(result),
    "runtime" => { "timings" => { "boot_ms" => 2577 } }
  })
end

# One export, from menu click to files on disk. Returns the dialog (nil when the
# pre-walk gate refused before one was ever created).
def export(model, result_json = nil)
  Sketchup.active_model = model
  UI.reset_messages
  dialog = DphPlusPoc.run("translate")
  return nil if dialog.nil?
  dialog.fire("on_ready", "")
  dialog.fire("on_result", result_json) if result_json
  dialog
ensure
  dialog.close if dialog
end

# The `translate` payload the session actually sent to the page, parsed back out
# of the `DphPlus.dispatch(...)` script.
def dispatched(dialog)
  script = dialog.scripts.find { |text| text.start_with?("DphPlus.dispatch(") }
  return nil if script.nil?
  message = JSON.parse(script[/\ADphPlus\.dispatch\((.*)\)\z/m, 1])
  message["payload"] && JSON.parse(message["payload"])
end

def last_message
  (UI.messages || []).last.to_s
end

# The refusal text Ruby pushed into the dialog's banner, or nil if it never did.
# ⚠ Distinct from the message box on purpose: the box is dismissed, the banner stays.
def banner_refusal(dialog)
  return nil if dialog.nil?
  script = dialog.scripts.find { |text| text.start_with?("DphPlus.showRefusal(") }
  script && JSON.parse("[" + script[/\ADphPlus\.showRefusal\((.*)\)\z/m, 1] + "]").first
end

# ---------------------------------------------------------------------------
group "The happy path -- three files, and what they contain"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = directory
  dialog = export(designph_model, translator_reply)

  check("the dialog opened", !dialog.nil? && dialog.shown?)
  check("...and served over http://127.0.0.1, never file://",
        dialog.url.start_with?("http://127.0.0.1"), dialog.url)

  payload = dispatched(dialog)
  check("a translate action was dispatched", !payload.nil?)
  check("...carrying contract version 2", payload["contract_version"] == 2)
  check("...with the classified face in it", payload["counts"]["faces_classified"] == 1)
  # ⚠ The extraction's own `file_name` must not come from `model.path` either —
  # it is what a captured fixture is filed under downstream.
  check("...named from the sanitised model title",
        payload["model"]["file_name"] == "adelphi-designph_COPY", payload["model"]["file_name"])

  written = Dir.glob(File.join(directory, "*")).map { |path| File.basename(path) }.sort
  check("the HBJSON was written", written.include?("adelphi-designph_COPY.hbjson"), written.join(", "))
  check("the report was written beside it", written.include?("adelphi-designph_COPY.report.json"))
  # The diagnostics checkbox is off by default, and the stub's `read_default`
  # returns the default — so the extraction must NOT be written.
  check("the extraction was not, with diagnostics off", written.size == 2, written.join(", "))
  check("no temp file survived", written.none? { |name| name.include?(".tmp") })

  hbjson = File.read(File.join(directory, "adelphi-designph_COPY.hbjson"))
  check("the HBJSON is the translator's own string, verbatim", hbjson == '{"type":"Model"}')

  report = JSON.parse(File.read(File.join(directory, "adelphi-designph_COPY.report.json")))
  check("the report carries the runtime measurements only JS could see",
        report["runtime"]["timings"]["boot_ms"] == 2577)
  check("...and the host notes", report.key?("host_notes"))

  check("the message box uses the translator's three-state headline",
        last_message.include?("PASSED WITH OMISSIONS"), last_message.lines.first.to_s.strip)
  check("...and states translated vs reported per kind",
        last_message.include?("apertures") && last_message.include?("46 translated"))
  check("...and TFA coverage", last_message.include?("368.5 m² covered"))
  check("...and names both files", last_message.include?(".hbjson") && last_message.include?(".report.json"))
end

# ---------------------------------------------------------------------------
group "Version refusal -- before the collector ever walks"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = directory
  dialog = export(designph_model(version: "3.0.1"), translator_reply)

  # ⚠ This is the point of the pre-walk half. A 3.0 model reaching a 2.x-shaped
  # walk produces neither a translation nor a report — and an 18 MB Pyodide
  # runtime would have booted first to get there.
  check("no dialog is opened at all", dialog.nil?)
  check("the refusal names the stamp", last_message.include?("3.0.1"), last_message.lines[2].to_s.strip)
  check("...and says which generation IS read", last_message.include?("designPH 2.x"))
  check("...and is headlined as a refusal, not a failure",
        last_message.include?("nothing exported") && !last_message.include?("FAILED"))
  check("nothing was written", Dir.glob(File.join(directory, "*")).empty?)
  # No banner to write to, and that is the point of refusing pre-walk: the message box is the
  # only surface that exists yet.
  check("no dialog means no banner to update", banner_refusal(dialog).nil?)
end

# ---------------------------------------------------------------------------
group "Not a designPH model -- only the walk can decide it"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = directory
  blank = Sketchup::Model.new(
    entities: [Sketchup::Face.new(square(M), persistent_id: 1)], title: "some sketch"
  )
  dialog = export(blank, translator_reply)

  # It gets a dialog: with no stamp anywhere, "not designPH" is undecidable
  # until the census comes back empty.
  check("the dialog opens", !dialog.nil?)
  check("...but nothing is dispatched to it", dispatched(dialog).nil?)
  check("the refusal says there is no designPH data", last_message.include?("no designPH data at all"))
  check("nothing was written", Dir.glob(File.join(directory, "*")).empty?)

  # ⚠ The live C1 run dismissed the message box and left the dialog reading `booting…` — a window
  # that had finished its work still claiming to be starting. The box is transient; the banner is
  # what stays on screen, so the banner is what has to carry the grade.
  banner = banner_refusal(dialog)
  check("the refusal also reaches the dialog banner", !banner.nil?)
  check("...with the same words as the message box",
        banner.to_s.include?("no designPH data at all"), banner.to_s.lines.first.to_s.strip)
  # And before the message box, which blanks the dialog while it is up.
  scripts = dialog.scripts.map { |s| s[0, 20] }
  check("...pushed before UI.messagebox blanks the window",
        scripts.any? { |s| s.start_with?("DphPlus.showRefusal") }, scripts.join(" | "))
end

# ---------------------------------------------------------------------------
group "No stamp, but real designPH data -- proceed, and say so"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = directory
  stampless = Sketchup::Model.new(
    entities: [Sketchup::Face.new(square(M), persistent_id: 1, dictionaries: {
      "DesignPH_dict" => { "areaGroupID" => 8, "tempZoneID" => "A" }
    })],
    title: "unstamped"
  )
  dialog = export(stampless, translator_reply)

  check("it translates", !dispatched(dialog).nil?)
  report = JSON.parse(File.read(File.join(directory, "unstamped.report.json")))
  check("the report records why it proceeded",
        report["host_notes"].any? { |text| text.include?("no designPH version stamp") },
        report["host_notes"].inspect)
  check("...naming the evidence", report["host_notes"].first.include?("1 tagged faces"))
  check("and the user is told too", last_message.include?("no designPH version stamp"))
end

# ---------------------------------------------------------------------------
group "The collector raising is a verdict, not a hang"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = directory
  exploding = designph_model
  # An exception from anywhere inside the walk. In SketchUp an exception that
  # escapes an action callback is swallowed and the dialog simply sits there —
  # which is the one outcome POC-4's gate calls an outright FAIL.
  def exploding.entities
    raise IOError, "simulated read failure"
  end

  dialog = export(exploding, nil)
  check("the dialog survives", !dialog.nil?)
  check("nothing is dispatched", dispatched(dialog).nil?)
  check("the user is shown FAILED", last_message.include?("FAILED"), last_message.lines.first.to_s.strip)
  check("...naming the error class", last_message.include?("IOError"))
  check("nothing was written", Dir.glob(File.join(directory, "*")).empty?)
end

# ---------------------------------------------------------------------------
group "A write failure names the path, and the run still reports"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = File.join(directory, "does-not-exist")
  dialog = export(designph_model, translator_reply)

  check("the translation still reports its verdict", last_message.include?("PASSED WITH OMISSIONS"))
  check("...and says the file was NOT written", last_message.include?("NOT WRITTEN"))
  check("...naming the OS error", last_message.include?("Errno::ENOENT"),
        last_message.lines.last.to_s.strip)
  check("nothing was left behind", Dir.glob(File.join(directory, "**", "*")).empty?)
end

# ---------------------------------------------------------------------------
group "A translator failure surfaces as its own error"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = directory
  reply = JSON.generate({
    "action" => "translate", "ok" => false,
    "error" => "Traceback (most recent call last):\n  KeyError: 'contract_version'"
  })
  export(designph_model, reply)
  check("the message box is FAILED", last_message.include?("FAILED"))
  check("...carrying the first line of the traceback", last_message.include?("Traceback"))
  check("nothing was written", Dir.glob(File.join(directory, "*")).empty?)
end

# ---------------------------------------------------------------------------
group "An oversized payload is refused before it crosses the bridge"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = directory
  # ≈250 bytes of contract per face, so this clears 3 MB. The real corpus runs
  # 334-501 KB, which is the number the refusal quotes back.
  export(designph_model(faces: 13_000), translator_reply)

  check("the export is refused", last_message.include?("nothing exported"),
        last_message.lines.first.to_s.strip)
  check("...naming the largest section", last_message.include?("faces"))
  # The breakdown is a block, so it only runs on this path — the check that it
  # runs at all, and that re-serialising a 3 MB payload does not itself raise.
  check("...with a megabyte figure", last_message =~ /\d+\.\d+ MB/ ? true : false)
  check("...and the corpus range, so 'too big' reads as a defect not a limit",
        last_message.include?("0.3–0.5 MB"))
  check("nothing was written", Dir.glob(File.join(directory, "*")).empty?)
end

# ---------------------------------------------------------------------------
group "The progress hook fires (⚠ which is NOT the same as being visible)"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-integration") do |directory|
  $sandbox = directory
  # ⛔ **What this suite CANNOT tell you, and did not:** whether any of it is on
  # screen. It is not. Measured in SketchUp on 2026-08-21 — the status bar lives
  # on the main window, behind the dialog, and more fundamentally the walk is a
  # synchronous main-thread loop, so neither the status bar nor the dialog
  # repaints until it ends (`main.rb`, `progress_reporter`).
  #
  # These checks are kept because the hook is real and the throttle is real, and
  # both become correct the day the walk yields. But **asserting that a string
  # was set is not asserting that a user saw it** — the fourth time this phase
  # that a call stood in for a surface, and the one the offline harness could
  # never have caught, because a stub has no screen.
  crowd = designph_model(faces: 600)
  Sketchup.status_text = nil
  export(crowd, translator_reply)

  history = (Sketchup.status_history || []).compact
  check("the hook set a status string", history.any? { |text| text.include?("reading the model") },
        history.first.to_s)
  check("...carrying a running count", 
        history.any? { |text| text =~ /\d+ entities/ }, history.select { |t| t =~ /entities/ }.first.to_s)
  # ⚠ Leaving a status message behind makes every later SketchUp action look
  # like it belongs to us.
  check("...and was cleared afterwards", Sketchup.status_text == "", Sketchup.status_text.inspect)
end

# ---------------------------------------------------------------------------
puts "\n" + ("=" * 68)
puts $failures.zero? ? "ALL CHECKS PASSED" : "#{$failures} CHECK(S) FAILED"
puts "=" * 68
exit($failures.zero? ? 0 : 1)
