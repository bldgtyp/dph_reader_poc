# Phase 1 section 1.2 -- how designPH window components attach to their host face.
#
# Paste into the SketchUp Ruby Console with a COPY of a corpus model open. Read-only.
# Decides the aperture strategy in PRD section 8.2.

# ---------------------------------------------------------------------------------------------
# Output goes to BOTH the Ruby Console and a file, so the results do not have to be copied out
# of the console by hand. Change OUT_DIR if the repo is not at this path.
# ---------------------------------------------------------------------------------------------
# Guarded so the file can be re-`load`ed without Ruby warning about a redefined constant.
unless defined?(OUT_DIR)
  OUT_DIR = File.join(Dir.home, "Desktop", "dph_plus_testing", "planning", "RESULTS", "phase1_live")
end

module BTPhase1Windows

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
    File.open(path, "w") do |f|
      f.puts("model: #{Sketchup.active_model.path}")
      f.puts(@lines)
    end
    puts "\n--- written to: #{path}"
  end

  def self.find(entities, xform, out)
    entities.each do |e|
      case e
      when Sketchup::ComponentInstance
        if e.definition.name =~ /designPH_Window/i
          out << [e, xform * e.transformation]
        else
          find(e.definition.entities, xform * e.transformation, out)
        end
      when Sketchup::Group
        find(e.entities, xform * e.transformation, out)
      end
    end
    out
  end

  def self.report
    # Dedupe by entityID -- recursing through a twice-placed component would report the same
    # nested window instance twice.
    wins = find(Sketchup.active_model.entities, Geom::Transformation.new, []).uniq { |i, _| i.entityID }
    emit "windows found: #{wins.size}"
    return if wins.empty?

    glued = wins.count { |inst, _| !inst.glued_to.nil? }
    cuts  = wins.count { |inst, _| inst.definition.behavior.cuts_opening? }
    emit "glued_to non-nil: #{glued} / #{wins.size}"
    emit "cuts_opening?:    #{cuts} / #{wins.size}"

    emit "\nfirst 15:"
    wins.first(15).each do |inst, _|
      b = inst.definition.behavior
      host = inst.glued_to
      emit format("%-30s id=%-7d is2d=%-5s cuts=%-5s snapto=%-2s glued_to=%s",
                  inst.definition.name, inst.entityID,
                  b.is2d?, b.cuts_opening?, b.snapto,
                  host ? "#{host.class.name}##{host.entityID}" : "nil")
    end

    # A face with more than one loop has a hole cut in it. If host faces have inner loops the
    # Honeybee Face3D carries a hole and the Aperture must fill it -- PRD section 8.2 would
    # need revising. If they do not, windows sit on unbroken faces as specced.
    hosts = wins.map { |i, _| i.glued_to }.compact.uniq
    emit "\ndistinct host faces: #{hosts.size}"
    with_holes = hosts.count { |f| f.respond_to?(:loops) && f.loops.size > 1 }
    emit "hosts with inner loops (holes): #{with_holes} / #{hosts.size}"
    hosts.first(10).each do |f|
      next unless f.respond_to?(:loops)
      emit format("    face %-8d loops=%-3d area=%.2f m2", f.entityID, f.loops.size,
                  f.area * 0.00064516)
    end
  end
end

BTPhase1Windows.reset
BTPhase1Windows.report
BTPhase1Windows.write_out('1-2_window_hosting.txt')
