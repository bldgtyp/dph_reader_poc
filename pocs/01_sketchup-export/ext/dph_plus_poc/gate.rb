# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- gate.rb
#
# The two refusals that stand between "the user picked Export HBJSON" and the
# translator: **is this a designPH 2.x model?** and **will its extraction fit
# across the bridge?**
#
# Pure functions over plain data, deliberately. Nothing here touches the model
# or the dialog, so every branch of both decision tables is reachable from
# `ext/tests/test_gate.rb` without SketchUp -- which matters because the branch
# that costs the most to get wrong (a designPH 3.0 model) is the one branch we
# have no file for and cannot obtain (`planning/01_sketchup-export/implementation/POC-4_integration.md` §3.3
# builds a synthetic stamp instead).
#
# ⚠ **The version check runs TWICE and that is not redundancy.**
#
#   * before the walk, on the model's own stamps alone -- a 3.x model must be
#     refused in milliseconds, and more importantly must be refused *before* a
#     collector written against the 2.x schema meets a schema it has never
#     seen. A refusal is a report; a `NoMethodError` from inside the walk is
#     not (POC-4 §2).
#   * after the walk, with the census as evidence -- because "no version stamp"
#     is only "not a designPH model" if the walk *also* found nothing, and the
#     corpus has models whose envelope data is fine with a stamp missing or
#     doubled. Pre-walk, that branch is simply undecidable, so it defers.
#
# ⚠ **Never version-key the READ.** Hard rule 6 stands: this gate decides
# whether to read at all. Once past it, `collector.rb` coalesces `*ID` ‖ `*Auto`
# regardless of any stamp -- `250708.skp` is 2.1.15 and keeps every assembly in
# `assemblyIDAuto`.
#
# SketchUp 2022 is Ruby 2.7. `ruby -c` before installing.
# ---------------------------------------------------------------------------
require "json"

module DphPlusPoc
  module Gate

    # The only designPH generation this reader understands. designPH 3.0 changed
    # the storage schema; the working assumption is that a 2.x reader will be
    # taught to translate it later (`00_POC_OVERVIEW.md` §2), and until then a
    # 3.x model must bounce off the front door rather than be half-read.
    SUPPORTED_MAJOR = 2

    # Refuse above this. The bridge is verified to 4 MB each way; the margin is
    # deliberate, and real contract-v2 extractions measured 334-501 KB across
    # the whole corpus, so nothing legitimate is anywhere near it.
    MAX_PAYLOAD_BYTES = 3_000_000

    # Log above this. ⚠ **Do not raise it because it never fires.** It fired on
    # the very first real capture it applied to and found a genuine defect --
    # 2.07 MB of a 2.25 MB payload was designPH's frame/glazing option lists,
    # byte-identical on all 46 windows (contract §5.1). A limit that never
    # fires teaches nothing; this one taught the contract's v2 shape.
    LOG_PAYLOAD_BYTES = 1_000_000

    # `allow` false is a refusal and `reason` says why, in the user's words.
    # `note` is a fact worth carrying into the report on a run that proceeds --
    # the two are independent, and a proceed-with-note is the common case on
    # real models.
    Decision = Struct.new(:allow, :reason, :note) do
      def refused?
        !allow
      end
    end

    ALLOWED = Decision.new(true, nil, nil).freeze

    NOT_DESIGNPH =
      "This model carries no designPH data at all: no version stamp, no tagged faces or edges, " \
      "no designPH windows and no designPH tables.\n\n" \
      "DesignPH-PLUS reads models prepared with the designPH SketchUp plugin. Nothing was read " \
      "and nothing was written.".freeze

    # -------------------------------------------------------------------
    # Version
    # -------------------------------------------------------------------

    # The raw stamps the model itself carries. Model-level only: designPH writes
    # one per model, and reading it costs nothing, which is what makes the
    # pre-walk refusal possible.
    def self.stamps(model)
      dictionary = model.attribute_dictionary(Collector::DICT)
      Array(dictionary && dictionary[Collector::MODEL_VERSION_KEY]).compact
    end

    # The decision table of `POC-4_integration.md` §1, as one function.
    #
    # `evidence` is the list of human-readable designPH findings from the walk,
    # or **nil when the walk has not run yet** -- the pre-walk call. The nil case
    # is the only difference between the two calls, and it only affects the
    # no-stamp row: pre-walk, "no stamp" is undecidable and defers; post-walk it
    # is either a note or the refusal.
    #
    #   all stamps 2.x, one distinct  -> proceed
    #   any stamp not 2.x             -> REFUSE, naming the stamp
    #   mixed 2.x stamps              -> proceed + note
    #   no stamp, evidence present    -> proceed + note
    #   no stamp, no evidence         -> REFUSE ("not a designPH model")
    #   no stamp, evidence unknown    -> proceed (defer to the post-walk call)
    def self.version(raw_stamps, evidence = nil)
      found = Array(raw_stamps).map { |stamp| stamp.to_s.strip }.reject(&:empty?)

      unsupported = found.reject { |stamp| major(stamp) == SUPPORTED_MAJOR }
      return Decision.new(false, unsupported_text(unsupported), nil) unless unsupported.empty?

      if found.empty?
        return ALLOWED if evidence.nil?
        return Decision.new(false, NOT_DESIGNPH, nil) if Array(evidence).empty?
        return Decision.new(
          true, nil,
          "no designPH version stamp on the model; proceeding on #{Array(evidence).join(', ')}"
        )
      end

      distinct = found.uniq
      return ALLOWED if distinct.size == 1
      # ⚠ Real: `2523 Wellington.skp` carries two stamps in its binary. The live
      # API returns only the current one, so this row fires on the offline
      # reader's view of a model rather than a session's -- keep it anyway, the
      # contract's field is a list and a future collector may fill it.
      # No behaviour hangs off which stamp wins — hard rule 6 forbids keying the
      # read on the version at all. The note exists so the fact reaches the
      # report, not so anything downstream branches on it.
      Decision.new(true, nil, "the model carries #{distinct.size} designPH version stamps: " \
                              "#{distinct.join(', ')}")
    end

    # Leading integer, or nil when there is not one. `"2.4.0 BETA PRO"` -> 2,
    # which is the intended answer: a beta of a 2.x release reads like a 2.x
    # release. `"3.0.1"` -> 3. `"unknown"` -> nil.
    def self.major(stamp)
      match = stamp.to_s.strip[/\A(\d+)/, 1]
      match && match.to_i
    end

    # Name the stamp. A refusal that does not say what it saw sends the user to
    # us to find out, and the stamp is the one fact that decides it.
    def self.unsupported_text(stamps)
      described = stamps.map do |stamp|
        found = major(stamp)
        why = if found.nil?
                "not a version this reader recognises"
              elsif found > SUPPORTED_MAJOR
                "newer than this reader"
              else
                "older than this reader supports"
              end
        "  #{stamp.inspect} — #{why}"
      end
      "This model reports a designPH version DesignPH-PLUS cannot read:\n\n" \
      "#{described.join("\n")}\n\n" \
      "This reader understands designPH #{SUPPORTED_MAJOR}.x. Nothing was read and nothing " \
      "was written."
    end

    # What the walk found that says "designPH". Human-readable because it goes
    # straight into a note the user reads -- "proceeding on 194 tagged faces,
    # 99 tagged edges" is a defensible reason to translate a model with no
    # stamp; a boolean is not.
    def self.evidence(extraction)
      model = extraction["model"] || {}
      counts = extraction["counts"] || {}
      found = []
      found << "#{counts['faces_tagged']} tagged faces" if counts["faces_tagged"].to_i > 0
      found << "#{counts['edges_tagged']} tagged edges" if counts["edges_tagged"].to_i > 0
      found << "#{counts['windows_found']} designPH windows" if counts["windows_found"].to_i > 0
      tables = Array(counts["tables_found"])
      found << "#{tables.size} designPH table(s)" unless tables.empty?
      found << "a designPH climate id" unless model["klima_id"].to_s.strip.empty?
      found
    end

    # -------------------------------------------------------------------
    # Payload size
    # -------------------------------------------------------------------

    # `breakdown` is `{section => bytes}` and is only ever used in the refusal,
    # so the caller passes a **block** instead and it is never computed on the
    # ordinary path -- it re-serialises every section. It is what turns "too
    # big" into something actionable: on the defect that made this rule earn its
    # keep, the answer was 92 % `windows` (duplicated libraries), which is a bug
    # report, not a modelling instruction.
    def self.payload(bytes, breakdown = nil)
      if bytes > MAX_PAYLOAD_BYTES
        sections = breakdown || (block_given? ? yield : {})
        return Decision.new(false, oversize_text(bytes, sections), nil)
      end
      return ALLOWED unless bytes > LOG_PAYLOAD_BYTES
      Decision.new(true, nil, "extraction payload is #{bytes} bytes " \
                              "(over the #{LOG_PAYLOAD_BYTES}-byte notice threshold)")
    end

    def self.oversize_text(bytes, breakdown)
      largest = breakdown.sort_by { |_, size| -size }.first(4).map do |section, size|
        format("  %-12s %8.2f MB  (%d%%)", section, size / 1_048_576.0,
               bytes.zero? ? 0 : (size * 100.0 / bytes).round)
      end
      "This model's extraction is #{format('%.2f', bytes / 1_048_576.0)} MB, over the " \
      "#{MAX_PAYLOAD_BYTES / 1_000_000} MB limit for one export.\n\n" \
      "#{largest.join("\n")}\n\n" \
      "The whole corpus this was measured against extracts to 0.3–0.5 MB, so a payload this " \
      "size is more likely a defect in the reader than a large model. Please report it with " \
      "the numbers above. Nothing was written."
    end

    # Per-top-level-section byte sizes, for the refusal message. Serialises each
    # section a second time, which is why it is only called once the cheap size
    # test has already decided to refuse.
    def self.breakdown(extraction)
      extraction.each_with_object({}) do |(key, value), sizes|
        sizes[key] = JSON.generate(value).bytesize
      end
    rescue StandardError
      {}
    end
  end
end
