# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- look inside a designPH window component.
#
#     load "/Users/em/Desktop/dph_plus_testing/poc/ext/tests/inspect_window_console.rb"
#     DphWin.inspect_one           # the first designPH window in the model
#     DphWin.inspect_one("403U")   # a named one
#
# This answers contract question **W-1**, which the captured extraction could not:
#
#   * the collector derives `panel_outer_loop` from `definition.entities.grep(Sketchup::Face)`
#     and got **nothing on all 46 Adelphi windows** -- so the pane geometry is nested inside
#     sub-groups rather than sitting at the top level of the definition. This prints the whole
#     nesting so the recursion can be written against what is actually there.
#   * the fallback (`transform` x `lenx`/`leny`) is refuted: `lenx*leny*0.00064516` equals the
#     stored `area` on only **20 of 46** windows, and every instance transform is unscaled, so
#     scale does not explain the other 26.
#   * ⚠ and the contract ships `instance.transformation` **verbatim**, which is the instance's
#     transform relative to its PARENT -- while every other geometry field is world-space. This
#     prints both so the difference is visible rather than inferred.
#
# READ-ONLY. Nothing here writes to the model.
# ---------------------------------------------------------------------------
module DphWin

  DC = "dynamic_attributes".freeze
  IN_TO_M = 0.0254

  # Walk to find window instances, carrying the accumulated transform so the world position of
  # each one is known -- which is exactly what the collector currently fails to ship.
  def self.find(entities, transform, path, found)
    entities.each do |e|
      case e
      when Sketchup::ComponentInstance
        dc = e.attribute_dictionary(DC)
        if dc && dc["frametypeid"]
          found << [e, transform, path]
        else
          find(e.definition.entities, transform * e.transformation, path + [e.persistent_id], found)
        end
      when Sketchup::Group
        find(e.entities, transform * e.transformation, path + [e.persistent_id], found)
      end
    end
    found
  end

  def self.inspect_one(name = nil)
    model = Sketchup.active_model
    windows = find(model.entities, Geom::Transformation.new, [], [])
    puts "\n#{'=' * 72}"
    puts "#{windows.size} designPH window instance(s) in #{model.title}"
    if windows.empty?
      puts "None found. Is a designPH model open?"
      return
    end

    instance, parent_transform, path = windows.find { |i, _, _| i.name.to_s == name.to_s } || windows.first
    puts "inspecting: #{instance.name.inspect}   definition: #{instance.definition.name.inspect}"
    puts "path (persistent ids of enclosing groups/components): #{path.inspect}"
    puts "=" * 72

    puts "\n-- transforms (translation shown in METRES for readability) --"
    show_transform("instance.transformation  (LOCAL, what the collector ships)", instance.transformation)
    show_transform("parent accumulated", parent_transform)
    show_transform("world = parent * instance", parent_transform * instance.transformation)

    puts "\n-- dynamic_attributes --"
    dc = instance.attribute_dictionary(DC)
    dc.each_pair { |k, v| puts format("   %-22s %-12s %s", k, v.class, v.inspect[0, 40]) } if dc

    puts "\n-- what is INSIDE the definition (the question) --"
    dump(instance.definition.entities, 1, Geom::Transformation.new)

    puts "\n-- host --"
    host = instance.glued_to
    if host.is_a?(Sketchup::Face)
      puts "   glued_to a Face, #{host.loops.size} loop(s), persistent_id #{host.persistent_id}"
      puts "   host area (SketchUp, net of glued openings): #{(host.area * 0.00064516).round(4)} m²"
      puts "   host outer loop, world:"
      host.outer_loop.vertices.first(6).each do |v|
        p = v.position.transform(parent_transform)
        puts "     #{[p.x.to_f * IN_TO_M, p.y.to_f * IN_TO_M, p.z.to_f * IN_TO_M].map { |c| c.round(4) }.inspect}"
      end
    else
      puts "   glued_to: #{host.class}"
    end
    puts "\n#{'=' * 72}\nSend me everything from the first ==== line down."
    nil
  end

  def self.show_transform(label, t)
    a = t.to_a
    puts "   #{label}"
    puts format("     translation: [%.4f, %.4f, %.4f] m",
                a[12] * IN_TO_M, a[13] * IN_TO_M, a[14] * IN_TO_M)
    puts format("     axes lengths: x=%.6f y=%.6f z=%.6f (1.0 = unscaled)",
                Math.sqrt(a[0]**2 + a[1]**2 + a[2]**2),
                Math.sqrt(a[4]**2 + a[5]**2 + a[6]**2),
                Math.sqrt(a[8]**2 + a[9]**2 + a[10]**2))
  end

  # Recursive dump of the definition's contents: what is at each level, and where the faces are.
  def self.dump(entities, depth, transform)
    pad = "   " + ("  " * depth)
    counts = Hash.new(0)
    entities.each { |e| counts[e.class.name.split("::").last] += 1 }
    puts "#{pad}contents: #{counts.map { |k, v| "#{v} #{k}" }.join(', ')}"

    entities.grep(Sketchup::Face).each_with_index do |f, i|
      normal = f.normal
      puts format("%sface %d: %8.4f m²  %2d pts  normal [%.2f, %.2f, %.2f]  loops=%d",
                  pad, i, f.area(transform) * 0.00064516, f.outer_loop.vertices.size,
                  normal.x, normal.y, normal.z, f.loops.size)
    end
    entities.each do |e|
      case e
      when Sketchup::Group
        puts "#{pad}GROUP #{e.persistent_id} (#{e.name.to_s.empty? ? 'unnamed' : e.name})"
        dump(e.entities, depth + 1, transform * e.transformation)
      when Sketchup::ComponentInstance
        puts "#{pad}COMPONENT #{e.persistent_id} def=#{e.definition.name.inspect}"
        dump(e.definition.entities, depth + 1, transform * e.transformation)
      end
    end
  end
end

puts "DphWin loaded. Run:  DphWin.inspect_one   (or DphWin.inspect_one(\"403U\"))"
