# Example add-ons

Five add-ons that together show what the suite does with add-on code: what ty-blender types, what it reports, and
what it cannot do yet. They are written the way add-ons are usually written, and each one loads in Blender. This
folder is a Workspace: every sub-folder is one add-on, and [ty.toml](ty.toml) configures the checker for all of them.

| Add-on | What it is |
| --- | --- |
| [scatter_tools](scatter_tools/) | Scatters copies of an object over a mesh. An Extension split into `properties`, `operators`, `ui` and `preferences`: every kind of property, operators with a poll mixin, panels with sub-panels and a UI list. |
| [batch_export_and_import](batch_export_and_import/) | Exports objects to files and imports them back. Built-in exporters, a macro, a file handler, presets, a key map, a save handler, and Scatter Tools as a declared dependency (`[tool.blender] uses`). |
| [node_kit](node_kit/) | A node tree type of its own with nodes and sockets, and helpers for the shader editor. It ships a `.blend` file. |
| [viewport_tools](viewport_tools/) | A modal measure operator with an overlay drawn by `gpu` and `blf`, a gizmo group, a toolbar tool and popovers. |
| [legacy_renamer](legacy_renamer/) | Renames objects by rules. A `bl_info` add-on written the old way, with the imprecise annotations and the two registration mistakes such add-ons often have. |

## How an example says what it shows

- **The add-on's own code is unmarked.** What the checker reports on it (the warnings of the `blender-*` rules, and
  errors where it cannot follow the code yet) is left as it is, so it shows in an editor.
- **`check_<addon>.py`** holds the types the add-on's code relies on, as `assert_type` calls and expected errors
  (`# ty: ignore[rule]`), with the markers of the feature tests ([tests/typecheck/README.md](../../tests/typecheck/README.md)).
  Blender never imports the file, and the manifest keeps it out of the built extension.
- **A `# demo: <id>` comment line** names what the statement below it shows. `<id>` is a feature directory of
  [tests/typecheck/features/](../../tests/typecheck/features/), a `blender-*` rule, or `later/<topic>` for a behaviour
  that does not work yet. [coverage.toml](coverage.toml) describes the `later/` topics and lists the rules the examples
  leave to the feature tests, because they need code that Blender rejects or that silently does nothing.
- **The results are recorded** in `examples/expected/<generator>/<version>.txt`: every diagnostic on the add-ons' own
  code and every marker that does not hold yet. A behaviour that starts to work shows as a change there. The
  results for Blender 5.2 are much longer than those for main: its stubs type a callback's `context` parameter
  `Context | None`, so almost every read of the context is an error there.

## Running the checks

```sh
mise run check:load main --examples       # each add-on registers and unregisters in Blender
mise run lint:addons main                 # stock ruff with the profile in config/ruff/addons.toml
mise run format:addons main
mise run check:addons main                # ty-blender; fails when the results differ from the recorded ones
mise run check:addons main --update       # record the results, after reading the difference
mise run examples:coverage                # check the tags and rewrite the tables below
```

Each task takes add-on names to narrow it (`mise run check:addons main node_kit`). `check:addons` writes ty's full
output and a summary per stub generator to `.cache/typecheck-results/<version>/<generator>/examples-*`.

`examples:coverage` checks every tag against the results recorded for the builtin stubs of Blender main: the
statement of a rule tag is reported under that rule, the statement of a feature tag passes, and the statement of a
`later/` tag still fails. When a `later/` topic starts to work, the task says so, and its tag becomes a feature tag.
`mise run test:scripts` runs the same check.

## In an editor

With ty-blender as the editor's language server, these places are worth trying. No task checks the IDE features
here (`check:ide` covers them in the feature tests):

- Hover `settings` in `OBJECT_OT_scatter_tools_scatter.execute` (`scatter_tools/operators.py`): a Registered property
  of the scene, typed as the add-on's `PropertyGroup`.
- Type `bpy.ops.object.scatter_tools_scatter(` in any add-on of this folder, for the operator's properties in the
  signature.
- Type `layout.operator("view3d.viewport_tools_measure").` in `viewport_tools/ui.py`, for the properties of that
  operator as completions.
- Hover `context.object` in `VIEWPORT_TOOLS_GGT_light.setup` (`viewport_tools/gizmos.py`): narrowed to a light object
  by the class's `poll`, with a warning that says so.

## Your own add-on

Copy or link the add-on's folder into this one and name it in the tasks above:

```sh
mise run check:load main --examples my_addon
mise run lint:addons main my_addon
mise run check:addons main my_addon
```

`check:addons` then lists every diagnostic as new (`+`) and fails, since nothing is recorded for the add-on; the full
output is in `.cache/typecheck-results/main/<generator>/examples-ty.txt`. Do not pass `--update`, and remove the
folder afterwards. An add-on that is no Extension needs no manifest: a `bl_info` dict is enough.

## What is shown where

The tables are written by `mise run examples:coverage`. To find the lines, search an add-on for `demo: <id>`.

<!-- BEGIN coverage (mise run examples:coverage) -->

### Features

| Feature | Shown in |
| --- | --- |
| [`addon_discovery`](../../tests/typecheck/features/addon_discovery/README.md) | [legacy_renamer/__init__.py](legacy_renamer/__init__.py) |
| [`addon_preferences`](../../tests/typecheck/features/addon_preferences/README.md) | [legacy_renamer/check_legacy_renamer.py](legacy_renamer/check_legacy_renamer.py), [scatter_tools/check_scatter_tools.py](scatter_tools/check_scatter_tools.py), [scatter_tools/preferences.py](scatter_tools/preferences.py) |
| [`api_types`](../../tests/typecheck/features/api_types/README.md) | [node_kit/check_node_kit.py](node_kit/check_node_kit.py), [node_kit/shader.py](node_kit/shader.py) |
| [`assumptions`](../../tests/typecheck/features/assumptions/README.md) | [legacy_renamer/ops.py](legacy_renamer/ops.py) |
| [`bpy_symbols`](../../tests/typecheck/features/bpy_symbols/README.md) | [batch_export_and_import/check_batch_export_and_import.py](batch_export_and_import/check_batch_export_and_import.py), [batch_export_and_import/handlers.py](batch_export_and_import/handlers.py), [batch_export_and_import/importer.py](batch_export_and_import/importer.py), [scatter_tools/operators.py](scatter_tools/operators.py), [viewport_tools/check_viewport_tools.py](viewport_tools/check_viewport_tools.py) |
| [`context_members`](../../tests/typecheck/features/context_members/README.md) | [batch_export_and_import/check_batch_export_and_import.py](batch_export_and_import/check_batch_export_and_import.py), [batch_export_and_import/export.py](batch_export_and_import/export.py), [node_kit/ui.py](node_kit/ui.py), [scatter_tools/ui.py](scatter_tools/ui.py) |
| [`implied_narrowings`](../../tests/typecheck/features/implied_narrowings/README.md) | [scatter_tools/ui.py](scatter_tools/ui.py) |
| [`imprecise_annotations`](../../tests/typecheck/features/imprecise_annotations/README.md) | [legacy_renamer/ops.py](legacy_renamer/ops.py) |
| [`inheritance`](../../tests/typecheck/features/inheritance/README.md) | [node_kit/tree.py](node_kit/tree.py), [scatter_tools/operators.py](scatter_tools/operators.py) |
| [`operator_calls`](../../tests/typecheck/features/operator_calls/README.md) | [batch_export_and_import/check_batch_export_and_import.py](batch_export_and_import/check_batch_export_and_import.py), [batch_export_and_import/export.py](batch_export_and_import/export.py), [scatter_tools/check_scatter_tools.py](scatter_tools/check_scatter_tools.py), [scatter_tools/operators.py](scatter_tools/operators.py), [viewport_tools/check_viewport_tools.py](viewport_tools/check_viewport_tools.py) |
| [`operator_properties`](../../tests/typecheck/features/operator_properties/README.md) | [batch_export_and_import/__init__.py](batch_export_and_import/__init__.py), [batch_export_and_import/check_batch_export_and_import.py](batch_export_and_import/check_batch_export_and_import.py), [node_kit/ui.py](node_kit/ui.py), [scatter_tools/ui.py](scatter_tools/ui.py), [viewport_tools/check_viewport_tools.py](viewport_tools/check_viewport_tools.py), [viewport_tools/gizmos.py](viewport_tools/gizmos.py), [viewport_tools/tool.py](viewport_tools/tool.py) |
| [`pointer_aliases`](../../tests/typecheck/features/pointer_aliases/README.md) | [node_kit/shader.py](node_kit/shader.py) |
| [`properties`](../../tests/typecheck/features/properties/README.md) | [legacy_renamer/props.py](legacy_renamer/props.py), [node_kit/check_node_kit.py](node_kit/check_node_kit.py), [scatter_tools/check_scatter_tools.py](scatter_tools/check_scatter_tools.py), [scatter_tools/properties.py](scatter_tools/properties.py) |
| [`property_wrappers`](../../tests/typecheck/features/property_wrappers/README.md) | [scatter_tools/check_scatter_tools.py](scatter_tools/check_scatter_tools.py), [scatter_tools/properties.py](scatter_tools/properties.py) |
| [`registration`](../../tests/typecheck/features/registration/README.md) | [legacy_renamer/check_legacy_renamer.py](legacy_renamer/check_legacy_renamer.py), [scatter_tools/__init__.py](scatter_tools/__init__.py) |
| [`registration_checks`](../../tests/typecheck/features/registration_checks/README.md) | [batch_export_and_import/check_batch_export_and_import.py](batch_export_and_import/check_batch_export_and_import.py), [batch_export_and_import/export.py](batch_export_and_import/export.py) |
| [`type_narrowing`](../../tests/typecheck/features/type_narrowing/README.md) | [node_kit/check_node_kit.py](node_kit/check_node_kit.py), [node_kit/shader.py](node_kit/shader.py), [node_kit/tree.py](node_kit/tree.py), [scatter_tools/check_scatter_tools.py](scatter_tools/check_scatter_tools.py), [scatter_tools/operators.py](scatter_tools/operators.py) |

### Rules

| Rule | Default level | Reported in |
| --- | --- | --- |
| `blender-assumed-added-object` | warn | [viewport_tools/measure.py](viewport_tools/measure.py) |
| `blender-assumed-complete-registration` | warn | [viewport_tools/ui.py](viewport_tools/ui.py) |
| `blender-assumed-context-member` | warn | [batch_export_and_import/importer.py](batch_export_and_import/importer.py), [legacy_renamer/ops.py](legacy_renamer/ops.py) |
| `blender-assumed-default-addon` | warn | feature tests only: needs a default add-on's source on a search path (see `later/default-addon-properties`) |
| `blender-assumed-editor-member` | warn | [viewport_tools/overlay.py](viewport_tools/overlay.py) |
| `blender-assumed-internal-operator` | warn | [legacy_renamer/ops.py](legacy_renamer/ops.py) |
| `blender-assumed-list-item` | warn | [scatter_tools/ui.py](scatter_tools/ui.py) |
| `blender-assumed-preferences` | warn | feature tests only: the read raises `AttributeError` in Blender: the preferences are `None` until their class is registered |
| `blender-assumed-preset-context` | warn | [batch_export_and_import/presets/batch_export_and_import/object/print.py](batch_export_and_import/presets/batch_export_and_import/object/print.py) |
| `blender-assumed-registration` | warn | [legacy_renamer/ops.py](legacy_renamer/ops.py) |
| `blender-assumed-subclass-member` | warn | [node_kit/shader.py](node_kit/shader.py) |
| `blender-duplicate-registration` | error | feature tests only: the add-on fails to enable, or one class silently replaces another |
| `blender-imprecise-callback-parameter` | warn | [legacy_renamer/ui.py](legacy_renamer/ui.py) |
| `blender-imprecise-enum-value` | warn | [legacy_renamer/ui.py](legacy_renamer/ui.py) |
| `blender-imprecise-operator-return` | warn | [legacy_renamer/ops.py](legacy_renamer/ops.py) |
| `blender-invalid-addon-metadata` | error | feature tests only: Blender refuses to list or install the add-on |
| `blender-invalid-base` | error | feature tests only: the class is silently registered as its first Blender base only |
| `blender-invalid-idname` | error | feature tests only: the add-on fails to enable, or Blender prints a warning |
| `blender-invalid-operator-property` | error | feature tests only: Blender registers the operator without the property and those after it |
| `blender-invalid-override` | error | feature tests only: the add-on fails to enable |
| `blender-invalid-property` | error | feature tests only: the add-on fails to enable |
| `blender-invalid-register` | error | feature tests only: the add-on fails to enable or to disable |
| `blender-legacy-property` | warn | [legacy_renamer/ops.py](legacy_renamer/ops.py) |
| `blender-missing-callback` | error | feature tests only: the add-on fails to enable |
| `blender-mixin-order` | warn | feature tests only: the mixin's method is silently never called |
| `blender-narrowed-by-bl-context` | warn | [batch_export_and_import/ui.py](batch_export_and_import/ui.py), [viewport_tools/ui.py](viewport_tools/ui.py) |
| `blender-narrowed-by-menu-prefix` | warn | [node_kit/ui.py](node_kit/ui.py) |
| `blender-narrowed-by-poll` | warn | [scatter_tools/operators.py](scatter_tools/operators.py), [viewport_tools/gizmos.py](viewport_tools/gizmos.py), [viewport_tools/measure.py](viewport_tools/measure.py) |
| `blender-narrowed-by-popover` | warn | [viewport_tools/ui.py](viewport_tools/ui.py) |
| `blender-preferences-idname` | warn | feature tests only: the preferences are silently never shown |
| `blender-register-order` | error | feature tests only: the add-on fails to enable |
| `blender-registered-base` | error | feature tests only: the base class's callbacks are silently no longer called |
| `blender-unknown-operator` | warn | [node_kit/ui.py](node_kit/ui.py) |
| `blender-unreachable-registration` | warn | feature tests only: the classes are silently never registered |
| `blender-unregister-mismatch` | warn | [legacy_renamer/__init__.py](legacy_renamer/__init__.py) |
| `blender-unregistered-class` | warn | [legacy_renamer/ui.py](legacy_renamer/ui.py) |
| `blender-unsupported-property-host` | warn | feature tests only: the property silently does not exist |
| `blender-unsupported-property-target` | warn | feature tests only: the property silently does not exist |

### Not working yet

| Topic (`later/...`) | What is missing | Source | Shown in |
| --- | --- | --- | --- |
| `blend-file-typing` | The data-blocks of a `.blend` file the add-on ships (`[tool.blender] blend-files`), by name: `bpy.data.materials["Rust"]` and the nodes of its tree | `prototypes/blend_typing/`; `docs/reports/remaining-causes.md` S12 | [node_kit/check_node_kit.py](node_kit/check_node_kit.py), [node_kit/shader.py](node_kit/shader.py) |
| `builtin-gizmo-types` | The properties of Blender's own gizmo types: `gizmos.new("GIZMO_GT_arrow_3d")` gives a plain `Gizmo` | `docs/reports/remaining-causes.md` S11 | [viewport_tools/check_viewport_tools.py](viewport_tools/check_viewport_tools.py), [viewport_tools/gizmos.py](viewport_tools/gizmos.py) |
| `default-addon-properties` | The properties of the add-ons Blender enables by default (`scene.cycles`): `check:addons` does not put their source on a search path, so `blender-assumed-default-addon` cannot be shown |  | [node_kit/check_node_kit.py](node_kit/check_node_kit.py) |
| `editor-members-in-modal` | `context.area`, `region` and `space_data` in an operator's `modal`, which Blender calls without polling again | `docs/reports/remaining-causes.md` R21 | [viewport_tools/measure.py](viewport_tools/measure.py) |
| `enum-items-unpacked` | The values of an `EnumProperty` whose `items` unpack another tuple (`(first, *OTHERS)`) |  | [batch_export_and_import/check_batch_export_and_import.py](batch_export_and_import/check_batch_export_and_import.py), [batch_export_and_import/settings.py](batch_export_and_import/settings.py) |
| `handler-callback-types` | The parameters of a function appended to `bpy.app.handlers` (a save handler's file path) |  | [batch_export_and_import/check_batch_export_and_import.py](batch_export_and_import/check_batch_export_and_import.py), [batch_export_and_import/handlers.py](batch_export_and_import/handlers.py) |
| `msgbus-keys` | A `(type, "property")` key of `bpy.msgbus.subscribe_rna`, which the builtin stubs reject |  | [viewport_tools/__init__.py](viewport_tools/__init__.py) |
| `own-node-sockets` | The sockets a node's `init` creates, by name (`node.inputs["A"]`) |  | [node_kit/check_node_kit.py](node_kit/check_node_kit.py) |
| `own-node-tree-types` | A node tree made by the idname of the add-on's own `NodeTree` class (`node_groups.new(name, "KitNodeTree")`) |  | [node_kit/check_node_kit.py](node_kit/check_node_kit.py), [node_kit/tree.py](node_kit/tree.py) |
| `popover-opened-by-appended-function` | What a function appended to one of Blender's headers or menus checked before it opens a popover |  | [viewport_tools/ui.py](viewport_tools/ui.py) |
| `preview-icons` | The previews of a `bpy.utils.previews` collection by name (`icons["ruler"].icon_id`), with the builtin stubs |  | [viewport_tools/check_viewport_tools.py](viewport_tools/check_viewport_tools.py) |
| `registered-property-write-on-partly-unknown` | A write to a Registered property of an object whose type is partly unknown (`Object \| Unknown`) is reported as `invalid-assignment`; the read and a write to a built-in attribute pass. A bug of the checker |  | [legacy_renamer/ops.py](legacy_renamer/ops.py) |
| `startup-modules-in-builtin-stubs` | Blender's startup modules (`bl_operators`, `bl_ui`) in the builtin stubs: `from bl_operators.presets import AddPresetBase` is not found |  | [batch_export_and_import/check_batch_export_and_import.py](batch_export_and_import/check_batch_export_and_import.py), [batch_export_and_import/ui.py](batch_export_and_import/ui.py) |
| `subclass-member-writes` | A write to a member only a subclass has (`socket.default_value = ...`): a read is assumed (`blender-assumed-subclass-member`), a write is an error |  | [node_kit/shader.py](node_kit/shader.py) |

<!-- END coverage -->
