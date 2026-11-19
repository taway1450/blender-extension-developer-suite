# assumptions

**The checker must:** accept code that relies on a fact Blender keeps in ordinary use but does not guarantee, type it
as if the fact held, and report it under a `blender-assumed-*` rule (category `blender-assumptions`, `warn` by default).

## What Blender does

- **Context members outside callbacks:** `bpy.context.scene` is the window's scene in a timer
  (`wm_event_timers_execute` sets the first window), the loaded file's scene in an app handler, a `--python` script,
  background mode or a test, and the full context in a preset. `view_layer` falls back to the scene's default layer
  and `tool_settings` belongs to the scene. They are `None` only under `context.temp_override(scene=None)`, and in the
  import operator of a FileHandler run by the collection importer (`collection_importer_import_exec` passes a context
  with no scene; `view_layer` then crashes rather than giving `None`). While an add-on is imported or registered,
  `bpy.context` has no `scene` at all (`_RestrictContext` raises), which no type expresses.
- **List items:** `UIList.draw_item` gets `item` `None` only for an empty slot of an array of ID pointers; the
  collection of an add-on's list has none. The items are those of the collection `dataptr.propname` that
  `layout.template_list("<list>", list_id, dataptr, propname, ...)` shows the list with (`uiTemplateList`).
- **Registration on a branch:** a class or property `register()` registers only under a condition (a version check,
  an except handler, a list extended under a condition, a timer) is there only when the condition held.
- **An incomplete walk:** when `register()` registers a class found at runtime (`getattr`, `importlib`, an
  `auto_load` module), the checker counts every class and property of the add-on as registered and turns the
  missing-registration checks off.
- **Preferences:** Blender adds the add-on's entry before `register()`, but `Addon.preferences` stays `None` until
  the preferences class is registered, and is `None` again after `unregister_class`.
- **Collection:** `context.collection` is the active layer collection's, else the scene's master collection
  (`CTX_data_collection`), so it is `None` exactly when `scene` is.
- **Internal operators:** `'INTERNAL'` in `bl_options` only hides an operator from the operator search
  (`OPTYPE_INTERNAL`). In ordinary use only its own add-on's button, menu entry or key calls it, from the editor and
  data it needs, but any script or user key map can call it anywhere.
- **Editor members in UI callbacks:** Blender polls a Panel or a Menu while drawing a region of an editor
  (`ED_region_panels`, `UI_menutype_draw`), calls a tool's `draw_settings` while drawing the tool header or the tool
  settings, and calls `RenderEngine.view_update` / `view_draw` for the 3D viewport that shows the render: `area`,
  `region` and `space_data` are set there. A script or `wm.call_menu` can poll a menu or panel with no editor.
- **Presets:** a preset (a `.py` file in a `presets` folder) runs with the context of the panel or menu that applies
  it (`script.execute_preset`): a camera preset finds `bpy.context.camera` from the camera tab. Nothing in the file
  names that panel.
- **Added objects:** `bpy.ops.mesh.primitive_cube_add()` and the other `*_add` operators add an object, select it and
  make it active (`ED_object_add_type`), so `context.object` and `active_object` are the new object after the call,
  when it succeeded. A failed poll gives `{'CANCELLED'}` or an exception, which the code does not show.
- **Subclass members:** a struct read by index or by name (`ob.constraints[0]`, `ob.modifiers["Subdivision"]`,
  `bpy.data.lights["Key"]`, `node.inputs["Color"]`) is always one of the subclasses its Type tag names
  (`rna_Constraint_refine`, ...), but nothing in the code says which: reading `target` takes it for one of the
  constraints that have a target.

## Rules

| Rule | Reports | Typed as |
| --- | --- | --- |
| `blender-assumed-context-member` | a read of `scene` / `view_layer` / `tool_settings` / `collection` on a `Context` outside a Blender callback (module level, a helper, a method of another class, a nested `def`, a handler or timer), and of `scene` / `tool_settings` / `collection` in a callback of an Operator a FileHandler names as its `bl_import_operator` | not `None` |
| `blender-assumed-list-item` | each read of an unannotated `item` parameter of `UIList.draw_item` (an override of an unannotated override too) | not `None`; where the add-on's `template_list` calls name the list (in any of its modules, or its folder for a file in no add-on), the element type of the collections they show, a union for several (a call whose `dataptr` is untyped says nothing); the parent's type when a typed call gives none or no typed call names the list |
| `blender-assumed-registration` | a use of a class or Registered property that `register()` registers only on a branch: `bpy.ops.x.y`, a Registered property read, `addons[...].preferences` | registered |
| `blender-assumed-complete-registration` | once per add-on, at the value the `register()` walk could not follow | every class and property counted as registered |
| `blender-assumed-preferences` | `addons[...].preferences` read while `register()` runs before `register_class(<preferences>)`, or while `unregister()` runs after `unregister_class(<preferences>)` | the add-on's preferences class |
| `blender-assumed-internal-operator` | a read of a context member in a callback (not `poll`) of an Operator with `'INTERNAL'` in its `bl_options`, its own or a base class's, that no poll checked | not `None` |
| `blender-assumed-editor-member` | a read of `area` / `region` / `space_data` in the `poll` of a Panel or Menu that names no editor, a tool's `draw_settings` and `RenderEngine.view_update` / `view_draw` | not `None` |
| `blender-assumed-preset-context` | a module-level read of a context member in a file under a `presets` folder (`scene` and its siblings stay `blender-assumed-context-member`), and a pointer the applying panel requires (`material.grease_pencil` in a Grease Pencil material preset) | not `None`; the panel's struct where it shows for one (`TextStrip`, a fluid domain) |
| `blender-assumed-added-object` | a read of `context.object` / `active_object` after a `bpy.ops.<category>.<name>_add()` (or `.add()`) call earlier in the same function or module-level script | not `None` |
| `blender-assumed-default-addon` | a read of a property that only an add-on Blender enables by default registers (`scene.cycles`), when neither the add-on's own code, an add-on its manifest declares (`[tool.blender] uses`) nor a startup package (`bl_operators`, `bl_ui`) gives it; the default add-on's source must be on a search path. No add-on here tests it: a test add-on named like a bundled one would replace it in Blender (`check:load`); the rule's documentation example and `check:blender` (Cycles' presets and tests) do | the default add-on's registration |
| `blender-assumed-subclass-member` | a read of a member that a refined base with a Type tag (`Constraint`, `Modifier`, `Light`, `Node`, `NodeSocket`, ...) lacks but some of its tagged subclasses declare; never on `bpy_struct` or `ID`, and a member no subclass declares stays an error | the union of the subclasses' declarations |

A read that is only tested for truth or `None` (`if bpy.context.scene:`, `item is None`) or that sits where the code's
own test already narrows it is not reported. Unannotated helper parameters are `Unknown` and get nothing. Inside a
Blender callback `scene` and its siblings stay a silent guarantee (context_members).

## Configuration

The category's name sets all eleven rules (`blender-assumptions = "ignore"`), a rule's name one of them;
`[blender] strictness = "lenient"` and `"default"` warn, `"strict"` makes them errors. An ignored rule still narrows.

| Addon | Variant |
| --- | --- |
| `asm_context_member` | `scene` / `view_layer` / `tool_settings` / `collection` through an annotated parameter, `bpy.context`, an alias, in a plain class's method, an app handler, a timer and a nested `def` in `draw`; a FileHandler's import operator (`scene`, `tool_settings`, `collection`; `view_layer` silent); `collection` silent in a callback; not reported: tested reads, a callback, an operator no FileHandler names, an unannotated parameter; guards: `blend_data`, `window` |
| `asm_list_item` | `item` read in `draw_item`, and `data` in `draw_item` and `filter_items` typed by the calls' `dataptr`; in an override of an unannotated override; typed by `template_list` calls in another module: a Registered collection property, `material_slots`, two sources of different types (a union), a misspelt member of the source (an error); a second call with an unannotated `dataptr` left out; `bpy_struct` with only such a call or none; not reported: a tested read; guard: an annotation with `None` |
| `asm_registration` | operators registered under a version check, in an except handler, from a list extended under a condition and from a timer; a Registered property and preferences registered under a version check; not reported: what `register()` always registers |
| `asm_complete_registration` | `register_class(getattr(module, name))`: one report at the `getattr` call; no `blender-unregistered-class` for a class never registered |
| `asm_preferences` | a read in `register()` before `register_class`, in a function `register()` calls before it, in `unregister()` after `unregister_class`; not reported: after `register_class`, in a callback; `strictness` presets (`_expected/strictness.toml`) |
| `asm_internal_operator` | `object`, `space_data`, `screen` in `execute` / `invoke` of an INTERNAL operator, the flag from a base class; not reported: a tested read, a read the poll checked (`blender-narrowed-by-poll`); guards: the poll, a helper, an operator without the flag; `strictness` presets |
| `asm_editor_member` | `region` in the poll of a Panel whose `bl_space_type` comes from a mixin after `Panel`, `space_data` / `area` in a Menu's poll, `region` in `view_update` / `view_draw` and a WorkSpaceTool's `draw_settings`; not reported: a tested read; guards: `RenderEngine.render`, an operator; `strictness` presets |
| `asm_preset_context` | `camera` and `object` read at module level in `presets/asm_preset_context/small_sensor.py`, `scene` there under `blender-assumed-context-member`; `active_strip` as a `TextStrip` in `presets/sequencer/text_style/`; `material.grease_pencil` set in `presets/gpencil_material/`, `fluid` as a domain in `presets/fluid/`; not reported: a tested read; guards: a function of the preset, a file outside `presets`; `strictness` presets |
| `asm_added_object` | `object` / `active_object` after `primitive_cube_add()`, `object.add()` and `light_add()` in a helper and an operator, as the Type tag view of the object added (`text_add()`, `object.add(type='LATTICE')`, `camera_add()`; `effector_add()` stays `Object`); not reported: a tested read; guards: a read before the call, another function, after a non-`_add` operator; `strictness` presets |
| `asm_subclass_member` | `target` of `ob.constraints[0]`, `levels` of `ob.modifiers["Subdivision"]`, `spot_size` of `bpy.data.lights["Key"]`, `default_value` of `node.inputs["Color"]`; not reported: after a Type tag test; errors: a misspelt member, a member of `ID`'s subclasses on an `ID`, of `TextCurve` on a `Curve` (no Type tag); `strictness` presets |
| `asm_config` | an `[[overrides]]` entry in `tests/typecheck/ty.toml`: the category at `error`, `blender-assumed-context-member` at `ignore`, the five rules of spec #123 at `warn` |

The `blender-*` markers need the checker; the `| None` markers and the upstream ones are guards (`bare-ok`).
