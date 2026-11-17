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
  collection of an add-on's list has none.
- **Registration on a branch:** a class or property `register()` registers only under a condition (a version check,
  an except handler, a list extended under a condition, a timer) is there only when the condition held.
- **An incomplete walk:** when `register()` registers a class found at runtime (`getattr`, `importlib`, an
  `auto_load` module), the checker counts every class and property of the add-on as registered and turns the
  missing-registration checks off.
- **Preferences:** Blender adds the add-on's entry before `register()`, but `Addon.preferences` stays `None` until
  the preferences class is registered, and is `None` again after `unregister_class`.

## Rules

| Rule | Reports | Typed as |
| --- | --- | --- |
| `blender-assumed-context-member` | a read of `scene` / `view_layer` / `tool_settings` on a `Context` outside a Blender callback (module level, a helper, a method of another class, a nested `def`, a handler or timer), and of `scene` / `tool_settings` in a callback of an Operator a FileHandler names as its `bl_import_operator` | not `None` |
| `blender-assumed-list-item` | each read of an unannotated `item` parameter of `UIList.draw_item` (an override of an unannotated override too) | not `None` |
| `blender-assumed-registration` | a use of a class or Registered property that `register()` registers only on a branch: `bpy.ops.x.y`, a Registered property read, `addons[...].preferences` | registered |
| `blender-assumed-complete-registration` | once per add-on, at the value the `register()` walk could not follow | every class and property counted as registered |
| `blender-assumed-preferences` | `addons[...].preferences` read while `register()` runs before `register_class(<preferences>)`, or while `unregister()` runs after `unregister_class(<preferences>)` | the add-on's preferences class |

A read that is only tested for truth or `None` (`if bpy.context.scene:`, `item is None`) or that sits where the code's
own test already narrows it is not reported. Unannotated helper parameters are `Unknown` and get nothing. Inside a
Blender callback `scene` and its siblings stay a silent guarantee (context_members).

## Configuration

The category's name sets all five rules (`blender-assumptions = "ignore"`), a rule's name one of them;
`[blender] strictness = "lenient"` and `"default"` warn, `"strict"` makes them errors. An ignored rule still narrows.

| Addon | Variant |
| --- | --- |
| `asm_context_member` | `scene` / `view_layer` / `tool_settings` through an annotated parameter, `bpy.context`, an alias, in a plain class's method, an app handler, a timer and a nested `def` in `draw`; a FileHandler's import operator (`scene`, `tool_settings`; `view_layer` silent); not reported: tested reads, a callback, an operator no FileHandler names, an unannotated parameter; guards: `blend_data`, `window` |
| `asm_list_item` | `item` read in `draw_item`, in an override of an unannotated override; not reported: a tested read; guard: an annotation with `None` |
| `asm_registration` | operators registered under a version check, in an except handler, from a list extended under a condition and from a timer; a Registered property and preferences registered under a version check; not reported: what `register()` always registers |
| `asm_complete_registration` | `register_class(getattr(module, name))`: one report at the `getattr` call; no `blender-unregistered-class` for a class never registered |
| `asm_preferences` | a read in `register()` before `register_class`, in a function `register()` calls before it, in `unregister()` after `unregister_class`; not reported: after `register_class`, in a callback; `strictness` presets (`_expected/strictness.toml`) |
| `asm_config` | an `[[overrides]]` entry in `tests/typecheck/ty.toml`: the category at `error`, `blender-assumed-context-member` at `ignore` |

The `blender-*` markers need the checker; the `| None` markers and the upstream ones are guards (`bare-ok`).
