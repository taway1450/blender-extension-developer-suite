# Spec #95 BF3: the warnings that stay in Blender's code

BF3 (#105) made every Imprecise annotation in Blender's code precise and fixed the Implied narrowings
where the code was wrong or an explicit check reads better. This report lists what stays, by rule and
pattern, with the reason. Counts are `check:blender main` with Blender's own (builtin) stubs at
`typecheck-fixes` `1bce53f6a88`; file:line references are to that commit.

## What BF3 changed

13 commits on `typecheck-fixes` (`543ab57dcdb..1bce53f6a88`), Python only, behaviour-preserving:

- `-> set[str]` / `Set[str]` operator results became `set[Literal[...]]` of the names returned (Copy
  Global Transform, Pose Library, Node Wrangler), and sets held in a variable got a declared type
  (`PREFERENCES_OT_addon_enable`, the SVG and FBX multi-file imports).
- `str` values passed as enum items got the enum type: a `Literal` of the few names assigned (Rigify's
  heel rotation mode and bone themes, the FBX light types, the extension repository source), or an
  alias of the builtin stubs' `_rna_enums` module imported under `if TYPE_CHECKING:` (constraint
  type, event type and value, image file format, report types, object mode). Lists of `(name, icon)`
  pairs became tuples so the names stay literal (sculpt filters, node group types, strip colors).
- Callback parameters: `RIGIFY_UL_action_slots.draw_item` drops its narrower `data` / item annotations
  and checks their types; `FixToCameraCommon`'s `report()` / `poll_message_set()` stubs take
  `Operator`'s signatures and the mixin is listed before `Operator` in both classes.
- `bpy.utils.keyconfig_set`'s `report` is documented as taking Blender's report types, which removes
  the two `keyconfig_set(report=self.report)` errors S2 left.
- Values the code only knows at runtime (enum items read from RNA in the UI and operator tests, the
  Hydra export method passed through the environment) are cast to their enum; the type tag probe types the enum
  items it tries as `Any`.
- Implied narrowings fixed: `INFO_MT_area` (opened from most editors' View menu) and
  `DOPESHEET_MT_channel_context_menu` (opened from the Graph Editor too) check the space they are
  drawn in instead of relying on their name prefix.

## Remaining Blender-rule warnings (builtin stubs)

| Rule | Count | Stays because |
|---|---:|---|
| `blender-assumed-context-member` | 880 | scripts, tests and presets that run with a window's scene |
| `blender-narrowed-by-poll` | 778 | the poll checked the pointer; the code is right |
| `blender-narrowed-by-menu-prefix` | 100 | menus opened only from their own editor, as their name says |
| `blender-assumed-list-item` | 97 | lists of structs, which never have an empty slot |
| `blender-assumed-registration` | 84 | properties registered behind an add-on option, read only when it is on |
| `blender-narrowed-by-popover` | 30 | popovers opened from their own editor's header |
| `blender-assumed-complete-registration` | 7 | `register()` loops over values the checker can't follow |
| `blender-assumed-preferences` | 1 | a helper read after registration that the checker attributes to `register()` |
| `blender-imprecise-*` | 0 | |

### `blender-assumed-context-member` (880)

`context.scene` 701, `context.view_layer` 159, `context.tool_settings` 19, read outside a Blender
callback. They are all `bpy.context` in code that runs with a window and a loaded file.

| Pattern | Count | Example |
|---|---:|---|
| Tests (`tests/`) | 475 | `tests/python/bl_usd_import_test.py:81`, `tests/performance/tests/animation.py:17` |
| Presets, run by `script.execute_preset` | 275 | `scripts/presets/color_management/white_balance/Illuminant_A.py:2` |
| Add-on helpers called from callbacks with `bpy.context` | 69 | `scripts/addons_core/hydra_storm/engine.py:20`, `scripts/addons_core/io_scene_gltf2/blender/exp/animation/action.py:305` |
| `bl_operators` helpers taking the operator's context | 23 | `scripts/startup/bl_operators/copy_global_transform.py:59` |
| Python API examples | 16 | `doc/python_api/examples/bpy.ops.1.py:29` |
| Modules with an optional context (`bpy.utils.time_from_frame`, previews, `anim_utils`) | 12 | `scripts/modules/bpy/utils/__init__.py:739` |
| Developer tools, templates, release scripts, Cycles' Hydra add-on | 10 | `tools/utils_doc/code_layout_diagram.py:547`, `scripts/templates_py/background_job.py:28` |

Reason: the read is right in ordinary use; an explicit `None` check in a test, a preset or a script
meant for the UI would only add noise. Moving the helpers to take a callback's `context` is a refactor
per add-on, not a fix.

One read stays although it is a real risk:
`doc/python_api/examples/bpy.types.FileHandler.1.py:49` links the imported object to
`bpy.context.scene.collection` in a FileHandler's import operator, which the collection importer
runs with no scene. The right target collection depends on what the importer puts in the context,
which this ticket did not verify at runtime; it is left for a follow-up with a runtime test.
`scripts/addons_core/io_curve_svg/import_svg.py:1788` (the SVG importer, also a FileHandler
operator, reads the scene's unit scale in a helper) is the same case.

### `blender-narrowed-by-poll` (778)

A pointer the class's `poll()` checked, read in `draw` / `execute` / `invoke`. By area: `bl_ui` 553,
add-ons 96, `bl_operators` 94, Cycles 27, templates 6, API examples 2. The most common reads are
`context.object` 156, `context.space_data` 56, the physics pointers (`context.fluid` 49,
`context.dynamic_paint` 28, `context.cloth` 27, `context.soft_body` 23), `context.space_data.clip` 29,
`context.active_strip` 28 and the ID pointers of the Properties editor's panels (`material`,
`texture`, `camera`, `world`, `light`, ... about 120).

Examples: `scripts/startup/bl_ui/properties_physics_fluid.py:122`,
`scripts/startup/bl_operators/clip.py:222`, `intern/cycles/blender/addon/ui.py:1222`.

Reason: the code is right; Blender calls these callbacks only after the poll returned true, with
the same context. Repeating the poll's check in every `draw` is the noise the rule exists to avoid.

### `blender-narrowed-by-menu-prefix` (100)

`context.space_data` in the `draw` of a menu named after its editor: Clip 20, Image 10, Sequencer 9,
Node 9, Geometry Nodes add menus 8, Dope Sheet 7, Graph 6, Outliner 5, File Browser 5, View 3D 4,
Text 4, Compositor add menus 3, NLA 2, one each in five other editors, and 3 Node Wrangler menus
(`scripts/addons_core/node_wrangler/operators/lazy_connect.py:196`).

Example: `scripts/startup/bl_ui/space_clip.py:273`.

Reason: these menus are opened only from their editor's header, sub-menus or key map, as the naming
convention (which menu search relies on) says. The two menus that are opened from another editor
were fixed.

### `blender-assumed-list-item` (97)

`UIList.draw_item`'s `item` read without a `None` check: `bl_ui` 67, add-ons 23, API examples 5,
templates 1, tests 1. Examples: `scripts/startup/bl_ui/properties_data_armature.py:89` (bone
collections), `scripts/addons_core/rigify/ui.py:291`, `doc/python_api/examples/bpy.types.UIList.1.py:31`.

Reason: every one of these lists shows a collection of structs; `None` only comes from an empty slot
of an array of ID pointers, which none of them draws.

### `blender-assumed-registration` (84)

Registered properties used where `register()` assigns them only on a branch: glTF's
`KHR_materials_variants` properties (46, registered when the add-on's variants option is on,
`scripts/addons_core/io_scene_gltf2/blender/com/gltf2_blender_ui.py:58`) and VR Scene Inspection's
action map properties (38, `scripts/addons_core/viewport_vr_preview/action_map.py:46`).

Reason: the reads are in UI and export code that runs only when the option registered them.

### `blender-narrowed-by-popover` (30)

`context.space_data` in a Panel the same file opens as a popover: View 3D 12, Node 5, Dope Sheet and
Timeline 4, Properties 2, File Browser 2, and one each in Clip, Graph, Image, Outliner and
Sequencer. Example: `scripts/startup/bl_ui/space_view3d.py:6746`.

Reason: each popover is opened from its own editor's header, so the space is its `bl_space_type`.

### `blender-assumed-complete-registration` (7)

`register()` registers values the walk can't follow (classes collected in a loop or from another
module's list): Cycles (`intern/cycles/blender/addon/ui.py:2694`), glTF, Node Wrangler, Pose
Library, Rigify's metarig menus, UI Translate and VR Scene Inspection.

Reason: the registration is right; spelling every class out would only serve the checker.

### `blender-assumed-preferences` (1)

`scripts/addons_core/rigify/__init__.py:204`: `RigifyPreferences.get_instance()` reads the add-on's
preferences; `register()` calls it after `register_class(RigifyPreferences)` and `unregister()` before
`unregister_class`, and it asserts the type. Reason: false positive of the order the checker sees.

## Other warnings (out of BF3's scope)

| Rule | Count | Group |
|---|---:|---|
| `unresolved-global` | 37 | typing debt (module globals assigned in functions) |
| `unused-type-ignore-comment` | 34 | typing debt |
| `deprecated` | 15 | typing debt |
| `redundant-condition` | 10 | unsorted |
| `possibly-missing-submodule` | 4 | typing debt |
| `mismatched-type-name` | 1 | unsorted |
| `blender-unsupported-property-target` | 1 | `tests/python/bl_pyapi_idprop_datablock.py:355`, a test that registers it on purpose |

## Imprecise annotations: errors that stay

The `imprecise-*` causes keep 5 errors in the builtin bucket report, none of them a precise
annotation to add:

- `tests/python/bl_operator_wrap_py_api.py:254`, `:269`, `:284`: operators with a wrong `execute` /
  `invoke` signature, written so to test that registration rejects them.
- `tests/python/bl_pyapi_idprop_datablock.py:360`: a `draw_item` with an extra parameter in a UIList
  the test expects registration to reject.
- `scripts/addons_core/rigify/rigs/limbs/leg.py:227`: `Matrix.Rotation(..., self.main_axis.upper())`,
  a `str` axis where mathutils takes `'X' | 'Y' | 'Z'`: a mathutils argument, not an RNA enum.

## fake-bpy-module

With fake-bpy-module stubs the same fixes apply, with these differences:

- 3 `blender-imprecise-callback-parameter` warnings stay at
  `scripts/addons_core/rigify/operators/action_layers.py:360-361`: fake-bpy-module types
  `draw_item`'s `active_propname` / `index` / `flt_flag` `str | None` / `int | None` where Blender
  always passes them (fake-bpy-module's general nullability, out of the spec's scope).
- 10 `invalid-method-override` errors on `AddPresetBase` subclasses (Cycles' presets, an API example)
  stay in `imprecise-operator-return`: fake-bpy-module's stub of `bl_operators.presets.AddPresetBase`
  types its `execute` / `invoke` results `set[str]`; Blender's own stubs don't.
- The 8 files that import an enum alias from `_rna_enums` under `if TYPE_CHECKING:` get an
  `import-not-found` error: the module exists only in the builtin stubs, which the spec takes as the
  source of the aliases.

## Bucket move (`check:blender main`, vs `cd4621a`)

| Cause | builtin | fake-bpy-module |
|---|---:|---|
| `imprecise-operator-return` | 18 → 3 | 28 → 13 |
| `imprecise-enum-value` | 35 → 1 | 35 → 1 |
| `imprecise-callback-parameter` | 3 → 1 | 6 → 4 |
| `narrowed-by-menu-prefix` | 105 → 102 | 92 → 89 |
| `stub-docstring` (`keyconfig_set(report=...)`) | 2 → 0 | 2 → 0 |
| `stub-gap` (builtin: the `FixToCameraCommon` overrides) | 183 → 180 | 767 → 768 |
| `unresolved-import` (`_rna_enums`) | 0 | 216 → 224 |
| errors | 7,190 → 7,183 | 9,460 → 9,464 |
| warnings | 2,131 → 2,079 | 2,195 → 2,143 |
