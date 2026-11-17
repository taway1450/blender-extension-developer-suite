# pointer_aliases

**The checker must:** apply, without reporting, what Blender's C code keeps between two pointers (a Pointer alias),
while a pointer no alias covers keeps its stub type. An area's type, which names its active space, is a Type tag
([type_narrowing](../type_narrowing/README.md)); what `context.temp_override(...)` passes is in
[context_members](../context_members/README.md).

## What Blender does

- **Node editor pointers** (`space_node.cc`): `ED_node_tree_start` sets `node_tree` and `edit_tree` to the same tree,
  `ED_node_tree_push` / `ED_node_tree_pop` keep `edit_tree` the last entry of the tree path (whose root is never
  popped), and `node_id_remap` clears both together. So `space_data.node_tree` being set means `space_data.edit_tree`
  is set. `context.active_node` is provided by the node editor only, as `node_get_active(*snode->edittree)`: it is
  `space_data.edit_tree.nodes.active`, the same pointer.
- **Grease Pencil brush settings:** the brush of a Grease Pencil paint mode (`tool_settings.gpencil_paint`,
  `gpencil_sculpt_paint`, `gpencil_weight_paint`, `gpencil_vertex_paint`) is one of that mode: `Paint.brush` is
  read-only and `BKE_paint_brush_set` takes only a brush whose `ob_mode` has the paint's mode. `BKE_brush_add` allocates
  `gpencil_settings` for the four Grease Pencil modes, `bpy.data.brushes.new()` for every brush, and entering Grease
  Pencil draw mode ensures them for its brush. So `<gp paint>.brush.gpencil_settings` is set wherever the brush is.
  The one gap: `Brush.use_paint_grease_pencil` / `use_vertex_grease_pencil` (`rna_brush.cc`) set a Grease Pencil bit
  on `ob_mode` without allocating the settings, so a brush loaded without them (not one made in Python) can be given a
  Grease Pencil mode by a script.

## What the checker does

- A poll fact about one side of a Pointer alias is a fact about the other side too (`node_tree` → `edit_tree`, one
  way; `context.active_node` ↔ `space_data.edit_tree.nodes.active`, both ways, also through local aliases such as
  `tree = context.space_data.edit_tree`, `nodes = tree.nodes`). The read of the poll's own path is still reported under
  `blender-narrowed-by-poll`; what the alias adds is not.
- A read of `<gp paint>.brush.gpencil_settings`, a path from the context through any of the four Grease Pencil paint
  settings, is not `None`. A brush of another paint (`tool_settings.sculpt.brush`) keeps `BrushGpencilSettings | None`.

| Addon | Variant |
| --- | --- |
| `ptr_node_editor` | Node Wrangler's `nw_check` (`node_tree`) and `nw_check_active` (`active_node`) in a helper, read as `edit_tree` and `edit_tree.nodes.active` in `execute`; the reverse direction in a Panel; errors: `edit_tree` does not imply `node_tree`, `node_tree` no active node |
| `ptr_brush` | `gpencil_paint.brush` after a poll, `gpencil_weight_paint` / `gpencil_vertex_paint` after the draw's own test; guard: a sculpt brush |

The narrowing markers are `oracle-skip`: the reference stubs cannot express a narrowing. **Named exceptions:** on 5.2
the callbacks' `context` parameter is `Context | None`, so the markers fail there with both generators. On main they
pass with both.
