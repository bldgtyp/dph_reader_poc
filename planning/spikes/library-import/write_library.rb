# write_library.rb — POC #3 Spike L-A, route A-1. PASTE into the SketchUp Ruby Console.
#
# Writes ONE assembly (+ its layer table), ONE frame and ONE glazing into the OPEN model's
# model-level `DesignPH_dict`, using designPH's own serialisation exactly: base64 of
# `Marshal.dump` of the self-describing :TOKENS table, written back onto the same key.
# ⚠ designPH mixes TWO base64 styles, sometimes within one model (Linde 2.2.29: frames_ud
# and glazing_ud newline-wrapped, assemblies_calc strict) — so each write matches the style
# the key already carries, and new keys get strict. Model-level keys ONLY — this script
# never touches a face, edge or window dictionary (POC #3's scoped amendment to hard rule 2).
#
# SAFETY, in order:
#   1. Runs only on a model whose TITLE contains "LIBIMPORT" — the spike's staged copies
#      (planning/spikes/library-import/prep_copies.py names them). A positive question about
#      the file, per the Model#path lesson; the residue (the printed path) is Ed's to check.
#   2. Refuses a designPH 3.x version stamp by name, same posture as the POC-1 gate.
#   3. DRY-RUN on paste. Nothing is written until you run:   DPHL.write!
#   4. Every write happens inside one undoable operation (Edit > Undo reverts all of it).
#
# Usage (Ruby Console):
#   paste this file            -> prints the dry-run plan for the open model
#   DPHL.write!                -> native-generation write (what the model already carries)
#   DPHL.write!(:both)         -> O-3: also write the OTHER assembly-table generation
#   DPHL.write!(:create)       -> also CREATE frames_ud/glazing_ud when absent (Adelphi probe)
#   DPHL.write!(:both, :create)
#
# After a successful write: File > Save As per the runbook
# (planning/03_library-import/RESULTS/LIBRARY-A_ed-runbook.md), then quit. Never overwrite
# the staged copy itself — the pristine copy is the diff baseline.
#
# Ruby 2.7 (SketchUp 2022). Syntax-checked with `ruby -c`.

require "base64"

module DPHL
  DICT     = "DesignPH_dict".freeze
  OUR_DICT = "DesignPHPlus_dict".freeze # provenance note only — our own namespace
  MARKER   = "ZZ-LIBIMPORT".freeze      # unmistakable in any designPH list, sorts last

  # ---- the payload: realistic PH values, every one hand-checkable -------------------------
  # Assembly build-up (SI: lambda W/mK, thickness mm; films R m2K/W):
  #   1  Gypsum board        0.250 W/mK   12.5 mm   R 0.0500
  #   2  Mineral wool        0.035 W/mK  300.0 mm   R 8.5714
  #   3  Wood fibreboard     0.130 W/mK   15.0 mm   R 0.1154
  #   films R_in 0.13 + R_out 0.04 (wall, horizontal flow)
  #   => U = 1 / 8.9068 = 0.1123 W/m2K   <- what designPH's own calculator must show (O-2)
  ASSEMBLY_DESC = "#{MARKER} Wall".freeze
  R_IN, R_OUT = 0.13, 0.04
  LAYERS = [
    ["#{MARKER} Gypsum",     0.25,  12.5],
    ["#{MARKER} MinWool",    0.035, 300.0],
    ["#{MARKER} FibreBoard", 0.13,  15.0],
  ].freeze
  FRAME_DESC   = "#{MARKER} Frame".freeze
  FRAME_U      = 1.1      # W/m2K, all four edges
  FRAME_WIDTH  = 0.115    # m, all four edges
  PSI_GLAZING  = 0.031    # W/mK, psi_G* (glazing edge)
  PSI_INSTALL  = 0.041    # W/mK, psi_F* (installation)
  CHI_GT       = 0.0
  GLAZING_DESC = "#{MARKER} Glazing".freeze
  GLAZING_G    = 0.52
  GLAZING_U    = 0.62     # W/m2K

  # Canonical :TOKENS, used only when a table must be CREATED (:create) — a model that already
  # carries a table keeps its own schema (rule in force: emit the schema the model carries).
  TOKENS_CALC    = [:id, :desc, :R_in, :R_out, :surf2_percentage, :surf3_percentage,
                    :additional_U_value, :int_insul].freeze
  TOKENS_UD      = [:id, :desc, :assem_num, :thk, :U_value, :int_insul].freeze
  TOKENS_LAYER   = [:id, :desc1, :lambda1, :desc2, :lambda2, :desc3, :lambda3, :thickness].freeze
  TOKENS_FRAME   = [:id, :desc, :U_FL, :U_FR, :U_FB, :U_FT, :width_L, :width_R, :width_B,
                    :width_T, :psi_GL, :psi_GR, :psi_GB, :psi_GT, :psi_FL, :psi_FR, :psi_FB,
                    :psi_FT, :chi_GT].freeze
  TOKENS_GLAZING = [:id, :desc, :g_value, :U_value].freeze

  class << self
    def model
      Sketchup.active_model
    end

    # -- serialisation: designPH's own convention, exactly --------------------------------
    def read_table(key)
      raw = model.get_attribute(DICT, key)
      return nil unless raw.is_a?(String) && raw.start_with?("BAh")
      # Marshal.load instantiates what the blob names. Acceptable here and only here: these
      # are BLDGTYP's own staged copies (guard below), and no corpus table has ever carried
      # a custom class. Offline / unknown-origin reads use the construct-nothing Python reader.
      Marshal.load(Base64.decode64(raw))
    end

    def write_table(key, rows)
      # Match the base64 style the key already carries (designPH mixes both; decode64 reads
      # either, but O-6 diffs are cleaner when we do not churn the style). New keys: strict.
      existing = model.get_attribute(DICT, key)
      wrapped = existing.is_a?(String) && existing.include?("\n")
      encoded = wrapped ? Base64.encode64(Marshal.dump(rows)) : Base64.strict_encode64(Marshal.dump(rows))
      model.set_attribute(DICT, key, encoded)
    end

    # -- guards ---------------------------------------------------------------------------
    def guard!
      title = model.title.to_s
      unless title.include?("LIBIMPORT")
        raise "REFUSED: model title #{title.inspect} lacks 'LIBIMPORT' — open a staged spike " \
              "copy (prep_copies.py), never a working model. Path: #{model.path.inspect}"
      end
      stamp = model.get_attribute(DICT, "designPH_version")
      if stamp.to_s =~ /^3\./
        raise "REFUSED: designPH #{stamp} model — 3.x is out of scope by name (POC-1 gate posture)"
      end
      stamp
    end

    # -- table helpers --------------------------------------------------------------------
    def data_rows(table)
      table.select { |r| r.is_a?(Array) && r[0].to_s != "#" }
    end

    def tokens_of(table)
      meta = table.find { |r| r.is_a?(Array) && r[0].to_s == "#" && r[1].to_s == "TOKENS" }
      meta ? meta[2] : nil
    end

    # First data row whose id is NNud within lo..hi and whose desc is blank.
    def free_slot(table, lo, hi)
      data_rows(table).find do |r|
        r[0].to_s =~ /\A(\d+)ud\z/ && Regexp.last_match(1).to_i.between?(lo, hi) &&
          r[1].to_s.strip.empty?
      end
    end

    def deep_copy(obj)
      Marshal.load(Marshal.dump(obj))
    end

    def intended_u
      1.0 / (R_IN + R_OUT + LAYERS.map { |_, lam, thk| (thk / 1000.0) / lam }.reduce(:+))
    end

    # -- the four writes (each edits a deep copy in memory; commit happens in write!) -----

    # assemblies_calc: fill the first blank user slot; create/replace layer_table_<id>.
    def plan_calc(actions, creating)
      table = read_table("assemblies_calc")
      if table.nil?
        return unless creating
        table = [["#", :TYPE, :TABLE], ["#", :ROW_DATA, :ARRAY], ["#", :TOKENS, TOKENS_CALC.dup]]
        82.times { |i| table << [format("%02dud", i + 1), "", 0.0, 0.0, 0.0, 0.0, 0.0, false] }
        actions << [:note, "assemblies_calc is ABSENT — creating it (99-row pre-allocation " \
                           "mimicked at 82, designPH's own shape)"]
      end
      table = deep_copy(table)
      slot = free_slot(table, 1, 82)
      raise "assemblies_calc: no blank user slot in 01ud..82ud" unless slot
      id = slot[0].to_s
      slot[1] = ASSEMBLY_DESC
      slot[2], slot[3] = R_IN, R_OUT
      slot[4] = slot[5] = slot[6] = 0.0
      slot[7] = false
      actions << [:write, "assemblies_calc", table,
                  "fill #{id}: #{ASSEMBLY_DESC.inspect} R_in=#{R_IN} R_out=#{R_OUT}"]
      plan_layer_table(actions, id)
      id
    end

    def plan_layer_table(actions, id)
      donor_key = model.attribute_dictionary(DICT) &&
                  model.attribute_dictionary(DICT).keys.sort.find { |k| k =~ /\Alayer_table_\d+ud\z/ }
      table =
        if donor_key
          t = deep_copy(read_table(donor_key))
          # blank every data row, keep the donor's schema and row count
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
      LAYERS.each_with_index do |(desc, lam, thk), i|
        row = data_rows(table)[i]
        raise "layer table has fewer than #{i + 1} rows" unless row
        row[1], row[2] = desc, lam           # desc1, lambda1 (single-path build-up)
        row[3], row[4], row[5], row[6] = "", 0.0, "", 0.0
        row[7] = thk                         # thickness, mm
        if width >= 12                       # Linde-shape extras: R1 R2 R3 R_tot — UNTESTED leg,
          r1 = (thk / 1000.0) / lam          # values kept consistent with the 8-col columns
          row[8], row[9], row[10], row[11] = r1, 0.0, 0.0, r1
        end
      end
      actions << [:write, "layer_table_#{id}", table,
                  "#{donor_key ? "cloned #{donor_key} schema" : 'canonical 8-col schema'}, " \
                  "#{LAYERS.length} layers -> intended U #{format('%.4f', intended_u)} W/m2K"]
    end

    # assemblies_ud (older generation): INSERT a new row — observed models hold only 83ud..99ud.
    def plan_ud(actions, creating)
      table = read_table("assemblies_ud")
      if table.nil?
        return unless creating
        table = [["#", :TYPE, :TABLE], ["#", :ROW_DATA, :ARRAY], ["#", :TOKENS, TOKENS_UD.dup]]
        actions << [:note, "assemblies_ud is ABSENT — creating header-only table"]
      end
      table = deep_copy(table)
      used = data_rows(table).map { |r| r[0].to_s[/\A(\d+)ud\z/, 1] }.compact.map(&:to_i)
      n = (1..82).find { |i| !used.include?(i) }
      raise "assemblies_ud: no unused id in 01ud..82ud" unless n
      id = format("%02dud", n)
      thickness_m = LAYERS.map { |_, _, thk| thk }.reduce(:+) / 1000.0
      row = [id, ASSEMBLY_DESC, ASSEMBLY_DESC, thickness_m.round(4), intended_u.round(3), false]
      # insert keeping ascending numeric id order among data rows
      anchor = table.index { |r| r.is_a?(Array) && r[0].to_s[/\A(\d+)ud\z/, 1].to_i > n }
      anchor ? table.insert(anchor, row) : table.push(row)
      actions << [:write, "assemblies_ud", table,
                  "insert #{id}: #{ASSEMBLY_DESC.inspect} U=#{intended_u.round(3)} (direct-U schema)"]
      id
    end

    def plan_frame(actions, creating)
      plan_window_table(actions, "frames_ud", creating) do |slot|
        slot[1] = FRAME_DESC
        (2..5).each  { |i| slot[i] = FRAME_U }
        (6..9).each  { |i| slot[i] = FRAME_WIDTH }
        (10..13).each { |i| slot[i] = PSI_GLAZING }
        (14..17).each { |i| slot[i] = PSI_INSTALL }
        slot[18] = CHI_GT
        "#{FRAME_DESC.inspect} U=#{FRAME_U} width=#{FRAME_WIDTH} psiG=#{PSI_GLAZING} psiF=#{PSI_INSTALL}"
      end
    end

    def plan_glazing(actions, creating)
      plan_window_table(actions, "glazing_ud", creating) do |slot|
        slot[1] = GLAZING_DESC
        slot[2] = GLAZING_G
        slot[3] = GLAZING_U
        "#{GLAZING_DESC.inspect} g=#{GLAZING_G} U=#{GLAZING_U}"
      end
    end

    def plan_window_table(actions, key, creating)
      table = read_table(key)
      if table.nil?
        unless creating
          actions << [:note, "#{key} is ABSENT and :create not given — skipped"]
          return nil
        end
        tokens = key == "frames_ud" ? TOKENS_FRAME : TOKENS_GLAZING
        table = [["#", :TYPE, :TABLE], ["#", :ROW_DATA, :ARRAY], ["#", :TOKENS, tokens.dup]]
        99.times do |i|
          table << ([format("%02dud", i + 1), ""] + Array.new(tokens.length - 2, 0.0))
        end
        actions << [:note, "#{key} is ABSENT — creating it with designPH's 99-row pre-allocation"]
      end
      table = deep_copy(table)
      slot = free_slot(table, 1, 91) # 92ud+ hold shipped presets on observed models
      raise "#{key}: no blank slot in 01ud..91ud" unless slot
      detail = yield(slot)
      actions << [:write, key, table, "fill #{slot[0]}: #{detail}"]
      slot[0].to_s
    end

    # -- entry points ---------------------------------------------------------------------
    def plan(*flags)
      both     = flags.include?(:both)
      creating = flags.include?(:create)
      stamp = guard!
      actions = []
      has_calc = !read_table("assemblies_calc").nil?
      has_ud   = !read_table("assemblies_ud").nil?
      native = has_calc ? "assemblies_calc" : (has_ud ? "assemblies_ud" : "NEITHER")
      plan_calc(actions, both || (!has_calc && !has_ud)) if has_calc || both || (!has_calc && !has_ud)
      plan_ud(actions, both) if has_ud || both
      plan_frame(actions, creating)
      plan_glazing(actions, creating)
      puts "=" * 78
      puts "DPHL Spike L-A dry-run  —  #{model.title}"
      puts "  path:              #{model.path}"
      puts "  designPH_version:  #{stamp.inspect}"
      puts "  native generation: #{native}   (flags: #{flags.inspect})"
      puts "  intended assembly U-value: #{format('%.4f', intended_u)} W/m2K (incl. films)"
      actions.each do |kind, key, _rows, detail|
        puts kind == :note ? "  NOTE  #{key}" : "  WRITE #{key}  —  #{detail}"
      end
      puts "Nothing written yet. Run DPHL.write!#{flags.empty? ? '' : '(' + flags.map(&:inspect).join(', ') + ')'} to commit."
      puts "=" * 78
      actions
    end

    def write!(*flags)
      actions = plan(*flags)
      writes = actions.select { |a| a[0] == :write }
      raise "nothing to write" if writes.empty?
      model.start_operation("DPHL Spike L-A library write", true)
      begin
        writes.each { |_, key, rows, _| write_table(key, rows) }
        model.set_attribute(OUR_DICT, "spike", "L-A")
        model.set_attribute(OUR_DICT, "written_at", Time.now.utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
        model.set_attribute(OUR_DICT, "wrote_keys", writes.map { |_, k, _, _| k }.join(","))
        model.commit_operation
      rescue StandardError => error
        model.abort_operation
        raise error
      end
      puts "WROTE #{writes.length} key(s): #{writes.map { |_, k, _, _| k }.join(', ')}"
      verify(writes.map { |_, k, _, _| k })
      puts "Now: File > Save As per the runbook (never overwrite the staged copy), then quit."
      nil
    end

    # O-8: rename the imported assembly AND retune a layer, through the same write path — run
    # only AFTER it is assigned to a face. desc gains " R2"; MinWool lambda 0.035 -> 0.040, so
    # designPH's calculator must move 0.1123 -> 0.1276 W/m2K if the edit is actually read.
    REVISED_LAMBDA = 0.04

    def revise!
      guard!
      revised_u = 1.0 / (R_IN + R_OUT + 0.0125 / 0.25 + 0.300 / REVISED_LAMBDA + 0.015 / 0.13)
      wrote = []
      model.start_operation("DPHL Spike L-A revise", true)
      begin
        %w[assemblies_calc assemblies_ud].each do |key|
          table = read_table(key)
          next if table.nil?
          table = deep_copy(table)
          row = data_rows(table).find { |r| r[1].to_s.include?(MARKER) }
          next if row.nil?
          row[1] = "#{ASSEMBLY_DESC} R2"
          if key == "assemblies_ud"
            row[4] = revised_u.round(3) # direct-U schema: retune means a new U
          else
            layer_key = "layer_table_#{row[0]}"
            layers = read_table(layer_key)
            raise "#{layer_key} missing" if layers.nil?
            layers = deep_copy(layers)
            wool = data_rows(layers).find { |r| r[1].to_s.include?("MinWool") }
            raise "#{layer_key}: MinWool layer not found" if wool.nil?
            wool[2] = REVISED_LAMBDA
            wool[8] = wool[11] = (wool[7] / 1000.0) / REVISED_LAMBDA if wool.length >= 12 # R1, R_tot
            write_table(layer_key, layers)
            wrote << layer_key
          end
          write_table(key, table)
          wrote << key
        end
        raise "nothing to revise — run DPHL.write! first" if wrote.empty?
        model.set_attribute(OUR_DICT, "revised_at", Time.now.utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
        model.commit_operation
      rescue StandardError => error
        model.abort_operation
        raise error
      end
      puts "REVISED #{wrote.join(', ')} — desc now \"#{ASSEMBLY_DESC} R2\", MinWool lambda " \
           "#{REVISED_LAMBDA}, intended U now #{format('%.4f', revised_u)} W/m2K"
      verify(wrote)
      nil
    end

    # Read every written key back off the live model and show our rows — proof the write landed.
    def verify(keys)
      keys.each do |key|
        table = read_table(key)
        if table.nil?
          puts "  VERIFY #{key}: MISSING AFTER WRITE (!)"
          next
        end
        ours = data_rows(table).select { |r| r.any? { |v| v.to_s.include?(MARKER) } }
        puts "  VERIFY #{key}: #{ours.length} marker row(s)"
        ours.each { |r| puts "    #{r.inspect}" }
      end
      nil
    end
  end
end

DPHL.plan
