# Every remaining cause in `check:blender main` that is not an Assumption

`docs/reports/remaining-large-groups.md` analysed the five largest causes and ranked twelve fixes; all twelve are
done. This report covers what is left. With the builtin stubs (Blender `3bd52da81e`, Linux platform), `check:blender
main` reports 7062 diagnostics: 4332 errors and 2730 warnings.

The `assumption` and `implied-narrowing` groups (2,380 diagnostics: `assumed-context-member` 903, `narrowed-by-poll`
855, `assumed-preset-context` 268, ...) are the dedicated `blender-*` rules reporting right code on purpose. They are
(d) by design and are not split again here. Every other cause is: `typing-debt`, `unsorted`, `blender-fix` and
`typechecker-fix`, about 4,100 diagnostics in 50 causes.

Fix kinds, as in the earlier report:

- **(a) rule**: a new narrowing or inference rule in ty-blender;
- **(b) stub**: a fact in the stub generator (RNA flags, docstrings, `sphinx_stub_gen.py`, fake-bpy-module);
- **(c) patch**: a change to Blender's scripts;
- **(d) leave**: honest looseness, or a deliberate assumption;
- **config**: `scripts/check_blender.py` or the bucket table in `scripts/_buckets.py`.

Counts are per cause with the builtin stubs (`.cache/analysis/builtin/<cause>.txt`); fake-bpy-module figures are
given where they differ. "Clears" is what a fix takes out of the total; "moves" means the diagnostic becomes a
reported Assumption or lands in another cause. A count marked `~` comes from a heuristic. The analysis ran on Windows
before `check:blender` pinned `--python-platform linux` (commit `1b9eb7b`): 18 platform diagnostics in `stub-gap` and
`unsorted` (`os.getuid`, `fcntl`, `termios`, `PipeConnection`) are counted below and are already gone; Linux adds 2
(`msvcrt.getch` in an unguarded Windows class of `tools/utils/git_log_review_commits*.py`).

## Blender bugs found

Real errors at runtime, all in Blender's own code:

| Where | What | Cause |
|---|---|---|
| `bl_operators/userpref.py:368-427` | `PREFERENCES_OT_keyitem_add` has no poll and `keymap_restore`'s non-`all` branch reads `context.keymap` unguarded: from the operator search both raise `AttributeError` | `set-by-ui-button` |
| `rigify/rot_mode.py:181`, `rigify/ui.py:1121`, `:1132` | `POSE_OT_convert_rotation`, `UpgradeMetarigTypes`, `UpgradeMetarigLayers` have no poll and read the active object | `operator-without-poll` |
| `rigify/ui.py:1408`, `:1483`, `:1613` | `Scene.frame_set()` is given keyframe times (floats): `TypeError` since Python 3.10, on FK/IK snapping over a keyed range | `untyped-python` |
| `bl_ui/space_userpref.py:2317` | `USERPREF_MT_extensions_active_repo_remove.draw` dereferences `active_repo`, which is None with no repository | `python-optional` |
| `bpy_extras/object_utils.py:64` | `add_object_align_init` reads `space_data.region_3d` with `align == 'VIEW'` outside a 3D View (`primitive_*_add(align='VIEW')` from a script) | `python-optional` |
| `bl_ui/properties_strip.py:607` | `elem.orig_fps` after `strip_elem_from_frame()`, which returns None; the lines above test `elem` twice | `ui-draw-pointer` |
| `bl_operators/image_as_planes.py:144-156` | `load_image()` returns None for a file that exists but cannot be opened; used unchecked | `none-excluded-by-arguments` |
| `bl_operators/object_quick_effects.py:565` | `self.style == {'FIRE', 'BOTH'}` compares a string with a set, always False: Quick Smoke never enables noise (line 600 uses `in`) | none (found nearby) |
| `bl_ui/space_view3d_toolbar.py:564` | the canvas panel's poll reads `tool_settings.sculpt.brush` in any paint mode; `sculpt` is None until Sculpt mode was entered (experimental 3D texture paint only) | `type-enum-sub-pointer` |
| `bl_ui/space_view3d_toolbar.py:1996` | `ma.grease_pencil.mode` on a slot material that may not be a Grease Pencil one | `type-enum-sub-pointer` |
| `doc/python_api/examples/bpy.types.Operator.6.py:39`, `bpy.types.RenderEngine.1.py:32` | `super().__del__()`: `bpy_struct` has no `__del__`, so it raises when the instance is freed | `mixin-self` |
| `viewport_vr_preview/configs/default.py:2704` | imports `viewport_vr_preview.io` (the module is `action_map_io`) and passes a name where `session_state` goes (under `__main__`) | `unresolved-import` |
| `tools/utils_maintenance/blender_menu_search_coverage.py:426-482` | sets `.value` on an operator's result set; calls the removed `mesh.vertex_color_add` and `object.gpencil_add` | `general-typing`, `operator-call` |
| `doc/blender_file_format/BlendFileDnaExporter_25.py:391`, `:452` | `sys.arch` (does not exist), `bpy.ops.wm.exit_blender` (the operator is `quit_blender`) | `stub-gap`, `operator-call` |
| `tests/python/modules/mesh_test.py:396` | dereferences `items` before its None check, so an invalid mode gives `AttributeError` instead of the intended `ValueError` | `unchecked-pointer` |
| `tests/python/bl_node_group_interface.py:361`, `bl_animation_armature.py:252`, `rna_info_dump.py:116` | an undefined `panel0`, `ArmatureBones.remove`, `Text.from_string(list)`: in code no test reaches | `unsorted` |
| `node_wrangler/utils/draw.py` (5 calls) | `batch_for_shader(shader, 'TRI_FAN', ...)` emits a `DeprecationWarning` | `deprecated-enum-value` |

Rigify's 15 `rigify-get-bone` writes (`.head`, `.tail`, `.length` on `get_bone()`, typed `EditBone | PoseBone`) are
right about the annotation but never fail: every one runs in an edit stage, where `get_bone` returns an `EditBone`.
They are an annotation fix for rigify's maintainers (BF2), not a bug.

## Everything that is not (d)

Ranked by kind, then by what it clears. **Now** is implemented with this report; **later** says why it waits.

### Config

| # | Fix | Clears | Effort | Decision |
|---|---|---:|---|---|
| C1 | Turn `unused-type-ignore-comment` off in `check:blender`: all 40 are comments for Blender's mypy check, which has no `bpy` stubs | 40 | S | now |
| C2 | Exclude `tools/debug/gdb/` (gdb's API hints, 50 diagnostics) and the 2.7x exporter `intern/cycles/app/io_export_cycles_xml.py` (4) | 54 | S | now |
| C3 | `_sha1`, `_sha2`, `_md5` in `ALLOWED_UNRESOLVED_IMPORTS` (private CPython modules, not in typeshed) | 3 | S | now |
| C4 | Bucket table: new causes `expected-error`, `test-bug`, `gdb-api-hints`; a `general-typing` catch-all for tests and tools before `unsorted`; Node Wrangler's `str` for an enum out of `correlated-union`; `file-registered-property` only for property calls | 0 (re-sorts ~290) | M | later: clears nothing; worth doing with the next slice of bucket work |

### Rules (a)

| # | Rule | Clears | Effort | Decision |
|---|---|---:|---|---|
| R1 | A mixin whose users all derive from `unittest.TestCase` types `self` as the mixin and `TestCase`, as the mixin rule does for `bpy.types` users | 140 | S-M | now |
| R2 | A dotted `bl_context` (`.mesh_edit`, `.sculpt_mode`, `.grease_pencil_paint`, `.posemode`, ...) gives its mode's facts, as the plain form does; `.paint_common` the intersection, `.objectmode` nothing | 69 | S | now |
| R3 | `type(X) is T` / `type(X) in {A, B}` as a poll conjunct: `X` is not None (and is `T`) | 55 | S | now: not None only; the class from `type(X)` is left to the rule's next step |
| R4 | `window`, `screen`, `workspace` are Guaranteed in the draw callbacks of a Panel, Menu, Header or UIList | 27 | S | now |
| R5 | A file in no add-on knows the operators it registers, at any scope (`bpy.ops.x.y()`, `layout.operator("x.y")`) | 35 | S-M | now |
| R6 | `assertNotEqual(x, None)` narrows like `assertIsNotNone(x)` | 17 | S | now |
| R7 | Pointer aliases: `particle_system` ⇒ `object`, `active_strip` ⇒ `sequencer_scene`, `tool_settings` is `scene.tool_settings`, `active_pose_bone` ⇒ `active_object` | 16 | S | now: the first two; the last two are not aliases (the sequencer gives the sequencer scene's tool settings, a hidden object leaves `active_object` `None`) |
| R8 | `poll` found past a `bpy.types` base on a mixin listed after it (`class X(Operator, NWBase)`) | 4+ | S | now |
| R9 | `self.layout` is `UILayout` in a function given to `Menu.append` / `prepend` (or whose `self` is annotated `Menu`, `Panel` or `Header`) | 15 | S | now: the annotated `self`; a function passed to `append` stays later (needs the call site) |
| R10 | `bpy.data.objects.new(name, data)` is the Type tag view of `data`'s type (`Camera` gives `_Object_CAMERA`, `None` gives `_Object_EMPTY`) | 7 | S | now |
| R11 | Type tag narrowing on a union of refined bases (narrow each member) | 6 | S | now |
| R12 | `NodeTreeInterface.new_socket(socket_type="NodeSocketX")` is `NodeTreeInterfaceSocketX` | 4 | S | now: the call swaps an unsupported type, but the `socket_type` enum rejects one first |
| R13 | A Registered property written through an intersection receiver (`X & ~AlwaysFalsy` after `if x:`) | 6 | S | now |
| R14 | Added-object type: after `mesh.primitive_*_add()`, `object.add(type=...)`, `light_add(type=...)`, `context.object` is the tag view of the new type (part of `blender-assumed-added-object`) | ~102 (+23 subclass reads) | M | done (2026-11-19): the operator-to-type table in `ty_blender::added_object_type`; clears 86 (a call in a branch the read is not in, an `object.add(type=kind)` and `**kwargs` give no view), while 15 reads of a light's subclass members (`light_add(type='SPOT')`, then `.data.spot_size`) and 4 real test mistakes now show; the `view_layer.objects.active` alias is left |
| R15 | A Grease Pencil material preset sees `object.active_material.grease_pencil` set (a path form of the preset table); fluid presets see a domain | 63 | S-M | done (2026-11-19), with P8: `ty_blender::preset_set_pointer` and a fluid entry in the preset table; clears 66 |
| R16 | A Registered property after `hasattr(x, "name")` has the property's type, also when the add-on registers it outside `register()` | 17 | M | done (2026-11-19): after `hasattr`, a property of the class (indexed, or registered anywhere in the add-on: an update callback, an operator) gives its type instead of the protocol's `object`; the registration write itself outside `register()` stays `missing-attribute`; clears 17 (`untyped-python` 397 → 380, the glTF action filter) |
| R17 | A write to a Type tag narrows when its setter rebuilds the sibling pointer (`fluid.fluid_type = 'DOMAIN'`) | 21 | M | done (2026-11-19): `ty_blender::rebuilds_on_tag_write` (`FluidModifier.fluid_type`), the last write of the tag (or `setattr`) before the read, a literal in a block holding the read with no later write in a loop around it; clears 19 with the builtin stubs (fake-bpy-module has no fluid tag views); the 2 `unsorted` errors it adds are `QuickLiquid.execute` writing `'BOBJECT'` to `cache_mesh_format` and `'PHI'` to `color_ramp_field`, dynamic enums whose stub lists only the static items (a docstring fix with S8's dynamic enums) |
| R18 | Implied narrowing for `SpaceX.draw_handler_add(fn, ..., 'WINDOW')` callbacks, one helper deep | 19 | M | done (2026-11-19): a module-level function given to `<Space>.draw_handler_add` (any file of the add-on), and a module-level helper only such functions call, reads `area` / `region` as set and `space_data` as that space, under `blender-assumed-editor-member`; clears 15 (`editor-context-member` 46 → 33, `script-context-member` 41 → 39), +15 warnings |
| R19 | `self.layout` in Operator methods called only from `draw` | 17 | M | done (2026-11-19): a method whose every `self.<name>` use is a direct call in a draw callback is one too; clears 15 (`layout-in-operator-helper` 23 → 8); the rest store the method or are mixin calls |
| R20 | A Type tag test through a local (`strip_type = strip.type`) | 15 | M | done (2026-11-19): `tag = x.type` then `if tag == 'LIT'` / `in {...}` / `!=` / `not in`, with `elif` / `else`, narrows `x` while neither is rebound and the scope writes no tag (member load, no upstream change); with R22 clears 21 (`correlated-union` 51 → 36, `type-enum-sub-pointer` 303 → 293, some move to `ui-draw-pointer` 283 → 287), +7 `blender-assumed-subclass-member` warnings |
| R21 | Assumption: `window` (with `screen` / `workspace`) outside UI draws; `area` / `space_data` in `invoke` / `modal` | moves 68 | S-M | later: turns errors into warnings without clearing them; a design decision for the Assumption spec |
| R22 | A popover inherits the guard of its `layout.popover()` call | 10 | M | done (2026-11-19): a `HEADER` panel opened only by `layout.popover()` calls has the facts every opener knows before its call, under `blender-narrowed-by-popover`; the 10 `space_node.py` geometry-node tool popover errors are gone, +5 warnings |
| R23 | Smaller rules: macro steps on a properties object (6), negated refined base (5), poll facts in a Panel's helpers (5), `bl_parent_id` into `bl_ui` (4), mixin users made by `type()` (5), `Object.mode` test (7), `driver_add` on a non-array path (8), `PointerProperty(poll=)` parameter (2), `init_socket` (2), opaque property call outside an add-on (3), literal tuple `+` in `items` (1), `bpy.types.<AddonClass>` (1), asset shelf `space_data` (1), `_GenericBone` (15) | ~65 | S-M each | later: low value each |
| R24 | After a statement dereferenced `x`, `x` is not None for the rest of the block (report once per receiver) | ~475 | L | later: general Python, belongs in upstream ty or is a presentation choice |

### Stubs (b)

| # | Fact | Clears | Effort | Decision |
|---|---|---:|---|---|
| S1 | `animation_data_create()` returns `AnimData` on every ID type with an `animation_data` property (`ID` keeps `\| None`) | 33 | S-M | now |
| S2 | gpu `Buffer` has the buffer protocol and `__iter__`; `GPUStorageBuf(data)` and `.update()` take any buffer; the `dimensions` setter takes `int \| Sequence[int]`; `GPUFrameBuffer.bind()` is a context manager | 24 | S | now |
| S3 | `PROP_NEVER_NULL`: strip `transform` / `crop`, `AreaSpaces.active`, Graph and NLA `dopesheet`, `RenderEngine.view_draw`'s `context` | 16 | S | now, but `view_draw`'s `context` (a callback parameter, not a pointer property) stays |
| S4 | `bpy_prop_collection.items() -> list[tuple[str, _T]]`, `values() -> list[_T]` | 13 | S | now |
| S5 | `ShapeKey.data` items are `ShapeKeyPoint \| ShapeKeyCurvePoint \| ShapeKeyBezierPoint` | 8 | S | now |
| S6 | `bpy_prop_array.foreach_get` / `foreach_set` take a buffer; `Vector.cross` takes any sequence | 10 | S | now |
| S7 | Refined bases: `Pose.ik_param` is `Itasc`; members every subclass declares hoisted (`Light.shadow_maximum_resolution`, `UserAssetLibrary.path`, `Attribute.data`); `BoneCollection.id_data` is `Armature` | 9 | S | now |
| S8 | Docstrings: vector property `get` / `set` take nested sequences for a multi-dimensional `size` (6), dynamic enums `view_transform`, `look`, `display_device`, `Curve.fill_mode` (3), `bl_rna` / `rna_type` on collection structs (4), `bpy.types.bpy_func` and `bpy_struct_meta_idprop` (2), `is_asset_browser(Space \| None)` (2), `ensure_ext(str \| bytes)` (2), `UI_UL_list` items (2), `batch_for_shader` indices (1) | 22 | S | now |
| S9 | `_DriverFCurve` with `driver: Driver` from `driver_add()` and in `AnimData.drivers` | 16 | M | later (2026-11-19): a new private class kind in both stub generators plus a docstring in the Blender fork, so a Blender rebuild; not done with the narrowing rows |
| S10 | Undocumented Python modules and `__all__` members in the builtin stubs (`bpy_extras.node_shader_utils`, ...); startup-registered classes in `bpy.types` with their Python members | 15 | M | startup classes done by the runtime generator (`--generator runtime`, `docs/research/runtime-stub-generator.md` §7: `registered-class-in-bpy-types` 8 → 2); the builtin stubs keep the gap |
| S11 | Built-in gizmo types (`GIZMO_GT_*`) as private classes for `gizmos.new()` | 7 | M | later (2026-11-19): needs a probe of the gizmo types Blender registers before stubs can name them; not done with the narrowing rows |
| S12 | `driver_add` overloads on `index`, `RenderPass.rect` nested, typed `libraries.load()` targets, `load_image(place_holder=True)` overload | 5 | S-M | later: low value |

### Patches (c)

| # | Patch | Clears | Effort | Decision |
|---|---|---:|---|---|
| P1 | The Blender bugs above | ~40 | S | now |
| P2 | Shipped code: `settings = coll` in the collision panels (17), `strip1 is None` in `SequencerCrossfadeSounds` (13), `properties is not None` in `add_object_align_init` (12), `I18nSettings` class annotations (18), rigify's `ActionSlot` import under another name (13), positional-only `/` on base methods whose overrides rename a parameter (25), `@contextmanager` returning `Generator` (11), `@staticmethod` on class-body functions (9), `[0] * n` buffers (3), `lamp.type` in FBX (2), checked `ob` in `rot_mode.py` (3), Freestyle and submodule imports (8), `from bl_ui.space_view3d import` (1), `import gdb` (9), theme mixin attributes (4) | ~150 | S | now |
| P3 | Tests: `del` instead of `= None` in `tearDown` (41), `Iterable[FCurve]` in a helper (13), `io_report` annotations (13), `x: T \| None = None` and `Any` (15) | 82 | S | now |
| P4 | Rigify `get_edit_bone()` at the 15 edit-stage writes | 15 | S-M | later: rigify maintainers' call |
| P5 | Node Wrangler records as tuples and a record class | 33 | M | later: touches mutable records |
| P6 | `script_paths_pref`, `is_path_extension` in `bpy.utils.__all__`; dead `DATA_UL_bone_collections`, `VIEW3D_PT_imagepaint_options`; `FixToCameraCommon`'s mypy stubs | 13 | S | later: public API and removals are the maintainers' call |
| P7 | `assert mod is not None` after `modifiers.new()` in the multires tests | 30 | S | later: typing-only churn in one test |
| P8 | The Grease Pencil material preset generator writes to `context.object.active_material`, not the `context.material` its panel shows | 0 | S | done (2026-11-19), with R15 |

## Nullable pointers

### `unchecked-pointer` (548)

What the cause holds: a nullable read that no earlier cause claimed, outside the untyped packages. Most earlier causes
skip `tests/`, so the test suite's nullable reads land here: 532 in `tests/`, 12 in `tools/`, 2 in `build_files/`, 1
in `doc/`, 1 in `scripts/`. By rule: 415 `missing-union-attribute`, 82 `invalid-assignment`, 32
`invalid-argument-type`, 19 `missing-attribute`.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| `obj.animation_data` of an object loaded from a test `.blend`, set by `bpy.ops` or keyed | 83 | 11 | (d); 16 follow `animation_data_create()` or `keyframe_insert()` |
| `Object` reads in tests: `context.object` after `open_mainfile` or an operator, objects read by name, `self.evaluated_object = None` | 82 | 23 | (d) |
| Action lookups: `channelbag`, `fcurves.find()`, `fcurve.group`, `action_slot` | 74 | 10 | (d); 2 R6 |
| `GreasePencilFrame.drawing` | 61 | 1 | (d) |
| `ID \| None` of `override_create()`, `depsgraph.id_eval_get()` | 42 | 3 | (d): both return None on failure |
| `self.image` / `self.me` / `self.ob = None` in `tearDown` (`bl_pyapi_prop_array.py`) | 41 | 1 | P3: `del self.x` |
| `Collection.importer` and its `import_properties` | 29 | 1 | (d) |
| `ob.motion_path` after `paths_calculate()` | 26 | 1 | 14 R6 (`assertNotEqual(x, None)`); 12 (d) |
| stdlib Optionals, optional imports (`gpu = None`) | 45 | 12 | (d) |
| `addons[...].preferences` in performance tests | 18 | 4 | (d) |
| `tool_settings.sculpt.brush` | 10 | 2 | (d) |
| `_write_animdata_desc(adt: AnimData)` given `x.animation_data`; the body tests `if adt:` | 9 | 1 | P3 |
| Other (`asset_data`, `sequence_editor`, `scene.world`, ...) | 28 | 15 | (d); 1 bug (`mesh_test.py:396`) |

About 267 of these (heuristic) re-read a receiver already reported earlier in the same function. Treating `x` as not
None after a statement that dereferenced it would report each receiver once (R24). That is general Python.

### `python-optional` (305)

What the cause holds: a nullable read whose types hold no Blender type, or a local initialised to None. 207 in
`scripts/`, 73 in `tests/`, 25 elsewhere.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| A value initialised to None and set later (attributes, globals, list and dict records) | 119 | 37 | (d) |
| The untyped packages' own Optionals | 78 | 32 | (d) |
| Python Optionals (`__doc__`, `__file__`, `os.cpu_count()`, `importlib` specs, numpy) | 45 | 19 | (d) |
| Narrowed through another check (a validating helper, a length) | 19 | 7 | (d) |
| `SequencerCrossfadeSounds.execute`: `strip1` is set whenever `strip2` is | 13 | 1 | P2 |
| `add_object_align_init`: `properties` tested through `if operator:` | 12 | 1 | P2 |
| Vector property `get=` returning a nested list for a multi-dimensional `size` | 6 | 1 | S8 |
| Tests passing a wrong type on purpose | 5 | 3 | (d) |
| `io_report.Report(comparison_func: Callable[[str, dict], None])` given `(Path) -> str` | 4 | 3 | P3 |
| Bugs: `active_repo` in the repository menu (2), `align == 'VIEW'` outside a 3D View (1), `file_path_foreach(**kwargs)` with keywords it does not take (1) | 4 | 3 | P1 |

### `set-by-preceding-call` (90)

A pointer an earlier call made exist (`bpy.ops.*`, `image.open()`), or that the callback which always runs first sets
(`self._timer` from `execute`, read in `modal`). 73 in `tests/`. All (d): an operator can fail, and the stub is right.
One read follows `assertNotEqual(x, None)` (R6).

### `none-excluded-by-arguments` (81)

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| `animation_data_create()` result | 29 | 4 | S1: None only for ID types without animation data |
| `x.animation_data` read again after `animation_data_create()` or `driver_add()` | 19 | 3 | (d): holds only until the next call that clears it |
| `to_mesh()` / `meshes.new_from_object()` | 21 | 3 | (d): None for a metaball that is not the mother |
| `load_image()` | 6 | 2 | P1 (5 in `image_as_planes`); 1 S12 |
| `uv_layers.new()`, `begin_result()`, `layers.active` | 6 | 4 | (d) |

### `rarely-none-member` (16), `helper-checks-none` (9), `modifiers-new` (35)

All (d), except `SpaceAssetInfo.is_asset_browser`, whose docstring types its argument `Space` though it tests for None
(S8, 2). `view_layer.depsgraph` is None until the view layer was evaluated once; Freestyle's `scene.camera` is None
outside a render; `modifiers.new()` returns None with a warning when the object rejects the modifier. 26 of the 35
`modifiers-new` reads re-read a modifier already reported.

### `correlated-union` (59)

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| `strip_type = strip.type`, then `if strip_type == 'SPEED':` (`properties_strip.py`) | 15 | 1 | R20 |
| `str` assigned to an enum (Node Wrangler) | 11 | 2 | (d); C4: belongs to `general-typing` |
| Unions picked by mode or path (`SelectPattern`, glTF, FBX, viewer nodes, dict records) | 23 | 7 | (d); 2 P2 (`lamp.type`) |
| Freestyle: three modifier bases tested by `m.type` | 6 | 1 | R11 |
| Other | 4 | 3 | (d) |

fake-bpy-module has 467 here: its `Object.data` is a union of the data types.

### `correlated-condition` (12)

`context.object` re-read after a checked `ob = context.object` (3, P2), `context.active_object` under `if
context.active_pose_bone` (2, R7), `scene.sequence_editor` under a poll on `active_strip` (2, (d) until R7 follows the
poll into `execute`), and 5 structural invariants (d).

## Subtypes

### `type-enum-sub-pointer` (411)

A nullable sub-pointer that exists for one value of a type or mode enum: an armature's `Object.pose` (211), a Grease
Pencil material's `grease_pencil`, a paint mode's `tool_settings.<mode>`, fluid `domain_settings`, `Object.collision`,
`FCurve.driver`. The probe types `_Object_ARMATURE.pose` as `Pose | None` on purpose (None from `objects.new()` until
the depsgraph builds it), so a tag test does not clear a `pose` read.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| rigify `self.obj.pose.bones`; test armatures' `.pose` | 189 | 41 | (d) |
| Grease Pencil material presets: `material.grease_pencil` | 57 | 3 | R15 |
| `QuickSmoke` / `QuickLiquid`: `fluid.fluid_type = 'DOMAIN'`, then `domain_settings` | 21 | 1 | R17 |
| Tool-settings panels with a dotted `bl_context` | 19 | 1 | R2 |
| Tests: `tool_settings.sculpt` after `open_mainfile` | 19 | 6 | (d) |
| `PHYSICS_PT_collision*`: `context.object.collision` after `coll = md.settings` was checked | 17 | 1 | P2: the same pointer |
| `FCurve.driver` of `driver_add()` or `AnimData.drivers` | 16 | 4 | S9 |
| Context-menu panels called from a mode's key map; armature panels; `QuickFur` | 35 | 4 | (d) |
| `NODE_PT_geometry_node_tool_*` popovers opened under `if snode.node_tree:` | 10 | 1 | R22 |
| Fluid presets read `context.fluid.domain_settings` | 6 | 3 | R15 |
| `Object.mode == 'PAINT_GREASE_PENCIL'`, `scene.tool_settings` | 7 | 3 | R23 |
| Other (bvh import, pose library, glTF, brush) | 13 | 9 | (d) |
| Bugs: canvas poll, `ma.grease_pencil.mode` | 2 | 1 | P1 |

### `object-data-untagged` (406)

`Object.data` (`ID | None`) read with no Type tag test. 360 in `tests/`, 25 in docs and templates, 21 shipped. Where
the code tests `ob.type`, the existing tag narrowing applies; what is left is objects whose type comes from how they
were made.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| Tests: `context.object` after `open_mainfile`, `evaluated_get().data`, `setUp` objects, objects by name, helpers | 233 | 36 | (d) |
| `context.object` after `primitive_*_add()`, `object.add(type=)`, `text_add`, `light_add` | ~125 | 13 | R14 |
| `bpy.data.objects.new(name, cam)` then `.data` | 7 | 3 | R10 |
| Docs and templates "with an active mesh"; shipped rigify widgets, previews | 35 | 16 | (d) |
| `type(data) == bpy.types.Mesh`; a helper's test | 5 | 3 | (c), later |
| Freestyle `camera.type != 'CAMERA' or camera.data.type` on `Object \| None` | 1 | 1 | (d) |

### `base-class-subtype` (101)

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| `bpy_prop_collection.items()` / `.values()` give `bpy_struct` | 13 | 3 | S4 |
| `UIList.draw_item` without a typed `template_list` caller; a list nothing uses (6) | 18 | 6 | (d); P6 |
| `Modifier` / `Constraint` by name, `ID.animation_data`, Freestyle `FEdge`, sockets by name, rigify | 37 | 16 | (d) |
| Built-in gizmos (`gizmos.new("GIZMO_GT_button_2d")`) | 7 | 4 | S11 |
| `Strip & ~EffectStrip`: negation leaves the base | 5 | 2 | R23 |
| Refined bases: `Pose.ik_param`, members every subclass has, `BoneCollection.id_data` | 9 | 5 | S7 |
| `PointerProperty(poll=)`, `init_socket`, asset shelf `space_data`, `KeyingSetInfo.generate` | 7 | 4 | R23; (d) |
| Other | 5 | 5 | (d) |

### `mixin-self` (257)

Since the mixin rule, a mixin of Blender classes types `self` as the mixin and its users' `bpy.types` classes. What
remains is mostly mixins of other bases.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| Test mixins whose users are all `unittest.TestCase` subclasses | 142 | 8 | R1 (140; `super().setUp()` stays) |
| Plain Python classes (`PackageInstaller.settings` set in `__new__`, `blendfile.py`, ...) | 53 | 12 | (d) |
| `_GenericBone` in `_bpy_types.py` | 15 | 1 | R23 |
| Another class's callback called with `self` (duck typing) | 9 | 3 | (d) |
| Class-body functions with no `self` | 9 | 2 | P2: `@staticmethod` |
| Users made by `type(name, (Mixin, ThemePanel, Panel), {...})`; attributes that dict sets | 9 | 1 | R23; P2 |
| Attributes a mixin's users define | 10 | 7 | R23 (upstream: bound `Self` by the union of the users) |
| `FixToCameraCommon`'s stubs, `TestCase._outcome`, `super().__del__()` (bug), others | 10 | 8 | P6; (d); P1 |

## Context and UI

### `ui-draw-pointer` (408)

A nullable read in a draw callback. None of it is a `UILayout` stub fact: `prop()` and the templates flag `data`
`PROP_NEVER_NULL` and raise `TypeError` for None, so any of these reads that is really None is an error in the draw.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| `context.object` in mode menus and header popovers drawn from a mode branch | 98 | 8 | (d) |
| `context.bone or context.edit_bone` correlations | 57 | 1 | (d) |
| `type(context.curve) is TextCurve` polls | 55 | 1 | R3 |
| Sidebar panels with a dotted `bl_context` | 50 | 1 | R2 |
| `context.window` / `screen` / `workspace` in a draw | 27 | 12 | R4 |
| `space.params` in file-browser menus; `particle_edit.object` | 25 | 2 | (d) |
| `strip.transform` / `strip.crop` after `strip.type != 'SOUND'` | 11 | 1 | S3 |
| `context.object` under a poll on `particle_system`; `sequencer_scene` under `active_strip`; GP `tool_settings` | 14 | 3 | R7 |
| `layout.operator()` of the file's own operator in doc examples | 5 | 2 | R5 |
| Rigify panel helper, Cycles sub-panel of a `bl_ui` panel, asset-browser mixins | 13 | 3 | R23 |
| Node Wrangler menus with `NWBaseMenu`'s poll after `Menu` | 2 | 1 | R8 |
| `elem.orig_fps` (bug), Graph editor `dopesheet` | 3 | 2 | P1; S3 |
| Other correlations | 48 | 16 | (d) |

### `editor-context-member` (47), `script-context-member` (46), `window-context-in-execute` (38), `context-member-outside-callback` (9)

`area`, `space_data`, `window` and friends read where the callback does not guarantee them. The window is set for a
`--python` script and for Blender's own `--background` tests, but not in a command-line render or under
`temp_override(window=None)`; `area` is missing for `bpy.ops.x('INVOKE_DEFAULT')` from a script. Both are R21
Assumptions (later). Draw-handler callbacks get their region's members (R18, later). Small facts: `AreaSpaces.active`
is never None (S3, 3), `view_draw`'s `context` neither (S3, 1), `animation_data_create()` (S1, 4), the
`layer_collection` of glTF import (R21), Node Wrangler's `NWBase` poll after `Operator` (R8, 2), and a template poll
that reads `space.type` unguarded (P2, 1).

### `layout-in-operator-helper` (38)

`pose_library_asset_browser_context_menu(self: Menu, context)`, prepended to a menu (15, R9); Operator methods called
only from `draw` (17, R19); methods called through a stored tuple (6, (d)).

### `set-by-ui-button` (10), `operator-without-poll` (7)

Both are mostly real bugs (P1): the keymap operators read `context.keymap` with no poll, and three rigify operators
read the active object with no poll. `keymap_items.from_id()` returning None for an unknown id (4) is (d).

### `operator-call` (67), `runtime-operator-idname` (2)

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| `bpy.ops.<cat>.<name>` of an operator the same file registers (examples, templates, tests) | 30 | 19 | R5 |
| Tests calling operators wrongly on purpose; node tools from a test file; a `getattr` chain; a dict value | 22 | 4 | (d) |
| Macro steps on a properties object (`props.MESH_OT_rip.use_fill`) | 6 | 2 | R23 |
| `lambda` passed where `Callable[[str, dict], None]` is expected (`io_report.py`) | 5 | 5 | P3 |
| Removed operators and 2.7x calls | 4 | 3 | P1; C2 |
| An idname built from a per-subclass attribute | 2 | 1 | (d) |

## Python typing

### `general-typing` (407)

Plain Python typing debt. The earlier report counted 512; the `global` declarations, the gdb exclusion and the
`import_svg` annotations took most of the drop.

| Sub-pattern | Count | Files | Fix |
|---|---:|---:|---|
| Attributes set at runtime on functions, modules and classes; monkeypatches | 99 | 24 | (d) |
| Python Optionals, placeholders, records in dicts and lists, `object` values | 91 | 41 | (d) |
| Unused `# type: ignore` (for mypy) | 39 | 17 | C1 |
| Node Wrangler `[index, socket]` and `[name, tags, file]` records | 33 | 2 | P5 |
| Annotations that disagree with the code (performance tests, `bl_pkg`'s `InfoItemCallable`, the fork's node socket probe) | 26 | 8 | P2, P3 |
| Overrides that rename a parameter: `/` on 5 base methods | 25 | 4 | P2 |
| Nullable Blender pointers reported on their `None` member | 14 | 4 | (d); C4 |
| `@contextmanager` with `-> Iterator[...]` (11); `array.array`, `onerror=` (3) | 14 | 9 | P2; (d) |
| `ShapeKey.data` items (8); `AutoKeying.options()` loses `@contextmanager` in the stub (1) | 9 | 2 | S5; S12 |
| Lint-style findings, deliberate errors in tests, narrowing overrides, other inference limits | 56 | 37 | (d) |
| A Blender bug: `.value` on an operator's result | 1 | 1 | P1 |

### `untyped-python` (452)

Every diagnostic in rigify (254), glTF (142), `_bl_i18n_utils` (26), `I18nSettings` (18), `bl_app_override` (8),
Freestyle (2) and numpy (2).

| Sub-pattern | Count | Fix |
|---|---:|---|
| The packages' own typing and Optionals, overrides, runtime attributes, `Vector.cross` unions, `path_resolve()` | 381 | (d) |
| `I18nSettings`: `__dict__` replaced by the settings module's globals | 18 | P2: class annotations |
| Registered property after `hasattr(x, "name")` (`gltf_action_filter`, `rigify_colors`) | 17 | R16 |
| rigify's `class ActionSlot` shadows the imported `bpy.types.ActionSlot` | 13 | P2 |
| numpy arrays to `bpy_prop_array.foreach_get` / `foreach_set` (7), `Vector.cross((0, 0, 1))` (3), `UI_UL_list` items (2) | 12 | S6; S8 |
| Registered property writes on an intersection receiver | 6 | R13 |
| `interface.new_socket(socket_type="NodeSocketFloat")` | 4 | R12 |
| `Scene.frame_set()` with float keyframe times | 3 | P1 |

## Small and unsorted causes

### `unsorted` (249)

Whatever no cause matched: 222 in `tests/`, `tools/`, `doc/` and `build_files/`.

| Sub-pattern | Count | Fix |
|---|---:|---|
| Plain Python typing in tests and tools; monkeypatches; Optional keys | 108 | (d); C4 |
| gdb API hints (`tools/debug/gdb/gdb/`) | 37 | C2 |
| gpu `Buffer` buffer protocol, `GPUStorageBuf` arguments | 20 | S2 |
| Deliberate errors in tests (`assertRaises`) | 17 | (d); C4 `expected-error` |
| `ActionChannelbagFCurves` passed to a helper typed `list[FCurve]` | 13 | P3 |
| `x: T = None` (11), `context: any` (4) in tests | 15 | P3 |
| `FCurve \| list[FCurve]` from `driver_add(path, -1)` | 10 | R23; S12 |
| Test bugs; 2.7x API; `sys.arch`-like dead API | 6 | P1; C2 |
| `bl_rna` on a collection, dynamic enums, `ensure_ext(bytes)`, `bind()` context manager, `_rna_info` protocols | 13 | S8; S2; P2 |
| Other (`KDTree.find()`, attribute value unions, `data_to` after `libraries.load`, `PipeConnection`) | 10 | (d); platform |

### `stub-gap` (55)

Platform (17, done with `--python-platform linux`), gdb hints (13, C2), test overrides that rename a parameter (12,
(d)), deliberately wrong callback signatures (6, (d)), dead API (`register_module`, `sys.arch`: 3, C2 and P1),
`bpy.types.bpy_func` (1, S8), `bpy.app.handlers` iterated as a module (1, (d)), tool typing (2, (d)).

### `unresolved-import` (39)

Script-directory imports (16, (d)), Blender Python modules the builtin stubs leave out (8, S10), names a module does
not export and submodules used after `import urllib` (8, P2), private CPython hashes (3, C3), `bpy.utils` members
missing from `__all__` (1, P6), `bpy_struct_meta_idprop` (1, S8), the wrong VR import (1, P1), `from space_view3d
import` after `sys.path.append` (1, P2). fake-bpy-module has 81: it ships none of Blender's private C modules.

### `runtime-name` (34)

`BMO_OP_SLOT_*` names put into `globals()` from a parsed C header (25, (d)), and `gdb` used without an import in a
script that runs inside GDB (9, P2: `import gdb`).

### `blender-rule` (5), `deprecated-enum-value` (5), `unexported-function` (3), `cross-file-registered-property` (2)

The 5 `blender-rule` reports are in classes a test registers to see them fail: right reports (d). `TRI_FAN` in Node
Wrangler is deprecated at runtime (P1). `script_paths_pref` is missing from `bpy.utils.__all__` (P6). Of the two
cross-file reads, `selection_sets` would need `scripts/startup/` as one registration unit and then moves to a nullable
cause; the Cycles read in a test stays.

### `typechecker-fix` causes (32)

| Cause | Count | Fix |
|---|---:|---|
| `file-registered-property` | 10 | 9 are class monkeypatches (C4); 1 R23-sized rule (a Registered property over a stub attribute) |
| `registered-class-in-bpy-types` | 8 | S10 (startup classes); 1 R23 (an add-on class) |
| `mathutils-protocol-stub` | 5 | S2 (2); (d) for `partial(setitem, vec)` and `Vector.cross` (3) |
| `stub-signature-gap` | 4 | P2 `[0] * n` (2); S12 (2) |
| `freestyle-positional` | 2 | (d): real Liskov narrowing in Freestyle's predicates (fake-bpy-module has 41: its C methods lack `/`) |
| `dynamic-enum` | 2 | R23 (tuple `+`); (d) |
| `filter-items-tuple` | 1 | P2 `[0] * n` |

### `rigify-get-bone` (15)

See "Blender bugs found": correct annotation errors in edit stages, P4.
