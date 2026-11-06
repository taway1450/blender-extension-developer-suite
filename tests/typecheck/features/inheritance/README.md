# inheritance

**The checker must:** type the parameters of an unannotated override of a Blender callback (`execute`, `poll`,
`draw`, `draw_item`, ...) from the Blender class it overrides, and check its return value against the parent's
return type, so add-ons can keep writing `def execute(self, context):`. It also reports the overrides, bases and
mixin orders Blender rejects or silently resolves differently.

## What Blender does

Checked in Blender 4.2 and 5.4. Registration was probed with `--background --factory-startup`, each case on its
own; the callbacks were then run with the UI open (`--enable-event-simulate`, a timer script that calls the
operators, simulates events for `modal`, shows the panels, menus and UI lists in the Properties editor and the
nodes in a Node Editor) and every call was logged. The RNA callback signatures come from `bl_rna.functions`
(`is_registered`, `is_registered_optional`); the registration code is `pyrna_register_class` in
`source/blender/python/intern/bpy_rna.cc`.

- **Chains of unregistered bases work.** A registered class may derive from any number of unregistered classes and
  has their properties and callbacks (grandchild operators, panels, menus and UI lists ran and drew); several
  registered classes may share a base. Built-in classes such as `VIEW3D_MT_object` can be subclassed and
  registered, and `super().draw(context)` works.
- **A registered class must not derive from another registered class.** Registering the subclass after its base
  detaches the base's Python class ("Old srna still references us" in `bpy_rna.cc`), so Blender no longer calls the
  base's callbacks: the operator returns `{"FINISHED"}` without running `execute`, the panel and menu draw nothing,
  the UI list draws no items, the node cannot be added. Blender only logs `WARNING unable to get Python class for
  RNA struct '...'` ("Rare case. can happen when registering subclasses."), and unregistering the subclass does not
  repair the base. Registered the other way round both work, but with `--debug-python` Blender warns about either
  order ("references and already registered base-class"), with the note that mixin classes are preferred. Property
  groups have no callbacks: a registered `PropertyGroup` chain A → B → C (A and C registered) keeps working, C has
  `a`, `b` and `c`.
- A subclass that inherits the parent's `bl_idname` replaces the parent ("has been registered before, unregistering
  previous"); the parent's `is_registered` becomes `False` and unregistering it fails. Calling the operator runs the
  subclass's `execute` in 4.2 and nothing at all in 5.4.
- Only the registrable RNA types (`Operator`, `Panel`, `Menu`, `Header`, `UIList`, `PropertyGroup`,
  `AddonPreferences`, `Macro`, `Gizmo`, `GizmoGroup`, `Node` and its subtypes, `NodeSocket`, `NodeTree`,
  `KeyingSetInfo`, `RenderEngine`, `FileHandler`, `AssetShelf`, ...) can be registered. A subclass of `Object`,
  `Mesh`, `Modifier` or `UILayout` can be defined, but `register_class` raises `ValueError: ... does not support
  registration`.
- Two Blender bases (`class X(Operator, Panel)`) register as the first one.
- **Mixins.** Blender looks up callbacks, `bl_*` attributes and property annotations along the whole MRO, so for
  them the order of the bases does not matter, including annotations of a mixin's own base. The order matters only
  for names that Blender's Python base classes define themselves (`Operator.as_keywords`, `Node.poll`,
  `Menu.append`/`prepend`/`draw_preset`, `_GenericUI.is_extended`, ...): a mixin listed after the Blender base loses
  to them, without any message. A mixin derived from `ABC` raises a metaclass conflict; one with non-empty
  `__slots__` raises "multiple bases have instance lay-out conflict".
- **Callback signatures.** At registration Blender checks each callback it finds (everything accepted here was
  also called at runtime and got its arguments):
  - the number of positional parameters, defaults included, must equal the RNA count: `execute(self)`,
    `execute(self, context, extra=None)` and `execute(self, *args)` fail ("expected ... to have 2 args, found 1").
    Names do not matter (Blender passes arguments by position), and keyword-only parameters (they keep their
    defaults), `*args` after the required ones (always empty) and `**kwargs` (always empty) are accepted;
  - `UIList.draw_item` is the exception: it accepts 7 to 10 parameters including `self`, and Blender passes only as
    many arguments as there are parameters (7 parameters end at `active_data`);
  - `poll`, `description` (Operator), `draw_color_simple` (NodeSocket), `NodeTree.poll`/`get_from_context`/
    `valid_socket_type`, `GizmoGroup.poll`/`setup_keymap` must be classmethods ("expected ... to be a static/class
    method"); the others must be plain functions: a classmethod `execute` fails ("to be a function, not a method"),
    a staticmethod `execute(self, context)` is accepted and still gets the operator as its first argument;
  - `Panel`, `Menu`, `Header` and `NodeSocket` need `draw` ("expected ... to have an "draw" attribute"); an
    operator without `execute` or a UI list without `draw_item` is fine.
- **Return values** are checked when Blender calls the callback: `execute`, `invoke` and `modal` must return a set
  of the operator return items; `None`, `{"DONE"}`, a string, a list or a tuple raise "incompatible return value"
  (`set()` is accepted). `poll` results are converted with `bool()`, so any value works.
- `Node.init` gets `None` as its context when the node is created with `nodes.new(...)`; the stubs say `Context`.
- Not observed at runtime: custom `Header` classes never drew in the probe (neither in the 3D Viewport nor in the
  Properties editor), and `Operator.check`, `cancel` and `description` were not triggered. Their rules above come
  from registration only.

The [Blender Python API docs](https://docs.blender.org/api/current/bpy.types.Operator.html) describe the callbacks
but none of these rules; mixins appear only in examples (`bpy.types.Panel`, `bpy_extras.asset_utils`).

## Variants

| Addon | Variant |
| --- | --- |
| `inh_chains` | registered leaves below two unregistered bases, siblings sharing a base, a panel and its subpanel sharing a base, a registered `PropertyGroup` chain. Its probes confirm that every class works |
| `inh_registered_base` | `blender-registered-base`: an operator, panel, menu, UI list and node registered together with a subclass, in both orders; a `PropertyGroup` chain (no error). Its probes confirm which classes break |
| `inh_inherited_idname` | `blender-duplicate-registration` and `blender-registered-base`: a child without its own `bl_idname` replaces the parent (unregister fails) |
| `inh_mixins` | mixins before and after the base, a mixin of a mixin, untyped plain mixins, a Blender-based intermediate base; `blender-mixin-order` for `Operator.as_keywords`, `Menu.append` and `Node.poll`. Its probes confirm which method wins |
| `inh_bases` | `blender-invalid-base` for two Blender bases; in `check_inh_bases.py` unregistrable bases (the stubs already reject them: `invalid-argument-type`), an `ABC` mixin (`conflicting-metaclass`) and a `__slots__` mixin (`instance-layout-conflict`) |
| `inh_overrides` | every Operator callback, Panel, Menu, Header, UIList, NodeTree, NodeSocket and Node callbacks without annotations; renamed, partly annotated, `*args`, keyword-only and `**kwargs` variants; `draw_item` with 7 and 10 parameters |
| `inh_override_types` | incompatible annotations (`invalid-method-override`), compatible ones (no error), unannotated returns Blender cannot convert (`invalid-return-type`), `poll` returning any value |
| `generated/inh_invalid_*` | `blender-invalid-override` and `blender-missing-callback`: one add-on per class Blender rejects (18 cases: wrong parameter counts, `poll`/`description` not a classmethod, a classmethod `execute`, `draw_item` with 6 or 11 parameters, `draw`/`draw_header` with an extra parameter, `Panel`/`Menu`/`Header`/`NodeSocket` without `draw`), from `scripts/feature_generators/inheritance.py`. Each fails at register with the error its `runtime.toml` names |

## Rules

- Unannotated parameters of an override take the parent's parameter types by position, also when renamed; an
  explicit annotation wins. Extra parameters Blender accepts keep their own types (`*args: tuple[Any, ...]`, a
  keyword-only default's type).
- An unannotated return is inferred as usual and must be assignable to the parent's return type
  (`invalid-return-type` otherwise); callers see the parent's return type. Callbacks Blender converts with `bool()`
  (`poll`, `check`, `poll_instance`, ...) accept any value.
- A plain mixin has no Blender parent, so its parameters stay `Unknown`; a mixin that derives from the Blender class
  gets the parent's types.
- Where Blender rejects an override, `blender-invalid-override` replaces ty's own `invalid-method-override`
  (fewer or more positional parameters, a missing classmethod or a wrong one). The renamed parameters and the short
  `draw_item` that ty reports as `invalid-method-override` are no error.
- `blender-missing-callback` on the class line of a registered `Panel`, `Menu`, `Header` or `NodeSocket` without
  `draw`.
- `blender-mixin-order` on the class line when a base listed after the Blender base defines a name that the Blender
  Python base class defines too.
- `blender-invalid-base` for a class with two Blender bases.
- `blender-registered-base` on the class line of a registered class (other than a `PropertyGroup`) that has a base
  the add-on registers too, whatever the order of registration: share code through an unregistered base or a mixin
  instead.

check:load confirms the runtime side: every rejected class fails at register with its own error, and the probes in
`_expected/runtime.toml` confirm after register that the classes `blender-registered-base` reports have lost their
Python class (`bpy.types.<name>` no longer gives the add-on's class, the node cannot be added) and that the classes
`inh_chains` registers have not. The callbacks of a broken class are not called in `--background`, so the probes
check the cause, which the UI probes showed to stop every callback.

The oracle cannot check the bodies of the overrides (stock ty types the parameters as `Unknown`), so the
`assert_type` calls there are only judged by check:features; `check_inh_overrides.py` checks the call sites
against reference stubs with explicit signatures. The `ABC` and `__slots__` cases are `oracle-skip`: no stubs
declare the C layout, and only the builtin stubs of `main` declare Blender's metaclass (`_RNAMeta`).
