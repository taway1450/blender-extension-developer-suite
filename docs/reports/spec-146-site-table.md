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
