# Typing code against the .blend file it runs on

Research note, 2026-11-18.

**Question.** Could ty-blender read `.blend` files to type the add-on and script code that runs against them? What can it read cheaply, how does code name the file it runs against, which approach fits ty, and how should the result present itself, given that a script can change the data and run against other files?

Conventions: `blender/` is the Blender checkout at the repo root (commit `71b11d84c80`). Its `.blend` files are Git LFS pointers (131-byte text files). `.cache/blender-src/main/` is the same commit with the LFS content fetched, and every measurement below uses it. Source paths without a prefix are relative to `blender/source/blender/`. `ty/` means `ty-blender/ruff-blender/crates/`. The probe is a 300-line read-only Python script (stdlib, plus the system `libzstd` through `ctypes`). Its parser is kept, trimmed, as `prototypes/blend_typing/blendread.py` (§8). It parses the header, the BHeads and the SDNA, then extracts the tiers in §2.

## 1. Answer

1. **The format is self-describing and cheap to read.** Every file carries its own struct layout (the DNA1 block). A reader needs no Blender version table to find `ID.name`, `Object.type`, `bNode.idname` or a socket's `identifier`. The probe read 2155 of the 2185 test and asset files from Blender 2.55 through 5.4: median 30 ms per file and 65 s for the corpus, in pure Python. The SDNA decode took most of that time (19 ms median). It failed on only 26 big-endian files from Blender 1.x/2.x, which Blender 5.0 refuses to open anyway, and 4 deliberately invalid files.
2. **Most files are compressed.** 1722 of the 2185 files are zstd, 172 gzip and 291 uncompressed. A reader needs zstd and gzip support. The SDNA is written last (`blenloader/intern/writefile.cc:1879-1892`), so even the cheapest fact means decompressing and scanning the whole file.
3. **The cheap tiers are the useful ones.** ID names per type, an object's type with its data's type (`Object.type` plus the `Object.data` pointer), node trees with their nodes and sockets, modifiers and constraints by name and struct, and custom-property names and value types are each a few lookups per block. The facts that break across versions are not in the bytes but in their meaning. A file is *versioned on load*, so an old file's raw facts can differ from what the script sees (§2.7).
4. **Code names its file statically less often than one would hope.** In `blender/tests/python/`, 142 of 217 `open_mainfile` calls name a literal `.blend` (53 of them `empty.blend`, which holds nothing useful). 39 reopen a file the test wrote itself, and 36 are computed. None of the 14 `libraries.load` calls in `tests/python/` or `scripts/` has a static path. 23 CMake test definitions pass a literal `.blend` positionally. One more runs `geo_node_test.py` against every one of the 431 files it globs (§3).
5. **Recommendation:** an offline extractor that writes a text manifest (B), bound to scripts by an explicit `[tool.blender]` mapping (D), and read by ty through `source_text`, so salsa tracks it like `pyproject.toml`. Everything typed from it is reported under a new Assumption rule, `blender-assumed-blend-content`. Reading the binary inside ty (A) is the long-term form. It needs a byte-reading `System` method that ruff_db does not have (§4). The gain in `check:blender` is modest (about 100-175 of the 668 test-side `unchecked-pointer` reads). The larger value is in the editor: key completion for `bpy.data.objects["…"]`, and `nodes["Principled BSDF"].inputs["Base Color"]` typed `NodeSocketColor`.

## 2. The file format, from the source

### 2.1 Header

Two layouts, told apart by byte 7 (`scripts/modules/_blendfile_header.py:85-130`, `blenloader_core/BLO_core_blend_header.hh:21-40`, decoder `blenloader_core/intern/blo_core_blend_header.cc:30-110`):

| Format | Size | Bytes | Block header |
|---|---|---|---|
| 0 (legacy) | 12 | `BLENDER`, `_`/`-` (4/8-byte pointers), `v`/`V` (little/big endian), 3 version digits (`305`) | `BHead4` or `SmallBHead8` |
| 1 | 17 | `BLENDER`, `17` (header size), `-`, `01` (format version), `v`, 4 version digits (`0405`) | `LargeBHead8` |

Blender writes format 1 when the system is little-endian with 8-byte pointers, unless the developer option `write_legacy_blend_file_format` is set (`writefile.cc:1675-1708`, `BLO_core_blend_header.hh:46`). Of the 2155 files the probe parsed, 758 have the 17-byte header and 1397 the 12-byte one.

### 2.2 BHead blocks

The file is a run of blocks, each a BHead followed by `len` bytes (`blenloader_core/BLO_core_bhead.hh:16-52`):

| Variant | Fields in file order |
|---|---|
| `BHead4` | `int code, len; uint old; int SDNAnr, nr` (20 bytes) |
| `SmallBHead8` | `int code, len; uint64 old; int SDNAnr, nr` (24 bytes) |
| `LargeBHead8` | `int code; int SDNAnr; uint64 old; int64 len; int64 nr` (32 bytes) |

- **code**: a two-letter ID code for an ID block (`OB\0\0`, `ME\0\0`, ...; `makesdna/DNA_ID_enums.h:137-180`), or `DATA`, `GLOB`, `DNA1`, `TEST` (thumbnail), `REND`, `USER`, `ENDB` (`BLO_core_bhead.hh:74-108`). Two non-obvious codes: screens are written with the deprecated `SN` (`blenkernel/intern/screen.cc:217`), and linked IDs are written as `ID` placeholder blocks that hold only an `ID` struct (`writefile.cc:1383`, `ID_LINK_PLACEHOLDER` in `DNA_ID_enums.h`).
- **old**: the block's identity. Every pointer stored inside a struct is replaced by such an identity on write (`writefile.cc:955-966`), so pointer following is a `dict` lookup from `old` to block. On disk the identities are *stable ids* seeded from a hash of the owning ID's name and library (`writefile.cc:640-663`, `821-870`). They are not memory addresses, they are unique file-wide, and they stay the same when an unchanged file is re-saved.
- **SDNAnr / nr**: the struct type of the block's data, and how many of them it holds.
- The legacy end marker can be 8 bytes (`_blendfile_header.py:215-227`).

Order (`writefile.cc:42-60`, `1840-1898`): header, `REND` (frame range and scene name, readable without the DNA: `writefile.cc:1200-1204`), `TEST`, `GLOB`, every local ID followed by its `DATA` blocks, libraries and their placeholders, `USER` (preferences files only), `DNA1` last, `ENDB`.

### 2.3 DNA1: the SDNA block

`SDNA` magic, then `NAME` (count, NUL-terminated member names such as `*next`, `name[258]`, `(*func)()`), `TYPE` (count, type names), `TLEN` (a `short` size per type), `STRC` (count, then per struct: `short type, short nfields`, and a `(type, name)` pair per field), with 4-byte alignment between sections, counted from the start of the block (`makesdna/intern/dna_genfile.cc:56-82`, parser `381-520`).

**Self-describing: yes, with three caveats.**

- Offsets follow from the sizes and names alone (`*` is a pointer of the header's size, `[n]` an array). Blender itself takes the `ID.name` offset from the file's SDNA, not from its own headers (`blenloader/intern/readfile.cc:948-950`). The probe confirms that a version table is not needed: `ID.name` is `name[24]` in 43 old files, `name[66]` in 1352 and `name[258]` in 760 (all 5.x). `ID` gained `asset_data` before `name`, which moved the offset (`makesdna/DNA_ID.h:416-434`).
- **Names in the file are the *static* (old) names.** `dna_rename_defs.h` lists 277 renames that exist only in C++: a file stores `Library.name` for what C++ calls `filepath` (`makesdna/intern/dna_rename_defs.h:132`), `Lamp` for `Light` and `Sequence` for `Strip` (`:51-60`), and `bNode.type` for `type_legacy` (`:282`). A reader keyed on the static names is stable across versions. A reader keyed on today's C++ names breaks. The probe hit this with `Library.filepath`.
- Blender patches some old SDNAs before using them (`blo_do_versions_dna`, `readfile.cc:941-943`; `blenloader/intern/versioning_dna.cc`), plus one inline hack for `gravity[3]` (`dna_genfile.cc:439-449`). This matters only for pre-2.5 files.

Since 4.x the SDNA is a subset holding only the structs the file uses (`DNA_sdna_encode_subset`, `dna_genfile.cc:779`). It is about 117-135 KB with 800-1000 structs. Its bytes differ from file to file, so caching by Blender version does not work, but caching by a hash of the DNA1 bytes does.

`ListBaseT<T>` is a C++ template, but the SDNA records it as plain `ListBase` (`first`, `last`), as the probe saw.

### 2.4 Compression

- **Read**: the first bytes pick plain, gzip (`1f 8b 08`) or zstd (frame or skippable-frame magic) (`blenloader_core/intern/blo_core_file_reader.cc:40-62`, `blenlib/intern/fileops_c.cc:259-275`).
- **Write**: only zstd, when "Compress" is on (`G_FILE_COMPRESS`, `writefile.cc:2204-2207`; preference `use_file_compression`, `makesrna/intern/rna_userdef.cc:7717`). It writes 1 MB chunks at level 3 (`writefile.cc:166-169`) plus a seek table in zstd's seekable format (`writefile.cc:296-297`). gzip files come only from older Blenders.
- In the corpus, compressed files are about 5.9× smaller (median). `geometry_nodes_essentials.blend` is 705 KB on disk and 9.3 MB decompressed.
- In Rust, `zstd` and `flate2` are already in ty's dependency graph through `zip` (`ty/ty_vendored/Cargo.toml:27-28`).

### 2.5 Endianness and pointer size

- **Endianness**: Blender 5.0 refuses big-endian files with "support for these files has been removed in Blender 5.0" (`readfile.cc:1270-1278`), so a reader can do the same.
- **Pointer size**: 4-byte pointers occur only in old legacy-header files. Blender narrows 64-bit ids to 32 bits when needed (`BLO_core_bhead.hh:118-132`). A reader that keeps `old` as a `u64` needs neither conversion.

### 2.6 ID blocks

Every ID struct starts with `ID id;` (`DNA_ID.h:416-526`):

- `name[258]`: two bytes of type code, then the name (`MAX_ID_NAME 258`, `DNA_ID.h:368`; `GS()` reads the code, `:411-414`). Before 5.0 it was 66 bytes, as the probe saw.
- `lib`: points to the owning `Library` (an `LI` block, whose path is the static member `name`). It is null for local data.
- `properties` and, since 5.0, `system_properties`: IDProperty groups (§2.7, tier 5).

### 2.7 What each typing fact costs and what breaks it

All tiers need the BHead scan and the SDNA. What a tier adds per block is small: the probe's node-tree pass over 1815 nodes and 10 863 sockets took 35 ms in Python, and the corpus median is 0.26 ms.

| Tier | DNA structs and fields | What breaks across versions |
|---|---|---|
| 1. ID names per type | BHead `code` + `ID.name[2:]`. Linked IDs: `ID` placeholder blocks + `ID.lib` → `Library.name` | Name length (24/66/258 bytes: read from the SDNA). Codes are stable (`DNA_ID_enums.h:137-180`); `ID_SCRN`/`SN` and legacy `GD` grease pencil exist. Blender's own name lister is this tier: `BLO_blendhandle_get_datablock_names` (`blenloader/intern/readblenentry.cc:123-148`), behind `libraries.load`'s `data_from` (`python/intern/bpy_library_load.cc:583-602`). |
| 2. `Object.type`, `Object.data` | `Object.type` (`short`, `ObjectType`, `makesdna/DNA_object_types.h:97-127`), `Object.data` (`ID *`, follow `old` → block `code`) | The number → RNA identifier map (`rna_enum_object_type_items`, `makesrna/intern/rna_object.cc:221`) is a table, though the values are stable. `CU` data is shared by `CURVE`/`SURFACE`/`FONT`, so `type` is needed, not only the data code. Legacy grease pencil (`OB_GPENCIL_LEGACY`) is converted to `GREASE_PENCIL` on load (`blenkernel/intern/grease_pencil_convert_legacy.cc:2917`). |
| 3. Node trees | `bNodeTree.idname`, `.nodes` (ListBase of `bNode`); `bNode.idname`, `.name`, `.inputs`/`.outputs` (ListBase of `bNodeSocket`); `bNodeSocket.idname`, `.identifier`, `.name`, `.flag` (`SOCK_UNAVAIL`) (`makesdna/DNA_node_types.h:1448-1480`, `1642-1700`, `1892-1930`). Trees are `NT` blocks, or `DATA` blocks with SDNA `bNodeTree` when embedded in a material, world or scene | `bNode.idname` is missing before 2.66 and is filled by versioning (`blenloader/intern/versioning_260.cc:2360-2362`). Versioning renames idnames and sockets: Mix RGB → `ShaderNodeMix` (`versioning_300.cc:1936`), Principled `Specular` → `Specular IOR Level` (`versioning_400.cc:1156`), `Subsurface Color` folded away (`versioning_400.cc:821`). On load, built-in nodes get their sockets rebuilt from the running Blender's declarations (`blenkernel/intern/node.cc:5574-5592`, `node_tree_update.cc:779-789`). |
| 4. Modifiers, constraints | `Object.modifiers` → each block's **SDNA struct name** (`SubsurfModifierData`) + `ModifierData.name`, `.type` (`makesdna/DNA_modifier_types.h:169-172`); `Object.constraints` → `bConstraint.name`, `.type`, `.data` → struct name (`makesdna/DNA_constraint_types.h:669-692`); pose-bone constraints via `bPose` | Struct name → RNA class (`SubsurfModifierData` → `SubsurfModifier`) is a per-version table (`rna_enum_object_modifier_type_items`, `makesrna/intern/rna_modifier.cc:46`; `rna_Modifier_refine`). Struct names are static names, so they are stable. |
| 5. Custom properties | `ID.properties`, `ID.system_properties` → `IDProperty` group; children `name[64]`, `type` (`STRING 0, INT 1, FLOAT 2, ARRAY 5, GROUP 6, ID 7, DOUBLE 8, IDPARRAY 9, BOOLEAN 10`, `makesdna/DNA_ID_enums.h:25-38`), `subtype` (element type of an array), `data.group` for nested groups (`DNA_ID.h:131-170`) | Before 5.0 there was one group. Loading an old file copies it into `system_properties` (`versioning_500.cc:96-103`), so in a 5.x file saved from an old one both groups repeat (the probe's `modifiers.blend`: 203 + 203). |
| 6. Scenes, collections, view layers | `SC` blocks; `Scene.view_layers` → `ViewLayer.name`, `.basact` → `Base.object` (the active object after loading); `Scene.master_collection`; `GR` blocks (`makesdna/DNA_scene_types.h:3000-3002`, `makesdna/DNA_layer_types.h:262-270`, `:195`) | `view_layers` is missing before 2.80: 398 corpus files (2.5x-2.7x) have none. |
| 7. Linked libraries | `LI` blocks (`Library.name` = path, `packedfile`); `ID` placeholders with `ID.lib` | Indirectly linked data appears only as placeholders. A missing library still yields IDs, but empty ones. |

Probe output, two files:

```
library_test_scene.blend (2.63, zstd):  MAGreenMaterial <- //libraries/indirect_datablocks.blend
                                        OBMonkey        <- //libraries/direct_linked_A.blend   (9 placeholders, 3 LI)
render/shader/bevel.blend (3.5): OB Plane: type 1 (MESH), data ME, modifiers [('SubsurfModifierData', 'Subsurf')]
  ShaderNodeBsdfPrincipled 'Principled BSDF' inputs: NodeSocketColor 'Base Color', NodeSocketFloatFactor 'Specular', ...
```

The last line is the versioning hazard. `Specular` exists in this 3.5 file, but a script running in 5.x sees `Specular IOR Level`.

**What is not in the file.**

- The *definitions* of Python properties. `bpy.props` values on an ID live in `system_properties` (`makesrna/intern/rna_access.cc:577-589`, `RNA_struct_system_idprops`, `:323-344`), as bare IDProperties: a name, a storage type and a value. The declared type, enum items, `update` callbacks and the property group class are not stored. So `scene.my_addon_settings` can be confirmed as a group that holds a key `count` of type INT, not typed as the add-on's `PropertyGroup`. The add-on's annotations already give that type (`properties` feature).
- Runtime data: the depsgraph and evaluated meshes, `typeinfo` pointers, anything under `runtime`, the window manager's IDProperties (never written, `blenkernel/intern/lib_id.cc:2973-2981`).
- What add-ons or `load_post` handlers create after loading.

### 2.8 `tools/modules/blendfile.py`

A 1108-line pure-Python reader, upstream of Blender Asset Tracer (`blender/tools/modules/blendfile.py:6-11`). It does:

- header and BHeads (through `_blendfile_header.py`), SDNA decode (`decode_structs`, `:164`), a `old` → block map (`:108-109`);
- typed field access by path and pointer following (`get`, `get_pointer`, `:322-483`), and writing fields back (`set`, `:437`);
- gzip and zstd by decompressing to a temp file (`:1064-1108`). zstd needs the third-party `zstandard` module (`:30`).

Users in the tree: `tools/utils/blend2json.py` (dumps a file to JSON with name filters, `:1-60`) and `tools/utils/blender_theme_as_c.py`. It has no notion of IDs, ListBase traversal or RNA mapping: those ~100 lines are what the probe added. It is GPL-2.0-or-later, like the rest of Blender. An extractor that imports it from the Blender checkout, rather than vendoring it, keeps the licensing question out of the suite.

## 3. How code ties to a file

Counted with an AST pass over `blender/tests/python/` (329 files) and `blender/scripts/`:

| `bpy.ops.wm.open_mainfile(filepath=…)` | Calls | Files |
|---|---:|---:|
| literal `.blend` name (mostly `args.testdir / "x.blend"`) | 89 | 22 |
| literal `empty.blend` (then builds its own data) | 53 | 12 |
| module constant holding a literal | 5 | 5 |
| a file the test wrote (`output_work_path`, temp dirs) | 39 | 7 |
| computed (loops, scenario dicts, parameters) | 31 | 20 |
| **total** | **217** | **55** |

- `bpy.data.libraries.load`: 9 calls in `tests/python/` and 5 in `scripts/` (`pose_library/functions.py:23,49`, `operators.py:258`), none with a static path.
- **CMake** (`blender/tests/python/CMakeLists.txt`). `add_blender_test` runs Blender with `--background --factory-startup` (`blender/tests/CMakeLists.txt:56-59`) and passes a `.blend` positionally. 23 definitions name one literal file (`:547`-`:1679`, for example `modeling/modifiers/modifiers.blend` → `modifier_test` scripts). One `file(GLOB …)` runs `geo_node_test.py` against every `.blend` in its directories (`:1356-1364`), 431 files. 71 definitions pass `--testdir`, which the scripts join with literal names.
- **Data lookups that a file could type**: 490 `bpy.data.<collection>["literal"]` (316 of them `objects`, 42 `materials`, 41 `node_groups`), 28 `.get("literal")`, 48 `nodes["literal"]`, 182 `inputs`/`outputs["literal"]` and 9 `modifiers["literal"]` in `blender/tests/`.
- **Add-ons and app templates**: the 12 core add-ons ship no `.blend` (`find blender/scripts/addons_core -name '*.blend'`: 0), and neither do this suite's test add-ons. The five system app templates each ship a `startup.blend` (`blender/scripts/startup/bl_app_templates_system/*/startup.blend`). Blender loads it in place of the default startup file (`windowmanager/intern/wm_files.cc:1428-1439`), and four of them have an `__init__.py` that runs against it. Extensions on the platform do ship `.blend` assets (asset libraries, node-group packs), but always loaded through a computed path (`os.path.join(os.path.dirname(__file__), …)`) with `libraries.load` or `append`.

So the file can be found statically in two places. For test-style scripts it is the CMake line, or `open_mainfile` with a literal (about 94 of 217 calls, leaving out `empty.blend`). For app templates it is the template folder. For add-ons a static analysis can almost never find it: an explicit declaration is the only general route.

## 4. Approaches

ty's model, as it matters here:

- Files are salsa inputs (`File` with a `revision` from mtime, `ty/ruff_db/src/files.rs:357-381`). Every changed path, `.blend` included, is synced into salsa by the watcher (`ty/ty_project/src/db/changes.rs:232-247`).
- Derived facts are `#[salsa::tracked]` functions. When an input changes, salsa recomputes only what depends on it, and an unchanged result does not invalidate dependents.
- `ruff_db::System` reads text only (`read_to_string`, `ty/ruff_db/src/system.rs:130`). `ty_blender` already reads `blender_manifest.toml` and `pyproject.toml` this way, through `source_text` (`ty/ty_blender/src/metadata.rs:76-79`, `ty/ty_blender/src/discovery.rs:7-9`).

### (A) A Rust reader in `ty_blender`, a tracked query per file

`#[salsa::tracked] fn blend_facts(db, file: File) -> Option<Arc<BlendFacts>>` decompresses, scans, decodes the SDNA and keeps only tiers 1-6, about a few KB per file. A second query maps a script to its files (D or inference).

- **Pros**: always current. Re-saving the file reruns only this query, and if the facts are equal (renaming a vertex changes nothing), salsa stops there. No extra step for the user. The LSP gets completions straight away.
- **Cons**: binary input does not fit `System`. Either add `read_to_bytes` to the trait and its three implementations (`os.rs`, `memory_fs.rs`, `test.rs`), well beyond a one-line hook in upstream files, or read with `std::fs` keyed on `File::revision`, which skips the memory file system that tests use. It needs a Rust SDNA decoder and ListBase walker (~1-1.5 k lines, written fresh, since `blendfile.py` is GPL Python). A 50 MB file costs real memory while it is decoded (decode and drop). The per-version RNA tables (§2.7: object types, modifier struct names) end up in Rust, the kind of table `type-tag-data-sources.md` §2.3 rejects. They would have to come from the stubs instead (tag views, `type` literals).
- **Effort**: L (several days for the reader, plus the typing in §4.6).

### (B) An offline extractor and a text manifest

A `mise run blend:manifest <paths…>` task (pure Python like the probe, no Blender binary) writes `<file>.blend.toml`, or one manifest per project, with the tiers and the source file's size, mtime and blake2 hash. ty reads the manifest with `source_text`.

- **Pros**: no binary I/O in ty, no new `System` method, and salsa tracking for free. The manifest is reviewable and diffable, and lives in Git next to an LFS-tracked `.blend`. The extractor is Python, so it can reuse `_blendfile_header.py` (which ships in Blender's `scripts/modules`) or import `tools/modules/blendfile.py` from a checkout. The RNA mapping can be done by the extractor, or better, by running it once inside Blender (`check:load` already runs Blender) to record what the *loaded* file holds after versioning (§5). That is the probe pattern of `type-tag-data-sources.md` §2.2.
- **Cons**: the manifest goes stale. ty can tell cheaply by comparing the recorded size and mtime with `path_metadata` (`ty/ruff_db/src/system.rs:56`) and reporting a stale manifest. It is an extra step for add-on authors.
- **Effort**: M for the extractor, M for reading and typing in ty.

### (C) Generated `.pyi` overlays per file, no checker change

Generate a stub overlay: a `bpy/types` partial or a typed facade module with `BlendDataObjects.__getitem__` overloads on `Literal["Cube"] → _Object_MESH`, and so on.

- **Pros**: works with any checker, including stock ty and pyright on fake-bpy-module. Key completion follows for free, because ty completes a string from its expected `Literal` type (`ty/ty_python_semantic/src/semantic_model.rs:703-740`, used by `ty/ty_ide/src/completion.rs:2365`).
- **Cons**: stubs are global per environment, while a `.blend` binds a *script*. One overlay per project works only if every script in the project runs against the same file. Otherwise the code has to import a facade (`from blendtypes.scene import data`), which Blender's tests and most add-ons will not do. A stub overload cannot express "only after `open_mainfile('x.blend')`", and it cannot drop `| None` from `.get()` for named keys only without an overload per key (possible, but large). It also collides with the builtin stubs' own `bpy/types/__init__.pyi`.
- **Effort**: M. A good prototype to check the typing of §4.6 with `check:oracle` before touching ty.

### (D) A declared mapping in `[tool.blender]`

```toml
[tool.blender]
blend-files = [
  { scripts = ["tests/python/modifiers.py"], files = ["tests/files/modeling/modifiers/modifiers.blend"] },
  { scripts = ["app_template/__init__.py"], files = ["app_template/startup.blend"] },
]
```

- **Pros**: explicit, the only general route for add-ons (§3), and it reuses the table discovery already reads (`ty/ty_blender/src/discovery.rs:7`). A script mapped to several files gets the facts that hold in all of them (§5).
- **Cons**: it supplies no facts by itself. It is the binding half of A or B.
- **Effort**: S on top of A or B.

### (E) Inferring the binding from the code

- **Ways to infer**: bind a script to the file in a literal `open_mainfile` (for code after the call, in the same function), to the positional `.blend` of a CMake `add_blender_test`, or to an app template folder's `startup.blend`.
- **Pros**: no configuration for Blender's own tests (about 94 calls and 23 CMake lines).
- **Cons**: parsing CMake is fragile, `testdir` needs the CMake value, and flow-sensitivity (facts valid only after the call) needs a new narrowing point. That is closer to `blender-assumed-added-object` (`context_assumptions`) than to a module-wide fact.
- **Effort**: M, after A or B.

### (F) LSP-only: completion and hover, no typing

Offer ID names, node names and socket identifiers as completions inside `bpy.data.objects["|"]`, `nodes["|"]` and `inputs["|"]`, and show "Mesh object in x.blend" on hover. Types stay as the stubs say.

- **Pros**: it cannot make `check` unsound, because nothing narrows. It is the most visible benefit for add-on authors.
- **Cons**: it does nothing for `check:blender`. It needs a completion hook in `ty_ide`, an upstream file (`hover/blender.rs` shows the fork already has one for hover).
- **Effort**: S-M after A or B.

### (G) B inside Blender: the loaded state

B's extractor, run in background Blender after it opens the file (the probe pattern, §6 step 2). It writes the same
manifest from `bpy.data`.

- **Pros**: it records what a script sees after versioning, and the RNA class names come from Blender itself. No
  table in the extractor has to keep up with Blender.
- **Cons**: it needs a Blender binary of the right version, and it starts Blender once per run.
- **Effort**: S on top of B.

### 4.6 How the typing would surface

Each step is one hook of the kind `ty_python_semantic/src/types/dedicated/blender/` already has:

| Expression | Stubs today | With a bound file |
|---|---|---|
| `bpy.data.objects["Cube"]` | `Object` | `_Object_MESH`: the existing tag view (`.cache/bpy-stubs-builtin/main/bpy/types/__init__.pyi:39878-39883`), so `.data` is `Mesh` and `.type` is `Literal['MESH']` |
| `bpy.data.objects.get("Cube")` | `Object \| None` | `_Object_MESH`, reported as an Assumption |
| `bpy.data.objects["` | no completion | the file's object names. Linked ones are keyed `("Monkey", "//libraries/direct_linked_A.blend")`, which the stubs' `str \| tuple[str, str \| None]` key accepts (`__init__.pyi:133`) |
| `bpy.data.materials["Mat"].node_tree.nodes["Principled BSDF"]` | `Node` | `ShaderNodeBsdfPrincipled` (the stored `bNode.idname` *is* the RNA class name for built-in nodes) |
| `….inputs["Base Color"]` | `NodeSocket` | `NodeSocketColor` (`bNodeSocket.idname`). The lookup matches `identifier` first and then `name`, except on Mix and Map Range nodes (`makesrna/intern/rna_nodetree.cc:2280-2312`), and skips unavailable sockets |
| `context.object` right after `open_mainfile("x.blend")` | `Object \| None` | the object of `ViewLayer.basact` |
| `scene["my_key"]` (IDProperty) | `Any` | the stored type (`int`, `float`, `str`, group) |

The node rows need the receiver's *identity* ("material `Mat` of file F"), not only its class. ty has no type that carries a data-block identity. Two ways:

- resolve the whole access chain syntactically, with simple aliases (`mat = bpy.data.materials["Mat"]`), the way pointer aliases and context members match paths today;
- add a dedicated Blender type, an instance with a key, which is a much larger change to upstream's `Type`.

The first covers the test patterns of §3. This is where deferred row 12 of `docs/reports/remaining-large-groups.md` comes in. A file gives the exact socket classes of the nodes *in that file*. It does not give the socket declarations of every built-in node (`nodes.new("ShaderNodeBsdfPrincipled").inputs["Base Color"]`). A corpus of files could seed such a table, but it would be a hand-collected per-version table. Row 12 still needs a Blender-side probe of node declarations, and a file reader does not replace it.

### 4.7 What it would clear in `check:blender`

The report counts 668 `unchecked-pointer` diagnostics in `tests/` (`docs/reports/remaining-large-groups.md:41`, table `:57-72`). With the binding of §3 (about 94 literal calls plus 23 CMake lines), the rows a file can answer are:

- `bpy.data.objects.get()` reads, part of the 71 Object/Mesh reads. The other 21 are `self.me = None`.
- `context.object` after `open_mainfile`, 27, if no operator runs in between.
- `obj.animation_data` of an object loaded from a test file: most of 90, if the file's `Object.adt` is non-null. 14 follow `animation_data_create()` and are not file facts.
- `Collection.importer`, 22, if the file holds it.

That is about 100-175 of the 668 (15-25 %), and none of the Action lookups, `GreasePencilFrame.drawing` or `override_create()` reads. On current main, 398 diagnostics in `tests/` concern `ID | None` (`Object.data`), mostly in `base-class-subtype` (`.cache/ty-results/main-builtin.txt`). The part whose object comes from a literal key would also go. Most come from `context.active_object` after an operator or from objects the test creates, which a file cannot answer. The report's own advice, to check `tests/` as a separate profile, removes more than this does.

## 5. Soundness

A file is a snapshot. What breaks the facts:

- **The script changes the data.** `objects.new` / `remove`, assigning `.name` (a clashing name gets a `.001` suffix, `BKE_id_new_name_validate`, `blenkernel/BKE_lib_id.hh:934`), `bpy.ops.object.delete`/`join`, `nodes.new`/`remove`, and `load_post` handlers. Facts hold at load, not at an arbitrary later line. Tracking every mutating call is not tractable, because operators are opaque.
- **One script, several files.** `geo_node_test.py` runs against 431 files, and a render test script against a whole folder. For several bound files, the checker should use the *intersection* of names and the *join* of types: `Object` if `Cube` is a mesh in one file and a curve in another.
- **The file changes on disk.** A handles this through salsa. B needs the stale check of §4(B).
- **Versioning on load.** The raw bytes of an old file are not what the script sees (§2.7: Principled sockets, Mix node idname, grease pencil conversion, socket rebuild from declarations). Raw facts are safe when the file was saved by the Blender version the stubs describe. Otherwise check each idname and identifier against the stubs, and fall back to the base class when it is unknown. The extractor-inside-Blender variant of B avoids the problem, because it records the versioned state.
- **Linked data.** A missing library still yields IDs, empty placeholders. Library overrides and relative `//` paths depend on where the file is opened from.
- **`empty.blend` and factory startup.** A file that holds nothing must not make `bpy.data.objects["Cube"]` an error. The script probably creates it.

**Presentation.** This is an Assumption in the glossary's sense: a Blender fact taken as given with no evidence in the code (`GLOSSARY.md:101-103`), like the existing `blender-assumed-*` rules (`ty/ty_python_semantic/src/types/dedicated/blender/assumptions.rs:1-24`, declared in `lints.rs`, at `warn` because ty has no info level: `docs/research/silent-assumptions.md:9-10`). Proposed:

- **`blender-assumed-blend-content`** (Assumption, `warn`): reported at each read whose type comes from a file, with the file and its saving version: "`bpy.data.objects.get("Cube")` is taken as the mesh object `Cube` of `tests/files/x.blend` (saved by Blender 5.2), but the script may have removed or renamed it". Reads that change nothing need no report: a subscript that only gains a subclass loses no `None`, so it can stay silent, like single-subclass collections (`silent-assumptions.md` §2.1). The report is owed where `None` is dropped (`.get()`, `context.object`, `animation_data`).
- **Unknown keys are not errors.** A name missing from every bound file keeps the stub type. At most a hint, under its own opt-in rule (`blender-unknown-blend-key`), because scripts create data.
- **A stale manifest** (B) is a warning on the `[tool.blender]` entry, not on every read.
- **Strictness**: lenient silences the Assumption, default warns, and strict also enables `blender-unknown-blend-key`.

## 6. Recommendation

1. **Start with B + D.** Write a pure-Python extractor as a mise task that reads a file's bytes, using the probe's logic or Blender's `_blendfile_header.py` plus `blendfile.py` from the checkout. It writes a TOML manifest with tiers 1-6 and the source file's size, mtime and hash. The binding is declared in `[tool.blender] blend-files`. ty reads the manifest through `source_text` in `ty_blender`, as a type-free fact, and the typing goes in a new `dedicated/blender/blend_content.rs` with one-line hooks at subscript and `.get()` resolution. The manifest is text, so salsa, the LSP and the memory-file-system tests work unchanged.
2. **Optionally record the loaded state, not the raw bytes.** Run the extractor once inside Blender (through the `check:load` machinery) for files older than the stubs' version, so versioning has already applied.
3. **Ship completions with the typing (F).** They follow from `Literal`-typed keys through the existing expected-type completion path, and give add-on authors most of the value.
4. **Prototype the typing first as overlays (C)** for one test file, and check it with `check:oracle`. This settles §4.6, including how chains keep identity, before touching ty.
5. **Defer A.** Move the reader into Rust only if manifests prove a burden in practice. It needs a byte-reading `System` method, which should be proposed upstream rather than patched into the fork.
6. **Do not count on large `check:blender` gains** (§4.7). Splitting `tests/` into its own profile is the cheaper fix there. Row 12 of the report still needs a node-declaration probe in Blender.

## 7. Open questions

- **Identity-carrying types**: is syntactic chain resolution enough for `nodes[…]` and `inputs[…]`, or is a keyed instance type worth an upstream discussion?
- **Inference (E)**: should the checker infer bindings from literal `open_mainfile` calls and CMake, or only accept declared ones? Flow-sensitive facts ("after this call") would make them another narrowing point.
- **Manifest location**: should the manifest live next to the `.blend`, which helps LFS-tracked assets, or in `.cache/`? Committing it makes reviews show data changes. Caching it hides them.
- **One manifest per file or per project**, given that Blender's tests bind 431 files to one script?
- **Raw or loaded state**: should the extractor record raw bytes, the loaded state (needs Blender), or both, with ty preferring loaded facts when present?
- **IDProperties**: how far should they be typed? `scene["key"]` typed by the stored value looks safe for reads, but writes change the type freely.
- **Files newer than the stubs**: forward-compatible reads may meet unknown idnames. Drop them silently or report?
- **Clones without LFS content**: should a bare Git LFS pointer (131-byte text, like every `.blend` under `blender/` here) be skipped silently or reported?
- **Asset-library add-ons**: should their bundled `.blend` assets ever bind to code, given they always load through computed paths?

## 8. Prototype results

Throwaway code in `prototypes/blend_typing/` (see its README). It tested approaches A, B and C, and G (B run inside
Blender, step 2 of §6), on three example add-ons in `prototypes/blend_typing/examples/`. Each add-on binds its files
with D (`[tool.blender] blend-files`), and `mise run probe:blend-typing <version>` runs all four approaches on them:

- `asset_pack`: an `assets.blend` with a material, a geometry node group and a mesh object with a Bevel modifier,
  which the add-on appends;
- `scene_template`: a `startup.blend` with a camera, an area light and a cube with a Subdivision modifier;
- `sculpt_template`: a copy of Blender's own Sculpting template `startup.blend`, saved by 5.2 and loaded by 5.4.

The first two are generated in Blender (`make_examples.py`).

- **B, extractor to TOML manifest** (`extract_manifest.py`). On the three files it writes 35-50 lines in 16-40 ms:
  ID names per collection; each object's type, data class and data name, and its modifiers; each material's nodes and
  each node group's nodes, with their class and their input and output socket classes. A light's data class needs one
  more field, `Lamp.type`, because `bpy.types` has a class per light type (`AreaLight`), and that class is what
  `Object.data` of a light is. Earlier, B used to record the base `Light`, which G showed was wrong.
- **G, the same manifest written by Blender** (`blender_extract.py`). It opens each file with `open_mainfile` in
  background Blender and writes B's schema from `bpy.data`, so it records the loaded state, after versioning. Opening
  takes 4-8 ms per file, but each run pays for starting Blender. On the two files saved by the Blender that loads
  them, B and G agree on every fact. That says little about B's own tables (object type to data class, light type to
  light class): the examples have no text, surface or other rarer objects, where B's tables could be wrong. On the Sculpting template, saved by 5.2, G has two Principled BSDF inputs that the file
  does not store: `Transmission Dispersion Scale` and `Transmission Dispersion Abbe Number`. Blender rebuilds a node's
  sockets from its declaration when it loads the file. So a raw reader is exact only for files saved by the stubs'
  version, as §5 expects. In this file a newer Blender only adds sockets, so the facts B has stay true there. That
  is one file, not a rule. The overlays from B's and G's manifests are identical even here, because C leaves a
  built-in node's sockets to the stubs (below). The difference would matter for a group or custom node.
- **C, overlay stub with `Literal` keys** (`gen_stubs.py`, checked with `check:addons --generator builtin`). The
  overlays of all three add-ons check clean against the builtin stubs. With the overlay, the checker gives the first
  set of types below; reading `bpy.data` today gives the second:

  | Expression | With the overlay | Through `bpy.data` today |
  |---|---|---|
  | `objects["Rock"].data` | `Mesh` | `ID \| None` |
  | `objects.get("Key Light")` | the object, not `None`; its `.data` is `AreaLight` | `Object \| None` |
  | `objects["Cube"].modifiers["Subdivision"]` | `SubsurfModifier` (`.levels` is `int`) | `Modifier` |
  | `materials["Rust"].node_tree.nodes["Principled BSDF"]` | the Principled BSDF node | `Node` |
  | `….inputs["Base Color"]` | `NodeSocketColor` | `NodeSocket` |
  | `node_groups["Scatter Points"]` | a `GeometryNodeTree` that knows its nodes | `NodeTree` |
  | `objects.get("Boulder")`, not in the file | `Object \| None` | the same |

  Three things had to change before the stub checked clean:

  - The stub repeats every signature of the base class's `__getitem__` and `get`, with the `(name, library)` key only
    on data-block collections.
  - It narrows a writable attribute (`Object.data`, `Object.type`) through a property whose setter still takes
    anything the base allows.
  - It leaves a built-in node's sockets alone. The builtin stubs already type `inputs["Base Color"]` per node class
    (`_ShaderNodeBsdfPrincipled_inputs`, from row 12 of `docs/reports/remaining-large-groups.md`). Re-declaring them
    would fight the base's overloads, so the overlay adds sockets only to group and custom nodes.

  The stubs and the file overlap here: for a built-in node, the file adds nothing to what the stubs know. Against the
  fake-bpy-module stubs, the same overlay gets override errors, because that generator's signatures differ. An overlay
  must be generated per stub generator, or be read by ty-blender rather than by stock ty. The add-ons bind the overlay
  by importing `data` from it under `TYPE_CHECKING`, a code change every script would need.
- **A, the reader at check time** (`reader_check.py`, with `measure_reader.py` on Blender's test files). `reader_check.py`
  reads the files that the add-on's manifest binds, with no manifest, and resolves each `reveal_type` argument
  syntactically through simple aliases, the first way of §4.6. On the three add-ons, it resolves every chain through
  the file's names that the overlay resolves. A member read after the chain (`camera.data.lens`) keeps the stubs'
  type, which the checker supplies. A also types the `check_bare` reads of `bpy.data`, which the overlay cannot reach: `rock.modifiers["Bevel"]`
  is `BevelModifier`, and `bpy.data.node_groups["Scatter Points"]` is `GeometryNodeTree`. Reading and merging the
  facts takes 16-34 ms per file in pure Python. The resolver is a sketch: it collects aliases in no particular order,
  and it treats any bare `data` as `bpy.data`. A reader in ty would follow the checker's own bindings. The earlier measurements on 58 test files still hold. The extractor
  reads only 17 `struct.field` paths (18 with `Lamp.type`). Decoding the SDNA dominates (median 17 ms), and it could be
  cached per Blender version. A 2.5 file has no `bNode.idname`, so every field must be optional.
- **How often a binding would help.** 12 test scripts open literal `.blend` files (other than `empty.blend`). Of their
  257 literal `bpy.data.<collection>["Name"]` and `.get("Name")` keys, 168 (65%) name an ID in a file the script opens.
  The rest are data the test creates or imports (USD, Alembic), or a file opened later. Typing from a file is
  therefore an assumption, as §5 says, and a missing key must stay legal.

Verdict:

- **B + D give the types this research hoped for, cheaply.** G is worth running for files older than the stubs.
- **G and B can share one schema,** so ty needs one manifest reader whichever wrote it.
- **Scripts can't be asked to bind through code** (C alone).
- **A's syntactic chains reach the plain `bpy.data` reads that an overlay can't.** That is the case for the
  checker-side typing of §6 step 1, with the manifest as its input. A Rust reader stays a later optimisation, with no
  blocker in the format.
