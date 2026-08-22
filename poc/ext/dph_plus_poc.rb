# ---------------------------------------------------------------------------
# dph_plus_poc.rb -- loader stub for the DesignPH-PLUS proof of concept
#
# Only `.rb` files sitting directly in `Plugins/` are auto-loaded; subfolders
# are not scanned. Hence the convention: a stub here, the real code in a
# same-named subfolder, and `SketchupExtension` as the bridge -- which is also
# what puts the POC in the Extension Manager so it can be disabled without
# deleting files. Same shape as `bt_inspector` and as designPH itself.
#
# ⚠ INTERNAL ONLY. This build is never distributed outside BLDGTYP: the AGPL
# question (`planning/RESULTS/PHASE-3_licence-question.md`) blocks *release*,
# and sharing the `.rbz` is the act that would change the legal footing.
# See `planning/POC/00_POC_OVERVIEW.md` §2.3.
#
# Read-only against the model, and never writes `DesignPH_dict`.
# ---------------------------------------------------------------------------
require "sketchup.rb"
require "extensions.rb"

module DphPlusPoc
  PLUGIN_DIR = File.join(File.dirname(__FILE__), "dph_plus_poc").freeze

  extension = SketchupExtension.new(
    "DesignPH-PLUS POC",
    File.join(PLUGIN_DIR, "main")
  )
  extension.version     = "0.1.0"
  extension.creator     = "BLDGTYP"
  extension.copyright   = "BLDGTYP, LLC 2026"
  extension.description = "Proof of concept: reads a designPH model and writes HBJSON plus a " \
                          "translation report. Internal build -- not for distribution. " \
                          "Read-only; writes nothing to the model."
  Sketchup.register_extension(extension, true) # true = load now, not on demand
end
