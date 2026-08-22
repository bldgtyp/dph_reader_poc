# designPH File Formats & On-Disk Conventions

Companion to [`DESIGNPH_DATA_MODEL.md`](DESIGNPH_DATA_MODEL.md), which covers in-model attribute
storage. This file covers what is on disk: the shipped libraries, the ID conventions, the material
files, and the `.skp` binary layout.

---

## 1. Install layout

```
~/Library/Application Support/SketchUp 2022/SketchUp/Plugins/
├── designPH.rb                     loader stub — SketchupExtension registration
├── designPH/
│   ├── designPH_config.rbe         entry point named by the stub
│   ├── designPH_Loader_class.rbe
│   ├── designPH.susig              extension signature (Trimble signing)
│   ├── rbe/                        core: _Entity, _Model_main, _Model_windows,
│   │                               _observers, _DCFunctions, _User, _onload
│   ├── lib/                        _lib_Data, _lib_Data_export, _lib_Climate,
│   │                               _lib_perez_model, _lib_model_shading,
│   │                               _lib_UI_dialog, _lib_notification_observers_*
│   ├── datatables/                 _DataTables_Areas, _assemblies, _components_U,
│   │                               _components_Psi, _TFA, _Shading,
│   │                               _pppwrite_PHPP9 / _PHPP10 / _IP / _IP8/9/10
│   ├── ui/                         dashboard, faceInfoTool, WinTool, toolbars
│   ├── data/                       *.csv — the shipped libraries (§2)
│   ├── materials/                  *.skm — display palette (§5)
│   ├── Components/designPH_library/  *.skp — DC window templates
│   ├── html/                       webdialog templates + JS bridge
│   ├── images/, Resources/         icons, *.strings localisation
└── designPH_beta/                  beta GUI + "preview features/designPH_full_2-4 BETA"
```

**All Ruby is `.rbe`** — Trimble's encrypted extension format (74 files). Not readable, and not
something to attempt to circumvent. Everything in these notes was recovered from data files and from
runtime introspection instead, which turned out to be sufficient.

Note the module names are self-documenting even encrypted: `_pppwrite_PHPP9` vs `_pppwrite_PHPP10`
vs `_pppwrite_PHPP_IP` shows one export writer per PHPP version *and* unit system.

---

## 2. CSV libraries (`designPH/data/`)

| File | Rows | PHPP ver | Contents |
|---|---|---|---|
| `phpp_assemblies_cert.csv` | 124 | 10.5 | PHI-certified construction systems |
| `phpp_assemblies_ud.csv` | 21 | 9.6 | Default/user assembly slots |
| `phpp_frames_cert.csv` | 518 | 10.5 | PHI-certified window frames |
| `phpp_frames_ud.csv` | 103 | 9.6 | User frame slots |
| `phpp_glazings_cert.csv` | 74 | 10.5 | Certified glazings |
| `phpp_glazings_ud.csv` | 103 | 9.6 | User glazing slots |
| `phpp_ventilation_units_cert.csv` | — | 10.5 | Certified MVHR units |
| `PHPP9_climate_monthly.csv` | ~430 KB | 9 | Climate datasets |
| `PHPP10_climate_monthly.csv` | ~687 KB | 10 | Climate datasets, `update_250523` |

### 2.0 ⚠ A large part of the frame and glazing libraries also travels *inside* the model

> ✅ **Superseded in scope, 2026-08-21.** This section describes the DC **option lists**, which
> carry `name=id` pairs and nothing else. They are not the only in-model route: the full numeric
> libraries are in the `frames_ud` / `glazing_ud` **Marshal tables** on 3 of 5 corpus models —
> per-edge U-values, frame widths, and installation and glazing-edge psi values.
> `DESIGNPH_DATA_MODEL.md` §7.0.1. Read the tables when they are there; fall back to the option
> lists, which are present more often, for names only.

*(Measured 2026-08-21 across the five captured corpus models.)*

The CSVs above live in the plugin folder, so the obvious reading is that a `.skp` alone cannot name
its own `frametypeid`. **That is wrong.** designPH writes the frame and glazing libraries onto every
window component as SketchUp Dynamic-Component **option lists**, `&<name>=<id>&<name>=<id>&`:

| key | size on Adelphi | contents |
|---|---|---|
| `_frametype_options` | **39,685 chars** | ~500 entries, down to real products — `Alumil S.A. - SD95 - SWISSPACER ULTIMATE=1806ed04` |
| `_glazingtype_options` | **5,230 chars** | `&PH Glazing=01ud&Single glazing=92ud&Double glazing 4/12mm air/4=93ud&…` |

No U-values and no g-values — it is a **name-for-id mapping**, which is exactly enough to turn a
report line reading `01ud` into one reading `PH Glazing (01ud)` with no library on disk. Bluff Reach
carries **two distinct** frame lists, from being touched by two designPH versions.

Two traps, both paid for:

- ⚠ **It is per-window and byte-identical.** All 46 of Adelphi's windows carry the same 44,915
  characters — 2.07 MB of a 2.25 MB extraction before it was hoisted to model level. It is *library*
  data wearing a window's clothes.
- ⚠ **designPH also writes a placeholder list**, `&Launch designPH to edit=01ud&`, on some
  definitions, claiming the same ids. Merging by "the longer name wins" picks the **placeholder** —
  *Launch designPH to edit* is 23 characters against *PH Glazing*'s 10 — and silently un-names the
  whole library. Merge by how many ids a *list* names.

### 2.1 The header convention

Same self-describing idea as the Marshal blobs. Metadata rows start with `#`:

```
#,designPH_version,2.1.14
#,PHPP_version,10.5
#,library_name,assemblies_cert
#,comment,"Certified Passive House Components:,PHPP 10.5 - December 2022"
#,language,en
#,"❆  Cold climate ❆"                    ← section divider, not metadata
1160cs02,"Izodom 2000 ... Complete Passive System","RO01 - Roof",0.433,0.09,0
```

The climate CSVs go further and name their columns explicitly:

```
#,PHPP_VERSION,10,update_250523
#,DESIGNPH_VERSION,2.2
#,TYPE,TABLE
#,ROW_DATA,ARRAY
#,COL_KEYS,climate_id,climate_status,location_number,country_code,climate_region,
          climate_location,climate_comment1,climate_comment2,latitude,longitude,
          elevation,summerTempDif,monAvgTemp_Jan,...
#,COL_GROUP_KEYS,monAvgTemp,monRadNorth,monRadEast,monRadSouth,monRadWest,
          monRadHori,avgDewTemp,avgSkyTemp,heatLoad1,heatLoad2,coolLoad1,coolLoad2,PER
```

`COL_GROUP_KEYS` names the repeating monthly blocks — 12 columns each. Note `#,TYPE,TABLE` and
`#,ROW_DATA,ARRAY` are **verbatim the same markers** used inside the Marshal blobs. One table
abstraction, two serialisation media.

**Parsing caution:** `#` rows are used for two different purposes — key/value metadata *and* visual
section dividers (the snowflake/sun rows). Discriminate on the number of fields and on whether
field 1 is a known key, not on the `#` alone.

### 2.2 Ventilation and climate lookups

Climate rows are keyed by `climate_id`, which appears in the model as `klima_ID`. See §3.3.

---

## 3. ID conventions

designPH uses one flat ID space across all libraries. Two shapes.

### 3.1 User-defined: `NNud`

Zero-padded number + literal `ud` ("user defined").

- `01ud`–`82ud` — user slots, empty by default
- `83ud`–`99ud` — designPH's shipped defaults, e.g.
  `83ud "PH External wall"`, `84ud "PH Roof"`, `85ud "PH Floor"`, `86ud "PH Basement wall"`,
  `87ud "Partition wall to neighbour"`, `88ud "Wall to zone X"`, `89ud "PH External Door"`,
  `93ud`–`99ud` existing-construction presets (`"Extg-Solid Brick 38cm"` etc.)
- `90ud`–`92ud` are deliberately blank spacer rows

**Separate ranges per library.** Thermal-bridge connections use `101ud`–`205ud`; ventilation uses
`97ud`. So `97ud` means different things depending on which table you are in — **the ID is only
unique within its library.** Do not build a global lookup keyed on the bare ID.

⚠ **And the id space is not shared with the `.ppp`/PHPP side either.** Adelphi's `.skp` names its
assemblies `83ud`/`84ud`/`85ud` where the PHPP export calls the same three constructions
`01ud`/`07ud`/`13ud` — the `.skp` is designPH 2.1.15, the `.ppp` beside it is 2.4.0 BETA, and they
renumber. **Join designPH data to PHPP data by NAME, never by id** (`DATA_CONTRACTS.md` §8).

### 3.2 Certified: `NNNN` + type + climate

```
1428wc01
└─┬─┘└┬┘└┬┘
  │   │  └─ PHI climate zone, 2 digits
  │   └──── component type, 2 letters
  └──────── PHI certificate number, 4 digits
```

**Climate zone codes** — mapped from the section dividers in `phpp_frames_cert.csv`:

| Code | Zone |
|---|---|
| `01` | ❆❆ arctic |
| `02` | ❆ cold |
| `03` | ❆☀ cool, temperate |
| `04` | ☁☀ warm, temperate |
| `05` | ☀ warm |
| `06` | *(hot — no certified products in this dataset)* |
| `07` | ☀☀☀ very hot |

**Type codes** — each identified from an actual row in the shipped libraries:

*Frames* (`phpp_frames_cert.csv`): `wi` window (212 rows, the common case) · `fx` fixed ·
`cw` curtain wall · `ed` exterior door · `sl` sliding · `ws` window/sash · `wc` window (climate-rated
variant) · `ds` door, sliding/entrance · `ic` roof-light industrial · `sk` skylight/hatch ·
`rw` roof window (e.g. VELUX) · `og` opening light/vent flap · `pm` mounting/installation system
(e.g. Soudal SoudaFrame — an *install* component, not a frame)

*Glazings*: `gl` glazing · `ed` door panel · `ds` door · `as` attic stair (e.g. Wellhöfer PH loft ladder)

*Assemblies*: `cs` construction system · `wa` wall · `rc` roof construction ·
`fs` foundation slab system · `es` refurbishment/EnerPHit system

**Data quirk:** in `phpp_assemblies_cert.csv` the suffix `03` appears under two different section
headers — one reading "Cool-temperate", one reading "Warm-temperate". That is an inconsistency in
PHI's own shipped data. **Trust the numeric suffix, not the section divider.**

### 3.3 Climate IDs

```
HU0001b        US0058a        AD0001a
└┬┘└─┬┘┬       
 │   │  └─ revision letter (a, b, …) — dataset revision, not a variant
 │   └──── 4-digit location number, unique within country
 └──────── ISO 3166-1 alpha-2 country code
```

Stored in the model as `klima_ID`, with the display name in `Klima_Standort`.

**Edge case:** the test model carries `klima_ID = "DE-9999"` — hyphenated, and `9999` is outside the
normal range. This is the **user-defined / custom climate** form and does **not** match a row in the
shipped CSVs. A reader that assumes `klima_ID` resolves against `PHPP10_climate_monthly.csv` will
fail on any model using a custom climate.

---

## 4. `.skp` binary layout

Undocumented and reverse-engineered. Validated only against the three models in
`DESIGNPH_DATA_MODEL.md` §2, on SketchUp 2022-era files. **The supported routes are the Ruby API and
the C SDK** — this is for reconnaissance.

### 4.1 Container

SketchUp 2014+ `.skp` is a **zip archive** behind a short header:

```
bytes 0..68   "SketchUp Model" + version string, UTF-16LE
byte  69+     zip archive
```

⚠ **A raw byte scan of the `.skp` finds nothing.** Everything is inside the zip — searching the
container for a string you know is in the model returns zero hits and means nothing. This wasted a
round of investigation into `Model#path`: the embedded paths were there all along, in `model.dat`.

```
model.dat                  ← the entire model, uncompressed (17.4 MB in Wellington)
meta/meta.dat
meta/model_thumbnail.png
meta/preview_thumbnail.png
materials/<name>/material.xml + thumbnail.jpg
thumbnails/<component>.png
styles/...
```

```python
import zipfile
model_dat = zipfile.ZipFile("model.skp").read("model.dat")
```

**Pre-2014 `.skp` is not a zip** — it is a flat binary stream, and `zipfile` raises `BadZipFile`.
`skp_attr_dump.py` falls back to reading the file directly, but **the opcodes below were only
validated on 2014+ files**: run against `BLDGTYP - Sketchup Sample DesignPH ready Model.skp` the
tool exits cleanly and finds *zero* dictionaries. That model genuinely has no designPH data, so
this is not proof of a parser failure — but it is also not proof the old format uses the same
encoding. **Treat a zero-dictionary result on a pre-2014 file as inconclusive, not as "no data".**

### 4.2 Attribute records inside `model.dat`

Length-prefixed records with 2-byte opcodes. All integers little-endian.

| Opcode | Meaning | Layout |
|---|---|---|
| `B4 36` | dictionary name | `B4 36 <uint32 len> <ascii name>` |
| `B6 36` | attribute key | `B6 36 <uint32 len> <ascii name>` |
| `A4 38` | value wrapper | `A4 38 <uint32 total_len>` then one value record; `total_len == 0` means **nil** |
| `AD 38` | String | `AD 38 <uint32 len> <bytes>` |
| `A7 38` | Integer | `A7 38 04 00 00 00 <int32>` |
| `A9 38` | Float | `A9 38 08 00 00 00 <double>` |
| `AA 38` | Boolean | `AA 38 01 00 00 00 <byte>` |

Cross-checked: `total_len` is always `2 + 4 + payload`, e.g. `"Default"` → `13 = 2+4+7`;
Integer → `10 = 2+4+4`; Float → `14 = 2+4+8`; Boolean → `7 = 2+4+1`.

Keys follow their dictionary marker in file order, so association is positional.

### 4.3 Traps

- **Regex `.` does not match `\n` in Python.** The length field is four raw bytes; a name of length
  10 gives `0A 00 00 00`, and `re.finditer(rb'\xb6\x36(....)', buf)` **silently skips it**. This cost
  us `tempZoneID`, `assemblyID`, and `tempZoneAuto` on the first pass and led to a wrong initial
  conclusion about the schema. **Always pass `re.DOTALL`.**
- **Strings are mixed encoding.** Dictionary and key names are ASCII; SketchUp's own model strings
  (layer names, component names, DC formulas) are UTF-16LE. Scan for both.
- **macOS `strings(1)` has no `-e` flag.** Use Python for UTF-16 extraction.
- **`model.dat` holds historical state.** Key counts exceed live entity counts. It is a union over
  the file's history, not a snapshot — see `DESIGNPH_DATA_MODEL.md` §8.7. ⚠ **But it is a union in
  one direction only.** A *live* count can legitimately exceed it, and for two independent reasons:
  the offline reader counts **entities carrying an area-group key** while a live walk counts
  **placements of everything carrying a `DesignPH_dict`**. On Bluff Reach that is 576 live
  dict-carriers against 293 offline records; on `250708`, 2456 placements against 1781 entities.
  Both reconcile exactly once compared like with like. "Live ≤ offline" is not a safe invariant.

### 4.4 `meta/meta.dat` — which SketchUp wrote the file

`meta.dat` carries a version list, and its first entry is the writing version:

```
25.0.660v   SketchUp Client (Windows) 24.0.553 … 25.0.660      ← 250703 - Linde Residence
26.1.188v   SketchUp Client (Mac) 23.1.341, 26.1.188           ← 2523 Wellington
22.0.353v   SketchUp Client (Mac) 22.0.353                     ← adelphi-designph
```

Useful because it is **offline, cheap, and answers questions about a file's provenance** that the
live API will not. It is how the correlation between "SketchUp 24+/26 wrote this" and "`Model#path`
came back stale" was found at all (`SKETCHUP_RUNTIME.md` §8.2) — n=5, a correlation, not a mechanism.

### 4.5 ⚠ `model.dat` stores absolute filesystem paths — other people's

Every imported component remembers where it came from, and the model remembers where it was last
saved. Both survive copying, and both are somebody else's machine:

```
/Users/johnmitchell/Dropbox/bldgtyp/2523 Wellington/08_DesignPH/2523 Weiilington.skp
C:\Users\greg\OneDrive\Documents\AA PROJECTS\Linde\…\Linde Residence - 2.0 kBTU - 7.3.25.skp
/Users/darnautu/AppData/Local/Temp/Component.skp
/Users/tully/AppData/Local/Temp/tree_2.skp
```

Two consequences:

- **`Sketchup::Model#path` can return the stored one** rather than the file you opened
  (`SKETCHUP_RUNTIME.md` §8.2). That is where these strings were traced from.
- ⚠ **A `.skp` handed to a third party leaks the author's directory structure and usernames.** Not a
  DesignPH-PLUS problem, and worth knowing before the corpus goes anywhere.

⚠ **And there is a second, independent leak inside the designPH data itself**: the `tracker_data`
Marshal table logs every calculation run with a **`username`**, a timestamp and the designPH build —
188 rows on one corpus model. Filesystem paths and analytics rows are two different vectors with two
different fixes; **both** have to be stripped before any corpus file leaves this repo.
`DESIGNPH_DATA_MODEL.md` §7.0.2.

`tools/skp_attr_dump.py` implements all of this, with the traps handled.

---

## 5. Material files (`designPH/materials/`)

19 `.skm` files. A `.skm` is a **zip**:

```
document.xml            the material definition
documentProperties.xml  title, timestamps, thumbnail ref
references.xml
doc_thumbnail.png
ref/<texture>.png
```

```xml
<mat:material name="designPH reverse material - Tomato" type="2"
              colorRed="255" colorGreen="99" colorBlue="71"
              colorizeType="1" trans="0.5" useTrans="0" hasTexture="1">
  <mat:texture textureFilename="/Users/Shared/designPH_project folder [COPY]/..."
               xScale="50" yScale="50" avgColor="4282868735">
```

Naming: `designPH_{front|reverse}_material[_EDU]_<areaGroup>.skm`, numbered `1, 7, 8, 9, 10, 11, 14`
— the PHPP area groups. `reverse_*` are striped textures flagging reversed face normals; `_EDU_*` is
the education-licence palette.

**Note** the `textureFilename` still carries the developer's absolute build path. Harmless, but a
reminder that `.skm` files leak whatever the authoring machine had.

---

## 6. Reproducing this investigation

```bash
# 1. unpack the model
python3 -c "import zipfile; open('model.dat','wb').write(zipfile.ZipFile('X.skp').read('model.dat'))"

# 2. dump every attribute dictionary
uv run tools/skp_attr_dump.py X.skp

# 3. decode a Marshal blob
ruby -rbase64 -rpp -e 'pp Marshal.load(Base64.decode64(File.read(ARGV[0])))' blob.b64
```

For **current** model state, prefer the BT Attribute Inspector extension inside SketchUp — the
binary parse cannot distinguish live entities from historical ones.
