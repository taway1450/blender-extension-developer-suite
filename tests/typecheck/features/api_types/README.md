# api_types

**The stubs must state:** which pointers and callback parameters Blender never sets to None. These are runtime facts
of the Blender API, not something the checker adds: the fix belongs in the stubs (Blender's RNA definitions, which
the stub generator reads), and the markers guard that the stubs keep saying so.

## What Blender does

- **A pointer to a struct embedded by value is never None.** When the DNA member is a struct, not a pointer to one,
  RNA's getter returns the member's address (`Camera.dof`, `Scene.view_settings`, `Scene.eevee`,
  `RenderSettings.ffmpeg`, `ToolSettings.image_paint`, ...: 62 properties, all read-only). Blender's fork flags them
  `PROP_NEVER_NULL` in makesrna, so `is_never_none` is true and the stubs drop `| None`.
- **A DNA pointer can be None:** `ToolSettings.sculpt` (allocated on first use), `Object.pose` (armatures only),
  every `animation_data` (until `animation_data_create()`). They stay `| None`.
- **Blender always passes a context** to `Menu.poll` / `draw`, `Header.draw`, `UIList.draw_item` / `draw_filter` /
  `filter_items`, `AssetShelf.poll` / `draw_context_menu`, `FileHandler.poll_drop`, `KeyingSetInfo.poll` /
  `iterator` / `generate` and `RenderEngine.draw` / `view_update` / `view_pause` / `view_resume`: the C caller
  passes the live `bContext`. `RenderEngine.view_draw` gets None when a viewport is drawn off-screen (Viewport
  Render, `GPUOffScreen.draw_view3d`), so it stays `Context | None`.

| Addon | Variant |
| --- | --- |
| `api_never_none` | embedded and DNA pointers; unannotated callback overrides of `Menu`, `Header`, `UIList` and `RenderEngine`, and their callers |

Only the stubs of Blender main built from the fork state these facts (both generators read the RNA flag); 5.2's
stubs fail these markers (named exceptions in spec #75). The pointer and caller markers are guards (`bare-ok`): they hold without the checker.
The callback overrides need the checker's inheritance typing.
