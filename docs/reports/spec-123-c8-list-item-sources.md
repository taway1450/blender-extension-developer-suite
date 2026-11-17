# Spec #123 C8: `UIList.draw_item`'s item typed by its `template_list` source

C8 (#131) asks whether the `item` of a `UIList.draw_item` can be typed from the add-on's
`template_list(listtype_name, list_id, dataptr, propname, ...)` calls as the collection's element type, with a
per-add-on lookup like the popover set, and implements it if the lookup is cheap. Counts are `check:blender main`
at Blender `e8e03296af`, before (`a5a3622`) and after this change; "done area" is shipped code, presets, examples
and templates.

## Measurement

Before C8, `item` was `bpy_struct` in every `draw_item`, and 84 diagnostics (builtin stubs) other than the
`blender-assumed-list-item` reads themselves sat in `draw_item` bodies: 67 `base-class-subtype`, 7
`assumed-subclass-member`, 4 `untyped-python`, 3 `assumed-registration`, 2 `ui-draw-pointer`, 1
`type-enum-sub-pointer`. A syntax pass over the add-on (or, for a file in no add-on such as `bl_ui`, its folder)
finds a `template_list` call with the list's idname as a string literal for:

| where the call is | sites |
|---|---:|
| the list's own file | 59 |
| another file of the add-on or folder (`MATERIAL_UL_matslots`, `MESH_UL_vgroups`, `TEXTURE_UL_texslots`, ...) | 13 |
| no call (`SCENE_UL_timeline_markers` in a doc example, `RIGIFY_UL_action_slots`, `DATA_UL_bone_collections` drawn by C) | 12 |

The lookup is the popover set's: one cached syntax pass per file for the list names, then, per list class, the
types of `dataptr` and `propname` read from the inference of only the scopes that hold a matching call. Those are
draw callbacks the check infers anyway. ty's time on `check:blender main` did not move beyond noise: 22.1 s / 21.7 s
before and 21.8 s / 22.2 s after (builtin), 22.6 s / 24.9 s before and 23.7 s / 24.0 s after (fake-bpy-module).

## Decision

Implemented, as a narrowing of the existing `blender-assumed-list-item` Assumption (no new rule): `item` is the
element type of the collections the list's calls show, the union of them for several. A call whose `dataptr` has
no type (an unannotated parameter: `context` in a mixin's `draw`, a helper's argument) says nothing and is left
out, which reports no read that `bpy_struct` did not. A call with a typed `dataptr` but no element type (a
`propname` that is no string literal, `ob.data` typed `ID`) keeps `bpy_struct` for its list.

## Move

| cause | builtin | fake-bpy-module |
|---|---:|---:|
| `base-class-subtype` (typing debt, errors) | 334 → 288 (−46) | 304 → 259 (−45) |
| `assumed-subclass-member` (warnings) | 169 → 163 (−6) | 227 → 221 (−6) |
| `untyped-python` | 652 → 651 (−1) | 980 → 979 (−1) |
| `ui-draw-pointer` | 524 → 525 (+1) | 475 → 476 (+1) |
| `item-type-tag-narrowing` | 10 → 13 (+3) | 10 → 13 (+3) |
| errors | 5,868 → 5,825 (−43) | 8,453 → 8,411 (−42) |
| warnings | 2,774 → 2,768 (−6) | 2,895 → 2,889 (−6) |

The done area keeps 0 `unsorted` for both stub sets. Two moves are reads the narrowing uncovers:

- `ui-draw-pointer` +1: `SCENE_UL_gltf2_filter_action` now reads `item.action` as `Action | None`.
- `item-type-tag-narrowing` +3: `PROJECT_UL_variables` reads `item.value` on a `ProjectVariable` after
  `match item.type`. The stubs declare no Type tag for its subclasses, as for `NodeTreeInterfaceItem`.

## What stays typing debt (21 `base-class-subtype` in `draw_item`, builtin)

| reads | sites | why |
|---|---:|---|
| of `data` (the list's owner), not `item`: `DATA_UL_bone_collections`, `DATA_UL_rigify_bone_collections`, `MESH_UL_color_attributes`, `TEXTURE_UL_texpaintslots` | 7 | `data` keeps the stub's `bpy_struct`; C8 types `item` only |
| `item` of `MESH_UL_color_attributes` | 3 | one call shows `mesh.color_attributes` with `mesh = ob.data`, typed `ID` |
| `item` of `TEXTURE_UL_texpaintslots`, `GPENCIL_UL_matslots`, `GPENCIL_UL_annotation_layer` | 6 | every call is in a mixin's method whose `context` (or `gpd`) is unannotated |
| `item` of `DATA_UL_bone_collections`, `SCENE_UL_timeline_markers` | 5 | no `template_list` call (drawn by `template_bone_collection_tree` in C; a doc example) |

## Named exception

Blender 5.2's own stubs type `item` as `AnyType`, which no collection element derives from, so there it keeps
`AnyType` (recorded in `tests/typecheck/expected/builtin/5.2.txt`).
