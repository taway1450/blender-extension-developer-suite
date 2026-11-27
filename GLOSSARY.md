# Blender add-on type checking

The language of ty-blender: what the checker knows about Blender add-ons on top of the bpy stubs.

## Add-ons

**Add-on**:
A unit of Python code Blender enables and registers as a whole, either an Extension or a Legacy add-on.
_Avoid_: addon package, plugin

**Extension**:
An Add-on whose folder holds a `blender_manifest.toml`; the manifest wins over any `bl_info`.

**Legacy add-on**:
An Add-on described by a `bl_info` dict, either in a package's `__init__.py` or in a single `.py` file.

**Add-on root**:
The folder that is one Add-on, or for a single-file Add-on the file itself; every module under it belongs to that Add-on and to no other, unless a nested Add-on root claims it.
_Avoid_: project root, addon dir

**Add-on name**:
The name Blender knows the Add-on by: the manifest `id` for an Extension, the folder name for a Legacy add-on package, the file stem for a single-file one. Not the module name the checker resolves it as.

**Discovery override**:
A `[tool.blender]` table in a `pyproject.toml` whose `addons` list names the Add-on roots in its folder tree, replacing the search there; each listed root is an Extension.

**Workspace**:
A folder holding several Add-ons side by side, each with its own Add-on root.

**Entry points**:
The module-level `register` and `unregister` callables of an Add-on's root module, called by Blender with no arguments.

## Symbols

**Blender symbol**:
A function, class or module that resolves to Blender's own `bpy`, `mathutils` or `bpy_extras` modules, however it was imported or aliased.
_Avoid_: bpy name (a local name that only looks like one is not a Blender symbol)

## Properties

**Property declaration**:
A call to a `bpy.props` function (`IntProperty(...)`), the deferred value that describes a property before Blender creates it.
_Avoid_: property definition, deferred property

**Property host**:
A Blender class whose annotations Blender turns into properties: PropertyGroup, Operator, Macro, AddonPreferences, UIList, Node, NodeSocket, NodeTree, NodeTreeInterfaceSocket, KeyConfigPreferences, Gizmo.

**Ignored host**:
A Blender class that accepts annotations without creating properties from them (Panel, Menu, Header, ...).

**Annotated property**:
A Property declaration used as the annotation of a class member on a Property host.

**Registered property**:
A Property declaration assigned to a Blender class at runtime (`bpy.types.Scene.x = IntProperty()`), giving every instance of that class the property.

**External registration**:
A Registered property that another add-on or package assigns, which a file reads when its own add-on gives the name nothing: from an add-on its manifest declares (`[tool.blender] uses = ["cycles"]`), a startup package Blender always loads (`bl_operators`), or an add-on Blender enables by default (`cycles`, reported as an assumption).

**Property evaluator**:
The part of the checker that reads which Property declarations an expression evaluates to, so that a module constant (`x: COMMON`), a dict or tuple item, a `functools.partial` or a small wrapper function (`x: color_property()`) counts as the property it gives. What it cannot read, but ty types as a `_PropertyDeferred` value, is an *opaque* property of any type.
_Avoid_: interpreter

**Value type**:
The type Blender gives an instance attribute for a property (`int` for `IntProperty`, `Literal["A", "B"]` for a static enum).
_Avoid_: property type (ambiguous with the declaration)

**Property member**:
The property behind an attribute of a Blender instance, whatever its origin (an Annotated property, a Registered property, or one that a class decorator adds: `@orientation_helper(...)` gives `axis_forward` and `axis_up`): it decides the attribute's Value type, whether it can be written and whether it is hidden. In the most derived class that mentions the name, the decorator wins over the class body, and a class body that declares the name wins over a registration.

## Classes

**Blender callback**:
A method Blender calls on a registered class (`execute`, `poll`, `draw`, `draw_item`, ...). Blender checks it when the class is registered: whether it is a classmethod or a plain function, and how many positional parameters it has. It passes the arguments by position, so their names don't matter.
_Avoid_: hook, handler (a handler is a function in `bpy.app.handlers`)

**Python base name**:
A name that Blender's own Python class for a `bpy.types` class defines on top of the C type (`Operator.as_keywords`, `Menu.append`, `Node.poll`). A mixin listed after that Blender class loses the name to it.

**Guaranteed context member**:
A member of `bpy.types.Context` that Blender always fills when it calls a given Blender callback (`context.scene` in a `draw`, `context.space_data` in a Panel of a known space type), so it is never None there. Outside that callback the same member may be None.

## Data

**Type tag**:
A property of a Blender instance whose value names the subclass that instance, or one of its pointers, really is: `Modifier.type` (`'SUBSURF'` is a `SubsurfModifier`), `Object.type` (`'MESH'` makes `Object.data` a `Mesh`), `Node.bl_idname`.
_Avoid_: discriminator, kind

**Value form**:
A Type tag that names the subclass of its own instance: `md.type == 'SUBSURF'` makes `md` a `SubsurfModifier`. Each refined subclass declares its tag value in the stubs (`type: Literal['SUBSURF']`).

**Sibling form**:
A Type tag that decides the type of a sibling pointer on the same instance, with no subclass of its own: `ob.type == 'MESH'` makes `ob.data` a `Mesh`, `fluid.fluid_type == 'DOMAIN'` makes `fluid.domain_settings` non-None. The stubs state it with a Tag view.

**Tag view**:
A private class in the stubs, one per value of a sibling-form Type tag, that states what the value implies for the instance's other members: `class _Object_MESH(Object)` with `type: Literal['MESH']` and `data: Mesh`. It exists only in the stubs; Blender has no such class.
_Avoid_: fake subclass

**Refined base**:
A `bpy.types` class whose instances Blender always hands out as one of its subclasses, picked from the instance's own data (`Modifier`, `Light`, `Node`, `Curve`). Most refined bases have a Type tag that names the subclass. `Curve` has none: only the constructor argument names it (`curves.new(type='FONT')` gives a `TextCurve`).

## Diagnostics

**Assumption**:
A Blender fact the typechecker takes as given with no evidence in the code, such as `context.scene` not being None outside a Blender callback, a preset's context members being filled by the panel that runs it, or `bpy.ops.mesh.primitive_cube_add()` having made a new object active. It reports each one under its own rule, so the user can see, raise or silence it.
_Avoid_: heuristic, soft error

**Implied narrowing**:
Narrowing from a Blender fact visible in the code that Python itself does not treat as a check, such as a `poll()` that checks a pointer, a menu's idname prefix naming the space it is drawn in, or a panel's `bl_context` naming the Properties tab or mode it is drawn in. Like an Assumption, it is reported under its own rule.

**Pointer alias**:
A guarantee Blender's C code keeps between two pointers, such that one being set means the other is set too, or the two are the same pointer: `space_data.node_tree` being set means `space_data.edit_tree` is set, and `context.active_node` is `space_data.edit_tree.nodes.active`. The typechecker applies it without reporting, so it is no Rule category.
_Avoid_: pointer invariant, correlated pointer

**Imprecise annotation**:
An annotation that is less precise than the stubs but works and is common in add-ons, such as `-> set[str]` on `execute`. The typechecker accepts it, types the code as the precise form, and reports it under its own rule.
_Avoid_: loose annotation, style issue

**Rule category**:
A group of Blender rules sorted by the evidence behind what the typechecker accepts: Assumption (none in the code), Implied narrowing (a Blender fact in the code) or Imprecise annotation (the code's own annotation is less precise than the stubs). A category's name sets the level of all its rules. Typing debt is no Rule category: it is about the code's own typing, not about Blender facts.
_Avoid_: rule group, rule family

**Strictness**:
The preset that sets the level of every Rule category at once: lenient, default or strict. A level set for a Rule category or a rule wins over it.
_Avoid_: mode, profile

**Internal operator**:
An Operator with `'INTERNAL'` in its `bl_options`: hidden from the operator search, but any script, button or key can still call it.

## Examples

**Example add-on**:
One of the realistic Add-ons in `examples/addons/` that together show what the typechecker types, what it reports and what it cannot do yet. Each one loads in Blender, unlike a feature-test add-on, which may fail on purpose.
_Avoid_: sample, demo add-on

**Demo tag**:
A `# demo: <id>` comment line in an Example add-on that names what the statement below it shows: a feature of the feature tests, a `blender-*` rule, or a `later/` topic that does not work yet. Whether the claim holds is checked against the recorded results.
_Avoid_: demo marker (a marker is an `assert_type` call or a `# ty: ignore[...]` comment)

## Catalog

**Catalog entry**:
One Blender-Python feature or quirk in the catalog for add-on authors (`docs/catalog/`): a checked example in `examples/catalog/<topic>/` with a header that says its status, its Safeguards and, when nothing handles it, what can change. A script outside any add-on unless it needs to be an Add-on.
_Avoid_: feature (a feature is a directory of the feature tests), catalog item

**Safeguard**:
What deals with a Catalog entry so that the add-on author does not have to: the stubs, the runtime probe, the Blender source parser, the add-on typechecker, the runtime add-on typechecker, a fix in Blender, the linter profile, or Blender itself at runtime.
_Avoid_: tool, provider, handler (a handler is a function in `bpy.app.handlers`)

**Gap tag**:
A `# gap: <reason>` comment line in a Catalog entry that says the statement below it fails today. The check fails both when such a statement passes (the gap is closed: remove the tag and review the status) and when a statement without one fails.
_Avoid_: xfail, todo marker

## Add-on code

**Add-on index**:
What an Add-on's code does to Blender as a whole, collected from all its files without type-checking them: today its Registered properties, later its registered classes and operators. It is read from the Add-on of the file that asks, so one Add-on's registrations never reach another.
_Avoid_: registry, add-on cache
