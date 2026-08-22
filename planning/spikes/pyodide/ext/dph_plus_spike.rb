# ---------------------------------------------------------------------------
# dph_plus_spike.rb -- loader stub for the DesignPH-PLUS Phase 3 spike
#
# Only `.rb` files sitting directly in `Plugins/` are auto-loaded; subfolders
# are not scanned. Hence the convention: a stub here, the real code in a
# same-named subfolder, and `SketchupExtension` as the bridge -- which is also
# what puts the spike in the Extension Manager so it can be disabled without
# deleting files. Same shape as `bt_inspector` and as designPH itself.
#
# THIS IS SPIKE CODE. It is read-only against the model, it is not v1, and it
# is expected to be deleted after Phase 3's gate is recorded.
# ---------------------------------------------------------------------------
require "sketchup.rb"
require "extensions.rb"

module BT
  module DPHPlusSpike
    PLUGIN_DIR = File.join(File.dirname(__FILE__), "dph_plus_spike").freeze

    extension = SketchupExtension.new(
      "DesignPH-PLUS Phase 3 Spike",
      File.join(PLUGIN_DIR, "main")
    )
    extension.version     = "0.1.0"
    extension.creator     = "BLDGTYP"
    extension.copyright   = "BLDGTYP, LLC 2026"
    extension.description = "Throwaway spike: does Pyodide (CPython in WASM) run inside " \
                            "SketchUp's HtmlDialog? Read-only; writes nothing to the model."
    Sketchup.register_extension(extension, true) # true = load now, not on demand
  end
end
