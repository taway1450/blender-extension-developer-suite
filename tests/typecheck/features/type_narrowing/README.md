# type_narrowing

**The checker must:** narrow a struct by a test of its Type tag: `md.type == 'SUBSURF'` makes `md` a
`SubsurfModifier` (value form), and `ob.type == 'MESH'` makes `ob.data` a `Mesh` (sibling form).

## What Blender does

- **Refined subclasses:** Blender gives a struct the subclass its tag names (`rna_Modifier_refine`, the
  `rna_*_refine` switches), and the tag is read-only. A modifier of type `'SUBSURF'` is always a `SubsurfModifier`,
  a node whose `bl_idname` is `'ShaderNodeMath'` a `ShaderNodeMath`. Several socket classes share one `type`
  (`'STRING'`: `NodeSocketString`, `NodeSocketStringFilePath`), and several node classes one legacy `type`
  (`'MATH'`: `ShaderNodeMath`, `TextureNodeMath`). Interface items (`item_type`), boid rules, line style
  modifiers, viewer path elements and project variables are refined by their tags too; every interface socket class
  shares `'SOCKET'`, and a line style modifier base (`LineStyleColorModifier`) has the `type` each subclass defines.
- **Sibling pointers:** an object's `type` fixes the type of its `data` (`'MESH'` → `Mesh`, `'FONT'` → `TextCurve`)
  and of its `pose` (`'ARMATURE'` → `Pose | None`, None until the depsgraph builds it; any other type → `None`),
  and a fluid modifier's `fluid_type` which of its three settings pointers is set (`'DOMAIN'` → `domain_settings`).
- **An area's type:** an area's first space is the space of its type (`ED_area_newspace` puts the new space first,
  and `Area.type` is that space's `spacetype`), so `area.type == 'VIEW_3D'` makes `area.spaces.active` a
  `SpaceView3D`.
- **Writable tags:** most tags are read-only, but `Light.type`, `Texture.type` and `Area.type` (also through
  `Area.ui_type`) can be written, and Blender refines the struct anew.

The stubs state both (`api_types`): each refined subclass declares its tag (`type: Literal['SUBSURF']`), and a
private tag view per tag value states what it implies (`class _Object_MESH(Object): type: Literal['MESH'];
data: Mesh`). The checker reads them as one table, (base, attribute, literal) → class, and a test intersects the
tested struct with the class: `ob` becomes `_Object_MESH`, so `ob.data` is a `Mesh` through ordinary member lookup.
`==`, `!=`, `else` / `elif`, `in` and `not in` (a literal tuple, set or list) narrow, in an `if`, a comprehension,
the rest of a function after an early `return`, and a `case` of a `match` on the tag.

A constructor narrows the same way, silently: `ob.constraints.new('COPY_LOCATION')` is a `CopyLocationConstraint`,
`bpy.data.lights.new(name, 'SPOT')` a `SpotLight`, `mesh.attributes.new(name, 'FLOAT', 'POINT')` a `FloatAttribute`.
Blender refines the new struct like any other (`rna_*_refine`), and in Blender's own stubs the parameter and the tag
share an `rna_enum_*` alias. `nodes.new(type=...)` and `gizmos.new(...)` take a `bl_idname` typed `str`, which the
checker pairs with the tag: a built-in value names its stub class, an add-on's value or `X.bl_idname` the add-on's
class (Blender creates an instance of the registered class).

An area's type names the class of a pointer below it: the checker narrows `area` to `Area & P`, where a synthesised
protocol `P` gives `spaces.active` the `Space` subclass whose Type tag is the value (`SpaceView3D.type:
Literal['VIEW_3D']`), so `area.spaces.active` is a `SpaceView3D` through ordinary member lookup.

Every Type tag narrowing is ty's ordinary narrowing of the tested variable, so rebinding it (`area = other`) drops it.
A scope that writes the tag of the same variable anywhere (`area.type = ...`, `area.ui_type = ...`) gets no narrowing
from a test of it, since the write may come between the test and a read.

Not narrowed: a variable read before the test (`data = ob.data`), which is another binding;
an add-on's own node or socket, whose `bl_idname` no stub class declares; and the tag `'CUSTOM'`, which every
add-on-defined node, socket and tree has. A `bl_idname` test does not narrow its `else` branch: an add-on class
derived from a built-in one (`ShaderNodeCustomGroup`) has its own `bl_idname`.

| Addon | Variant |
| --- | --- |
| `narrow_values` | modifier in a loop over `ob.modifiers`, constraint, strip, light, node `bl_idname`, node `type` and socket `type` (many-to-one), interface `item_type` (a shared value on an intermediate class), boid rule, line style modifier (the tag on its base), viewer path element, project variable, an object's `pose`; `elif`, `!=` with an early return, `in {...}`, `not in (...)`, `match`; not narrowed: an add-on's own node |
| `narrow_constructors` | `constraints.new` (positional, `type=`), `lights.new` (a literal, a conditional of two), `attributes.new`, `nodes.new` (`type=`, positional), `gizmos.new(MyGizmo.bl_idname)` in a GizmoGroup's `setup`; not narrowed: a `str` argument, an unknown `bl_idname`, a C gizmo type |
| `narrow_area_type` | `area.spaces.active` after `==` in a loop, `in {...}` in an `elif`, `!=` with `continue`, `and` in a generator, a list comprehension; not narrowed: the `else` branch, `area` rebound after the test, a function that writes `area.type` or `area.ui_type` |
| `narrow_views` | `ob.data` after `ob.type == 'MESH'`, after a call, after `!= 'FONT'` with an early return, in a comprehension; `match`; Fluid `domain_settings`; not narrowed: `data = ob.data` before the test |

The narrowing markers are in the add-ons' `__init__.py` (the reference stubs cannot express narrowing); the
guards in `check_*.py` hold without the checker (`bare-ok`). `narrow_area_type` has no `check_*.py`: its markers are all in `__init__.py`. Only Blender main's stubs declare the
Type tags: 5.2 fails every narrowing marker, a named exception in spec #75. fake-bpy-module also spells the constructor parameters as literals (with `| None`), not
as the tag's alias, so `constraints.new`, `lights.new` and `attributes.new` are not narrowed there: a named exception
in spec #123.
