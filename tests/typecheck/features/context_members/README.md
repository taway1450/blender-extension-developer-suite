# context_members

**The checker must:** drop `None` from a Guaranteed context member read inside a Blender callback, and type
`context.space_data` by the `bl_space_type` of a Panel, Header or GizmoGroup.

## What Blender does

- **Always filled in a callback:** `preferences`, `window_manager`, `blend_data`, `scene`, `view_layer` and
  `tool_settings`. `preferences` is a static global, the window manager and `Main` exist for the whole session,
  `scene` is the window's scene (or the loaded file's in background mode), and `view_layer` / `tool_settings` belong
  to the scene. This holds in every callback, `Operator.execute` in `--background` included. The stubs type them
  `X | None`, since a restricted context (`bpy.context` while add-ons are imported) or `temp_override(scene=None)`
  has none.
- **The editor of a Panel, Header or GizmoGroup:** Blender registers it into the region type of its
  `bl_space_type` and draws or runs it only there, so `area`, `space_data` and `region` are set, and `space_data` is
  the editor's `Space` subclass (`'VIEW_3D'` gives `SpaceView3D`; `'TOPBAR'`, `'STATUSBAR'` and `'EMPTY'` have none
  and give `Space`). The subclass is the one whose Type tag (`SpaceView3D.type: Literal['VIEW_3D']`) names it.
  `GizmoGroup.setup_keymap` runs when the key map is set up, outside any editor, and gets nothing of this.
- **No editor:** a Menu (`wm.call_menu` from any editor), a UIList (drawn in any layout), an Operator (run from
  anywhere, a timer or `--background`) and a RenderEngine have no `bl_space_type`; their `area`, `space_data` and
  `region` may be None.

The checker keys on the receiver's type, `bpy.types.Context`, so `context.scene`, a renamed parameter
(`ctx.scene`), `bpy.context.scene` and an alias (`scene = context.scene`) are all narrowed, but only lexically inside
the callback (a lambda or comprehension in it too): a helper function, a nested `def` (it may run later) and module
level keep the stub type.

Known unsoundness, not special-cased: a Panel opened as a popover (`layout.popover`, `wm.call_panel`) gets the
opening editor's area, so its `space_data` may be another subclass; and `context.temp_override(scene=None)` around a
call that reaches a callback breaks every guarantee. `Gizmo` callbacks are left out: they run in their group's
editor, but that was not confirmed.

| Addon | Variant |
| --- | --- |
| `ctx_members` | the six members in `Panel.poll` / `draw`, `Operator.execute`, `Menu.draw`, `UIList.draw_item`; `bpy.context`, a renamed parameter, an alias, a comprehension; still `\| None` in a nested `def`, a helper and at module level |
| `ctx_spaces` | `space_data` / `area` / `region` in a `VIEW_3D` Panel, a Panel whose base sets `bl_space_type`, `PROPERTIES` and `TOPBAR` Headers, a GizmoGroup; still `\| None` in a Menu, a UIList and an Operator |

The markers in the callbacks need the checker; the `| None` ones are guards (`bare-ok`). Only Blender main's stubs
type the callbacks' `context` parameter `Context` (5.2's say `Context | None`, so every read in a callback is an
error there) and declare the Type tags `space_data` is read from: 5.2 fails these markers, a named exception in
spec #75.
