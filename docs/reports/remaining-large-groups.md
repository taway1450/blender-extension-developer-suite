# The five large groups that remain in `check:blender main`

Five causes hold 2232 of the 7536 diagnostics of `check:blender main` with the builtin stubs (Blender
`8309cbc080`, `.cache/ty-results/main-builtin.txt`): `unchecked-pointer` (684), `general-typing` (512),
`untyped-python` (449), `base-class-subtype` (319) and `assumed-preset-context` (268). This report splits each
one into sub-patterns, reads the source behind them, and says which fix applies:

- **(a) rule**: a new narrowing or inference rule in ty-blender;
- **(b) stub**: a fact in the stub generator (RNA, docstrings);
- **(c) patch**: a change to Blender's scripts;
- **(d) leave**: honest looseness, or an assumption reported on purpose.

Counts come from `_buckets.read_diagnostics` and `cause()` on that output. "Clears" is what the fix removes from
the total; a fix that only moves a diagnostic to another cause says so.

## Top opportunities

Effort: S is an hour or two, M a day, L several days.

| # | Opportunity | Kind | Clears | Effort | Cause |
|---|---|---|---:|---|---|
| 1 | ~~Exclude `tools/debug/gdb/gdb/` (gdb's API stubs written as `.py`) from `check:blender`~~ done in `scripts/check_blender.py` | config | 28 | S | general-typing |
| 2 | ~~`ID.evaluated_get(depsgraph)` returns the receiver's type (`Self`)~~ done in Blender `784231af35` | (b) | 26-57 | S | base-class-subtype |
| 3 | ~~A preset in `presets/sequencer/text_style/` takes `context.active_strip` as `TextStrip`~~ done in ty-blender | (a) | 54 | S | base-class-subtype |
| 4 | ~~Tests: `args = None` module globals declared `args: argparse.Namespace`~~ done in Blender | (c) 29 files | 69 | S | unchecked-pointer |
| 5 | ~~`self.assertIsNotNone(x)` / `self.assertTrue(x)` narrow `x` like `assert x`~~ done in ty-blender (any `self.` receiver) | (a), upstream | 62 | M | unchecked-pointer |
| 6 | ~~`global x` with no module-level binding: declare `x: T` at module level~~ done in Blender | (c) 17 files | 37 | S | general-typing |
| 7 | ~~Instance attributes initialised to `None`: annotate them (`import_svg`, `bl_usd_import_test`)~~ done in Blender | (c) 2 files | 31 | S | general-typing |
| 8 | ~~`bl_constraints.py` reads constraints by name: `assert isinstance` per test~~ done in Blender | (c) 1 file | 45 | M | base-class-subtype |
| 9 | ~~Registered properties visible across the modules of one Add-on~~ done; also a base class registering on `cls.owner` (Hydra). Left: cycles presets (12) and rigify's `selection_sets` (2), which another add-on registers | (a) | 19 (+35 in `cross-file-registered-property`) | M | untyped-python |
| 10 | ~~`id_data` typed by owner (`Node`/`NodeSocket` → `NodeTree`, `PoseBone` → `Object`, `AttributeGroupMesh` → `Mesh`)~~ done in both stub generators, for structs every pointer to which carries that owner (not `Bone`, `ShapeKey`, `ParticleSystem`) | (b) | ~17 | M | base-class-subtype |
| 11 | ~~`UIList.draw_item`'s `data` typed from `template_list` (C8 types `item` only)~~ done in ty-blender, `filter_items` too | (a) | ~7 | M | base-class-subtype |
| 12 | ~~Socket types per built-in node (`principled.inputs["Base Color"]` is `NodeSocketColor`)~~ done in both stub generators: Blender's fork probes each node over its states while writing the docs (`sphinx_doc_gen_node_sockets.py`), by name, identifier and index; a group's and a zone's item sockets stay `NodeSocket` (feature `api_node_sockets`). Left: a node read back by name (`nodes["Background"]`) is a `Node` | (b) | ~30 | L | base-class-subtype |

With rows 1–11 done, `check:blender main` with the builtin stubs is down from 7536 to 7102 diagnostics (Blender
`71b11d84c8`). A few readings narrowed by these fixes show a diagnostic further on that was masked before (5 more in
`unsorted`, 2 in `correlated-union`).

Two decisions change more than any fix, and are not fixes:

- **Scope.** 668 of the 684 `unchecked-pointer` diagnostics are in `tests/`: test code that reads data it
  just loaded or made, and fails loudly if it is missing. Checking `tests/` as its own profile, or not at all,
  would remove them. Nothing in them is a Blender bug.
- **Presentation.** `blender-assumed-preset-context` reports every read. Reporting it once per preset file
  and member would turn 268 warnings into 85, with the same information.

Not worth a rule: `animation_data` after `animation_data_create()` / `keyframe_insert()` on the same object
(14 here, 2 in `set-by-preceding-call`). The rule would hold only until the next call that clears it.

## `unchecked-pointer` (684)

What the cause holds: a nullable read (`X | None`) that no earlier cause claimed, outside the untyped
packages. Earlier causes skip `tests/` (`outside_tests`), so this is where the test suite's nullable reads
land: 668 in `tests/`, 12 in `tools/`, 2 in `build_files/`, 1 in `doc/`, 1 in `scripts/`. Rules: 534
`missing-union-attribute`, 82 `invalid-assignment`, 41 `invalid-argument-type`, 27 `missing-attribute`.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| `obj.animation_data` of an object loaded from a test `.blend` or set by `bpy.ops` | 90 | 12 | (d); 14 follow `animation_data_create()` in the same function |
| Action lookups: `channelbag`, `fcurves.find()`, `fcurve.group`, `action_slot` | 74 | 10 | (d) |
| `Object` / `Mesh` reads: `self.me = None` in `tearDown`, `bpy.data.objects.get()` | 71 | 11 | (c) for `self.me` (21, `del self.me`); (d) for the rest |
| Module global `args = None`, set in `main()` (`None \| Namespace`) | 69 | 29 | (c): declare `args: argparse.Namespace` |
| A read right after `self.assertIsNotNone(x)` / `assertTrue(x)` on the same expression | 62 | 10 | (a): see below |
| `GreasePencilFrame.drawing` | 59 | 1 | (d): RNA returns None for an end frame or a drawing reference |
| `ID \| None` of `override_create()`, `depsgraph.id_eval_get()` | 48 | 4 | (d): both return None on failure |
| `bpy.context.object` / `active_object` after `open_mainfile` or an operator | 27 | 13 | (d) |
| `ob.motion_path` after `paths_calculate()` | 26 | 1 | (d) |
| Optional imports (`gpu = None` when the module is missing) | 24 | 5 | (d) |
| `Collection.importer` of a file the test set up | 22 | 1 | (d) |
| `addons[...].preferences` in performance tests | 18 | 4 | (d) |
| stdlib Optionals (`Popen.stdout`, `frame.f_back`, `IO[bytes]`) | 15 | 6 | (d) |
| Other (brush, `uv_layers.active`, `compositing_node_group`, ...) | 79 | 25 | (d) |

```python
self.assertIsNotNone(local_id.override_library)               # bl_blendfile_library_overrides.py:113
self.assertEqual(len(local_id.override_library.properties), 0)  # :114, `IDOverrideLibrary | None`
bpy.ops.wm.open_mainfile(filepath=str(args.testdir / "x.blend"))   # bl_alembic_io_test.py:258, `None | Namespace`
frame1.drawing.add_strokes([3, 5, 7, 11])                     # bl_pyapi_grease_pencil.py:209
```

The `assertIsNotNone` rule is sound: `unittest`'s assert methods raise on failure, whatever `-O` says, so a
statement `self.assertIsNotNone(e)` on a `TestCase` excludes None from `e` for the rest of the block, as
`assert e is not None` does (`assertTrue(e)` as `assert e`, `assertIsInstance(e, T)` as `isinstance`). typeshed
cannot say this (`TypeIs` needs a `bool` return), so it needs a narrowing hook. It is not Blender-specific:
it belongs in upstream ty, and in the fork only as a small, separate hook.

The rest are tests that read what they loaded. They assert the data exists by using it; a rule that took
those reads as non-None would also hide the real None-dereferences the same reads have in add-on code.

## `general-typing` (512)

What the cause holds: plain Python typing debt, by rule (`deprecated`, `unused-type-ignore-comment`,
`unresolved-global`, stub-body returns) or by message (method overrides, function attributes, records in
lists, Python-only types). 240 in `scripts/`, 164 in `tests/`, 74 in `tools/`, 23 in `doc/`.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| Other Python typing: Node Wrangler's `[index, socket]` records (26), `object`-typed values (25), `str` for a `Literal` (9), assorted | 174 | 69 | (d); Node Wrangler's records (c) as tuples |
| Instance or class attribute initialised to `None`, then subscripted or read | 75 | 21 | (c): annotate; `import_svg.py` (19) and `bl_usd_import_test.py` (12) are 31 of them |
| Attributes set on functions (`modules._is_first`, `easy_keys.event_step._ticks...`) | 63 | 12 | (d): a static-variable idiom ty does not model |
| Unused `# type: ignore` (comments kept for mypy) | 39 | 17 | (d), or turn `unused-ignore-comment` off in `check:blender` |
| `global x` with no module-level binding (`record_stage` in performance tests) | 37 | 17 | (c): one line per file |
| subscript on a record or dict value (`spec.default_value[0]`) | 36 | 16 | (d) |
| gdb's API stubs as `.py` with `pass` bodies (`tools/debug/gdb/gdb/`) | 28 | 2 | config: exclude the folder, or (c) rename to `.pyi` |
| Override renames a parameter (`_source` vs `source` in `code_clean.py`: 21) | 27 | 5 | (c) or (d): calls are positional |
| `mod.bl_info = ...` on a `ModuleType` (`addon_utils.py`) | 19 | 4 | (d) |
| Deprecated stdlib calls (`shutil.rmtree(onerror=)`, `sqlite3` adapters) | 14 | 9 | (c), outside the spec's scope |

```python
self._appendPoint(self._point[0], self._point[1])   # import_svg.py:676, `self._point` is `None`
global sort_choices, default_sort_choice            # rna_cleaner.py:312, no module-level binding
def const(self) -> Type:                            # tools/debug/gdb/gdb/gdb.py:69, body `pass`
```

Nothing here is a Blender fact. Only one sub-pattern touches the bpy API: `bpy.data.node_groups.new(name,
'GeometryNodeTree')` stays `NodeTree`, so `group.is_modifier = True` fails (5, `geometry_nodes.py`,
`bl_node_tool.py`). The constructor narrowing (`constructors.rs`) does not cover `BlendDataNodeTrees.new` yet.
That is a small (a) worth adding.

## `untyped-python` (449)

What the cause holds: every diagnostic in rigify (247), glTF (146), `_bl_i18n_utils` (26), `ui_translate`'s
`I18nSettings` (18), `bl_app_override` (8), Freestyle (2), and any numpy message (2 in a template). The cause
is a path rule: whatever the pattern, it lands here.

| Sub-pattern | Count | Fix |
|---|---:|---|
| The package's own typing: dict records, own classes, generics, glTF's `export_settings` | 233 | (d) |
| Override compatibility: rigify's `bones: BaseRig.ToplevelBones[...]` per rig (26), node-skin classes | 57 | (d); (c) only with rigify's maintainers |
| The package's own Optionals (`BaseRig \| None`, `ControlBoneNode \| None`, `re.match()`) | 40 | (d) |
| Nullable Blender pointers (`animation_data`, `LayerCollection`, `socket.socket`) | 36 | (d): real Optionals, the same as elsewhere |
| mathutils: `Vector.cross()` is `Vector \| float` (2D gives a float), `Matrix((v1, v2, v3))` | 33 | (d): the length decides; ty does not track it |
| A Registered property read in another module of the Add-on (`scene.gltf_action_filter`, `armature.rigify_colors`) | 19 | (a): see below |
| `I18nSettings` attributes set by `setattr` from a settings module | 18 | (c): declare them on the class |
| numpy arrays | 11 | (d) |
| Function attributes | 2 | (d) |

```python
for item in bpy.data.scenes[0].gltf_action_filter if item.keep is False   # action.py:1456, `object` is not iterable
armature.rigify_colors[-1].name = unique_name(...)                         # rigify/ui.py:679
align_bone_x_axis(self.obj, orgs[2], foot_x)                               # leg.py:84, `Vector | float`
```

The Registered property rule is the one Blender fact here. `bpy.types.Scene.gltf_action_filter =
CollectionProperty(type=GLTF2_filter_action)` in `io_scene_gltf2/__init__.py` gives every `Scene` the
property, at runtime, for every module. The checker reads it only in the file that assigns it
(`file-registered-property`). Collecting registrations per Add-on root, as the Add-on index already does for
classes, would clear these 19 and most of the 35 `cross-file-registered-property` diagnostics. It is sound
under the same assumption as `blender-assumed-registration`: the code runs after `register()`.

## `base-class-subtype` (319)

What the cause holds: an attribute missing on a base class (`ID`, `Strip`, `Constraint`, `bpy_struct`,
`NodeSocket`, ...) that a subclass has, plus `id_data` owners. 179 in `scripts/` (54 of them presets), 130 in
`tests/`. Rules: 305 `missing-attribute`, 9 `missing-union-attribute`, 5 other.

| Sub-pattern | Count | Fix |
|---|---:|---|
| `x.evaluated_get(depsgraph)` is `ID`: `.data` 31, `.matrix_world` 9, `.to_mesh()` 11 | 57 | (b): `-> Self`. The 31 `.data` reads become `ID \| None` (`object-data-untagged`), so 26 clear outright |
| `bpy.context.active_strip` in the 3 text-style presets (18 reads each) | 54 | (a): see below |
| `owner.constraints['Child Of']` in `tests/python/bl_constraints.py` | 45 | (c): `assert isinstance(con, ChildOfConstraint)`, or (d) |
| `bpy_struct`: `UIList.draw_item`'s `data` (21), `bl_rna.functions.items()` (13), other (4) | 38 | (a) for `data` (~7 have a `template_list` call); (d) for the rest |
| `node.inputs["Name"].default_value`: the socket by name is `NodeSocket` | 30 | ~~(b)~~ done (row 12) for a node typed by its class or `nodes.new`; a node read back by name stays a `Node` |
| `id_data` owner: `node.id_data.nodes` (9), rigify `PropertyGroup.id_data` (8), FBX `attributes.id_data` (4) | 29 | (b) for structs with one owner type (~17); (d) for a PropertyGroup's owner |
| Other `ID` reads (`animated_id`, `blender_mesh[i]`, function parameters typed `ID`) | 21 | (d) |
| Small bases: Freestyle `FEdge` 8, `modifiers[...]` 8, template `gizmos.new()` 7, `IKParam` 4, others | 45 | (d) |

```python
strip = bpy.context.active_strip
strip.wrap_width = 1.0                                   # presets/sequencer/text_style/Main_Title.py
ob_eval = self.cube.evaluated_get(depsgraph); ob_eval.matrix_world   # bl_alembic_io_test.py
nodes = node_tree.nodes                                  # node_wrangler reset_selected.py:96, `node.id_data`
```

**Text-style presets.** `STRIP_PT_effect_text_style_presets` (`preset_subdir = "sequencer/text_style"`) is
drawn only from `STRIP_PT_effect.draw_header_preset` under `if strip.type == 'TEXT'`, and
`STRIP_PT_effect_text_style.poll` returns `strip.type == 'TEXT'`. So a preset in that folder runs with a
`TextStrip`. The rule extends `blender-assumed-preset-context`: the member's type is the type the
applying panel's guard narrows it to. The cheap form is a table next to `is_preset_path`
(`sequencer/text_style` → `active_strip: TextStrip`). The general form finds the `PresetPanel` /
`PresetMenu` with that `preset_subdir`, and the poll or `if` that draws it. Only this folder needs it today.
The read stays reported as the same Assumption, so nothing is hidden.

**`evaluated_get`.** `DEG_get_evaluated_id` returns the evaluated copy of the same ID, so `-> Self` is exact.
`override_create()` could take `Self | None` too, but that only renames `ID | None` to `Object | None` and
clears nothing.

## After the typechecker fixes

The fixes that followed this report (Blender `784231af35`) take the builtin-stub totals from 4787 errors to
4708. The `typechecker-fix` group falls from 97 to 32:

- `evaluated_get` and `ID.copy` return `Self`.
- C docstrings and RNA argument types are corrected.
- Dynamic enums are typed `str`.
- Callback parameters are never None.
- Registered functions are written without defaults.

Read-only attributes are now properties without a setter. Assigning one is reported, as Blender raises. That
adds 15 correct `rigify-get-bone` errors (`PoseBone.head`, `.tail`, `.length`).

`Self` from `copy` and `evaluated_get` moves diagnostics rather than clears them. `base-class-subtype` falls by 68,
from 319 to 251. A read on `ob.evaluated_get(depsgraph)` is now a read on an `Object`, so it lands in the cause of
that read instead:

- `object-data-untagged` +49: `Object.data` is `ID | None`.
- `none-excluded-by-arguments` +20.
- `type-enum-sub-pointer` +3.

The remaining 32 are left as they are:

- `Buffer` iteration and its `dimensions` setter.
- `partial(setitem, vec)`.
- The `Vector.cross` union.
- `RenderPass.rect`.
- `data_to.actions[0]`.
- A registered class looked up in `bpy.types`.
- File-registered properties.
- Freestyle's positional calls.
- `foreach_set` with `list[None]`.
- Filter-items tuples.

## `assumed-preset-context` (268)

What the cause holds: the `blender-assumed-preset-context` warnings. A preset reads `bpy.context.<member>` at
module level, and the checker takes the member as present because Blender runs the preset with the
context of the panel that applies it.

| Member | Taken as | Reads | Files |
|---|---|---:|---:|
| `context.cloth` | `ClothModifier` | 120 | 5 |
| `context.camera` | `Camera` | 93 | 31 |
| `context.edit_movieclip` | `MovieClip` | 39 | 39 |
| `context.fluid` | `FluidModifier` | 6 | 3 |
| `context.particle_system` | `ParticleSystem` | 4 | 1 |
| `context.object` | `Object` | 3 | 3 |
| `context.active_strip` | `Strip` | 3 | 3 |

```python
bpy.context.cloth.settings.quality = 5        # presets/cloth/Cotton.py, one warning per line
bpy.context.camera.sensor_width = 13.2        # presets/camera/1_inch.py
camera = bpy.context.edit_movieclip.tracking.camera   # presets/tracking_camera/1_inch.py
```

Every read is right, and the warning is the Assumption working as designed: (d). The only lever is how often
it speaks. Each of the 85 files reads one member, so one warning per file and member would give 85 instead of
268. The cloth presets alone go from 120 to 5. That is a presentation change in the rule, not a typing
change. It is worth it only if the warning count is read as a to-do list. The `active_strip` reads need the
`TextStrip` narrowing above, whatever the count.
