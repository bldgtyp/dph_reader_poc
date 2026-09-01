# write_library_b.rb — POC #3 Spike L-B. PASTE into the SketchUp Ruby Console.
#
# The data-driven successor to L-A's write_library.rb: reads the PHN-mapped payload
# (`_private/payload/lb_payload.json`, produced by map_phn.py) and writes EVERY assembly
# (+ its layer table), frame and glazing in it into the OPEN model's model-level
# `DesignPH_dict`, using designPH's own serialisation exactly (L-A's accepted recipe,
# `00_Context/DESIGNPH_DATA_MODEL.md` §14.2): match each key's base64 style, emit the schema
# the model's own tables carry, fill-next-blank-slot ids, never touch an entity dictionary
# or a DC option list.
#
# SAFETY — identical posture to L-A:
#   1. Runs only on a model whose TITLE contains "LIBIMPORT" (staged copies from
#      prep_copies_b.py). The printed path is Ed's residue to check.
#   2. Refuses a designPH 3.x version stamp by name.
#   3. DRY-RUN on paste. Nothing is written until:   DPHLB.write!
#   4. One undoable operation.
#
# Usage (Ruby Console):
#   paste this file        -> dry-run plan for the open model
#   DPHLB.write!           -> write the full payload (assemblies + frames + glazings)
#   DPHLB.write!(:probe)   -> ⚠ ONLY on the dedicated `-xc` copy: additionally append a
#                             foreign `phn_id` COLUMN to assemblies_calc (extra token + one
#                             extra cell per row). This deliberately violates "emit the schema
#                             the model carries" — it is the update-key probe: does designPH
#                             still read the table, and does the column survive its save?
#
# After a successful write: File > Save As per the L-B runbook, then quit. Never overwrite
# the staged copy — the pristine copy is the diff baseline.
#
# Ruby 2.7 (SketchUp 2022). Syntax-checked with `ruby -c`.

require "base64"
require "json"

module DPHLB
  DICT     = "DesignPH_dict".freeze
  OUR_DICT = "DesignPHPlus_dict".freeze

  # Absolute path — the console has no __FILE__ for a paste. Ed: adjust if the repo moved.
  PAYLOAD = File.expand_path(
    "~/Dropbox/bldgtyp-00/00_PH_Tools/dph_reader_poc/planning/spikes/library-import/" \
    "_private/payload/lb_payload.json"
  ).freeze

  TOKENS_CALC    = [:id, :desc, :R_in, :R_out, :surf2_percentage, :surf3_percentage,
                    :additional_U_value, :int_insul].freeze
  TOKENS_LAYER   = [:id, :desc1, :lambda1, :desc2, :lambda2, :desc3, :lambda3, :thickness].freeze
  TOKENS_FRAME   = [:id, :desc, :U_FL, :U_FR, :U_FB, :U_FT, :width_L, :width_R, :width_B,
                    :width_T, :psi_GL, :psi_GR, :psi_GB, :psi_GT, :psi_FL, :psi_FR, :psi_FB,
                    :psi_FT, :chi_GT].freeze
  TOKENS_GLAZING = [:id, :desc, :g_value, :U_value].freeze

  FRAME_FIELDS = %w[
    U_FL U_FR U_FB U_FT width_L width_R width_B width_T
    psi_GL psi_GR psi_GB psi_GT psi_FL psi_FR psi_FB psi_FT chi_GT
  ].freeze

  class << self
    def model
      Sketchup.active_model
    end

    def payload
      @payload ||= JSON.parse(File.read(PAYLOAD))
    end

    # -- serialisation: L-A's accepted recipe, verbatim -----------------------------------
    def read_table(key)
      raw = model.get_attribute(DICT, key)
      return nil unless raw.is_a?(String) && raw.start_with?("BAh")
      Marshal.load(Base64.decode64(raw))
    end

    def write_table(key, rows)
      existing = model.get_attribute(DICT, key)
      wrapped = existing.is_a?(String) && existing.include?("\n")
      encoded = wrapped ? Base64.encode64(Marshal.dump(rows)) : Base64.strict_encode64(Marshal.dump(rows))
      model.set_attribute(DICT, key, encoded)
    end

    def guard!
      title = model.title.to_s
      unless title.include?("LIBIMPORT")
        raise "REFUSED: model title #{title.inspect} lacks 'LIBIMPORT' — open a staged spike " \
              "copy (prep_copies_b.py), never a working model. Path: #{model.path.inspect}"
      end
      stamp = model.get_attribute(DICT, "designPH_version")
      if stamp.to_s =~ /^3\./
        raise "REFUSED: designPH #{stamp} model — 3.x is out of scope by name"
      end
      stamp
    end

    def data_rows(table)
      table.select { |r| r.is_a?(Array) && r[0].to_s != "#" }
    end

    def tokens_of(table)
      meta = table.find { |r| r.is_a?(Array) && r[0].to_s == "#" && r[1].to_s == "TOKENS" }
      meta ? meta[2] : nil
    end

    def free_slots(table, lo, hi)
      data_rows(table).select do |r|
        r[0].to_s =~ /\A(\d+)ud\z/ && Regexp.last_match(1).to_i.between?(lo, hi) &&
          r[1].to_s.strip.empty?
      end
    end

    def deep_copy(obj)
      Marshal.load(Marshal.dump(obj))
    end

    # -- planning -------------------------------------------------------------------------

    # assemblies_calc: one blank slot per payload assembly; a layer table per slot.
    # Hard rule 4: too few slots is a REFUSAL, not a partial write.
    def plan_assemblies(actions)
      table = read_table("assemblies_calc")
      if table.nil?
        table = [["#", :TYPE, :TABLE], ["#", :ROW_DATA, :ARRAY], ["#", :TOKENS, TOKENS_CALC.dup]]
        82.times { |i| table << [format("%02dud", i + 1), "", 0.0, 0.0, 0.0, 0.0, 0.0, false] }
        actions << [:note, "assemblies_calc ABSENT — creating (82-row pre-allocation)"]
      end
      table = deep_copy(table)
      wanted = payload.fetch("assemblies")
      slots = free_slots(table, 1, 82)
      if slots.length < wanted.length
        raise "assemblies_calc: #{wanted.length} assemblies but only #{slots.length} blank slots"
      end
      pairs = wanted.zip(slots.first(wanted.length))
      pairs.each do |asm, slot|
        slot[1] = asm.fetch("desc")
        slot[2] = asm.fetch("R_in")
        slot[3] = asm.fetch("R_out")
        slot[4] = asm.fetch("surf2_percentage")
        slot[5] = asm.fetch("surf3_percentage")
        slot[6] = asm.fetch("additional_U_value")
        slot[7] = asm.fetch("int_insul")
      end
      actions << [:write, "assemblies_calc", table,
                  pairs.map { |asm, slot| "#{slot[0]}=#{asm['desc'].inspect}" }.join(", ")]
      pairs.each { |asm, slot| plan_layer_table(actions, slot[0].to_s, asm) }
    end

    def plan_layer_table(actions, id, asm)
      donor_key = model.attribute_dictionary(DICT) &&
                  model.attribute_dictionary(DICT).keys.sort.find { |k| k =~ /\Alayer_table_\d+ud\z/ }
      table =
        if donor_key
          t = deep_copy(read_table(donor_key))
          width = (tokens_of(t) || TOKENS_LAYER).length
          data_rows(t).each do |r|
            (1...width).each { |i| r[i] = r[i].is_a?(String) ? "" : 0.0 }
          end
          t
        else
          t = [["#", :TYPE, :TABLE], ["#", :ROW_DATA, :ARRAY], ["#", :TOKENS, TOKENS_LAYER.dup]]
          8.times { |i| t << [i + 1, "", 0.0, "", 0.0, "", 0.0, 0.0] }
          t
        end
      width = (tokens_of(table) || TOKENS_LAYER).length
      layers = asm.fetch("layers")
      raise "#{asm['desc']}: #{layers.length} layers > #{data_rows(table).length} rows" if layers.length > data_rows(table).length
      layers.each_with_index do |layer, i|
        row = data_rows(table)[i]
        row[1] = layer.fetch("desc1")
        row[2] = layer.fetch("lambda1")
        row[3] = layer.fetch("desc2")
        row[4] = layer.fetch("lambda2")
        row[5] = layer.fetch("desc3")
        row[6] = layer.fetch("lambda3")
        row[7] = layer.fetch("thickness_mm")
        if width >= 12 # 12-col donor (Linde shape): R per path, lambda blank falls back to 1.
          thk_m = layer["thickness_mm"] / 1000.0
          l1 = layer["lambda1"]
          l2 = layer["lambda2"] > 0 ? layer["lambda2"] : l1
          l3 = layer["lambda3"] > 0 ? layer["lambda3"] : l1
          row[8], row[9], row[10] = thk_m / l1, thk_m / l2, thk_m / l3
          row[11] = row[8] # R_tot: observed equal to R1 on uniform rows; UNTESTED leg
        end
      end
      actions << [:write, "layer_table_#{id}", table,
                  "#{asm['desc'].inspect}: #{layers.length} layers " \
                  "(#{donor_key ? "cloned #{donor_key} schema" : 'canonical 8-col'}) " \
                  "-> intended U #{format('%.4f', asm['intended_u'])}"]
    end

    def plan_window_table(actions, key, entries, tokens, fields)
      table = read_table(key)
      if table.nil?
        table = [["#", :TYPE, :TABLE], ["#", :ROW_DATA, :ARRAY], ["#", :TOKENS, tokens.dup]]
        99.times { |i| table << ([format("%02dud", i + 1), ""] + Array.new(tokens.length - 2, 0.0)) }
        actions << [:note, "#{key} ABSENT — creating (99-row pre-allocation)"]
      end
      table = deep_copy(table)
      slots = free_slots(table, 1, 91) # 92ud+ hold shipped presets on observed models
      if slots.length < entries.length
        raise "#{key}: #{entries.length} entries but only #{slots.length} blank slots in 01ud..91ud"
      end
      entries.zip(slots.first(entries.length)).each do |entry, slot|
        slot[1] = entry.fetch("desc")
        fields.each_with_index { |field, i| slot[2 + i] = entry.fetch(field) }
      end
      actions << [:write, key, table,
                  entries.zip(slots).map { |e, s| "#{s[0]}=#{e['desc'].inspect}" }.join(", ")]
    end

    # ⚠ :probe only, `-xc` copy only — the update-key probe (foreign extra column).
    def plan_probe(actions)
      idx = actions.index { |a| a[0] == :write && a[1] == "assemblies_calc" }
      raise "probe: assemblies_calc write not planned" unless idx
      table = actions[idx][2]
      tokens = tokens_of(table)
      raise "probe: TOKENS row not found" unless tokens
      tokens << :phn_id
      by_desc = {}
      payload.fetch("assemblies").each { |a| by_desc[a["desc"]] = a["phn_id"] }
      data_rows(table).each { |r| r << (by_desc[r[1]] || "") }
      actions << [:note, "PROBE: appended :phn_id token + column to assemblies_calc " \
                         "(#{by_desc.length} rows carry a PHN id) — schema-tolerance test"]
    end

    # -- entry points ---------------------------------------------------------------------
    def plan(*flags)
      stamp = guard!
      actions = []
      plan_assemblies(actions)
      plan_window_table(actions, "frames_ud", payload.fetch("frames"), TOKENS_FRAME, FRAME_FIELDS)
      plan_window_table(actions, "glazing_ud", payload.fetch("glazings"), TOKENS_GLAZING,
                        %w[g_value U_value])
      plan_probe(actions) if flags.include?(:probe)
      puts "=" * 78
      puts "DPHLB Spike L-B dry-run  —  #{model.title}"
      puts "  path:             #{model.path}"
      puts "  designPH_version: #{stamp.inspect}"
      puts "  payload:          #{PAYLOAD}"
      puts "  #{payload['assemblies'].length} assemblies, #{payload['frames'].length} frames, " \
           "#{payload['glazings'].length} glazings (flags: #{flags.inspect})"
      actions.each do |kind, key, _rows, detail|
        puts kind == :note ? "  NOTE  #{key}" : "  WRITE #{key}  —  #{detail}"
      end
      puts "Nothing written yet. Run DPHLB.write!#{flags.empty? ? '' : '(:probe)'} to commit."
      puts "=" * 78
      actions
    end

    def write!(*flags)
      actions = plan(*flags)
      writes = actions.select { |a| a[0] == :write }
      raise "nothing to write" if writes.empty?
      model.start_operation("DPHLB Spike L-B library write", true)
      begin
        writes.each { |_, key, rows, _| write_table(key, rows) }
        model.set_attribute(OUR_DICT, "spike", "L-B")
        model.set_attribute(OUR_DICT, "written_at", Time.now.utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
        model.set_attribute(OUR_DICT, "wrote_keys", writes.map { |_, k, _, _| k }.join(","))
        model.set_attribute(OUR_DICT, "phn_version_etag", payload["source"]["version_etag"])
        model.commit_operation
      rescue StandardError => error
        model.abort_operation
        raise error
      end
      puts "WROTE #{writes.length} key(s): #{writes.map { |_, k, _, _| k }.join(', ')}"
      verify(writes.map { |_, k, _, _| k })
      puts "Now: File > Save As per the L-B runbook (never overwrite the staged copy), then quit."
      nil
    end

    def verify(keys)
      marker = payload.fetch("marker")
      keys.each do |key|
        table = read_table(key)
        if table.nil?
          puts "  VERIFY #{key}: MISSING AFTER WRITE (!)"
          next
        end
        ours = data_rows(table).select { |r| r[1].to_s.start_with?(marker) }
        puts "  VERIFY #{key}: #{ours.length} marker row(s)"
        ours.first(2).each { |r| puts "    #{r.inspect}" }
      end
      nil
    end
  end
end

DPHLB.plan
