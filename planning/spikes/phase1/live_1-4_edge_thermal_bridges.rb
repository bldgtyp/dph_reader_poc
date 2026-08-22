# Phase 1 section 1.4 follow-up -- confirm that thermal bridges live on EDGES, not faces.
#
# Paste into the SketchUp Ruby Console with a COPY of a corpus model open. Read-only.
#
# Why: run 3a walked faces only and found 194 carrying `areaGroupID` on Bluff Reach, where the
# offline reader counts 293 records. The 99-record gap is exactly that model's thermal-bridge
# count (PHPP area groups 15, 16, 17), and exactly the gap in `assemblyID` too (153 -> 54).
# Thermal bridges are entered in PHPP as *lengths*, so an edge is the natural carrier -- and the
# 99 records never carry the cached `Material`/`BackMaterial` that designPH writes when it
# repaints a face.
#
# EXPECTED: edges carry `DesignPH_dict`, their area groups are 15/16/17, and
# edges_with_dict + faces_with_dict accounts for the offline record count.
#
# THIS MATTERS: a translator that walks only faces loses every thermal bridge, silently.

# Guarded so the file can be re-`load`ed without Ruby warning about a redefined constant.
unless defined?(OUT_DIR)
  OUT_DIR = File.join(Dir.home, "Desktop", "dph_plus_testing", "planning", "RESULTS", "phase1_live")
end

module BTPhase1Edges
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
    File.open(path, "w") do |f|
      f.puts("model: #{Sketchup.active_model.path}")
      f.puts(@lines)
    end
    puts "\n--- written to: #{path}"
  end

  # Collect every entity type that carries a DesignPH_dict, not just the two we expect --
  # assuming the answer is the way this got missed the first time.
  def self.walk(entities, out)
    entities.each do |e|
      out << e unless e.attribute_dictionary("DesignPH_dict").nil?
      case e
      when Sketchup::Group             then walk(e.entities, out)
      when Sketchup::ComponentInstance then walk(e.definition.entities, out)
      end
    end
    out
  end

  def self.report
    carriers = walk(Sketchup.active_model.entities, []).uniq { |e| e.entityID }
    emit "entities carrying DesignPH_dict: #{carriers.size}"

    by_class = Hash.new(0)
    carriers.each { |e| by_class[e.class.name] += 1 }
    emit "\nby entity class:"
    by_class.sort_by { |_, n| -n }.each { |cls, n| emit format("  %6d  %s", n, cls) }

    edges = carriers.grep(Sketchup::Edge)
    emit "\nedges carrying DesignPH_dict: #{edges.size}"
    return if edges.empty?

    groups = Hash.new(0)
    keys   = Hash.new(0)
    edges.each do |e|
      g = e.get_attribute("DesignPH_dict", "areaGroupID") ||
          e.get_attribute("DesignPH_dict", "areaGroupAuto")
      groups[g] += 1
      keys[e.attribute_dictionary("DesignPH_dict").keys.sort.join(", ")] += 1
    end

    emit "\nedge area groups (15/16/17 are PHPP's thermal-bridge groups):"
    groups.sort_by { |_, n| -n }.each { |g, n| emit format("  %6d  areaGroup=%s", n, g.inspect) }

    emit "\nedge key shapes:"
    keys.sort_by { |_, n| -n }.each { |shape, n| emit format("  %6d  %s", n, shape) }

    emit "\nfirst 5 edges in full:"
    edges.first(5).each do |e|
      emit "  edge #{e.entityID} length=#{(e.length * 0.0254).round(3)} m"
      e.attribute_dictionary("DesignPH_dict").each_pair do |k, v|
        emit format("      %-18s %-10s %s", k, v.class.name, v.inspect)
      end
    end
  end
end

BTPhase1Edges.reset
BTPhase1Edges.report
BTPhase1Edges.write_out('1-4_edge_thermal_bridges.txt')
