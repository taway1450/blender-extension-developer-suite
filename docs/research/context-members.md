# Which Context members does Blender guarantee in each callback?

Research for [#68](https://github.com/taway1450/blender-extension-developer-suite/issues/68) (map [#67](https://github.com/taway1450/blender-extension-developer-suite/issues/67)). Sources: Blender `main` as checked out in `.cache/blender-src/main` (the `dc491af090` of the map), Blender's own stubs in `.cache/bpy-stubs-builtin/main`, the ty fork in `ty-blender/ruff-blender`, and `.cache/analysis/main-builtin.txt`. Read from source only; the runtime probes that would confirm the open points are described at the end, not run.

Paths below are relative to the Blender source root unless they start with `ty-blender/`.

## How a Context member is read

Two paths, and which one a member takes decides when it can be `None`.

1. **RNA properties of `Context`** (`window_manager`, `window`, `workspace`, `screen`, `area`, `space_data`, `region`, `region_popup`, `region_data`, `gizmo_group`, `asset`, `blend_data`, `scene`, `view_layer`, `engine`, `collection`, `layer_collection`, `tool_settings`, `preferences`, `mode`) are defined in `source/blender/makesrna/intern/rna_context.cc` (`RNA_def_context`, lines 250-380). `pyrna_struct_getattro` finds them first (`source/blender/python/intern/bpy_rna.cc:4899`) and calls the C getter. None of them has `PROP_NEVER_NULL`, which is why the stubs type every pointer `X | None`.
2. **Everything else** (`object`, `active_object`, `selected_objects`, `edit_object`, ...) falls through to `CTX_data_get` (`bpy_rna.cc:4907-5029`): a pointer member that the screen/area/region callbacks answer with no data gives `None` (`CTX_RESULT_NO_DATA`, line 5022), and a member nobody answers raises `AttributeError` (line 5028). Blender's own stubs type these members **without** `None` (`object: Object`, `active_object: Object`, ...), so they produce no `nullable:context-member` diagnostics today; that is a stub soundness question for `api_types`, not for this feature.

`CTX_data_get` (`source/blender/blenkernel/intern/context.cc:478-573`) asks, in order: a Python `temp_override` dict, the context store (`layout.context_pointer_set`), the region type's callback, the area type's callback, the screen's callback (`editors/screen/screen_context.cc`). The window-manager getters `CTX_wm_window/screen/area/region` (`context.cc:937-967`) read `C->wm.*`, also overridable from a `temp_override`.

## The always-guaranteed members

| Member | Getter | Why it is never `None` |
|---|---|---|
| `preferences` | `rna_Context_preferences_get` returns `&U` (`rna_context.cc:214`) | A static global; it does not even read the context. `_RestrictContext` (`scripts/modules/_bpy_restrict_state.py:16`), the stand-in `bpy.context` during add-on `register()` at startup, also serves it. |
| `window_manager` | `CTX_wm_manager` = `C->wm.manager` (`context.cc:927`) | Set at startup and on every file load, also in background mode (Blender always has one window manager); `CTX_wm_interface_locked` (`context.cc:932`) dereferences it unguarded. `_RestrictContext` serves it too. |
| `blend_data` | `CTX_data_main`: an override, else `C->data.main` (`context.cc:1312`) | `C->data.main` is set for the whole session (`CTX_data_main_set`). |
| `scene` | `CTX_data_scene`: the screen callback `screen_ctx_scene` (window's active scene, `screen_context.cc:128`), else `C->data.scene` (`context.cc:1328`) | `CTX_wm_window_set` sets `C->data.scene = win->scene` (`context.cc:1194`); in background mode file loading sets it. Blender's own getters assume it: `CTX_data_engine_type` dereferences it (`context.cc:1374`, so `context.engine`, typed `str`, would crash otherwise) and so does `rna_Context_view_layer_get` (`rna_context.cc:166`). |
| `view_layer` | `CTX_data_view_layer` (`context.cc:1351`) | Falls back to `BKE_view_layer_default_view(scene)`; a scene always has a view layer. Non-`None` whenever `scene` is. |
| `tool_settings` | `CTX_data_tool_settings` (`context.cc:1560`), `rna_Context_tool_settings_get` | `scene->toolsettings`, allocated in `scene_init_data` (`blenkernel/intern/scene.cc:194`) and freed only with the scene (`scene.cc:416`). Non-`None` whenever `scene` is. **Not in the map's settled list**; it is the same guarantee as `view_layer` and carries 267 diagnostics (`ToolSettings \| None`) on builtin stubs. |

These hold in **every** callback, including `Operator.execute` in background mode, timers and handlers, so the guarantee does not depend on the callback kind at all. The only way to break them is user code: `context.temp_override(scene=None)` (a `None` value in the override dict answers the member with no data) around a call that reaches the callback. That is outside "Blender calls the callback" and stays a known unsoundness.

`preferences` and `window_manager` are non-`None` even outside callbacks (module level, `register()`); `blend_data`, `scene`, `view_layer` are not reachable through `_RestrictContext` at startup (`AttributeError`, not `None`). So the settled scope (inside callbacks only) is right for those three; `preferences` / `window_manager` could be guaranteed everywhere, at the spec's choice.

## Window members per callback

`window`, `workspace`, `screen`, `area`, `space_data`, `region` come from `C->wm.*`, set by the window manager when it draws or dispatches an event (`CTX_wm_window_set` / `_area_set` / `_region_set`, `context.cc:1190-1245`). `space_data` is `area->spacedata.first` (`context.cc:958`), so it is non-`None` exactly when `area` is.

| Callback | `window` / `screen` / `workspace` | `area` / `space_data` | `region` | Evidence |
|---|---|---|---|---|
| `Panel.poll` / `draw` / `draw_header` / `draw_header_preset`, drawn in its region | yes | yes, of `bl_space_type` | yes, of `bl_region_type` | A panel type is registered into the `ARegionType` of its `bl_space_type` / `bl_region_type` (`rna_ui.cc` `region_type_find`, line 88, used at 209 / 296) and drawn by that region's draw. |
| the same Panel drawn as a **popover** (`layout.popover`, `wm.call_panel`) | yes | an area, but **of whatever editor opened it** | the popup region | `popover_panel_invoke` (`editors/interface/regions/interface_region_popover.cc:321`) finds the panel by idname (`WM_paneltype_find`) with no space-type check. Blender's own UI uses `bl_space_type` as a **dummy** on popover-only panels: `TOPBAR_PT_tool_fallback` says `VIEW_3D` and is drawn from the top bar (`space_toolsystem_common.py:861`), `IMAGE_PT_uv_sculpt_curve` says `'TOPBAR'  # dummy.` (`space_image.py:1422`); 7 `# dummy` lines in `bl_ui`. |
| `Header.draw` | yes | yes, of `bl_space_type` | yes | Registered into `art->headertypes` of its space/region (`rna_ui.cc:829-925`), drawn only there. |
| `Menu.poll` / `draw` | yes | **no** guarantee | yes (a popup or the header region) | Menus have no `bl_space_type`; `wm.call_menu` opens any menu from any editor's keymap. |
| `UIList.draw_item` / `draw_filter` / `filter_items` | yes | **no** | yes | `template_list` runs in any layout: a panel, a menu, an operator dialog. |
| `Operator.poll` / `invoke` / `execute` / `modal` / `cancel` | **no** (background mode, `bpy.app.timers`, app handlers) | **no** | **no** | Operators have no `bl_space_type`; `bpy.ops` calls from anywhere. |
| `Operator.draw` (redo panel, props dialog) | yes | **no** (a dialog from a timer has none) | yes | drawn in a UI region. |
| `GizmoGroup.poll` / `setup` / `refresh` / `draw_prepare`, `Gizmo.*` | yes | yes, of the group's `bl_space_type` | yes, of `bl_region_type` | Gizmo maps are per `{space, region}` type (`WM_gizmomaptype_ensure`). Not confirmed callback by callback here; see probes. |
| `RenderEngine.view_update` / `view_draw` | yes in practice | **no**: Blender itself null-checks `CTX_wm_area(evil_C)` before calling (`draw/engines/external/external_engine.cc:281-297`) | not claimed | `render` / `update` / `bake` take no context. |
| `AddonPreferences.draw` | yes | yes (`PREFERENCES` space) | yes | drawn in the Preferences editor's panel; not worth a special case. |

So the settled rule "`area` / `region` / `space_data` with a `bl_space_type`" is **right for Panel (in its region), Header and GizmoGroup**, and must **not** apply to Menu, UIList, Operator and RenderEngine (no `bl_space_type`). Its one gap is the popover: a Panel with a `bl_space_type` still gets non-`None` `area` / `space_data` (a popover opens from an editor), but `space_data` is the opening editor's subclass, not necessarily `bl_space_type`'s. Whether a panel is only ever a popover cannot be seen statically, so the spec should record this as a known unsoundness rather than special-case it. `window` / `screen` / `workspace` are guaranteed in every drawn callback but are not in the settled list and carry only ~100 diagnostics; adding them for UI callbacks is cheap but optional.

## `bl_space_type` → `Space` subclass

The mapping is the C switch `rna_Space_refine` (`makesrna/intern/rna_space.cc:795-838`), keyed by the enum `rna_enum_space_type_items` (`rna_space.cc:92`):

| `bl_space_type` | `space_data` type |
|---|---|
| `VIEW_3D` | `SpaceView3D` |
| `IMAGE_EDITOR` | `SpaceImageEditor` |
| `NODE_EDITOR` | `SpaceNodeEditor` |
| `SEQUENCE_EDITOR` | `SpaceSequenceEditor` |
| `CLIP_EDITOR` | `SpaceClipEditor` |
| `DOPESHEET_EDITOR` | `SpaceDopeSheetEditor` |
| `GRAPH_EDITOR` | `SpaceGraphEditor` |
| `NLA_EDITOR` | `SpaceNLA` |
| `TEXT_EDITOR` | `SpaceTextEditor` |
| `CONSOLE` | `SpaceConsole` |
| `INFO` | `SpaceInfo` |
| `OUTLINER` | `SpaceOutliner` |
| `PROPERTIES` | `SpaceProperties` |
| `FILE_BROWSER` | `SpaceFileBrowser` |
| `SPREADSHEET` | `SpaceSpreadsheet` |
| `PREFERENCES` | `SpacePreferences` |
| `PROJECT` | `SpaceProject` |
| `TOPBAR`, `STATUSBAR`, `EMPTY` | `Space` (no refined type: "Currently no type info", line 830) |

**Not in RNA metadata.** Nothing in the RNA reflection links an enum item to a struct: the refine function is C code, and the Space subclasses have no `bl_space_type`-like property. Names do not follow a rule either (`NLA_EDITOR` → `SpaceNLA`, `DOPESHEET_EDITOR` → `SpaceDopeSheetEditor`, `PREFERENCES` → `SpacePreferences`). Ways to generate it, inside Blender (where the stub generator already runs):

- **Probe in the generator:** for each `bpy.types.Area.bl_rna.properties["type"].enum_items` identifier, set a scratch area's `type` under a `temp_override` and record `type(area.spaces.active).__name__`. Needs a window (not `--background`) or must be tried there first; see probe 2.
- **Scrape the C switch** (`case SPACE_X: return RNA_SpaceY;`) together with the enum (`{SPACE_X, "IDENT"`) from `rna_space.cc`. Exact, but parses C and needs the source tree.

Either way the table is emitted as a generated fact (the map's settled "table generated from RNA"); a hand table checked by `check:load` is the fallback if neither is acceptable.

## Diagnostic volume (builtin stubs, `main-builtin.txt`)

Messages naming `X | None` per member type: `Scene` 1,516, `Space` 937 (almost all also need the subclass: `Space | None` has no attribute `shading`), `Preferences` 343, `ViewLayer` 329, `WindowManager` 273, `ToolSettings` 267, `Window` 55, `Region` 40, `Collection` 39, `Area` 27, `WorkSpace` 23, `Screen` 21, `AssetRepresentation` 20, others < 10. The settled members plus `tool_settings` cover ~4,000 of the ~4,460 bucket, minus reads that happen outside callbacks (helper functions taking a `context` parameter, module-level `bpy.context`), which a callback-scoped hook does not reach.

## Where ty-blender can narrow

**Hook site:** `blender::on_load` (`ty-blender/ruff-blender/crates/ty_python_semantic/src/types/dedicated/blender/member.rs:402`), the same one-line hook that already drops `None` from `self.layout` in draw callbacks (`member.rs:438`, `is_drawn_layout` / the tracked `is_draw_callback`, lines 460-523). Add a sibling branch:

- the attribute name is a guaranteed member, the receiver type is `bpy.types.Context` (an instance), and the read is lexically inside a Blender callback of a class deriving from a callback root: the same scope walk as `is_drawn_layout`, but with the callback found through `ty_blender::callback_of(root, name)` (the table `override_types` uses, `overrides.rs:35`, `callback_root` at line 57) instead of the `DRAW_CALLBACKS` list;
- then `place.map_type(without_none)` for the five-or-six always-guaranteed members, and for `space_data` / `area` / `region` only when the root is `Panel` / `Header` / `GizmoGroup`(/`Gizmo`) and the class (or a base) has a literal `bl_space_type` / `bl_region_type`; `space_data` is replaced by the table's subclass.
- Keying on the receiver's **type**, not on it being the `context` parameter, covers `ctx` renames (already typed `Context` by `override_types` hook B), `bpy.context.scene` inside a callback (the same C context at runtime), and aliases (`scene = context.scene`) since the hook changes the expression's type. Helpers outside the callback keep the stub type, as settled.
- `bl_space_type` is read the way the fork already reads class attributes for operators (`bl_idname`), a type-free fact for `crates/ty_blender`; it needs a tracked per-class query so `draw` does not depend on the class body's AST from another file.

No upstream file changes beyond what exists: the `on_load` hook is already in place.

## `poll()` narrowing (input for the fog)

- **Blender's guarantee:** `poll` gates the other callbacks for Panel (`draw`, `draw_header` only after `pt->poll`, e.g. `interface_region_popover.cc:331`), Menu, and Operator `invoke` / `execute` (`WM_operator_poll` in `windowmanager/intern/wm_event_system.cc:1137`, `1385`, `1656`; `bpy.ops` raises "context is incorrect" otherwise). **Not** for `modal` or `cancel` (later events; the context may have changed since `invoke`), and not confirmed for `Operator.draw`.
- **Payoff on builtin stubs is small.** The members `poll` typically checks (`context.object`, `active_object`, `edit_object`) are already typed non-`None` by Blender's stubs, so they produce no diagnostics today. What remains is `space_data` / `area` checks in Operator/Menu polls (`context.area.type == 'VIEW_3D'`, `context.space_data is not None`), a few hundred lines at most. On fake-bpy-module (everything `| None`) the payoff is larger, but that generator is out of the map's main scope.
- **Feasibility and cost:** a tracked per-class query that reads `poll`'s `return` expressions and collects conjuncts of the forms `context.X`, `context.X is not None`, `context.X.type == 'LIT'` (and `and` chains; early `return False` guards make it harder), then the `on_load` branch above consults it for `draw` / `invoke` / `execute`. Cost: a small AST pattern matcher (no type inference needed for the `is not None` / truthy forms; the `area.type == 'VIEW_3D'` → `SpaceView3D` form needs the space table and Type-tag machinery), plus soundness caveats (poll inherited from a mixin, poll calling a helper). Estimate: one build slice, comparable to `is_drawn_layout`; recommended to defer until the re-measured bucket report shows what is left.

## Probes that would confirm the open points (not run)

1. **Member matrix.** An add-on whose Panel (`VIEW_3D`/`UI`), the same Panel opened by `wm.call_panel` from the Outliner, a Header, a Menu (via `wm.call_menu` from the Outliner), a UIList, a GizmoGroup, and an Operator (run from a button, from `bpy.app.timers`, and in `--background` via `bpy.ops`) each record `{m: getattr(context, m) is None}` for every RNA `Context` member plus `type(context.space_data).__name__`; print the matrix from `check:load`.
2. **Space table.** In Blender with a window, for each `Area.type` enum identifier set a scratch area's type under `temp_override(area=...)` and record `type(area.spaces.active).__name__`; also try it with `--background` to learn whether the generator can do it there.
3. **`temp_override(scene=None)`** around `bpy.ops.<op>()` to confirm `context.scene is None` inside `execute` (the known unsoundness).
