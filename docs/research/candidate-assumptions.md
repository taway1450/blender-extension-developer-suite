# Candidate Assumptions: how reliable is a menu's idname prefix, and where to report

Research note, 2026-11-16, for [#90](https://github.com/taway1450/blender-extension-developer-suite/issues/90) (map
[#87](https://github.com/taway1450/blender-extension-developer-suite/issues/87)). Trimmed on 2026-11-18 to the
rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings. It
follows on from [context-members.md](context-members.md) (#68).

The note studied three candidate **Assumptions**: pointers checked in `poll()`, `scene` / `view_layer` outside
Blender callbacks, and a menu's idname prefix naming the editor it is drawn in. The design changed since: the
`poll()` check and the menu prefix are **Implied narrowings** on main (`blender-narrowed-by-poll`,
`blender-narrowed-by-menu-prefix`: narrowing from a Blender fact visible in the code), not Assumptions, and every
rule ships at `warn`. What stays here is the prefix evidence and the reporting choice.

Sources: Blender `main` at `7031144c2c` (`.cache/blender-src/main`). Paths are relative to the Blender source root.

## 1. Menu idname prefix → space

### Facts from Blender's source

- A `Menu` has no `bl_space_type`. It is drawn wherever `layout.menu(...)`, `menu_contents`, `wm.call_menu(_pie)`, a
  keymap item or C code (`WM_menu_name_call`, `UI_popup_menu_invoke`) names it. The context is that of the editor
  (area) it is drawn from (#68).
- By convention the idname starts with the editor's prefix. Each editor's header class is `<PREFIX>_HT_*` with that
  editor's `bl_space_type`. These 19 header prefixes map one-to-one to spaces in Blender's own code: no prefix appears
  with two spaces. Menu search relies on the same convention: it maps each space type to its root menu
  `<PREFIX>_MT_editor_menus` (`editors/interface/templates/interface_template_search_menu.cc:628-645`, "by convention
  each space-type has a single root-menu that headers use").
- A menu's idname is `bl_idname`, or the class name when it has none (`python/intern/bpy_rna.cc:9861`, "Allow Python
  `__name__` to be used for `bl_idname`").
- Two Blender-internal prefixes have no header class of their own: `TIME` (the timeline is a dope sheet mode) and
  `ASSETBROWSER` (the asset browser is a file browser mode). `TOPBAR` and `STATUSBAR` have no `Space` subclass, so
  only the non-None part holds for them.

### How reliable is the prefix?

- **Menus in Blender:** most `Menu` classes have one of the 19 header prefixes or `TIME` / `ASSETBROWSER`. Others
  have a prefix that names data, not a space (`OBJECT`, `WM`, `MASK` (drawn in both the clip and the image editor),
  `MESH`, `ARMATURE`, `POSE`, `RENDER`, ...), and some have no `<PREFIX>_MT_` form at all (base classes such as
  node_add_menu's `NodeMenu`). Those get nothing.
- **Draw sites** (idname strings in Python classes with a `bl_space_type`, followed through parent menus, keymap items
  in `blender_default.py` with the keymap's `space_type`, `EMPTY` keymaps resolved to the editors that add them, C
  strings under `editors/space_*`, menu search's map). Of the menus with a header prefix, most are drawn only in
  their own editor, many have no draw site a scan can attribute (`layout.menu(cls.bl_idname)` built dynamically,
  appended draw functions, ...), and **8 contradict the prefix**:
  - drawn in other editors too: `INFO_MT_area` (the View > Area submenu of every editor, 17 spaces),
    `DOPESHEET_MT_channel_context_menu` (the "Animation Channels" keymap, added by the dope sheet, graph and NLA
    editors), `IMAGE_MT_uvs_unwrap` (also `menu_contents` in `space_view3d.py:1514`), `SEQUENCER_MT_modifier_add`
    (also `wm.call_menu` from the Properties editor, `properties_strip_modifier.py:30`);
  - drawn only elsewhere: `TOPBAR_MT_edit_armature_add`, `TOPBAR_MT_edit_curve_add` (drawn in the 3D view; `TOPBAR`
    gives plain `Space`, so only the non-None part is assumed), `USERPREF_MT_extensions_active_repo(_remove)` (from a
    panel whose `bl_space_type` is the top bar, a popover dummy as described in #68).

### Failure examples

- `scripts/startup/bl_ui/space_info.py:74`: `INFO_MT_area.draw` tests `context.space_data.type == 'VIEW_3D'`. It is
  drawn from every editor, but the prefix types `space_data` as `SpaceInfo`, whose Type tag is `'INFO'`. With Type-tag
  narrowing, the branch then looks unreachable, a silent wrong conclusion.
- `scripts/startup/bl_ui/space_dopesheet.py:890`: `DOPESHEET_MT_channel_context_menu`, "This menu is used from the graph
  editor too". It branches on `context.area.type`, and under the prefix `space_data` would wrongly be
  `SpaceDopeSheetEditor` in the graph and NLA editors.
- A user keymap entry `wm.call_menu(name="CLIP_MT_view")` in another editor. Any menu can be bound anywhere, which is why
  this is unusual rather than impossible.
- Add-ons naming menus after data rather than the editor (`IMAGE_MT_my_tools` drawn from a 3D-view panel).

A `bl_space_type` (for Panel / Header / GizmoGroup) stays a silent guarantee, while a prefix-derived space is
reported.

## 2. Blender facts behind the other two candidates

**`poll()` gates these callbacks**, with the same context, immediately before:
- Panel `draw` / `draw_header` / `draw_header_preset`: `editors/screen/area.cc:3416` (region panels),
  `editors/interface/regions/interface_region_popover.cc:331` (popovers),
  `editors/interface/interface_layout.cc:3192` (`layout.popover`).
- Menu `draw`: `WM_menutype_poll` (`windowmanager/intern/wm_menu_type.cc:94`) before every menu draw.
- Operator `invoke` / `execute`: `WM_operator_poll` in `wm_operator_exec` (`windowmanager/intern/wm_event_system.cc:1390`,
  so also after a props dialog and on redo) and in `wm_operator_call_internal` (`:1660`), and `bpy.ops` refuses to
  call one whose poll fails (`python/intern/bpy_operator_function.cc:288`).
- Not gated: Operator `modal` and `cancel` (the context may have changed since `invoke`), `check`, `description`,
  every UIList callback, and any callback that Python code calls directly (`op.execute(context)`;
  `scripts/templates_py/Operator/modal_view3d.py:28` calls `self.execute(context)` from `modal`).
- A poll that raises fails the poll: Blender reads the result from the parameter list after `rna_ext.call`
  (`panel_poll`, `makesrna/intern/rna_ui.cc:112-134`), and a raising poll leaves it false. So an attribute read on
  `X` while computing a true result is as good as `X is not None`.

**`context.scene` outside callbacks** is `CTX_data_scene`: a Python/context-store override, then the screen callback,
else `C->data.scene` (`blenkernel/intern/context.cc:1328-1336`).
- Add-on import and `register()`: `bpy.context` is `_RestrictContext`, so reading `scene` **raises**
  `AttributeError` rather than giving `None` (`scripts/modules/_bpy_restrict_state.py:16-36`, `addon_utils.py:458`).
- `bpy.app.timers`: the first window's scene (`wm_event_system.cc:577-582`, `context.cc:1190-1195`).
- App handlers, `--python` scripts, background mode, tests: the loaded file's scene (`blendfile.cc:1165`).
- The collection importer runs a file handler's import operator with a context whose scene is `nullptr`
  (`editors/object/object_collection.cc:819-825`, call at `:841`), so there `scene` and `tool_settings` are `None`.
- `view_layer` is never `None` while `scene` is set (`context.cc:1351-1368`); without a scene it dereferences
  null rather than giving `None`. `tool_settings` follows `scene` (`context.cc:1560-1572`).

## 3. Reporting

The narrowing happens where ty resolves the member read, a hook that returns a type. Two ways to report it:

- **At the narrowed read:** pass the inference context into the existing hook (it stays one line) and report when
  the narrowing actually removed a `None` or replaced `Space`. One diagnostic per read, so fewer than the errors it
  replaces, since one alias read feeds several uses. Reads that never fail (`if context.scene:`, passing it on to a
  `Scene | None` parameter) are reported too, unless the hook checks that the narrowed place is used.
- **At the failing use:** keep the type, and when an upstream `unresolved-attribute` / `invalid-argument-type` is about
  to be reported on a `None` arm, re-level it if the receiver's canonical path is narrowed. This keeps the counts
  identical to the errors replaced, but it touches upstream's diagnostic paths (more than one hook) and needs the path
  computation at every report site.

The first fits the fork's "one-line hook" rule. The second fits "replace the upstream error" more literally. Main
reports at the read.
