# implied_narrowings

**The checker must:** narrow a read that Blender's call order or naming conventions make safe but no test in the
code shows, and report it under a `blender-narrowed-by-*` rule (category `blender-implied-narrowings`, `warn` by
default), while a pointer nothing checked stays an error.

## What Blender does

- **`poll()` gates callbacks:** Blender calls a Panel's `draw` / `draw_header` / `draw_header_preset`, a Menu's
  `draw`, an Operator's `invoke` / `execute` and a GizmoGroup's `setup` / `refresh` / `draw_prepare` /
  `invoke_prepare` only right after the class's `poll()` returned True, with the same context (`area.cc`,
  `WM_menutype_poll`, `WM_operator_poll`, the gizmo map; `bpy.ops` refuses an operator whose poll fails). A poll that
  raises counts as False (`rna_ui.cc` reads the result parameter, which stays false), so a pointer read through while
  the result is computed (`ob.data.is_editmode`) was not None either. Not gated: Operator `modal` / `cancel` (later
  events), `check`, `description`, `draw` (a props dialog draws without a new poll) and UIList callbacks.
- **Sub-panels:** Blender polls a sub-panel (`bl_parent_id`) only while it draws the parent panel, and draws the parent
  only after the parent's poll returned True (`ed_panel_draw` in `area.cc`). So every poll up the chain holds in a
  sub-panel's own `poll` and in the callbacks it gates. A sub-panel opened as a popover or through `wm.call_panel` is
  drawn without its parent.
- **Menu idname prefixes:** a Menu has no `bl_space_type` and can be drawn from any editor, but by convention its
  idname starts with the header prefix of the editor it belongs to (`CLIP_MT_view`, as the header is
  `CLIP_HT_header`); menu search relies on it (`<PREFIX>_MT_editor_menus`). The 19 header prefixes, `TIME` (dope sheet)
  and `ASSETBROWSER` (file browser) name an editor; `TOPBAR` / `STATUSBAR` have no `Space` subclass.
- **`bl_context`:** Blender adds a top-level panel to a region only when the region's contexts name its `bl_context`,
  before it polls the panel (`panel_add_check` in `area.cc`), and draws a sub-panel only inside its parent. The
  Properties editor's main region passes the active tab, and a tab is shown only while its context path exists
  (`buttons_context_compute` in `buttons_context.cc`): the `object`, `physics`, `constraint`, `modifier`, `shaderfx` and
  `bone_constraint` paths need an object, which is `context.object` there; `data`, `material` and `particle` also take
  pinned data, a material or particle settings without one. The 3D viewport's sidebar and toolbar pass the mode's
  string (`CTX_data_mode_string` in `context.cc`), so `"mesh_edit"` is drawn only in mesh edit mode. Their dotted
  contexts (`".objectmode"`, `".mesh_edit"`, `".paint_common"`) are display-only groups of tool settings that the tool
  header also draws as popovers, where no context is checked; other editors check no mode.
- **Popovers:** a Panel opened as a popover (`layout.popover`, `wm.call_panel`) is drawn with the area of the editor
  that opened it, whatever its `bl_space_type` says.

## Rules

| Rule | Reports | Typed as |
| --- | --- | --- |
| `blender-narrowed-by-poll` | a read of a pointer the class's `poll()` checked, in a callback the poll gates | not `None`; a Type tag test narrows it (`ob.type == 'MESH'` makes `ob.data` a `Mesh`), and one on `space_data` or `area` makes `space_data` the editor's subclass |
| `blender-narrowed-by-menu-prefix` | `space_data` / `area` in a menu's `draw` / `poll`, from its idname prefix | the prefix's `Space` subclass; `area` not `None` |
| `blender-narrowed-by-popover` | `space_data` in a Panel the same add-on opens as a popover | its `bl_space_type` subclass |
| `blender-narrowed-by-bl-context` | a context member a Panel's `bl_context` guarantees, in its `poll`, its gated callbacks and those of its sub-panels | `context.object` not `None` in the object-needing Properties tabs; in the 3D viewport's mode contexts what the mode gives (as `context.mode == ...` in a poll) |

What a poll checks is read from its code: the conjuncts of a `return` (`X`, `X is not None`, `isinstance(X, T)`,
`bool(X)`, `X.type == 'LIT'` / `in {...}`, `context.mode == 'EDIT_MESH'` / `in {...}`, which gives what that mode
implies by `CTX_data_mode_enum_ex`: the edit object of the mode's type, the paint mode's tool settings, the pose of
an armature), attribute reads always evaluated while the result is computed, early
`return False` guards, local aliases (`ob = context.object`, `ob = getattr(context, "object", None)`, `(ob :=
context.object)`), `super().poll(context)` / `Base.poll(context)`, an inherited or mixin poll, `bool(a and b)`, a `try`
whose handlers never return true, `XrSessionState.is_running(context)` (which checks
`window_manager.xr_session_state`), and helper functions taking the context, followed up to three calls deep. A fact is about a path from the context
(`context.object.active_material`, also through a local alias), never about the class as a whole: a pointer the poll
did not check stays an error. A read that the callback only tests (`if context.object:`, `x = context.object` with
`if x is None:` after it) or that sits where the callback's own test already narrows it is not reported. A Panel's,
Header's or GizmoGroup's `bl_space_type` stays a silent guarantee unless the panel is a popover. A read a poll's `return` only tests
(`return context.object is not None`) is not reported either.

A sub-panel gets the facts of the polls up its `bl_parent_id` chain, the parent being the panel of that idname in the
same file or else the same add-on (a parent that is Blender's own panel gives nothing), and the message names the parent
whose poll checked the read. A sub-panel the add-on also opens as a popover gets none. A read inside a poll knows what
the poll's earlier guards checked (`if not helper(context): return False`, `helper(context) and context.object.mode`):
that is the poll's own control flow, so it is not reported.

## Configuration

The category's name sets all three rules (`blender-implied-narrowings = "ignore"`), a rule's name one of them, as for
the other categories; `[blender] strictness = "lenient"` ignores them, `default` warns, `strict` makes them errors.
An ignored rule still narrows.

| Addon | Variant |
| --- | --- |
| `nar_poll` | Panel conjuncts (`is not None`, truth, `isinstance`, `bool`, `bpy.context`, a sub-pointer, an alias), `draw_header`; early guards with a Type tag giving `ob.data`; a mixin poll, `super().poll`, `Base.poll` and helpers two calls deep giving `space_data` a subclass; a Menu poll reading `area.type`; a GizmoGroup; not reported: a tested read; errors: a pointer the poll did not check; guards: `modal`, `Operator.draw`, a class with no poll |
| `nar_poll_reach` | a sub-panel's `poll` and `draw`, a grandchild and a sub-panel in another module reading their parents' facts; the poll's own flow after a helper guard and through `and` (silent); `getattr` and walrus aliases; `XrSessionState.is_running`; `bool(a and b)`; a helper's `try` body; errors: a sub-panel also opened as a popover, a pointer no poll up the chain checked |
| `nar_mode` | `context.mode` in a poll: `EDIT_MESH` (object, active and edit object as mesh objects), `SCULPT` (`tool_settings.sculpt`, also silently in the poll after a guard), `in {"PAINT_VERTEX", "PAINT_WEIGHT"}` (only what both give), `POSE` (`object.pose`); errors: `OBJECT` gives nothing |
| `nar_menu_prefix` | `VIEW3D_`, `CLIP_` (`bl_idname`), `TIME_`, `TOPBAR_` menus in `draw` and `poll`; guards: a helper method, an add-on's own prefix |
| `nar_popover` | a panel opened by `layout.popover` and one by `wm.call_panel`; silent: a panel drawn only in its region; `strictness` presets (`_expected/strictness.toml`) |
| `nar_bl_context` | Properties `object` (through a mixin, in a poll, a sub-panel) and `physics` tabs; `mesh_edit` (sidebar) and `posemode` (toolbar); a poll's own check wins over `bl_context`; errors: the `data` tab, `".objectmode"`, `".mesh_edit"`, `"objectmode"`, a mode in the image editor, a panel opened as a popover, `active_object` in a Properties tab; `strictness` presets |
| `nar_config` | an `[[overrides]]` entry in `tests/typecheck/ty.toml`: the category at `error`, `blender-narrowed-by-menu-prefix` at `ignore` |

The `blender-*` markers need the checker; the upstream ones and the `| None` markers are guards (`bare-ok`).

**Named exceptions:** only Blender main's builtin stubs type the dynamic context members (`context.object`,
`active_node`, ...) `X | None`; 5.2's stubs type them non-None and its callbacks' `context` parameter `Context |
None`, so the poll and `bl_context` markers (`nar_poll`, `nar_poll_reach`, `nar_mode`, `nar_bl_context`) fail on 5.2. fake-bpy-module has no Type tag
views, so the markers that a Type tag narrows (`nar_poll`'s `active_object.data` as `Mesh` and `object.data` as
`Light`, `nar_mode`'s and `nar_bl_context`'s `object.data` as `Mesh`) fail with it.
