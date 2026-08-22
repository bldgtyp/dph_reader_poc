# ---------------------------------------------------------------------------
# DesignPH-PLUS POC -- exercise the collector outside SketchUp.
#
#     ruby poc/ext/tests/test_collector.rb
#
# This is the suite that keeps POC-2's Ed budget at two SketchUp sessions. Every
# rule that loses data *silently* is checked here, against a hand-built stub
# entity tree: thermal bridges on edges, the `*ID` ‖ `*Auto` coalesce (including
# the `areaGroupAuto`-not-`areaGroupIDAuto` trap), nil dictionary guards,
# transform accumulation through nested/scaled/mirrored groups, path-qualified
# ids under component instancing, the census invariant, and Marshal decoding
# with the `:TOKENS` row at either end.
#
# ⚠ **None of it is evidence about designPH.** The trees are hand-made, and a
# synthetic model already produced one confidently wrong schema rule on this
# project. What carries evidential weight is the reconciliation against the
# Phase 0/1 corpus baselines, which needs real models and therefore Ed.
#
# Ruby 2.7. `ruby -c` before installing.
# ---------------------------------------------------------------------------
require "base64"
require "fileutils"
require_relative "sketchup_stub"

Thread.abort_on_exception = true

load File.join(__dir__, "..", "dph_plus_poc", "main.rb")

C = DphPlusPoc::Collector

$failures = 0

def check(label, condition, detail = nil)
  $failures += 1 unless condition
  puts format("  %-4s %s%s", condition ? "ok" : "FAIL", label, detail ? "  (#{detail})" : "")
  condition
end

def group(title)
  puts "\n#{title}"
end

def marshal_blob(rows)
  Base64.strict_encode64(Marshal.dump(rows))
end

# A metre in SketchUp's internal units, which are always inches.
M = 1.0 / 0.0254

def square(size, z: 0.0)
  [[0, 0, z], [size, 0, z], [size, size, z], [0, size, z]]
end

def dph(values)
  { "DesignPH_dict" => values }
end

# ---------------------------------------------------------------------------
group "Classification -- by value, never by presence"
# ---------------------------------------------------------------------------

# `areaGroupID` is a String on 1359 of 1441 faces in the primary corpus model,
# most often `'n'`. A filter on presence would ship all 1441.
{ 8 => true, "8" => true, " 10 " => true, 1 => true,
  "n" => false, "" => false, nil => false, 0 => false, "0" => false, -1 => false }.each do |raw, want|
  check("classified?(#{raw.inspect}) == #{want}", C.classified?(raw) == want)
end

# ---------------------------------------------------------------------------
group "The coalesce -- *ID or *Auto, never version-keyed"
# ---------------------------------------------------------------------------

# ⚠ The fallback key is `areaGroupAuto`, with no "ID". The Phase 3 spike wrote
# `areaGroupIDAuto` and read nothing; Adelphi masked it because every one of its
# classified faces carries `areaGroupID`. `250708.skp` would have lost all 92 of
# its assemblies to the same class of typo.
auto_only = Sketchup::Model.new(entities: [
  Sketchup::Face.new(square(M), persistent_id: 1, dictionaries: dph(
    "areaGroupAuto" => 10, "tempZoneAuto" => "A", "assemblyIDAuto" => "83ud",
    "descNameAuto" => "Roof_001"
  ))
])
face = C.extract(auto_only)["faces"].first
check("areaGroupAuto is read (not areaGroupIDAuto)", face && face["area_group"] == 10)
check("tempZoneAuto is read", face && face["temp_zone"] == "A")
check("assemblyIDAuto is read", face && face["assembly_ref"] == "83ud")
check("descNameAuto is read", face && face["desc_name"] == "Roof_001")

id_wins = Sketchup::Model.new(entities: [
  Sketchup::Face.new(square(M), persistent_id: 2, dictionaries: dph(
    "areaGroupID" => 8, "areaGroupAuto" => 10,
    "descName" => "104C HALL", "descNameAuto" => "Wall_004_S"
  ))
])
face = C.extract(id_wins)["faces"].first
check("*ID wins when both are present", face["area_group"] == 8)
check("the user's name wins over the generated one", face["desc_name"] == "104C HALL")
# The corpus says both-populated is impossible. If it happens the model is not
# what we think, so it must reach the report rather than be quietly coalesced.
check("...and both-populated pairs are named for the report",
      face["both_generations"].sort == %w[area_group desc_name],
      face["both_generations"].inspect)

# ---------------------------------------------------------------------------
group "Untagged and tagged-but-unclassified faces"
# ---------------------------------------------------------------------------

mixed = Sketchup::Model.new(entities: [
  Sketchup::Face.new(square(M), persistent_id: 10, dictionaries: dph("areaGroupID" => 8)),
  Sketchup::Face.new(square(M), persistent_id: 11, dictionaries: dph("areaGroupID" => "n"),
                     tag: "04_SHADING_TREES"),
  # No DesignPH_dict at all -- `attribute_dictionary` returns nil, not empty.
  Sketchup::Face.new(square(M), persistent_id: 12, tag: "04_SHADING_TREES"),
  Sketchup::Face.new(square(M), persistent_id: 13, tag: "Layer0")
])
payload = C.extract(mixed)
check("classified faces ship as geometry", payload["faces"].size == 1)
check("tagged-but-unclassified ship as compact records",
      payload["unclassified"]["tagged_faces"].size == 1)
check("...naming the raw area group as found",
      payload["unclassified"]["tagged_faces"].first["area_group"] == "n")
check("...and the SketchUp tag",
      payload["unclassified"]["tagged_faces"].first["tag"] == "04_SHADING_TREES")
check("untagged faces aggregate by tag only",
      payload["unclassified"]["untagged_by_tag"] == { "04_SHADING_TREES" => 1, "Layer0" => 1 },
      payload["unclassified"]["untagged_by_tag"].inspect)
check("faces_walked counts every live face", payload["counts"]["faces_walked"] == 4)
check("faces_tagged counts DesignPH_dict carriers", payload["counts"]["faces_tagged"] == 2)
# Contract §6.1's invariant, which the translator also asserts.
check("census invariant: classified + tagged-unclassified == faces_tagged",
      payload["faces"].size + payload["unclassified"]["tagged_faces"].size ==
        payload["counts"]["faces_tagged"])

# ---------------------------------------------------------------------------
group "Thermal bridges -- on edges, and a face-only walk loses all of them"
# ---------------------------------------------------------------------------

bridges = Sketchup::Model.new(entities: [
  Sketchup::Edge.new([0, 0, 0], [4 * M, 0, 0], persistent_id: 20, dictionaries: dph(
    "areaGroupID" => 15, "assemblyID" => "101ud"
  )),
  # An edge with no designPH data is ordinary geometry and must not ship.
  Sketchup::Edge.new([0, 0, 0], [1, 0, 0], persistent_id: 21),
  # An anomalous group still ships -- Python reports it (contract §3).
  Sketchup::Edge.new([0, 0, 0], [0, M, 0], persistent_id: 22, dictionaries: dph(
    "areaGroupAuto" => 8
  ))
])
payload = C.extract(bridges)
check("tagged edges are collected", payload["edges"].size == 2)
check("...counted", payload["counts"]["edges_tagged"] == 2)
edge = payload["edges"].first
# Named `connection_ref`, not `assembly_ref`: it resolves against
# `connections_ud`, and both namespaces use `NNud` ids, so joining it to the
# assemblies by accident returns an unrelated row rather than an error.
check("the ref is named connection_ref, not assembly_ref",
      edge.key?("connection_ref") && !edge.key?("assembly_ref"))
check("...and carries the coalesced value", edge["connection_ref"] == "101ud")
check("length comes from the transformed endpoints", (edge["length_m"] - 4.0).abs < 1e-6,
      edge["length_m"].to_s)
check("an anomalous area group still ships", payload["edges"].last["area_group"] == 8)

# ---------------------------------------------------------------------------
group "Transform accumulation -- nested, scaled, mirrored"
# ---------------------------------------------------------------------------

# A face inside a group is stored in the group's LOCAL coordinates. Without the
# accumulated transform every nested face lands in the wrong place, and every
# scaled group lies about its size -- silently, in both cases.
inner_face = Sketchup::Face.new(square(M), persistent_id: 31,
                                dictionaries: dph("areaGroupID" => 8))
inner_group = Sketchup::Group.new(
  entities: [inner_face], persistent_id: 30,
  transformation: Geom::Transformation.translation(2 * M, 0, 0)
)
outer_group = Sketchup::Group.new(
  entities: [inner_group], persistent_id: 29,
  transformation: Geom::Transformation.scaling(3.0)
)
payload = C.extract(Sketchup::Model.new(entities: [outer_group]))
face = payload["faces"].first
check("nested transforms compose", face["outer_loop"].first == [6.0, 0.0, 0.0],
      face["outer_loop"].first.inspect)
check("...and scale reaches the geometry", face["outer_loop"][2] == [9.0, 3.0, 0.0],
      face["outer_loop"][2].inspect)
check("area is the TRUE area under the transform", (face["area_m2"] - 9.0).abs < 1e-6,
      face["area_m2"].to_s)
# The id is path-qualified: outer group, inner group, then the face.
check("ids are path-qualified through the nesting", face["id"] == "face_29_30_31", face["id"])

mirrored = Sketchup::Group.new(
  entities: [Sketchup::Face.new(square(M), persistent_id: 41,
                                dictionaries: dph("areaGroupID" => 10))],
  persistent_id: 40,
  transformation: Geom::Transformation.scaling(-1.0, 1.0, 1.0)
)
face = C.extract(Sketchup::Model.new(entities: [mirrored]))["faces"].first
# No normal is shipped. A mirrored transform flips the winding along with the
# geometry, so the orientation Python derives from `Face3D.normal` stays
# consistent -- whereas transforming a normal by the matrix would not.
check("a mirrored group flips the geometry", face["outer_loop"][1] == [-1.0, 0.0, 0.0],
      face["outer_loop"][1].inspect)
check("...and no normal is shipped for Python to trust", !face.key?("normal"))

# ---------------------------------------------------------------------------
group "Component instancing -- one definition, two placements, two ids"
# ---------------------------------------------------------------------------

# Each placement is a distinct envelope surface. Both share the face's own
# persistent id, so only the path keeps them apart.
shared = Sketchup::ComponentDefinition.new("Bay", [
  Sketchup::Face.new(square(M), persistent_id: 51, dictionaries: dph("areaGroupID" => 8))
])
payload = C.extract(Sketchup::Model.new(entities: [
  Sketchup::ComponentInstance.new(definition: shared, persistent_id: 50),
  Sketchup::ComponentInstance.new(definition: shared, persistent_id: 52,
                                  transformation: Geom::Transformation.translation(5 * M, 0, 0))
]))
ids = payload["faces"].map { |f| f["id"] }
check("both placements ship", payload["faces"].size == 2)
check("...with distinct path-qualified ids", ids == %w[face_50_51 face_52_51], ids.inspect)
check("...and their own world geometry",
      payload["faces"][1]["outer_loop"].first == [5.0, 0.0, 0.0])

# ---------------------------------------------------------------------------
group "Windows -- Dynamic Components, hosts, and the census"
# ---------------------------------------------------------------------------

host = Sketchup::Face.new(square(4 * M), persistent_id: 61,
                          inner: [[[M, 0, 0], [2 * M, 0, 0], [2 * M, M, 0], [M, M, 0]]],
                          dictionaries: dph("areaGroupID" => 8))
window_definition = Sketchup::ComponentDefinition.new(
  "designPH_Window_Simple_1-1",
  # Window internals: a big panel face and a small one. Neither may be walked.
  [Sketchup::Face.new(square(M), persistent_id: 71),
   Sketchup::Face.new(square(0.1 * M), persistent_id: 72)],
  { "dynamic_attributes" => { "framewidth" => 4.33 } }
)
window = Sketchup::ComponentInstance.new(
  definition: window_definition, persistent_id: 70, glued_to: host,
  transformation: Geom::Transformation.translation(0, 0, 3 * M),
  dictionaries: {
    "dynamic_attributes" => {
      "frametypeid" => "01ud", "glazingtypeid" => "01ud",
      "lenx" => "225.18749999999997", "leny" => "390.1875",
      "d_reveal" => "12.5", "o_reveal" => "11", "area" => 56.687207693906245,
      # ★ Carries the frame/glazing library id → name mapping INLINE, so it is
      # an allow-listed underscore key rather than an editor artefact.
      "_frametype_options" => "&PH-FRAMES: average thermal quality=01ud",
      # Editor artefacts that must NOT ship.
      "_lenx_formulaunits" => "INCHES", "_name_label" => "Window"
    }
  }
)
# Host and window sit inside a group together -- a glued instance glues within
# its own drawing context, so the two always share a path. That also gives the
# walk a non-identity accumulated transform, which is the only condition under
# which the parent-relative trap is visible at all.
window_group = Sketchup::Group.new(
  entities: [host, window], persistent_id: 90,
  transformation: Geom::Transformation.translation(0, 0, 10 * M)
)
payload = C.extract(Sketchup::Model.new(entities: [window_group]))
record = payload["windows"].first
check("a DC carrying frametypeid is a window", payload["windows"].size == 1)
check("window internals are NOT walked", payload["counts"]["faces_walked"] == 1,
      payload["counts"]["faces_walked"].to_s)
check("glued_to resolves the host", record["host_resolution"] == "glued_to")
check("...to the host's path-qualified id", record["host_face_id"] == "face_90_61",
      record["host_face_id"])
# ⚠ Never `cuts_opening?`: it is true on all 46 Adelphi windows, while only 1 of
# 16 host faces actually has an inner loop.
check("host holes come from the HOST's loops", record["host_has_inner_loops"] == true)
check("dynamic attributes pass through RAW", record["dynamic_attributes"]["lenx"] ==
      "225.18749999999997")
check("...with per-field units untouched", record["dynamic_attributes"]["area"] ==
      56.687207693906245)
check("...and every shipped key is on the allow-list",
      (record["dynamic_attributes"].keys - C::WINDOW_DC_KEYS).empty?,
      record["dynamic_attributes"].keys.inspect)
check("...so no underscore key rides along on a window",
      record["dynamic_attributes"].keys.none? { |k| k.start_with?("_") },
      record["dynamic_attributes"].keys.inspect)
# ★ The frame/glazing option lists ARE wanted -- they name the ids with no CSV
# library on disk -- but they are model-level library data, not window data, and
# repeating them per window cost 2.07 MB on Adelphi. See the v2 group below.
check("...including the option lists, which are model-level now",
      record["dynamic_attributes"]["_frametype_options"].nil? &&
        payload["libraries"]["frame_types"].first.to_s.include?("01ud"),
      payload["libraries"]["frame_types"].inspect)
check("definition values fill in where the instance is silent",
      record["dynamic_attributes"]["framewidth"] == 4.33)
# ⚠ The trap: `instance.transformation` alone puts the window 10 m below its
# host, because it is relative to the enclosing group (contract §8.2).
check("the transformation is ACCUMULATED to world, in inches",
      record["transformation"][14] == 13 * M, record["transformation"][14].to_s)
check("a name is always resolvable", !record["designph_name"].to_s.empty?,
      record["designph_name"])
# The rough opening: `lenx` × `leny` from the local origin, in world metres.
# ⚠ NOT the definition's largest face -- that is the glazing, 41 % small, and on
# a real window definition `grep(Face)` finds nothing at all.
panel = record["panel_outer_loop"]
check("the panel loop is the rough opening, +x/+y from the local origin",
      panel && panel[0] == [0.0, 0.0, 13.0] &&
        panel[2] == [(225.18749999999997 * 0.0254).round(6), (390.1875 * 0.0254).round(6), 13.0],
      panel.inspect)
check("...and it is NOT the definition's largest face",
      panel && panel[2] != [1.0, 1.0, 13.0], panel.inspect)

# An unglued window is legal contract data, not an error: it ships with its
# transform and panel loop so Python can attempt recovery if it ever needs to.
unglued = Sketchup::ComponentInstance.new(
  definition: window_definition, persistent_id: 80,
  dictionaries: { "dynamic_attributes" => {
    "frametypeid" => "02ud", "lenx" => "40.0", "leny" => "30.0"
  } }
)
record = C.extract(Sketchup::Model.new(entities: [unglued]))["windows"].first
check("an unglued window reports rather than guesses",
      record["host_resolution"] == "unresolved" && record["host_face_id"].nil?)
check("...and still carries its geometry for a Python-side recovery",
      !record["transformation"].nil? && !record["panel_outer_loop"].nil?)

# `null` no longer means "hard to derive" -- it means the size is unreadable,
# which is a reportable failure rather than a shrug (contract §8.3).
sizeless = Sketchup::ComponentInstance.new(
  definition: window_definition, persistent_id: 81,
  dictionaries: { "dynamic_attributes" => { "frametypeid" => "02ud", "lenx" => "n/a" } }
)
record = C.extract(Sketchup::Model.new(entities: [sizeless]))["windows"].first
check("an unreadable lenx/leny gives a null panel loop, not a guess",
      record["panel_outer_loop"].nil?, record["panel_outer_loop"].inspect)

# ---------------------------------------------------------------------------
group "Marshal tables"
# ---------------------------------------------------------------------------

assemblies = marshal_blob([
  ["#", :TYPE, :TABLE],
  ["#", :ROW_DATA, :ARRAY],
  ["#", :TOKENS, %i[id desc assem_num thk U_value int_insul]],
  ["83ud", "WT-1", 1, 0.35, 0.15, false]
])
# ⚠ `vent_ud` and `ihg_ud` decode to a FLAT array with `:TOKENS` at the END.
# Assuming row 3 is the header loses the whole table.
vent = marshal_blob([
  1, 1, 2.5, 1234.0, 0.6, 0.07, 15.0,
  ["#", :TOKENS, %i[vent_sys_ID vent_type_ID room_height V_n50 result_n50 coeff_e coeff_f]]
])
model = Sketchup::Model.new(
  entities: [],
  dictionaries: {
    "DesignPH_dict" => {
      "designPH_version" => "2.1.15",
      "klima_ID" => "US0058a",
      "assemblies_ud" => assemblies,
      "vent_ud" => vent,
      "layer_table_01ud" => marshal_blob([["#", :TOKENS, %i[id desc1 lambda1]], ["01ud", "EPS", 0.032]]),
      "tracker_data" => marshal_blob([["#", :TOKENS, [:x]], [1]]),
      "Dashboard" => true
    }
  },
  path: "/tmp/Some Model.skp"
)
payload = C.extract(model)
tables = payload["tables"]
check("assemblies_ud decodes with its tokens",
      tables["assemblies_ud"]["tokens"] == %w[id desc assem_num thk U_value int_insul],
      tables["assemblies_ud"]["tokens"].inspect)
check("...metadata rows are stripped", tables["assemblies_ud"]["rows"].size == 1)
check("...values are left exactly as designPH stored them",
      tables["assemblies_ud"]["rows"].first == ["83ud", "WT-1", 1, 0.35, 0.15, false])
check("a :TOKENS row at the END is still found",
      tables["vent_ud"]["tokens"].first == "vent_sys_ID")
check("...and the flat scalars become one row",
      tables["vent_ud"]["rows"] == [[1, 1, 2.5, 1234.0, 0.6, 0.07, 15.0]],
      tables["vent_ud"]["rows"].inspect)
check("layer_table_* is a family, matched by prefix", tables.key?("layer_table_01ud"))
check("tables the POC does not consume are listed, not shipped",
      !tables.key?("tracker_data") && payload["counts"]["tables_found"].include?("tracker_data"))
check("non-blob keys are not mistaken for tables",
      !payload["counts"]["tables_found"].include?("Dashboard"))
check("the model's version stamp is read", payload["model"]["designph_versions"] == ["2.1.15"])
check("the climate id is read", payload["model"]["klima_id"] == "US0058a")
check("the file name comes from the .skp path", payload["model"]["file_name"] == "Some Model")

# A blob that will not decode is REPORTED, not dropped -- "table absent" is the
# normal case and must stay distinguishable from "the collector failed".
broken = Sketchup::Model.new(entities: [], dictionaries: {
  "DesignPH_dict" => { "connections_ud" => "BAh_not_actually_marshal" }
})
decoded = C.extract(broken)["tables"]["connections_ud"]
check("an undecodable blob ships as an error", decoded.key?("error"), decoded.inspect)

# ---------------------------------------------------------------------------
group "The whole payload"
# ---------------------------------------------------------------------------

payload = C.extract(Sketchup::Model.new(entities: []))
check("it declares the contract version",
      payload["contract_version"] == C::CONTRACT_VERSION)
check("a real collector run is not marked as a stub", !C.stub?(payload))
check("...and every contract section is present, even when empty",
      %w[contract_version generated_by model counts faces edges windows libraries tables unclassified]
        .all? { |key| payload.key?(key) })
check("the payload is JSON-serialisable", !JSON.generate(payload).empty?)

FileUtils.rm_rf(STUB_LOAD_DIR)

# ---------------------------------------------------------------------------
group "The inline frame/glazing libraries -- model-level, deduplicated (v2)"
# ---------------------------------------------------------------------------

# ⚠ Contract v1 shipped these inside every window's `dynamic_attributes`. On
# Adelphi that is 44,915 characters repeated BYTE-IDENTICALLY on all 46 windows
# -- 2.07 MB of a 2.25 MB payload, against a bridge verified to 4 MB. They are
# library data and belong to the model.
frame_list = "&PH-FRAMES: average thermal quality=01ud&Alumil S.A. - SD95=1806ed04&"
placeholder = "&Launch designPH to edit=01ud&"
lib_definition = Sketchup::ComponentDefinition.new(
  "designPH_Window_Simple 1.2", [],
  { "dynamic_attributes" => { "_glazingtype_options" => "&PH Glazing=01ud&" } }
)
lib_windows = (1..3).map do |i|
  Sketchup::ComponentInstance.new(
    definition: lib_definition, persistent_id: 300 + i,
    dictionaries: { "dynamic_attributes" => {
      "frametypeid" => "01ud", "lenx" => "40.0", "leny" => "30.0",
      # Every instance repeats the same list -- exactly designPH's behaviour.
      "_frametype_options" => frame_list,
      "_glazingtype_options" => i == 1 ? placeholder : "&PH Glazing=01ud&"
    } }
  )
end
payload = C.extract(Sketchup::Model.new(entities: lib_windows))
check("the option lists leave the window records entirely",
      payload["windows"].none? { |w| w["dynamic_attributes"].keys.any? { |k| k.start_with?("_") } },
      payload["windows"].first["dynamic_attributes"].keys.inspect)
check("...and ship once at model level, deduplicated",
      payload["libraries"]["frame_types"] == [frame_list],
      payload["libraries"]["frame_types"].inspect)
# Ruby dedupes; it does not choose. Picking a winner between a real library and
# designPH's placeholder is a judgement call, and those are Python's.
check("distinct values all ship -- Ruby dedupes, it does not choose",
      payload["libraries"]["glazing_types"].sort == [placeholder, "&PH Glazing=01ud&"].sort,
      payload["libraries"]["glazing_types"].inspect)
check("the definition's list is read as well as the instance's",
      payload["libraries"]["glazing_types"].include?("&PH Glazing=01ud&"))
check("a model with no windows still declares the section",
      C.extract(Sketchup::Model.new(entities: []))["libraries"] ==
        { "frame_types" => [], "glazing_types" => [] })

# ---------------------------------------------------------------------------
group "Model naming -- model.path is not the file you opened"
# ---------------------------------------------------------------------------

# ⚠ `Sketchup::Model#path` returns the location the model was last SAVED. On a
# file authored elsewhere that is somebody else's machine: Wellington reports
# `/Users/johnmitchell/.../2523 Weiilington.skp` and Linde a whole
# `C:\Users\greg\OneDrive\...` path. `SKETCHUP_RUNTIME.md` §8.2.
stale = Sketchup::Model.new(entities: [], path: "C:\\Users\\greg\\OneDrive\\Linde - 7.3.25.skp")
check("a Windows path does not become the model name wholesale",
      C.extract(stale)["model"]["file_name"] == "Linde - 7.3.25",
      C.extract(stale)["model"]["file_name"])
check("...and the caller's name wins outright",
      C.extract(stale, "test", "250703 - Linde Residence_COPY")["model"]["file_name"] ==
        "250703 - Linde Residence_COPY")
check("a blank override falls back rather than blanking the name",
      C.extract(stale, "test", "  ")["model"]["file_name"] == "Linde - 7.3.25")

puts "\n#{$failures.zero? ? 'ALL CHECKS PASSED' : "#{$failures} CHECK(S) FAILED"}"
exit($failures.zero? ? 0 : 1)
