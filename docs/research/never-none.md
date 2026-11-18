# Which pointers and callback parameters are never None?

Research note, 2026-11-06, for [#69](https://github.com/taway1450/blender-extension-developer-suite/issues/69) (map [#67](https://github.com/taway1450/blender-extension-developer-suite/issues/67)). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

Blender main `dc491af090`. Paths are relative to `.cache/blender-src/main` unless stated. Generated RNA code is in `.cache/blender-build/main/source/blender/makesrna/intern/rna_*_gen.cc`.

Main now: both fixes are in the Blender fork. makesrna flags embedded pointers `PROP_NEVER_NULL` (the hook below), and the safe callback parameters carry `PROP_NEVER_NULL`; `RenderEngine.view_draw`'s context stays nullable. `scripts/probe_never_none.py` (`mise run probe:never-none`) replaces the probe this note sketched; see [never-none-probe.md](never-none-probe.md).

## Answer

- **Where nullability is decided.** Not in `sphinx_stub_gen.py`; that file only parses the RST written by `sphinx_doc_gen.py`. The type string comes from `InfoPropertyRNA.get_type_description` in `scripts/modules/_rna_info.py:568-574`: a pointer property, and any pointer function parameter (its `default_str` is always `"None"`, line 392-395), gets `| None` unless `rna_prop.is_never_none`. `is_never_none` is the RNA flag `PROP_NEVER_NULL` (`makesrna/RNA_types.hh:447`). No other input is used.
- **Embedded pointers.** The rule "non-ID struct owned by its parent is never None" is **too broad**. The exact rule is **"the DNA member is a struct value, not a pointer"**: makesrna generates the getter `return RNA_pointer_create_with_parent(*ptr, RNA_X, &data->member);` (`makesrna/intern/makesrna.cc:762-766`), and the address of an embedded member is never null (`Camera.dof`, `Scene.view_settings`, `Scene.eevee`, `MovieTracking.camera`, `ToolSettings.image_paint`, `RenderSettings.ffmpeg`, ...). All of them are read-only and none targets an ID.
- **Owned non-ID pointers that can be None.** Properties with a DNA *pointer* member (`data->member`) are lazily allocated or optional data such as `ToolSettings.sculpt` / `vertex_paint` / `weight_paint` / `gpencil_paint`, `Object.pose` / `rigid_body` / `soft_body` / `motion_path`, every `*.animation_data`, `Scene.sequence_editor` / `rigidbody_world`, `Image`/`Sound`/`VectorFont`/`Volume.packed_file`, `Bone.parent`, `Node.parent`. They stay `| None`. Non-ID properties with hand-written getters (`active`, `parent`, `Context.*`, `KeyMapItem.properties`, ...) are nullable by design or can't be decided statically, so they stay as they are.
- **The generator can't learn the embedded rule from Python.** `bpy` exposes no sdna information, and `RNA_def_struct_nested` doesn't work as a proxy: none of the embedded targets is declared nested in its owner, and the pointers that are nested in their owner already carry `PROP_NEVER_NULL`. So the fix is a hook in makesrna on the Blender fork: in `rna_def_property_funcs`, `case PROP_POINTER`, a pointer with no hand-written getter whose DNA member is a struct value gets `PROP_NEVER_NULL`. Property definitions are written after all `rna_def_property_funcs` calls, so the flag reaches the runtime, `is_never_none` and the stubs. The change has no behavioural effect because all these properties are read-only. `PROP_NEVER_NULL` on a pointer only blocks assigning `None` (`RNA_types.hh:441-447`).
- **Callback parameters.** The `Context | None` parameters are callback parameters defined with `RNA_def_parameter_flags(parm, PropertyFlag(0), PARM_REQUIRED)`, while `Panel`, `Operator`, `Node`, `NodeSocket`, `Gizmo` and `GizmoGroup` use `PROP_NEVER_NULL` (table below). In every C caller the context comes from a live `bContext *C`, with one exception: `RenderEngine.view_draw` can receive `None` during off-screen drawing. Fix: add `PROP_NEVER_NULL` to the safe parameters in the RNA definitions, the same one-token change Panel already has. The generator needs no change.

## Where nullability is decided, end to end

1. RNA definition: `RNA_def_property_flag(prop, PROP_NEVER_NULL)` for properties, `RNA_def_parameter_flags(parm, PROP_NEVER_NULL, ...)` for function parameters. In `makesrna/intern/rna_define.cc:1281-1293`, a string gets `PROP_NEVER_NULL` by default and a pointer gets only `PROP_THICK_WRAP`.
2. Python: `bpy.types.Property.is_never_none` reads the flag. `_rna_info.py:335` copies it into `InfoPropertyRNA.is_never_none`.
3. `_rna_info.py:571-574` appends `" | None"` (for arguments: `default_str == "None"`, which every pointer has; for attributes: `type == "pointer"`). Line 612 also adds the "never None" qualifier to the docs.
4. `sphinx_doc_gen.py` writes `:type:` with that string into the RST, and `sphinx_stub_gen.py` copies it into `bpy/types/__init__.pyi`.

Collections never get `| None` as attributes; only pointers do.

## Embedded by value vs DNA pointer

`AnimData` isn't an ID, so all `*.animation_data` count as "DNA pointer, non-ID": nullable, as they should be.

Note that `ToolSettings` mixes both kinds. `image_paint`, `uv_sculpt`, `particle_edit`, `gpencil_sculpt`, `gpencil_interpolate` and `paint_mode` are embedded. `sculpt`, `vertex_paint`, `weight_paint`, `curves_sculpt` and the `gpencil_*_paint` modes are DNA pointers, allocated lazily by `BKE_paint_ensure`. Those last ones are genuinely `None` on a scene from `bpy.data.scenes.new()`. So "owned by the parent" isn't the criterion; the DNA layout is.

## Callback parameters

Pointer parameters of `FUNC_REGISTER` functions in `makesrna/intern/rna_*.cc`, as they stood before the fix:

| Callback | Parameter flags | C caller and where its context comes from | Always non-None? |
|---|---|---|---|
| `Panel.poll/draw/draw_header/draw_header_preset` | `PROP_NEVER_NULL` (`rna_ui.cc:1889-1909`) | `panel_poll` / `panel_draw` (`rna_ui.cc:112-184`) | already non-None |
| `Operator.*`, `Macro.*`, `Gizmo.*`, `GizmoGroup.*`, `Node.*`, `NodeSocket.*`, `NodeTree.poll`, `NodeTreeInterfaceSocket.*` | `PROP_NEVER_NULL` | | already non-None |
| `Header.draw` | `PropertyFlag(0)` (`rna_ui.cc:2243`) | `header_draw(const bContext *C, ...)` (`rna_ui.cc:802`), from region header layout | yes |
| `Menu.poll`, `Menu.draw` | `PropertyFlag(0)` (`rna_ui.cc:2314, 2321`) | `menu_poll`/`menu_draw` (`rna_ui.cc:941, 965`). `WM_menutype_poll` dereferences `C` before calling poll (`windowmanager/intern/wm_menu_type.cc:94-106`), and `mt->draw(C, &menu)` runs in `interface_layout.cc:6406` | yes |
| `UIList.draw_item`, `draw_filter`, `filter_items` | `PropertyFlag(0)` (`rna_ui.cc:2131, 2169, 2181`) | `uilist_draw_item` / `uilist_draw_filter` / `uilist_filter_items` (`rna_ui.cc:536-593`), called from `uiTemplateList` with the drawing `C` (`interface_template_list.cc:818, 880, 1003`) | yes |
| `AssetShelf.poll`, `draw_context_menu` | `PropertyFlag(0)` (`rna_ui.cc:2488, 2519`) | `asset_shelf_poll` / `asset_shelf_draw_context_menu` (`rna_ui.cc:1148, 1194`), from shelf region drawing | yes |
| `FileHandler.poll_drop` | `PropertyFlag(0)` (`rna_ui.cc:2629`) | `file_handler_poll_drop` (`rna_ui.cc:1569`), from drop-box polling with the window `C` | yes |
| `KeyingSetInfo.poll`, `iterator`, `generate` | `PropertyFlag(0)` (`rna_animation.cc:1251, 1259, 1269`) | `RKS_POLL/ITER/GEN_rna_internal` (`rna_animation.cc:463-532`), called from `animrig/intern/keyingsets.cc:205, 235, 248` and `editors/animation/keyingsets.cc:737`, all inside operator or auto-key paths that own a `C` | yes |
| `RenderEngine.view_pause`, `view_resume` | `PropertyFlag(0)` (`rna_render.cc:653, 659`) | `RE_engine_view_pause_notify` (`render/intern/engine.cc:1468-1488`), called only from `render_view3d_engines_foreach`, which builds a context per region (`editors/render/render_update.cc:153-166`) | yes |
| `RenderEngine.view_update` | `PropertyFlag(0)` (`rna_render.cc:637`) | `render_update.cc:108` (a real `C`) and `draw/engines/external/external_engine.cc:285` (`draw_ctx->evil_C`). On the external-engine path, `CTX_wm_area(evil_C)` at line 281 dereferences the context first, so a null context would crash before Python runs | yes, in practice |
| `RenderEngine.draw` (image editor) | `PropertyFlag(0)` (`rna_render.cc:604`) | `external_engine.cc:398`, image-editor path. Line 360 passes `evil_C` to `ED_render_job_get_current_scene` first. Off-screen drawing is 3D-view only | yes, in practice |
| **`RenderEngine.view_draw`** | `PropertyFlag(0)` (`rna_render.cc:645`) | `external_engine.cc:297` with `draw_ctx->evil_C`, which is `nullptr` for off-screen drawing: `ED_view3d_draw_offscreen_imbuf` (`editors/space_view3d/view3d_draw.cc:2144-2149`, used by Viewport Render in Rendered shading) and `gpu.types.GPUOffScreen.draw_view3d` (`python/gpu/gpu_py_offscreen.cc:492-497`) both pass `nullptr` | **no**: `None` when an existing viewport render engine is drawn off-screen |

`view_draw` is the only real exception. Cycles itself dereferences the context unconditionally (`intern/cycles/blender/addon/__init__.py:94-95`: `context.region`, `context.space_data`). So typing it `Context` matches what Blender's own engine assumes, but it isn't strictly sound. The map's rule ("callback parameters Blender *always* passes") keeps it nullable, and main does so.

Other nullable callback parameters seen on the same path: `UIList.draw_item(layout, data, item, active_data)`, `UIList.filter_items(data)`, `AssetShelf.draw_context_menu(asset, layout)`, `KeyingSetInfo.iterator/generate(ks)`, the `RenderEngine.*(depsgraph)` parameters, `RenderEngine.bake(object)`, `RenderEngine.update_script_node(node)`, `Node.poll(node_tree)`. `UIList.draw_filter(layout)` already has `PROP_NEVER_NULL`, and `draw_item(layout)` is built from the same non-null layout (`uilist_draw_item`). Main flags `UIList.draw_item` / `filter_items`' `data`, `KeyingSetInfo`'s `ks`, `AssetShelf`'s `asset` and `layout`, and the `RenderEngine` `depsgraph` parameters too; `UIList.draw_item`'s `item` and `active_data` stay nullable (see `tests/typecheck/features/api_types/README.md`).

**How the generator learns it:** through the RNA flag, because `_rna_info.py` already honours `is_never_none`. A generator-side rule ("a `Context` parameter of a registered function is never None", readable through `Function.is_registered`) also works without touching C, but it would hard-code `view_draw` as an exception and wouldn't change the runtime's `is_never_none` or the docs. The RNA edit is the upstreamable one, and it mirrors what `Panel` / `Operator` already do.
