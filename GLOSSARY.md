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
A Blender class whose annotations Blender turns into properties: PropertyGroup, Operator, Macro, AddonPreferences, UIList, Node, NodeSocket, NodeTree, Gizmo.

**Ignored host**:
A Blender class that accepts annotations without creating properties from them (Panel, Menu, Header, ...).

**Annotated property**:
A Property declaration used as the annotation of a class member on a Property host.

**Registered property**:
A Property declaration assigned to a Blender class at runtime (`bpy.types.Scene.x = IntProperty()`), giving every instance of that class the property.

**Property evaluator**:
The part of the checker that reads which Property declarations an expression evaluates to, so that a module constant (`x: COMMON`), a dict or tuple item, a `functools.partial` or a small wrapper function (`x: color_property()`) counts as the property it gives. What it cannot read, but ty types as a deferred property, is an *opaque* property of any type.
_Avoid_: interpreter

**Value type**:
The type Blender gives an instance attribute for a property (`int` for `IntProperty`, `Literal["A", "B"]` for a static enum).
_Avoid_: property type (ambiguous with the declaration)

**Property member**:
The property behind an attribute of a Blender instance, whatever its origin (an Annotated property or a Registered property): it decides the attribute's Value type, whether it can be written and whether it is hidden. In the most derived class that mentions the name, a class body that declares the name wins over a registration.

## Add-on code

**Add-on index**:
What an Add-on's code does to Blender as a whole, collected from all its files without type-checking them: today its Registered properties, later its registered classes and operators. It is read from the Add-on of the file that asks, so one Add-on's registrations never reach another.
_Avoid_: registry, add-on cache
