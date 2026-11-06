# Which pointers and callback parameters are never None?

Research for [#69](https://github.com/taway1450/blender-extension-developer-suite/issues/69) (map [#67](https://github.com/taway1450/blender-extension-developer-suite/issues/67)). Blender main `dc491af090`. Paths are relative to `.cache/blender-src/main` unless stated. Generated RNA code is in `.cache/blender-build/main/source/blender/makesrna/intern/rna_*_gen.cc`.

## Answer

- **Where nullability is decided.** Not in `sphinx_stub_gen.py`; that file only parses the RST written by `sphinx_doc_gen.py`. The type string comes from `InfoPropertyRNA.get_type_description` in `scripts/modules/_rna_info.py:568-574`: a pointer property, and any pointer function parameter (its `default_str` is always `"None"`, line 392-395), gets `| None` unless `rna_prop.is_never_none`. `is_never_none` is the RNA flag `PROP_NEVER_NULL` (`makesrna/RNA_types.hh:447`). No other input is used.
- **Embedded pointers.** The rule "non-ID struct owned by its parent is never None" is **too broad**. The exact rule is **"the DNA member is a struct value, not a pointer"**: makesrna generates the getter `return RNA_pointer_create_with_parent(*ptr, RNA_X, &data->member);` (`makesrna/intern/makesrna.cc:762-766`), and the address of an embedded member is never null. That applies to **62 pointer properties** (`Camera.dof`, `Scene.view_settings`, `Scene.eevee`, `MovieTracking.camera`, `ToolSettings.image_paint`, `RenderSettings.ffmpeg`, ...). All 62 are read-only and none targets an ID. Counted statically from the generated code. A runtime probe isn't needed to prove them, only as a sanity check (script below).
- **Owned non-ID pointers that can be None.** 211 properties have a DNA *pointer* member (`data->member`): lazily allocated or optional data such as `ToolSettings.sculpt` / `vertex_paint` / `weight_paint` / `gpencil_paint`, `Object.pose` / `rigid_body` / `soft_body` / `motion_path`, every `*.animation_data`, `Scene.sequence_editor` / `rigidbody_world`, `Image`/`Sound`/`VectorFont`/`Volume.packed_file`, `Bone.parent`, `Node.parent`. They stay `| None`. Another 159 non-ID properties have hand-written getters (`active`, `parent`, `Context.*`, `KeyMapItem.properties`, ...). They are nullable by design or can't be decided statically, so they stay as they are.
- **The generator can't learn the embedded rule from Python.** `bpy` exposes no sdna information, and `RNA_def_struct_nested` doesn't work as a proxy: 0 of the 62 embedded targets are declared nested in their owner, and all 35 nested-in-owner pointers already carry `PROP_NEVER_NULL`. The fix is a hook in makesrna on the Blender fork. In `rna_def_property_funcs`, `case PROP_POINTER` (`makesrna.cc:2184`), add `if (!pprop->get && dp->dnapointerlevel == 0 && dp->dnaname) { prop->flag |= PROP_NEVER_NULL; }` before the getter is generated. Property definitions (which print `PropertyFlag(%u)`) are written after all `rna_def_property_funcs` calls (`makesrna.cc:4256-4262` before the struct output), so the flag reaches the runtime, `is_never_none` and the stubs. The change has no behavioural effect because all 62 properties are read-only. `PROP_NEVER_NULL` on a pointer only blocks assigning `None` (`RNA_types.hh:441-447`).
- **Callback parameters.** The 17 `Context | None` parameters are callback parameters defined with `RNA_def_parameter_flags(parm, PropertyFlag(0), PARM_REQUIRED)`, while `Panel`, `Operator`, `Node`, `NodeSocket`, `Gizmo` and `GizmoGroup` use `PROP_NEVER_NULL` (table below). In every C caller the context comes from a live `bContext *C`, with one exception: `RenderEngine.view_draw` can receive `None` during off-screen drawing. Fix: add `PROP_NEVER_NULL` to the 16 safe parameters in the RNA definitions, the same one-token change Panel already has. The generator needs no change. `view_draw` is a judgement call (see below).
- **Diagnostics removed** (from `.cache/analysis/main-builtin.txt`, 14,077 total):
  - **Embedded pointers: 712** (`nullable:other-pointer/optional` 496, `nullable:type-discriminated-pointer` 92, `nullable:context-member` 124; by area: product 331, presets 333, tests/doc/tools 48). Every diagnostic matched by type is unambiguous: no embedded target type is also reached through a nullable pointer, except `BoneColor`, where the 4 matches are resolved by attribute name.
  - **Callback `Context | None`: 372** (all in the `nullable:context-member*` buckets: 346 + 26; product 362, tests/doc 10). Many of these turn into the next link's `Scene | None` and similar until the `context_members` guarantee lands. So the net drop is smaller than 372 on its own, and close to 372 together with #68.

## Where nullability is decided, end to end

1. RNA definition: `RNA_def_property_flag(prop, PROP_NEVER_NULL)` for properties, `RNA_def_parameter_flags(parm, PROP_NEVER_NULL, ...)` for function parameters. In `makesrna/intern/rna_define.cc:1281-1293`, a string gets `PROP_NEVER_NULL` by default and a pointer gets only `PROP_THICK_WRAP`.
2. Python: `bpy.types.Property.is_never_none` reads the flag. `_rna_info.py:335` copies it into `InfoPropertyRNA.is_never_none`.
3. `_rna_info.py:571-574` appends `" | None"` (for arguments: `default_str == "None"`, which every pointer has; for attributes: `type == "pointer"`). Line 612 also adds the "never None" qualifier to the docs.
4. `sphinx_doc_gen.py` writes `:type:` with that string into the RST, and `sphinx_stub_gen.py` copies it into `bpy/types/__init__.pyi` (for example `dof: CameraDOFSettings | None` at line 1887 and `render: RenderSettings` at line 3076 of `.cache/bpy-stubs-builtin/main/bpy/types/__init__.pyi`).

Collections never get `| None` as attributes; only pointers do.

## Pointer properties, classified from the generated getters

Method: every `PointerPropertyRNA` with a non-null getter in `rna_*_gen.cc` (function parameters have none), classified by its getter body. `rna_type` (one per struct, 663) is left out. Target "ID" means the target class derives from `ID` in the stubs.

| Getter | non-ID target | ID target | Meaning |
|---|---|---|---|
| already `PROP_NEVER_NULL` | 218 | 8 | already non-None in the stubs (`Scene.render`, `Scene.tool_settings`, ...) |
| auto, `&data->member` (**embedded**) | **62** | 0 | never NULL: becomes non-None with the makesrna hook |
| auto, `data->member` (DNA pointer) | 211 | 307 | can be NULL: stays `| None` |
| hand-written getter | 159 | 36 | unknown statically: stays `| None` |
| **total** | 650 | 351 | 1001 |

`AnimData` isn't an ID, so all `*.animation_data` count as "DNA pointer, non-ID": nullable, as they should be.

The 62 embedded properties: `Bone.color`, `PoseBone.color`, `Brush.texture_slot`, `Brush.mask_texture_slot`, `Camera.dof`, `Scopes.histogram`, `TextCurve.edit_format`, `Image.colorspace_settings`, `MaskSplinePoint.parent`, `Material.lineart`, `Object.lineart`, `MovieClip.tracking`, `MovieClip.proxy`, `MovieClip.colorspace_settings`, `CompositorNodeConvertToDisplay.view_settings`/`display_settings`, `CompositorNodeOutputFile.format`, `NodeCompositorFileOutputItem.format`, `FunctionNodeInputString.textbox_state`, `NodeTree.interface`, `Scene.view_settings`/`display_settings`/`sequencer_colorspace_settings`/`display`/`eevee`/`grease_pencil_settings`/`hydra`, `ToolSettings.image_paint`/`paint_mode`/`uv_sculpt`/`particle_edit`/`gpencil_sculpt`/`gpencil_interpolate`, `ImageFormatSettings.view_settings`/`display_settings`/`linear_colorspace_settings`, `SceneDisplay.shading`, `SceneEEVEE.ray_tracing_options`, `RenderSettings.ffmpeg`/`motion_blur_shutter_curve`, `GPencilSculptSettings.guide`, `ImageStrip`/`MovieStrip.colorspace_settings`, `TextStrip.textbox_state`, `ColorBalanceModifier.color_balance`, `CurvesModifier`/`HueCorrectModifier`/`EQCurveMappingData.curve_mapping`, `SpaceImageEditor.scopes`/`sample_histogram`, `SpaceDopeSheetEditor.dopesheet`, `SpaceClipEditor.scopes`, `SpreadsheetTableIDGeometry`/`SpaceSpreadsheet.viewer_path`, `ImageTexture.image_user`, `ColorMapping.color_ramp`, `MovieTracking.settings`/`camera`/`stabilization`/`dopesheet`, `Volume.display`/`render`.

Note that `ToolSettings` mixes both kinds. `image_paint`, `uv_sculpt`, `particle_edit`, `gpencil_sculpt`, `gpencil_interpolate` and `paint_mode` are embedded. `sculpt`, `vertex_paint`, `weight_paint`, `curves_sculpt` and the `gpencil_*_paint` modes are DNA pointers, allocated lazily by `BKE_paint_ensure`. Those last ones are genuinely `None` on a scene from `bpy.data.scenes.new()`. So "owned by the parent" isn't the criterion; the DNA layout is.

### Runtime probe (sanity check, optional)

The static count is exact, so the probe only confirms it. Run it inside Blender main, through a mise task, never directly:

```python
import bpy

def instances():
    for coll in dir(bpy.data):
        c = getattr(bpy.data, coll, None)
        if isinstance(c, bpy.types.bpy_prop_collection):
            yield from c
    yield bpy.context.preferences
    yield bpy.context.window_manager

seen, none = {}, set()
stack = list(instances())
while stack:
    obj = stack.pop()
    if not hasattr(obj, "bl_rna") or obj.as_pointer() in seen:
        continue
    seen[obj.as_pointer()] = obj
    for prop in obj.bl_rna.properties:
        if prop.type != "POINTER" or prop.identifier == "rna_type":
            continue
        v = getattr(obj, prop.identifier, None)
        key = f"{obj.bl_rna.identifier}.{prop.identifier}"
        if v is None:
            none.add((key, prop.is_never_none))
        elif not isinstance(v, bpy.types.ID):
            stack.append(v)

print(sorted(none))
```

It must show that none of the 62 embedded properties (list above) is ever `None`, on factory startup plus fresh `bpy.data.<collection>.new()` data, and that no `PROP_NEVER_NULL` property is `None`. Properties that show up `None` are the exceptions; expect DNA-pointer ones such as `ToolSettings.sculpt`, `Object.pose` and `*.animation_data`.

## Callback parameters

Pointer parameters of `FUNC_REGISTER` functions in `makesrna/intern/rna_*.cc`, as they stand now:

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

`view_draw` is the only real exception. Cycles itself dereferences the context unconditionally (`intern/cycles/blender/addon/__init__.py:94-95`: `context.region`, `context.space_data`). So typing it `Context` matches what Blender's own engine assumes, but it isn't strictly sound. Option A: mark it `PROP_NEVER_NULL` too, as a documented unsoundness. Option B: keep it nullable. The map's rule ("callback parameters Blender *always* passes") points to B. It costs only the `view_draw` diagnostics, a handful.

Other nullable callback parameters seen on the same path (not counted above): `UIList.draw_item(layout, data, item, active_data)`, `UIList.filter_items(data)`, `AssetShelf.draw_context_menu(asset, layout)`, `KeyingSetInfo.iterator/generate(ks)`, the `RenderEngine.*(depsgraph)` parameters, `RenderEngine.bake(object)`, `RenderEngine.update_script_node(node)`, `Node.poll(node_tree)`. `UIList.draw_filter(layout)` already has `PROP_NEVER_NULL`, and `draw_item(layout)` is built from the same non-null layout (`uilist_draw_item`). These belong to the same RNA edit if the spec wants them.

**How the generator learns it:** through the RNA flag, because `_rna_info.py` already honours `is_never_none`, so the change is `PropertyFlag(0)` → `PROP_NEVER_NULL` on 16 parameter definitions (`rna_ui.cc` ×9: Header 1, Menu 2, UIList 3, AssetShelf 2, FileHandler 1; `rna_animation.cc` ×3; `rna_render.cc` ×4: `draw`, `view_update`, `view_pause`, `view_resume`). A generator-side rule ("a `Context` parameter of a registered function is never None", readable through `Function.is_registered`) also works without touching C, but it would hard-code `view_draw` as an exception and wouldn't change the runtime's `is_never_none` or the docs. The RNA edit is the upstreamable one, and it mirrors what `Panel` / `Operator` already do.

## Counting method

The classifier is the one in `.cache/analysis/bucket.py`. A diagnostic counts:

- for callbacks, when its message contains `` `Context | None` ``;
- for embedded pointers, when it is in a `nullable:*` bucket and its first `` `X | None` `` names a type X that is the target of an embedded property. If X were also reached through a nullable pointer, the diagnostic would count only when the source line accesses `.<embedded attribute>`. The only such type was `BoneColor` (4 diagnostics, all through embedded `.color`); no other diagnostic was ambiguous.

By target type: `SceneEEVEE` 101, `MovieTrackingCamera` 93, `FFmpegSettings` 80, `ColorManagedViewSettings` 75, `MovieTrackingSettings` 56, `ImagePaint` 47, `MovieTracking` 39, `CameraDOFSettings` 34, `ParticleEdit` 32, `RaytraceEEVEE` 29, `GPencilSculptSettings` 23, `NodeTreeInterface` 19, `GPencilSculptGuide` 19, `SceneDisplay` 10, `VolumeDisplay` 9, others 46.

A removed diagnostic can expose the next link of the same chain (for example `context.scene.eevee.x`, where `scene` is `Scene | None`). Those are already counted separately in `nullable:context-member`, so these numbers are what each change removes on its own.
