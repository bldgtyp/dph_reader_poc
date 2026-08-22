# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- collector.rb
#
# The read layer: one recursive walk of the model, emitting the extraction JSON
# described by `planning/POC/CONTRACT_extraction-json.md`.
#
# ⚠ READ-ONLY, structurally. Nothing here writes to the model, and nothing
# writes to `DesignPH_dict` (hard rules 2 and 3). Not even a temporary
# attribute -- the console runner asserts `model.modified?` is unchanged
# across a whole corpus sweep.
#
# **Ruby stays dumb.** This file coalesces key generations, accumulates
# transforms, converts SketchUp lengths to metres, and decodes Marshal tables.
# It does NO type normalisation, no geometry maths beyond transforms, and no
# classification logic -- with one sanctioned exception, `classified?` (§2 of
# the contract), which decides only *whether a face record ships*. Every other
# judgement call belongs to Python: one place to get it wrong, not two.
#
# Four traps are designed around here, each of which loses data silently:
#
#   1. **Thermal bridges are on `Sketchup::Edge`.** A face-only walk drops all
#      99 of them on `2414 Bluff Reach.skp` with no error at all.
#   2. **Coalesce `*ID` ‖ `*Auto`; never version-key.** They are mutually
#      exclusive per face, and both hold real data regardless of the version
#      stamp. ⚠ The fallback key for the area group is `areaGroupAuto` -- no
#      "ID". The Phase 3 spike wrote `areaGroupIDAuto`, which reads nothing;
#      it was masked because every classified Adelphi face carries `areaGroupID`.
#   3. **`attribute_dictionaries` returns `nil`, not empty.**
#   4. **A face inside a group is in the group's LOCAL coordinates.** Without
#      the accumulated transform every nested face lands in the wrong place and
#      every scaled group lies about its size.
#   5. **`ComponentInstance#transformation` is PARENT-relative** while every
#      other geometry field here is world -- the same trap as 4, wearing the
#      clothes of an answer. It cost Adelphi's 46 windows 1.2-3.3 m of offset
#      from their own hosts. Compose it once, in `visit_window`.
#
# When designPH 3.0 arrives, this file and the contract are the blast radius.
# Keep it free of translation logic and that stays true.
#
# SketchUp 2022 is Ruby 2.7. Syntax-check with `ruby -c` before installing.
# ---------------------------------------------------------------------------
require "base64"
require "json"

module DphPlusPoc
  module Collector

    # Contract version this collector emits. The translator hard-fails on a
    # version it does not know -- no compatibility shims in a POC (contract §9).
    CONTRACT_VERSION = 2

    DICT = "DesignPH_dict".freeze
    DC_DICT = "dynamic_attributes".freeze

    # SketchUp's internal unit is inches, whatever the model displays.
    IN_TO_M   = 0.0254
    IN2_TO_M2 = 0.00064516

    # Coordinates are rounded on the way out. 1e-6 m is a micron -- far below
    # any modelling tolerance, and it keeps float noise out of the diffs that
    # POC-5 takes between re-runs of the same model.
    COORD_DECIMALS = 6

    # The key pairs to coalesce, and the contract field each produces.
    # ⚠ `areaGroupAuto` and `tempZoneAuto` carry no "ID"; `assemblyIDAuto` does.
    # The asymmetry is designPH's, not a typo. `DESIGNPH_DATA_MODEL.md` §5.
    COALESCE = {
      "area_group"   => %w[areaGroupID areaGroupAuto],
      "temp_zone"    => %w[tempZoneID tempZoneAuto],
      "assembly_ref" => %w[assemblyID assemblyIDAuto],
      "desc_name"    => %w[descName descNameAuto]
    }.freeze

    # Marshal tables the POC consumes. Everything else that decodes is listed in
    # `counts.tables_found` but not shipped -- see `SHIP_TABLE_PREFIXES` for the
    # `layer_table_*` family, which is a family and not one key (Linde `250703`
    # carries 25).
    SHIP_TABLES = %w[assemblies_calc assemblies_ud connections_ud vent_ud ihg_ud].freeze
    SHIP_TABLE_PREFIXES = %w[layer_table_].freeze

    # base64 of "\x04\x08", Ruby's Marshal format marker.
    MARSHAL_PREFIX = "BAh".freeze

    # Model-level keys that identify the project rather than carry a table.
    MODEL_VERSION_KEY = "designPH_version".freeze
    MODEL_KLIMA_ID    = "klima_ID".freeze
    MODEL_KLIMA_NAME  = "Klima_Standort".freeze

    # The `dynamic_attributes` subset the contract ships. An allow-list, because
    # the DC dictionary also holds `_<name>_formulaunits`, `_<name>_label` and
    # a dozen other editor artefacts that say nothing about the window.
    #
    # ⚠ Units are PER FIELD and are NOT converted here: `lenx`/`leny`/`d_reveal`/
    # `o_reveal`/`framedepth`/`revealdepth` are inches-as-Strings, `framewidth*`
    # are inches-as-Floats, and `instcill`/`insthead`/`instleft`/`instright` are
    # `"0"`/`"1"` flags. Python converts (contract §4).
    #
    # ⚠ `area` is a **stale Dynamic-Component formula output** and nothing may
    # compute from it: it equals `lenx × leny × 0.00064516` on only 20 of
    # Adelphi's 46 windows (`DESIGNPH_DATA_MODEL.md` §9.2). It ships so a report
    # can say what the model claims, and for no other reason.
    #
    WINDOW_DC_KEYS = %w[
      frametypeid glazingtypeid frametype glazingtype
      lenx leny area
      framewidth framewidthl framewidthr framewidthtop framewidthbot
      framedepth revealdepth d_reveal o_reveal
      instcill insthead instleft instright
    ].freeze

    # ★ designPH's frame and glazing libraries, stored **inline in the model** as
    # SketchUp DC option lists -- `&<name>=<id>&<name>=<id>&`. They are the only
    # way to put a name to a `frametypeid` with no installed CSV library
    # (`DESIGNPH_FILE_FORMATS.md` §3 says those live on disk; this says a large
    # part of one also travels in the `.skp`).
    #
    # ⚠ They are LIBRARY data and belong to the model, not to a window. Shipping
    # them per-window is what contract v1 did, and on Adelphi that is 44,915
    # characters repeated **byte-identically on all 46 windows** -- 2.07 MB of a
    # 2.25 MB payload, against a bridge verified to 4 MB. Deduplicated they are
    # 45 KB (contract v2, §5.1).
    #
    # Distinct raw values ship, in first-seen order. Deduplication is not a
    # judgement call; choosing between them is, and that is Python's.
    WINDOW_LIBRARY_KEYS = {
      "_frametype_options" => "frame_types",
      "_glazingtype_options" => "glazing_types"
    }.freeze

    # The DC keys the rough-opening rectangle is built from. Named apart because
    # they are the only designPH values this file coerces to a number (§4).
    WINDOW_SIZE_KEYS = %w[lenx leny].freeze

    # What makes a component instance a designPH window. Settled by predicate,
    # not by definition name -- users rename definitions.
    WINDOW_MARKER = "frametypeid".freeze

    # The marker that says an extraction did not come from a real model.
    STUB_MARKER = "STUB".freeze

    # -------------------------------------------------------------------
    # Entry point
    # -------------------------------------------------------------------

    # Returns the extraction as a Ruby Hash of contract shape.
    #
    # `file_name` overrides the name derived from `model.path`. ⚠ That derivation is the only
    # source available here and it is **not reliable**: `Sketchup::Model#path` returns the location
    # the model was last SAVED, which on a file authored elsewhere is somebody else's machine —
    # Wellington reports `2523 Weiilington` and Linde reports a whole `C:\Users\greg\...` path
    # (`SKETCHUP_RUNTIME.md` §8.2). When the caller knows better, it says so, and the fixture stops
    # carrying a name that identifies nothing.
    # `progress` is an optional callable receiving the running entity count. It
    # exists because the walk takes **100 ms to 9.7 s** across the corpus and
    # tracks *placements* rather than model size, so there is no way to predict
    # from the outside which end a given model lands on. A ten-second freeze
    # with no feedback is the bug a user reports; the walk itself is fine.
    def self.extract(model, generated_by = "dph_plus_poc collector", file_name = nil, progress = nil)
      Walk.new(model, generated_by, file_name, progress).run
    end

    # Was this extraction produced without reading a model? Derived from the
    # payload rather than a flag, so nothing has to be remembered.
    def self.stub?(payload)
      payload["generated_by"].to_s.include?(STUB_MARKER)
    end

    # A face is classified iff its coalesced area group parses as a positive
    # integer. `'n'` -- designPH's "not assigned" -- is the common case: 1359 of
    # 1441 tagged faces on Adelphi. The filter must therefore be by VALUE, not
    # by presence (hard rule 5).
    def self.classified?(raw)
      return false if raw.nil?
      Integer(raw.to_s, 10) > 0
    rescue ArgumentError, TypeError
      false
    end

    # -------------------------------------------------------------------
    # Marshal tables
    # -------------------------------------------------------------------
    module Tables

      # Decode one base64'd `Marshal.dump` into `{tokens, rows}`.
      #
      # ⚠ `Marshal.load` instantiates whatever the blob names. That is
      # acceptable for the POC, which only ever reads BLDGTYP's own corpus
      # models. **Before v1 ever opens a stranger's file**, port
      # `planning/spikes/phase1/ruby_marshal.py`'s construct-nothing approach
      # to Ruby: it reads Marshal 4.8 without instantiating anything, so an
      # unknown class becomes an inert record of its name.
      def self.decode(blob)
        raw = Marshal.load(Base64.decode64(blob))
        normalise(raw)
      rescue StandardError => error
        { "error" => "#{error.class}: #{error.message}" }
      end

      # designPH's tables are self-describing: a `["#", :TOKENS, [...]]` row
      # travels with the data. **Its position varies** -- `vent_ud` and `ihg_ud`
      # put it at the END and their data is a flat array of scalars rather than
      # a list of rows (`DESIGNPH_DATA_MODEL.md` §7). Normalising to
      # `{tokens, rows}` here is what stops Python having to know that.
      def self.normalise(raw)
        return { "error" => "not an Array (#{raw.class})" } unless raw.is_a?(Array)

        tokens = []
        rows = []
        scalars = []
        raw.each do |entry|
          if metadata_row?(entry)
            tokens = Array(entry[2]).map { |token| plain(token) } if entry[1].to_s == "TOKENS"
          elsif entry.is_a?(Array)
            rows << entry.map { |value| plain(value) }
          else
            scalars << plain(entry)
          end
        end
        # A flat table: the scalars ARE the single row.
        rows << scalars unless scalars.empty?
        { "tokens" => tokens, "rows" => rows }
      end

      def self.metadata_row?(entry)
        entry.is_a?(Array) && entry[0].to_s == "#"
      end

      # Symbols become Strings; everything else is left exactly as designPH
      # stored it. Table values are already SI/PHPP units (lambda, Psi, mm) and
      # stay that way -- only *SketchUp geometry* is converted to metres.
      def self.plain(value)
        case value
        when Symbol then value.to_s
        when Array  then value.map { |item| plain(item) }
        else value
        end
      end
    end

    # -------------------------------------------------------------------
    # The walk
    # -------------------------------------------------------------------
    class Walk

      # How many entities pass before `progress` is called again. Coarse on
      # purpose: the point is a status line that moves, and the callback itself
      # (a `Time.now` and a status-bar write) is not free on a million-placement
      # walk.
      PROGRESS_EVERY = 250

      def initialize(model, generated_by, file_name = nil, progress = nil)
        @model = model
        @generated_by = generated_by
        @file_name = file_name
        @progress = progress
        @visited = 0
        @faces = []
        @edges = []
        @windows = []
        @tagged_unclassified = []
        @untagged_by_tag = Hash.new(0)
        # Distinct raw option-list strings, in first-seen order (§5.1).
        @libraries = WINDOW_LIBRARY_KEYS.values.each_with_object({}) { |name, out| out[name] = [] }
        @faces_walked = 0
        @faces_tagged = 0
      end

      def run
        walk(@model.entities, identity, [])
        tables, found = collect_tables
        {
          "contract_version" => CONTRACT_VERSION,
          "generated_by" => @generated_by,
          "model" => model_info,
          "counts" => {
            "faces_walked" => @faces_walked,
            "faces_tagged" => @faces_tagged,
            "faces_classified" => @faces.size,
            "edges_tagged" => @edges.size,
            "windows_found" => @windows.size,
            "tables_found" => found
          },
          "faces" => @faces,
          "edges" => @edges,
          "windows" => @windows,
          "libraries" => @libraries,
          "tables" => tables,
          "unclassified" => {
            "tagged_faces" => @tagged_unclassified,
            "untagged_by_tag" => @untagged_by_tag
          }
        }
      end

      private

      def identity
        Geom::Transformation.new
      end

      # `path` is the persistent ids of the enclosing groups/components, which
      # is what makes an id unique under component instancing: one definition
      # placed twice is two envelope surfaces, visited once per placement, each
      # with its own composed transform (contract §2.1).
      def walk(entities, transform, path)
        entities.each do |entity|
          @visited += 1
          if @progress && (@visited % PROGRESS_EVERY).zero?
            # A reporting hook must never be able to fail the read it reports on.
            begin
              @progress.call(@visited)
            rescue StandardError
              @progress = nil
            end
          end
          case entity
          when Sketchup::Face
            visit_face(entity, transform, path)
          when Sketchup::Edge
            visit_edge(entity, transform, path)
          when Sketchup::ComponentInstance
            next if visit_window(entity, transform, path)
            walk(entity.definition.entities, transform * entity.transformation,
                 path + [entity.persistent_id])
          when Sketchup::Group
            walk(entity.entities, transform * entity.transformation,
                 path + [entity.persistent_id])
          end
        end
      end

      # -----------------------------------------------------------------
      # Faces
      # -----------------------------------------------------------------

      def visit_face(face, transform, path)
        @faces_walked += 1
        dictionary = face.attribute_dictionary(DICT)
        if dictionary.nil?
          @untagged_by_tag[tag_name(face)] += 1
          return
        end

        @faces_tagged += 1
        values = coalesce(dictionary)
        if Collector.classified?(values["area_group"])
          @faces << face_record(face, dictionary, values, transform, path)
        else
          # Compact, ~100 bytes: enough for the report to NAME every tagged face
          # the translation omits, which is what hard rule 4 asks for.
          @tagged_unclassified << {
            "id" => entity_id("face", face, path),
            "area_group" => values["area_group"],
            "tag" => tag_name(face)
          }
        end
      end

      def face_record(face, dictionary, values, transform, path)
        loops = face.loops
        outer = face.outer_loop
        {
          "id" => entity_id("face", face, path),
          "entity_id" => face.entityID,
          "area_group" => values["area_group"],
          "temp_zone" => values["temp_zone"],
          "assembly_ref" => values["assembly_ref"],
          "desc_name" => values["desc_name"],
          "tfa_rf" => dictionary["TFA_rf"],
          # SketchUp's winding order is preserved verbatim: orientation is
          # derived from it in Python. No normal is shipped -- transforming one
          # is wrong under non-uniform scale or mirroring, and a mirrored
          # transform flips the winding with the geometry, so the derived
          # normal stays consistent (contract §2.2).
          "outer_loop" => loop_points(outer, transform),
          "inner_loops" => loops.reject { |l| l == outer }.map { |l| loop_points(l, transform) },
          "area_m2" => round_number(face.area(transform) * IN2_TO_M2),
          "both_generations" => values["both_generations"]
        }
      end

      # -----------------------------------------------------------------
      # Edges -- thermal bridges
      # -----------------------------------------------------------------

      def visit_edge(edge, transform, path)
        dictionary = edge.attribute_dictionary(DICT)
        return if dictionary.nil?

        values = coalesce(dictionary)
        start_point = point(edge.start.position, transform)
        end_point = point(edge.end.position, transform)
        @edges << {
          "id" => entity_id("edge", edge, path),
          "entity_id" => edge.entityID,
          "area_group" => values["area_group"],
          # Named differently from a face's `assembly_ref` on purpose: it
          # resolves against `connections_ud`, NOT the assembly tables. Both
          # namespaces use `NNud` ids, so joining it to assemblies by accident
          # would return an unrelated row rather than an error.
          "connection_ref" => values["assembly_ref"],
          "desc_name" => values["desc_name"],
          # From the TRANSFORMED endpoints. `Edge#length` taking a transform
          # argument is unverified API; two subtractions are not.
          "length_m" => round_number(distance(start_point, end_point)),
          "start" => start_point,
          "end" => end_point,
          "both_generations" => values["both_generations"]
        }
      end

      # -----------------------------------------------------------------
      # Windows -- Dynamic Components, not DesignPH_dict
      # -----------------------------------------------------------------

      # Returns true when `instance` was a designPH window, which also means the
      # walk must NOT descend into it: window internals are neither walked nor
      # counted (contract §6.1).
      def visit_window(instance, transform, path)
        dc = instance.attribute_dictionary(DC_DICT)
        return false if dc.nil? || dc[WINDOW_MARKER].nil?

        host = host_face(instance)
        attributes = window_attributes(instance, dc)
        collect_libraries(instance, dc)
        # ⚠ `instance.transformation` is the placement within the ENCLOSING
        # GROUP, while every other geometry field in the contract is world.
        # Mixing the two put Adelphi's 46 windows 1.2-3.3 m off their own hosts,
        # on a real model, with the containment check as the only symptom
        # (`DESIGNPH_DATA_MODEL.md` §9.3). The two are the same object type and
        # differ only in where they were read, so compose here, once.
        world = transform * instance.transformation
        @windows << {
          "id" => entity_id("window", instance, path),
          "entity_id" => instance.entityID,
          "designph_name" => window_name(instance),
          "definition_name" => instance.definition.name,
          "instance_name" => blank_to_nil(instance.name),
          "dynamic_attributes" => attributes,
          # `to_a`: SketchUp's column-major layout, translation at indices
          # 12-14, in INCHES -- but the ACCUMULATED world transform, not the
          # instance's own (contract §8.2).
          "transformation" => world.to_a,
          "panel_outer_loop" => panel_loop(world, attributes),
          "host_face_id" => host ? entity_id("face", host, path) : nil,
          # No geometric fallback in Ruby. "unresolved" is legal contract data
          # and ships with the transform and panel loop, so a Python-side
          # coplanar recovery stays possible without Ruby guessing (POC-3 §4).
          "host_resolution" => host ? "glued_to" : "unresolved",
          # ⚠ NEVER `cuts_opening?`. That is a capability of the DEFINITION --
          # true on all 46 Adelphi windows, while only 2 of the 16 real host
          # faces have an inner loop. It says nothing about this host.
          #
          # ⚠ Nor is this a host *test*: a glued opening reduces `face.area`
          # without creating a loop, so `glued_to` is the only thing that
          # identifies a host. This field reports whether the hole was MODELLED,
          # which is why `face.area` comes back net while the loop is gross.
          "host_has_inner_loops" => host ? host.loops.size > 1 : false
        }
        true
      end

      def host_face(instance)
        host = instance.respond_to?(:glued_to) ? instance.glued_to : nil
        host.is_a?(Sketchup::Face) ? host : nil
      end

      # Never nil: every report line downstream names its window with this.
      def window_name(instance)
        dictionary = instance.attribute_dictionary(DICT)
        generated = dictionary && (dictionary["descName"] || dictionary["descNameAuto"])
        blank_to_nil(instance.name) || blank_to_nil(generated) ||
          "#{instance.definition.name}##{instance.persistent_id}"
      end

      # Per-window values live on the INSTANCE; the shared template lives on the
      # definition. Reading only one gives wrong answers
      # (`DESIGNPH_DATA_MODEL.md` §8.2).
      def window_attributes(instance, instance_dc)
        definition_dc = instance.definition.attribute_dictionary(DC_DICT)
        WINDOW_DC_KEYS.each_with_object({}) do |key, out|
          value = instance_dc[key]
          value = definition_dc[key] if value.nil? && definition_dc
          out[key] = value unless value.nil?
        end
      end

      # Model-level library data, gathered while walking the windows that happen
      # to carry it. Instance AND definition are both read: a definition can hold
      # the real list while its instances hold designPH's
      # `&Launch designPH to edit=01ud&` placeholder, and vice versa.
      def collect_libraries(instance, instance_dc)
        definition_dc = instance.definition.attribute_dictionary(DC_DICT)
        WINDOW_LIBRARY_KEYS.each do |key, name|
          [instance_dc[key], definition_dc && definition_dc[key]].each do |value|
            next unless value.is_a?(String) && !value.strip.empty?
            @libraries[name] << value unless @libraries[name].include?(value)
          end
        end
      end

      # The window rectangle is the **rough opening**: the definition-local
      # `(0,0,0) → (lenx,0,0) → (lenx,leny,0) → (0,leny,0)` through the world
      # transform. Contract §8.1; settled, not a candidate.
      #
      # ⚠ Two refuted alternatives, because both look right:
      #
      #   1. "the definition's largest face" -- what this used to do -- finds
      #      NOTHING: `definition.entities.grep(Sketchup::Face)` is `[]` on all
      #      46 Adelphi windows, the geometry sitting two and three levels down.
      #      And recursing to reach it is *worse*, not better: the largest face
      #      is the GLAZING, `(lenx − 2·framewidth)(leny − 2·framewidth)`, which
      #      is 41 % smaller than the opening while being real geometry in the
      #      right place and the right shape. Nothing downstream would flag it.
      #   2. `dynamic_attributes["area"]` is a stale DC formula output (§9.2).
      #
      # A honeybee `Aperture` represents the whole window -- frame and glazing
      # travel as PH properties on it -- so the rough opening is the rectangle
      # it wants. `DESIGNPH_DATA_MODEL.md` §9.1.
      #
      # The corner convention is **measured, not assumed**: with the parent
      # transform recovered from the first capture, `+x/+y` from the origin puts
      # all 46 windows inside their host polygons, against 23, 15 and 12 for the
      # centred and the two flipped conventions
      # (`planning/spikes/poc/solve_window_parent.py`).
      #
      # `nil` now means a genuine read failure -- no usable `lenx`/`leny` on the
      # instance or its definition (contract §8.3).
      def panel_loop(world, attributes)
        lenx, leny = WINDOW_SIZE_KEYS.map { |key| inches(attributes[key]) }
        return nil if lenx.nil? || leny.nil?

        [[0.0, 0.0], [lenx, 0.0], [lenx, leny], [0.0, leny]].map do |x, y|
          point(Geom::Point3d.new(x, y, 0.0), world)
        end
      end

      # The one designPH value this file coerces, and only because the rectangle
      # cannot be built without a number. The raw String still ships in
      # `dynamic_attributes`, so Python's type check runs on the authoritative
      # copy and "Ruby stays dumb" survives intact.
      def inches(value)
        return nil if value.nil?
        number = Float(value.to_s)
        number.finite? && number > 0 ? number : nil
      rescue ArgumentError, TypeError
        nil
      end

      # -----------------------------------------------------------------
      # Shared reading
      # -----------------------------------------------------------------

      # `face[*ID] or face[*Auto]`, per pair. The two are mutually exclusive per
      # face across all 14 corpus models -- so this is a coalesce, not a
      # precedence, and it is deliberately version-independent. Any rule keyed
      # on the designPH version stamp loses envelope data silently: `250708.skp`
      # is 2.1.15 and keeps every one of its 92 assemblies in `*Auto`.
      #
      # A pair with BOTH values non-nil is impossible according to the corpus.
      # If it ever happens the model is not what we think, so it is named in
      # `both_generations` and left for Python to report (§6.5's obligation).
      def coalesce(dictionary)
        both = []
        values = {}
        COALESCE.each do |field, (primary, fallback)|
          first = dictionary[primary]
          second = dictionary[fallback]
          # The pair's name, not the contract field's: `assembly_ref` is the
          # field, `assembly` is the designPH concept the two keys share.
          both << field.sub(/_ref\z/, "") if !first.nil? && !second.nil?
          values[field] = first.nil? ? second : first
        end
        values["both_generations"] = both
        values
      end

      def loop_points(entity_loop, transform)
        entity_loop.vertices.map { |vertex| point(vertex.position, transform) }
      end

      def point(position, transform)
        transformed = position.transform(transform)
        [round_number(transformed.x.to_f * IN_TO_M),
         round_number(transformed.y.to_f * IN_TO_M),
         round_number(transformed.z.to_f * IN_TO_M)]
      end

      def distance(a, b)
        Math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2 + (a[2] - b[2])**2)
      end

      def round_number(value)
        value.round(COORD_DECIMALS)
      end

      def entity_id(kind, entity, path)
        ([kind] + path + [entity.persistent_id]).join("_")
      end

      def tag_name(entity)
        layer = entity.layer
        layer ? layer.name.to_s : "Untagged"
      rescue StandardError
        "Untagged"
      end

      def blank_to_nil(value)
        text = value.to_s.strip
        text.empty? ? nil : text
      end

      # -----------------------------------------------------------------
      # Model-level data
      # -----------------------------------------------------------------

      def model_info
        dictionary = @model.attribute_dictionary(DICT)
        {
          "file_name" => model_file_name,
          # ⚠ ONE stamp, not all of them. Wellington's `.skp` holds two version
          # values, but that is historical state visible only to the offline
          # binary reader; the live API returns what the model carries now.
          # Shipped as a list because the contract's shape allows for more.
          "designph_versions" => Array(dictionary && dictionary[MODEL_VERSION_KEY]).compact,
          "klima_id" => dictionary && dictionary[MODEL_KLIMA_ID],
          "klima_standort" => dictionary && dictionary[MODEL_KLIMA_NAME],
          "units_note" => "geometry in metres; raw designPH table and DC values untouched " \
                          "(mixed units, see contract §4/§5)"
        }
      end

      # ⚠ `model.path` is the last-SAVED location, not the opened file, so on a model authored
      # elsewhere this derives a name that identifies nothing. The caller's `file_name` wins when
      # it has one. `SKETCHUP_RUNTIME.md` §8.2.
      def model_file_name
        return @file_name if blank_to_nil(@file_name)
        path = @model.path.to_s.tr("\\", "/")
        return File.basename(path, ".skp") unless path.empty?
        blank_to_nil(@model.title) || "untitled"
      end

      # Returns [shipped_tables, every_blob_key_found].
      def collect_tables
        dictionary = @model.attribute_dictionary(DICT)
        return [{}, []] if dictionary.nil?

        found = []
        shipped = {}
        dictionary.each_pair do |key, value|
          next unless value.is_a?(String) && value.start_with?(MARSHAL_PREFIX)
          found << key
          shipped[key] = Tables.decode(value) if ship_table?(key)
        end
        [shipped, found.sort]
      end

      def ship_table?(key)
        SHIP_TABLES.include?(key) || SHIP_TABLE_PREFIXES.any? { |p| key.start_with?(p) }
      end
    end
  end
end
