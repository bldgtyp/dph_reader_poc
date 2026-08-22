# Phase 1 section 1.1 -- confirm the `*ID` / `*Auto` reading against LIVE entities.
#
# Paste into the SketchUp Ruby Console with a COPY of a corpus model open.
# Read-only: this never writes to DesignPH_dict.
#
# Why this is still needed after the offline analysis: `model.dat` accumulates historical state,
# so the offline reader sees dictionaries that may belong to deleted entities. This walks live
# faces only. The offline run found, across 14 models, that `*ID` and `*Auto` are never both
# populated on one face -- so the read rule is a coalesce, not a precedence. Confirm that here.
#
# EXPECTED, if the offline finding holds: every `both` count is 0.
# If any `both` count is non-zero, the precedence question is real and section 1.1 is not settled.

# ---------------------------------------------------------------------------------------------
# Output goes to BOTH the Ruby Console and a file, so the results do not have to be copied out
# of the console by hand. Change OUT_DIR if the repo is not at this path.
# ---------------------------------------------------------------------------------------------
# Guarded so the file can be re-`load`ed without Ruby warning about a redefined constant.
unless defined?(OUT_DIR)
  OUT_DIR = File.join(Dir.home, "Desktop", "dph_plus_testing", "planning", "RESULTS", "phase1_live")
end

module BTPhase1

  # Collect as well as print, so the whole report can be written out in one piece.
  # `reset` matters: the module outlives one run, so a second run would otherwise append
  # to the first run's output and the written file would hold both.
  def self.reset
    @lines = []
  end

  def self.emit(line = "")
    @lines ||= []
    @lines << line
    puts line
  end

  def self.write_out(name)
    require "fileutils"
    FileUtils.mkdir_p(OUT_DIR)
    # Stamp the model name into the file: run 2 is meant to be run on more than one model,
    # and the first version of this silently overwrote Adelphi's output with Bluff Reach's.
    model = File.basename(Sketchup.active_model.path.to_s, ".skp")
    model = "unsaved" if model.empty?
    path = File.join(OUT_DIR, "#{File.basename(name, '.txt')}__#{model}.txt")
    File.open(path, "w") { |f| f.puts(Sketchup.active_model.path) ; f.puts(@lines) }
    emit "\n--- written to: #{path}"
  end
  PAIRS = [
    ["areaGroupID", "areaGroupAuto"],
    ["tempZoneID",  "tempZoneAuto"],
    ["assemblyID",  "assemblyIDAuto"]
  ]

  def self.faces(entities, out = [])
    entities.each do |e|
      case e
      when Sketchup::Face
        out << e
      when Sketchup::Group
        faces(e.entities, out)
      when Sketchup::ComponentInstance
        faces(e.definition.entities, out)
      end
    end
    out
  end

  def self.report
    # Dedupe by entityID: a component definition's faces are the same entities on every
    # instance, so a twice-placed component would otherwise count its faces twice.
    all = faces(Sketchup.active_model.entities).uniq { |f| f.entityID }
    emit "live faces: #{all.size}"

    PAIRS.each do |id_key, auto_key|
      counts = Hash.new(0)
      values = Hash.new(0)
      all.each do |f|
        id_v   = f.get_attribute("DesignPH_dict", id_key)
        auto_v = f.get_attribute("DesignPH_dict", auto_key)
        if !id_v.nil? && !auto_v.nil?
          counts[:both] += 1
          values[[id_v, auto_v]] += 1
        elsif !id_v.nil?
          counts[:id_only] += 1
        elsif !auto_v.nil?
          counts[:auto_only] += 1
        else
          counts[:neither] += 1
        end
      end
      emit format("%-14s id_only=%-5d auto_only=%-5d both=%-5d neither=%-5d",
                  id_key, counts[:id_only], counts[:auto_only],
                  counts[:both], counts[:neither])
      values.sort_by { |_, n| -n }.first(5).each do |(id_v, auto_v), n|
        emit "    both: #{id_key}=#{id_v.inspect} #{auto_key}=#{auto_v.inspect}  (#{n})"
      end
    end
  end

  # Dump one face in full. Select a face, then: BTPhase1.dump_selected
  # Run this BEFORE and AFTER changing the face's area group in the designPH UI --
  # the diff is what says which key designPH actually writes.
  def self.dump_selected
    sel = Sketchup.active_model.selection.grep(Sketchup::Face)
    if sel.empty?
      emit "select a face first"
      return
    end
    sel.each do |f|
      dict = f.attribute_dictionary("DesignPH_dict")
      emit "face #{f.entityID} area=#{(f.area * 0.00064516).round(3)} m2"
      if dict.nil?
        emit "    (no DesignPH_dict -- note: this returns nil, never an empty collection)"
      else
        dict.each_pair { |k, v| puts format("    %-18s %-10s %s", k, v.class.name, v.inspect) }
      end
    end
  end
end

BTPhase1.reset
BTPhase1.report
BTPhase1.write_out('1-1_generation_check.txt')
