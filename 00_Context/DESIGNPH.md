# designPH — Basics

High-level orientation only. For how it stores data, see [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md)
and [`DESIGNPH_FILE_FORMATS.md`](DESIGNPH_FILE_FORMATS.md).

---

## What it is

A SketchUp plugin from the **Passivhaus Institut (PHI)** that turns a SketchUp model into PHPP
input. You model the envelope in SketchUp, designPH classifies the surfaces, runs a simplified
monthly energy balance in-canvas for immediate feedback, and then exports a file that populates
PHPP's **Areas**, **Windows**, and **Shading** worksheets.

It is a *pre-design / early-design* tool, not a certification tool. The stated value is (a) skipping
the tedious manual area take-off into PHPP, and (b) getting a rough specific heat demand while the
massing is still moving. Detailed design, refinement, and certification still happen in PHPP.

- **Website:** <https://passivehouse.com/designph> (the older `designph.org` 301s here)
- **Extension Warehouse:** <https://extensions.sketchup.com/extension/d74d1e31-9d33-40c3-bdc8-6e68c349b4b0/design-ph>
- **Passipedia:** <https://passipedia.org/planning/calculating_energy_efficiency/phpp_-_the_passive_house_planning_package/designph_plugin>

## Authors

From the extension metadata in `designPH.rb`:

- **Creators:** Dave Edwards, Harald Malzer, Dragos Arnautu
- **Copyright:** Passivhaus Institut, 2025
- **Description string:** "Passivhaus pre-planning design and export tool"

Dave Edwards is the author named in the JavaScript headers (`DME_webdialog_lib.js`, "David Edwards 2012"),
and the beta loader lists him alone.

## Version history

Only partially reconstructible. What is directly evidenced:

| Version | Evidence | Notes |
|---|---|---|
| 2.0 / 2.0.0 | `phpp_frames_ud.csv`, `phpp_assemblies_ud.csv` headers | paired with PHPP 9.6 |
| 2.1.10 | `designPH_version` value inside `2523 Wellington.skp` | historical; the live stamp is 2.2.29 |
| 2.1.15 | `adelphi-designph.skp`, `250708.skp` | |
| 2.2.24 | `2414_Bluff Reach.skp` | |
| 2.1.14 | `phpp_*_cert.csv` headers | paired with PHPP 10.5, "December 2022" |
| 2.2 | `PHPP10_climate_monthly.csv` header (`update_250523`) | |
| **2.2.29** | installed release; `designPH.rb`; released **2025-06-24** | the base install on this machine |
| **2.4.0 BETA** | `designPH_beta/preview features/designPH_full_2-4 BETA/sub-version.config` | "Monthly method: Heating and cooling balance" |
| 3.0 | vendor site — released **2026-07-28** | not installed here |

✅ **Confirmed live, 2026-08-21**, from SketchUp's own console on this machine:

```
designPH running version: [none]
designPH loaded version: 2.2.29
beta loaded? true
```

⚠ **The version that WROTE a model and the version READING it are routinely different, and it
matters.** `adelphi-designph.skp` was written by **2.1.15** and is opened here under **2.2.29 with
the beta overlay**. Since designPH's Dynamic-Component formula functions only evaluate while the
plugin is recomputing (§9 of the data model), **derived DC values in an older model can be stale** —
which is the leading explanation for `dynamic_attributes["area"]` disagreeing with `lenx × leny` on
26 of Adelphi's 46 windows. Read the `designPH_version` stamp before trusting any derived value.

**Live version stamps across the whole captured corpus, 2026-08-21** — five real projects, four
designPH versions, none of them the installed one:

| model | designPH stamp | SketchUp that last wrote the file |
|---|---|---|
| `adelphi-designph` | 2.1.15 | 22.0.353 (Mac) |
| `250708` | 2.1.15 | 22.0.353 |
| `2414_Bluff Reach` | 2.2.24 | 23.1.341 (Mac) |
| `250703 - Linde Residence` | 2.2.29 | **25.0.660 (Windows)** |
| `2523 Wellington` | 2.2.29 | **26.1.188 (Mac)** |

Two things worth taking from that table beyond the version spread:

- **Real project files are written by whatever the collaborator had.** Two of five came off machines
  running SketchUp newer than the one reading them, and one off Windows. A tool that assumes its own
  host's versions will meet models that do not.
- ⚠ **The 2.4.0 BETA overlay is what reads them all here**, and it is the version whose UI settled
  the multi-section U-value question (`DESIGNPH_DATA_MODEL.md` §7.2). Its *dialog* was ground truth;
  its *file output* (the `.ppp` beside Adelphi) is a different id space from the 2.1.15 `.skp`.

### ⚠ The `.ppp` and the `.skp` beside it are not two views of one tool

Worth stating flatly because it has now caused one confused investigation. Adelphi's corpus folder
holds a `.skp` written by **2.1.15** and a `.ppp`/PHPP exported by **2.4.0 BETA**. Joining their
assemblies by id matches nothing useful — `83ud`/`84ud`/`85ud` in the model are `01ud`/`07ud`/`13ud`
in the export. **Join by name, and expect only a partial overlap** (3 of 14 on Adelphi). Use the
PHPP as ground truth for *arithmetic and method*, never for identity (`DATA_CONTRACTS.md` §8).

**Note:** designPH 3.0 is current upstream; this machine runs 2.2.29 with the 2.4.0 BETA overlay
active. Anything recorded in these notes describes 2.1–2.4 behaviour and should be re-verified
against 3.0 before being relied on.

### The beta / sub-version mechanism

designPH ships its own patch framework rather than requiring a full reinstall. `sub-version.config`:

```
sub_version_framework = 1.1.5;
// type can be "overlay", "incremental", "cumulative" or "full"
// status can be "RC", "beta", "alpha", "dev"
base_version  = "0.0.0";
patch_version = "2.4.0";
type   = full;
status = beta;
access = scrambled;
description = "Monthly method: Heating and cooling balance";
```

**Important behavioural quirk:** the root loader `designPH.rb` checks for the beta folder *first*
and loads the beta GUI instead of the release one if it is present:

```ruby
if (beta_plugin_folder = Sketchup.find_support_file(File.join("Plugins", "designPH_beta")))
  plugin = SketchupExtension.new("designPH 2.2.29 (base version)", ...)
else
  plugin_folder = Sketchup.find_support_file(File.join("Plugins", "designPH"))
  plugin = SketchupExtension.new("designPH 2.2.29", ...)
end
```

So with both installed you are running the beta, and the Extension Manager still says "2.2.29".
The version actually written into a model can therefore disagree with what the UI reports — the
test model here is stamped `2.4.0 BETA` while its own backup is stamped `2.2.29`.

## Compatibility

- **SketchUp:** v2 supports SketchUp 2017–2025 desktop (Win/Mac). v3.0 supports 2026.
  The 2017 floor is the `WebDialog` → `HtmlDialog` API break, visible in the plugin's own JS comments.
- **PHPP:** separate export writers exist per PHPP version and unit system —
  `designPH_data_pppwrite_PHPP9`, `_PHPP10`, `_PHPP_IP`, `_PHPP_IP8`, `_PHPP_IP9`, `_PHPP_IP10`.
- **Ruby:** whatever the host SketchUp ships. SketchUp 2022 = **Ruby 2.7**.

## Licensing

Commercial, licensed per user by PHI; a demo exists. Certified-component libraries
(`*_cert.csv`) ship with the plugin. Note the presence of `EDU`-suffixed material files
(`designPH_front_material_EDU_*.skm`) — an education licence tier renders surfaces with a
distinct texture.

## Where it lives (this machine)

```
/Applications/SketchUp 2022/SketchUp.app
~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/
├── designPH.rb                 loader stub (also loads the beta, see above)
├── designPH/                   3.6 MB — release 2.2.29
└── designPH_beta/              6.1 MB — beta GUI 1.1.28 + 2.4.0 BETA payload
```

## Use cases (ours)

1. **Early massing feedback** — specific heat demand while geometry is still fluid.
2. **Area take-off into PHPP** — the real time-saver; Areas/Windows/Shading arrive pre-populated.
3. **Shading** — designPH computes reduction factors from actual 3D context geometry, which is
   painful to do by hand in PHPP.

Not a substitute for PHPP for certification, and not a WUFI/Phius path at all.

## The part that matters for us

designPH writes everything into **standard SketchUp attribute dictionaries**, which means the data
**travels inside the `.skp` and is fully readable without designPH installed** — by the SketchUp
Ruby API, the C SDK, or by parsing the file directly. The plugin's own Ruby is encrypted (`.rbe`),
but the data is not obfuscated in any way. See `DESIGNPH_DATA_MODEL.md`.
