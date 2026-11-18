# Spec #146 H1: the draw-pointer and object-data sites

Slice H1 of the UI draw bug hunt re-runs `check:blender main` after specs 1–4 (#95, #123, #140) and lists every
`ui-draw-pointer` and `object-data-untagged` site in the done area: shipped scripts, examples and templates (presets
have none). [spec-146-site-table.tsv](spec-146-site-table.tsv) has one row per diagnostic, so a line with two
diagnostics has two rows. The table is for `check:blender main` at Blender `38d1df8a1b` (`typecheck-fixes`).

H2 (`scripts/startup`) and H3 (add-ons and the rest) fill in `decision` and `reason`, one of:

- `bug`: draw raises in a reachable state, fixed on `typecheck-fixes`;
- `gap`: a guarantee the checker should see (name the mechanism);
- `debt`: right code whose types can't show it (give the reason).

## Columns

- `site`: `path:line`.
- `area`: `shipped`, `examples` or `templates`.
- `cause`: `ui-draw-pointer` or `object-data-untagged`.
- `generators`: which stubs report it: `both`, `builtin` (Blender's own) or `fake-bpy-module`.
- `scope`: the enclosing class and function. `bases`: the class's bases as written.
- `rule`, and `type`: the nullable type the message names, with `None` last (fake-bpy-module's `Object.data` union is
  written `ID | None`, as in Blender's own stubs).
- `line_text`: the source line.
- `poll`: the body of the class's `poll`, its own or that of a base class in the same file, joined by ` ; `. `-` means
  no poll in the file: a base class from another module (see `bases`) can still have one.
- `class_context`: the class's `bl_context`, `bl_parent_id`, `bl_space_type` and `bl_region_type`.
- `nearby_check`: the nearest condition before the line, in the same function, that names what the line reads.
  It is found by text and is a hint only.
- `decision`, `reason`: empty, for H2 and H3.

## Rows

| cause | rows | `scripts/startup` (H2) | rest (H3) | both stubs | builtin only | fake-bpy-module only |
|---|---:|---:|---:|---:|---:|---:|
| `ui-draw-pointer` | 505 | 482 | 23 | 437 | 66 | 2 |
| `object-data-untagged` | 55 | 6 | 49 | 26 | 29 | 0 |
| total | 560 | 488 | 72 | 463 | 95 | 2 |

Of the 505 `ui-draw-pointer` rows, 277 have a poll in the file, 249 a `bl_context` or `bl_parent_id`, and 152 a nearby
check. By type:

| type | rows |
|---|---:|
| `Object \| None` | 110 |
| `ID \| None` | 97 |
| `Curve \| None` | 55 |
| bones (`Bone`, `EditBone`, `PoseBone` unions) | 53 |
| `Brush \| None` | 48 |
| `bpy_struct \| None` | 21 |
| `FileSelectParams \| None` | 15 |
| `Screen \| None` | 13 |
| `WorkSpace \| None` | 11 |
| other | 82 |

The H3 `ui-draw-pointer` rows are in Rigify (10), Cycles' `ui.py` (4), Node Wrangler (2), glTF (1) and the doc examples (6).
The `object-data-untagged` rows are reads of `Object.data` with no Type tag test: 22 in the doc examples, 4 in the
templates, 20 in add-ons (glTF variants, Rigify, the VR camera), 6 in `scripts/startup` and 3 elsewhere. 49 are
`ID | None` and 6 `ID`.

## The re-sort

`object-data-untagged` used to match any message naming `ID` whose line contained the text `data`. So it also took
`id_data` (a struct's owner), `animation_data` read on an `ID`, and even `fcurve_ensure_for_datablock(None, ...)`.
`_buckets.py` now requires the receiver of the attribute, or the value, to be a `.data` read or a local set from
one. Specs 1–4 made two other causes precise enough to take the rest:

- `base-class-subtype`: an `ID` read for a member of a subclass. This covers `animation_data`, an evaluated object's
  `data`, and Rigify's `PointerProperty` poll argument. It also covers a struct's owner, `bpy_struct.id_data`, which
  both stub sets type as the base `ID` (fake-bpy-module adds `| None`), though the struct decides it. That
  includes one owner read through a list in `NLA_OT_bake`, listed by site.
- `narrowed-by-poll-helper`: `ASSET_OT_assign_action`, whose poll tests `isinstance(context.id, Action)`.
- `untyped-python`: Rigify's `TypedObject.data` override.

Done area, before → after:

| cause | builtin | fake-bpy-module |
|---|---:|---:|
| `object-data-untagged` | 82 → 55 | 51 → 26 |
| `base-class-subtype` | 159 → 184 (+24 shipped, +1 example) | 161 → 192 (+23 from object data, +8 from `narrowed-by-poll-helper`) |
| `narrowed-by-poll-helper` | 27 → 28 | 36 → 29 |
| `untyped-python` | 446 → 447 | 460 → 461 |
| `ui-draw-pointer` | 503 → 503 | 439 → 439 |

With fake-bpy-module, `narrowed-by-poll-helper` gives 8 sites to `base-class-subtype`. These are Node Wrangler's
`node_tree = node.id_data`, which no poll checks. Outside the done area, `tests/` and tools also move:

- 48 (builtin) and 4 (fake-bpy-module) to `base-class-subtype`;
- 12 and 4 to `unchecked-pointer`: `ID | None` values that are not `Object.data`;
- 1 to `unsorted`: the `datablock` argument.

The done area keeps 0 in the `unsorted` cause with both stub sets. The one `unchecked-pointer` site, the file
browser `params` in the Video Editing template's `__init__.py`, predates this slice and is unchanged.

## H2: scripts/startup

All 488 `scripts/startup` rows have a decision: 72 `bug`, 344 `gap`, 72 `debt`.

### Bugs

Each fix is one commit on `typecheck-fixes`, touching only `scripts/startup`. In the rare state the guard draws
nothing, a placeholder, or an inactive row. `mise run probe:ui-draw main` draws each panel in its state in background
Blender, on a stub layout that rejects None pointers as `UILayout` does. All 20 draws raised before the fixes and
pass after them.

| commit | state | panels and menus |
|---|---|---|
| `ae67f65f0c4` | a paint mode without a brush (deleted, or missing asset library) | the sculpt, vertex and texture paint and three Grease Pencil context menus, Sculpt Gravity, Grease Pencil sculpt settings |
| `9e044bbf86e` | pinned particle settings: no `particle_system` | Fluid Interaction, Render Timing |
| `4137594c096` | pinned object data: no `object` | Curves Surface, both light probe Viewport Display panels, Lattice |
| `352cd7a8c54` | pinned armature in the Bone tab while a mesh is in edit mode | Bone Collections (shows its placeholder) |
| `f73173d1f22` | a node group interface without an active item | interface context menu |
| `8536c0b027d` | no sequencer scene | sequencer View panel and pie |
| `d4f812a5dc2` | a sequencer scene without a sequence editor | Preview Overlays |
| `613e3dcb8a6` | no open project | Project Variables |

### Gaps

Follow-up notes; no checker code changed.

| mechanism | rows |
|---|---:|
| narrowed-by-poll-in-caller: a menu or popover drawn only from a parent, guarded header or mode keymap | 108 |
| bl-context-mode: a tool-settings `bl_context` implies the active object, its type and data | 56 |
| poll-type-comparison: `type(context.curve) is Curve` / `in {...}` in the poll | 55 |
| poll-or-fallback: poll `bone or edit_bone`, draw falls back to `edit_bone` | 53 |
| context-never-none: `window`, `screen`, `workspace` while a window draws | 27 |
| rna-never-none: no PROP_NEVER_NULL on file browser `params`, `owner_asset_library`, the graph editor's `dopesheet` | 17 |
| narrowed-by-poll-alias: the poll checks the pointer through another path | 9 |
| bl-context-implies-member: the Bone tab's armature, the Curves tab's data | 8 |
| context-mode: `context.mode` or the UV edit state implies the object | 7 |
| narrowed-by-poll-helper: a mixin poll in `bpy_extras.asset_utils`, a `hasattr` poll | 4 |

### Debt

| reason | rows |
|---|---:|
| correlated-condition (shape key / key, `psys` / object, pinned particle settings, active strip / scene, assets, texture user) | 33 |
| template-list-stub: the collection wrapper given as active data is not a `bpy_struct` in the stubs | 19 |
| type-enum-sub-pointer: a visual strip's crop and transform | 11 |
| base-class-subtype: `id_data` | 3 |
| helper-checks-none, object-data-untagged (an object just made from the data), none-excluded-by-arguments | 6 |

`check:blender main`, done area, shipped: `ui-draw-pointer` 503 → 431 (builtin) and 439 → 368 (fake-bpy-module).
With fake-bpy-module, `correlated-union` and `type-enum-sub-pointer` lose one site each. With builtin, only
`type-enum-sub-pointer` loses one. The `unsorted` cause stays at 0.
