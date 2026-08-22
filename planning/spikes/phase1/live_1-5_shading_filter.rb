# Phase 1 section 1.5 -- data for the untagged-face filter (which untagged faces are shading
# geometry, and which are interior clutter that must never become shading).
#
# Paste into the SketchUp Ruby Console with a COPY of a corpus model open. Read-only.
#
# The offline run found `faceTypeAuto` splits Adelphi's 1359 untagged faces into
# 'xo' x420, 'i' x405, 'xi' x19 and nil x515 -- but it is EMPTY on two of the seven real project
# models, so it cannot be the whole filter. This gathers the geometric evidence the offline reader
# cannot see: whether the face sits inside the tagged envelope, its tag, and its nesting depth.
#
# NOTE the transformation carried through the walk. A face inside a group or component reports
# `bounds` in its own local coordinates, so testing those against a model-space envelope would
# place nested geometry arbitrarily. Every corpus model nests, so this is not a corner case.

# ---------------------------------------------------------------------------------------------
# Output goes to BOTH the Ruby Console and a file, so the results do not have to be copied out
# of the console by hand. Change OUT_DIR if the repo is not at this path.
# ---------------------------------------------------------------------------------------------
# Guarded so the file can be re-`load`ed without Ruby warning about a redefined constant.
unless defined?(OUT_DIR)
  OUT_DIR = File.join(Dir.home, "Desktop", "dph_plus_testing", "planning", "RESULTS", "phase1_live")
end

module BTPhase1Shading

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
  UNTAGGED = ["n", nil]
  IN2_TO_M2 = 0.00064516
  IN_TO_M   = 0.0254

  # => [[face, model_space_bounds, depth, xform], ...]
  def self.walk(entities, xform, depth, out)
    entities.each do |e|
      case e
      when Sketchup::Face
        bounds = Geom::BoundingBox.new
        e.vertices.each { |v| bounds.add(v.position.transform(xform)) }
        out << [e, bounds, depth, xform]
      when Sketchup::Group
        walk(e.entities, xform * e.transformation, depth + 1, out)
      when Sketchup::ComponentInstance
        walk(e.definition.entities, xform * e.transformation, depth + 1, out)
      end
    end
    out
  end

  def self.area_group(face)
    face.get_attribute("DesignPH_dict", "areaGroupID") ||
      face.get_attribute("DesignPH_dict", "areaGroupAuto")
  end

  def self.report
    model = Sketchup.active_model
    # Dedupe by entityID: a component definition's faces are the same entities on every instance.
    # This keeps the first placement's transform, which is enough for a bucketing heuristic but
    # means a component placed in two very different spots is judged only at the first.
    faces = walk(model.entities, Geom::Transformation.new, 0, []).uniq { |f, _, _, _| f.entityID }
    emit "live faces: #{faces.size}"

    tagged, untagged = faces.partition { |face, _, _, _| !UNTAGGED.include?(area_group(face)) }
    emit "tagged=#{tagged.size} untagged=#{untagged.size}"
    if tagged.empty?
      emit "no tagged faces -- cannot compute an envelope bounding box"
      return
    end

    envelope = Geom::BoundingBox.new
    tagged.each { |_, bounds, _, _| envelope.add(bounds) }
    emit format("envelope bbox: %.1f x %.1f x %.1f m",
                envelope.width * IN_TO_M, envelope.depth * IN_TO_M, envelope.height * IN_TO_M)

    buckets = Hash.new(0)
    untagged.each do |face, bounds, depth, _|
      key = [face.get_attribute("DesignPH_dict", "faceTypeAuto"),
             envelope.contains?(bounds.center),
             depth > 0,
             face.layer.name]
      buckets[key] += 1
    end

    emit "\nuntagged faces by (faceTypeAuto, centre inside envelope, nested, tag):"
    buckets.sort_by { |_, n| -n }.first(30).each do |(ftype, inside, nested, tag), n|
      emit format("  %6d  faceType=%-5s inside=%-5s nested=%-5s tag=%s",
                  n, ftype.inspect, inside, nested, tag)
    end

    # 'xi' is the last undecoded face-level value: 25 faces corpus-wide, always on an untagged
    # face. Print enough to go and look at them in the model.
    xi = untagged.select { |f, _, _, _| f.get_attribute("DesignPH_dict", "faceTypeAuto") == "xi" }
    emit "\n'xi' faces: #{xi.size}"
    xi.first(10).each do |face, bounds, depth, xform|
      # Model-space normal. Groups here are rigid, so transforming the vector directly is right;
      # it would need the inverse-transpose only under non-uniform scale.
      n = face.normal.transform(xform).normalize
      emit format("  id=%-8d depth=%d area=%.2f m2 normal=(%.2f,%.2f,%.2f) inside=%-5s tag=%s",
                  face.entityID, depth, face.area * IN2_TO_M2, n.x, n.y, n.z,
                  envelope.contains?(bounds.center), face.layer.name)
    end
  end
end

BTPhase1Shading.reset
BTPhase1Shading.report
BTPhase1Shading.write_out('1-5_shading_filter.txt')
