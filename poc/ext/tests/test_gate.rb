# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- the version and payload gates.
#
#     ruby poc/ext/tests/test_gate.rb
#
# Every row of both decision tables in `planning/POC/POC-4_integration.md` §1,
# plus the safe-name and atomic-write rules that surround them.
#
# ⚠ This is the one suite whose *most important* case cannot come from the
# corpus: nobody here has a designPH 3.0 model, and by the time one exists the
# refusal has to already work. So the 3.x rows are synthetic on purpose, and
# Ed's §3.3 failure-path run stamps a **fresh empty model** rather than a corpus
# copy -- hard rule 3 protects real designPH data, and a synthetic stamp on an
# empty model touches none of it.
#
# Ruby 2.7. `ruby -c` before installing.
# ---------------------------------------------------------------------------
require "fileutils"
require "tmpdir"
require_relative "sketchup_stub"

Thread.abort_on_exception = true

load File.join(__dir__, "..", "dph_plus_poc", "main.rb")

G = DphPlusPoc::Gate
W = DphPlusPoc::Writer

$failures = 0

def check(label, condition, detail = nil)
  $failures += 1 unless condition
  puts format("  %-4s %s%s", condition ? "ok" : "FAIL", label, detail ? "  (#{detail})" : "")
  condition
end

def group(title)
  puts "\n#{title}"
end

def extraction(counts = {}, model = {})
  { "model" => model, "counts" => counts }
end

# ---------------------------------------------------------------------------
group "Version -- the leading integer decides, and a beta of 2.x is 2.x"
# ---------------------------------------------------------------------------

{ "2.1.15" => 2, "2.2.29" => 2, "2.4.0 BETA PRO" => 2, " 2.0 " => 2,
  "3.0.1" => 3, "10.1" => 10, "1.9" => 1,
  "unknown" => nil, "" => nil, "v2.1" => nil }.each do |stamp, want|
  check("major(#{stamp.inspect}) == #{want.inspect}", G.major(stamp) == want)
end

# ⚠ `"v2.1"` reads as unrecognised, not as 2.x. That is deliberate: designPH has
# never written a `v` prefix on any of the 14 corpus models, so a stamp shaped
# that way is a format this reader has not seen and the honest answer is to
# refuse and name it rather than to guess a generation from it.

# ---------------------------------------------------------------------------
group "Version -- the decision table, row by row"
# ---------------------------------------------------------------------------

# Row: all stamps parse as 2.x -> proceed, silently.
plain = G.version(["2.1.15"], ["82 tagged faces"])
check("a single 2.x stamp proceeds", plain.allow)
check("...with no note", plain.note.nil?)

# Row: any stamp >= 3 -> refuse, naming it.
future = G.version(["3.0.1"], ["82 tagged faces"])
check("a 3.x stamp is refused", future.refused?)
check("...naming the stamp", future.reason.include?("3.0.1"), future.reason.lines.first.strip)
check("...and saying which generation IS read", future.reason.include?("designPH 2.x"))
# Evidence cannot rescue it: a 3.0 model is full of designPH data and that is
# precisely the danger -- the collector would walk it against a 2.x schema.
check("...even with a full census behind it",
      G.version(["3.0.1"], ["500 tagged faces", "99 tagged edges"]).refused?)
check("...and refuses PRE-walk too, before the collector sees the schema",
      G.version(["3.0.1"], nil).refused?)

# Row: unrecognised -> refuse. Same branch, different wording.
unknown = G.version(["banana"], ["82 tagged faces"])
check("an unparseable stamp is refused", unknown.refused?)
check("...described as unrecognised, not as newer",
      unknown.reason.include?("not a version this reader recognises"))

older = G.version(["1.9"], ["82 tagged faces"])
check("a 1.x stamp is refused", older.refused?)
check("...described as older", older.reason.include?("older than this reader supports"))

# One bad stamp among good ones still refuses -- the safe direction.
mixed_bad = G.version(["2.1.15", "3.0.1"], ["82 tagged faces"])
check("2.x + 3.x refuses", mixed_bad.refused?)
check("...naming only the unsupported one", mixed_bad.reason.include?("3.0.1") &&
                                            !mixed_bad.reason.include?("2.1.15"))

# Row: mixed 2.x stamps -> proceed + note. Wellington's `.skp` really does carry
# two, visible to the offline binary reader.
mixed = G.version(["2.1.15", "2.2.29"], ["103 tagged faces"])
check("two different 2.x stamps proceed", mixed.allow)
check("...with a note naming both",
      mixed.note.include?("2.1.15") && mixed.note.include?("2.2.29"), mixed.note)
# The same stamp twice is not "mixed".
check("the same stamp repeated is not a mixed model",
      G.version(["2.1.15", "2.1.15"], ["82 tagged faces"]).note.nil?)

# Row: no stamp, but the walk found designPH data -> proceed + note.
stampless = G.version([], ["194 tagged faces", "99 tagged edges"])
check("no stamp + evidence proceeds", stampless.allow)
check("...with a note carrying the evidence",
      stampless.note.include?("194 tagged faces") && stampless.note.include?("99 tagged edges"),
      stampless.note)

# Row: no stamp, nothing found -> the polite refusal.
blank = G.version([], [])
check("no stamp + no evidence is refused", blank.refused?)
check("...as 'no designPH data'", blank.reason.include?("no designPH data at all"))

# Row: no stamp, evidence unknown (PRE-walk) -> defer, do not refuse.
#
# ⚠ This is the row that makes the gate run twice. Refusing here would refuse
# every model whose stamp sits on entities rather than at model level, before
# the walk that would have proved it fine.
check("no stamp pre-walk defers rather than refusing", G.version([], nil).allow)
check("...silently, so the post-walk call owns the note", G.version([], nil).note.nil?)

# Blank and nil stamps are absent, not unrecognised. `Array(nil)` and designPH's
# own nil placeholders both land here.
check("nil stamps are absent, not unrecognised", G.version([nil, ""], []).reason.include?("no designPH data"))

# ---------------------------------------------------------------------------
group "Version -- reading the stamps off a model"
# ---------------------------------------------------------------------------

stamped = Sketchup::Model.new(dictionaries: { "DesignPH_dict" => { "designPH_version" => "2.2.29" } })
check("stamps() reads the model dictionary", G.stamps(stamped) == ["2.2.29"])
# ⚠ `attribute_dictionary` returns nil, not empty, when there is none.
check("stamps() survives a model with no DesignPH_dict", G.stamps(Sketchup::Model.new) == [])

# ---------------------------------------------------------------------------
group "Evidence -- what counts as 'this is a designPH model'"
# ---------------------------------------------------------------------------

check("an empty model yields no evidence", G.evidence(extraction).empty?)
check("tagged faces are evidence",
      G.evidence(extraction("faces_tagged" => 194)) == ["194 tagged faces"])
# ⚠ Bluff Reach's 99 thermal bridges are on EDGES. A face-only notion of
# evidence would call an edges-only model "not designPH" and refuse it.
check("tagged edges alone are evidence",
      G.evidence(extraction("edges_tagged" => 99)) == ["99 tagged edges"])
check("windows alone are evidence",
      G.evidence(extraction("windows_found" => 46)) == ["46 designPH windows"])
check("model tables alone are evidence",
      G.evidence(extraction("tables_found" => %w[assemblies_ud vent_ud])) == ["2 designPH table(s)"])
check("a climate id alone is evidence",
      G.evidence(extraction({}, "klima_id" => "US0058a")) == ["a designPH climate id"])
check("a blank climate id is not evidence", G.evidence(extraction({}, "klima_id" => " ")).empty?)
# Zero counts must not read as presence -- the same by-value/by-presence trap as
# `classified?` (hard rule 5).
check("zero counts are not evidence",
      G.evidence(extraction("faces_tagged" => 0, "edges_tagged" => 0, "windows_found" => 0)).empty?)

# ---------------------------------------------------------------------------
group "Payload -- refuse over 3 MB, notice over 1 MB"
# ---------------------------------------------------------------------------

check("a corpus-sized payload passes silently", G.payload(501_000).allow && G.payload(501_000).note.nil?)
notice = G.payload(2_250_000)
check("2.25 MB proceeds", notice.allow)
check("...with a notice", !notice.note.nil?, notice.note)
# 2.25 MB is the real number from the defect this threshold caught. It must stay
# a notice and not a refusal: the export succeeded, and the notice is what made
# anyone look at where the bytes went.
check("...and is NOT refused", !notice.refused?)

big = G.payload(4_500_000, { "windows" => 4_100_000, "faces" => 300_000 })
check("4.5 MB is refused", big.refused?)
check("...naming the largest section", big.reason.include?("windows"), big.reason.lines[2].to_s.strip)
check("...with its share", big.reason.include?("91%"))
check("...and saying what normal looks like", big.reason.include?("0.3–0.5 MB"))
check("exactly at the limit still passes", G.payload(G::MAX_PAYLOAD_BYTES).allow)
check("one byte over does not", G.payload(G::MAX_PAYLOAD_BYTES + 1).refused?)

sections = G.breakdown({ "faces" => [1, 2, 3], "windows" => [] })
check("breakdown() sizes every top-level section", sections.keys.sort == %w[faces windows])
check("...in bytes of its own JSON", sections["faces"] == "[1,2,3]".bytesize)

# ---------------------------------------------------------------------------
group "Output naming -- never derived from an untrustworthy model.path"
# ---------------------------------------------------------------------------

# ⚠ The two real values measured across the corpus copies, both of which are
# where some *other* machine last saved the model. Deriving a filename from
# either wrote one capture into `~/Documents` under the whole Windows path as a
# single filename, and lost the other to ENOENT (`SKETCHUP_RUNTIME.md` §8.2).
windows_path = "C:\\Users\\greg\\OneDrive\\Linde Residence - 2.0 kBTU - 7.3.25.skp"
foreign_path = "/Users/johnmitchell/Dropbox/2523 Weiilington.skp"

check("a Windows path yields a bare stem",
      W.safe_stem(windows_path) == "Linde Residence - 2.0 kBTU - 7.3.25",
      W.safe_stem(windows_path))
check("a foreign POSIX path yields a bare stem",
      W.safe_stem(foreign_path) == "2523 Weiilington", W.safe_stem(foreign_path))
check("...with no separator left anywhere",
      !W.safe_stem(windows_path).include?("/") && !W.safe_stem(windows_path).include?("\\"))
check("a plain title passes through", W.safe_stem("adelphi-designph") == "adelphi-designph")
check("an empty title falls back", W.safe_stem("") == "untitled")
check("a title of only separators falls back", W.safe_stem("///") == "untitled")
check("path traversal cannot survive", W.safe_stem("../../etc/passwd") == "passwd")
check("shell and glob characters are neutralised",
      W.safe_stem("a$b;c*d?e") == "a_b_c_d_e", W.safe_stem("a$b;c*d?e"))
# Non-ASCII is not dangerous, but SketchUp's own save panel round-trips it
# inconsistently across platforms and a mangled filename is a support call.
check("non-ASCII is transliterated to underscores", W.safe_stem("Grüner Weg") == "Gr_ner Weg")

# `model.title` is what the Writer actually reads, and it is a *title*, not a
# path -- but on a model last saved elsewhere it can still carry one.
check("stem_for reads the model title",
      W.stem_for(Sketchup::Model.new(title: "adelphi-designph")) == "adelphi-designph")
check("stem_for sanitises a title that is really a path",
      W.stem_for(Sketchup::Model.new(title: windows_path)) == "Linde Residence - 2.0 kBTU - 7.3.25")
check("stem_for falls back on an untitled model",
      W.stem_for(Sketchup::Model.new(title: "")) == "untitled")

# ---------------------------------------------------------------------------
group "Writing -- atomic, UTF-8, and no debris on failure"
# ---------------------------------------------------------------------------

Dir.mktmpdir("dphplus-writer") do |directory|
  target = File.join(directory, "out.hbjson")

  W.write(target, "{\"a\": \"°C ✓\"}")
  check("write() creates the file", File.file?(target))
  check("...as UTF-8", File.read(target, mode: "r:UTF-8") == "{\"a\": \"°C ✓\"}")
  check("...leaving no temp file behind", Dir.glob(File.join(directory, "*")).size == 1,
        Dir.glob(File.join(directory, "*")).join(", "))

  # The point of the rename: a reader either sees the old file or the new one,
  # never a half-written one. Overwriting is the case that would otherwise
  # truncate in place.
  W.write(target, "replaced")
  check("write() replaces atomically", File.read(target) == "replaced")
  check("...still with no debris", Dir.glob(File.join(directory, "*")).size == 1)

  begin
    W.write(File.join(directory, "no-such-dir", "out.json"), "x")
    check("a write into a missing directory raises", false)
  rescue StandardError => error
    check("a write into a missing directory raises", true, error.class.to_s)
  end
  check("...and leaves the directory clean", Dir.glob(File.join(directory, "*")).size == 1)
end

# ---------------------------------------------------------------------------
puts "\n" + ("=" * 68)
puts $failures.zero? ? "ALL CHECKS PASSED" : "#{$failures} CHECK(S) FAILED"
puts "=" * 68
exit($failures.zero? ? 0 : 1)
