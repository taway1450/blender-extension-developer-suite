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
- **Menu idname prefixes:** a Menu has no `bl_space_type` and can be drawn from any editor, but by convention its
  idname starts with the header prefix of the editor it belongs to (`CLIP_MT_view`, as the header is
  `CLIP_HT_header`); menu search relies on it (`<PREFIX>_MT_editor_menus`). The 19 header prefixes, `TIME` (dope sheet)
  and `ASSETBROWSER` (file browser) name an editor; `TOPBAR` / `STATUSBAR` have no `Space` subclass.
- **Popovers:** a Panel opened as a popover (`layout.popover`, `wm.call_panel`) is drawn with the area of the editor
  that opened it, whatever its `bl_space_type` says.

## Rules

| Rule | Reports | Typed as |
| --- | --- | --- |
| `blender-narrowed-by-poll` | a read of a pointer the class's `poll()` checked, in a callback the poll gates | not `None`; a Type tag test narrows it (`ob.type == 'MESH'` makes `ob.data` a `Mesh`), and one on `space_data` or `area` makes `space_data` the editor's subclass |
| `blender-narrowed-by-menu-prefix` | `space_data` / `area` in a menu's `draw` / `poll`, from its idname prefix | the prefix's `Space` subclass; `area` not `None` |
| `blender-narrowed-by-popover` | `space_data` in a Panel the same add-on opens as a popover | its `bl_space_type` subclass |

What a poll checks is read from its code: the conjuncts of a `return` (`X`, `X is not None`, `isinstance(X, T)`,
`bool(X)`, `X.type == 'LIT'` / `in {...}`), attribute reads always evaluated while the result is computed, early
`return False` guards, local aliases, `super().poll(context)` / `Base.poll(context)`, an inherited or mixin poll, and
helper functions taking the context, followed up to three calls deep. A fact is about a path from the context
(`context.object.active_material`, also through a local alias), never about the class as a whole: a pointer the poll
did not check stays an error. A read that the callback only tests (`if context.object:`, `x = context.object` with
`if x is None:` after it) or that sits where the callback's own test already narrows it is not reported. A Panel's,
Header's or GizmoGroup's `bl_space_type` stays a silent guarantee unless the panel is a popover.

## Configuration

The category's name sets all three rules (`blender-implied-narrowings = "ignore"`), a rule's name one of them, as for
the other categories; `[blender] strictness = "lenient"` ignores them, `default` warns, `strict` makes them errors.
An ignored rule still narrows.

| Addon | Variant |
| --- | --- |
| `nar_poll` | Panel conjuncts (`is not None`, truth, `isinstance`, `bool`, `bpy.context`, a sub-pointer, an alias), `draw_header`; early guards with a Type tag giving `ob.data`; a mixin poll, `super().poll`, `Base.poll` and helpers two calls deep giving `space_data` a subclass; a Menu poll reading `area.type`; a GizmoGroup; not reported: a tested read; errors: a pointer the poll did not check; guards: `modal`, `Operator.draw`, a class with no poll |
| `nar_menu_prefix` | `VIEW3D_`, `CLIP_` (`bl_idname`), `TIME_`, `TOPBAR_` menus in `draw` and `poll`; guards: a helper method, an add-on's own prefix |
| `nar_popover` | a panel opened by `layout.popover` and one by `wm.call_panel`; silent: a panel drawn only in its region; `strictness` presets (`_expected/strictness.toml`) |
| `nar_config` | an `[[overrides]]` entry in `tests/typecheck/ty.toml`: the category at `error`, `blender-narrowed-by-menu-prefix` at `ignore` |

The `blender-*` markers need the checker; the upstream ones and the `| None` markers are guards (`bare-ok`).

**Named exceptions:** only Blender main's builtin stubs type the dynamic context members (`context.object`,
`active_node`, ...) `X | None`; 5.2's stubs type them non-None and its callbacks' `context` parameter `Context |
None`, so the poll markers fail on 5.2. fake-bpy-module has no Type tag views, so `nar_poll`'s two markers that a
Type tag narrows (`active_object.data` as `Mesh`, `object.data` as `Light`) fail with it.
