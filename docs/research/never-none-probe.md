# Which RNA pointers and returns are truly never None (#109)

Research note, 2026-11-17, for [#109](https://github.com/taway1450/blender-extension-developer-suite/issues/109) (map [#107](https://github.com/taway1450/blender-extension-developer-suite/issues/107)). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

Blender `main` built headless from the fork's `typecheck-fixes` tip `9a7af0b847`.

Every never-null verdict below landed in the Blender fork; `tests/typecheck/features/api_types/README.md` lists them and cites #109. The source reasoning for embedded pointers and callback contexts is in [never-none.md](never-none.md).

## How the probe works

`mise run probe:never-none <version>` (`scripts/probe_never_none.py`) regenerates the per-member, per-state table into `.cache/never-none-probe/<version>/table.md`. It runs Blender `--background --factory-startup` twice:

- **synthetic**: edge states built in factory startup: new data, `copy()`, save then append and link, invalid arguments, every node tree type and a registered custom one, one ID of every `bpy.data` collection, and `read_homefile()` / `read_factory_settings(use_empty=True)` / `read_homefile(use_empty=True)`.
- **corpus**: every `.blend` under the source worktree's `tests/files` (`invalid_blendfiles/` left out), saved by Blender versions from before 2.80 to 5.x. The big-endian files back to 1.62 fail to open, because current Blender no longer reads them.

"Background" is the only state a headless build has: no window, so no `context.window`, `context.screen` or `context.area`. Screens and areas from the file still exist and were probed through `bpy.data.screens`.

## Members that stay nullable or are null in some state

| Member | Verdict | Evidence |
|---|---|---|
| `ID.animation_data_create` | **null-in-state**: the ID type has no animation data | Returns None for the 13 ID types flagged `IDTYPE_FLAGS_NO_ANIMDATA` (Action, Brush, Collection, Image, Library, Palette, PaintCurve, Screen, Sound, Text, VectorFont, WindowManager, WorkSpace) and for link placeholders. The probe confirmed None on Screen, WindowManager, Image, Collection, Text, Action, Palette and WorkSpace, and a value on the other types it could make. It is defined once on `ID`, so a `PROP_NEVER_NULL` flag would be wrong. Making it non-None would need a per-subclass stub override; main keeps it `AnimData \| None`. |
| `MovieTrackingObjects.active` | **null-in-state**: `active_object_index` out of range | Never None in the corpus, for a new clip, or after removing the active object through `remove()`. But `tracking.active_object_index = 99` was stored unclamped (it read back 99), and `active` was then None. The range function exists, but the setter didn't clamp. Main: the fork clamps the index, and flags `active` never-null. |
| `MeshUVLoopLayers.new` | **nullable** | The 9th and 10th calls on one mesh return None (8-layer limit, warning report only). |
| `ObjectModifiers.new` | **nullable** | `SUBSURF` on an empty returns None (warning only), and on a mesh returns the modifier. |
| `bpy_extras.image_utils.load_image` | **nullable** | Python, documented to return None when the file isn't found. Not RNA. |
| `RenderEngine.begin_result` | **nullable** | Source: null when the clamped tile is empty (`engine.cc:365`). Not probed (needs a running render). |
| `Object.to_mesh` | **unknown**, keep nullable | Raises for an object without geometry. A non-mother metaball still gave a mesh. The C null path (`mesh_new_from_object` for a basis-less metaball) was not reached. |
| `XrSessionState` (`WindowManager.xr_session_state`) | **nullable** | None in every probed state (no VR session headless). `XrSessionState.viewfinder` is never-null whenever its parent exists: both are null only when `xr->runtime` is null (`wm_xr_session.cc:467-475`). |
| `DepsgraphObjectInstance.instance_object` / `.parent` | **nullable** | None for every non-instance, as documented. `.object` is never None. |
| `ID.asset_data`, `FileSelectEntry.asset_data` | **nullable** | `AssetRepresentation.metadata` is never-null (`get_metadata()` returns a reference), but these are not. |

## Findings on the way

- **`KeyConfigurations` subtype misuse.** `rna_wm.cc:2921-2937` passed `PROP_NEVER_NULL` as the *subtype* argument of `RNA_def_property` (`PROP_POINTER, PROP_NEVER_NULL`), so the flag was never set and the stubs said `KeyConfig | None` for `default`, `addon` and `user`. The fix is `PROP_NONE` plus `RNA_def_property_flag(prop, PROP_NEVER_NULL)`. `KeyConfigurations.active` falls back to `wm->runtime->defaultconf`.
- **Failures that raise instead of returning None.** `BlendDataNodeTrees.new` returns null only for an enum index without a tree type, and RNA validates the enum first (an unknown or unregistered type raises `TypeError`). `AssetLibraryCollection.new`, `BlendDataObjects.new` and `BlendDataMeshes.new_from_object` return null only with an `RPT_ERROR` report, which bpy raises as `RuntimeError`. `bpy_struct.id_properties_ui` raises `KeyError` or `TypeError` for every reachable failure; its `| None` was a hand-written docstring (`:rtype:`), not RNA.
- **`Material.node_tree` / `World.node_tree` and the pre-5.0 gap.** `material_init_data` / `world_init_data` always embed a tree. In 5.0, `do_version_*_remove_use_nodes` add one to data saved with `use_nodes = False` and no tree. None was found over the corpus or in any synthetic state. One gap in the evidence: versioning only adds a tree when `use_nodes` was False. A pre-5.0 material with `use_nodes = True` and no tree would still read None. Old Blender always created the tree when `use_nodes` was enabled, and no pre-5.0 material in the corpus had that state.
