# type_narrowing

**The checker must:** narrow a struct by a test of its Type tag: `md.type == 'SUBSURF'` makes `md` a
`SubsurfModifier` (value form), and `ob.type == 'MESH'` makes `ob.data` a `Mesh` (sibling form).

## What Blender does

- **Refined subclasses:** Blender gives a struct the subclass its tag names (`rna_Modifier_refine`, the
  `rna_*_refine` switches), and the tag is read-only. A modifier of type `'SUBSURF'` is always a `SubsurfModifier`,
  a node whose `bl_idname` is `'ShaderNodeMath'` a `ShaderNodeMath`. Several socket classes share one `type`
  (`'STRING'`: `NodeSocketString`, `NodeSocketStringFilePath`).
- **Sibling pointers:** an object's `type` fixes the type of its `data` (`'MESH'` → `Mesh`, `'FONT'` → `TextCurve`),
  and a fluid modifier's `fluid_type` which of its three settings pointers is set (`'DOMAIN'` → `domain_settings`).

The stubs state both (`api_types`): each refined subclass declares its tag (`type: Literal['SUBSURF']`), and a
private tag view per tag value states what it implies (`class _Object_MESH(Object): type: Literal['MESH'];
data: Mesh`). The checker reads them as one table, (base, attribute, literal) → class, and a test intersects the
tested struct with the class: `ob` becomes `_Object_MESH`, so `ob.data` is a `Mesh` through ordinary member lookup.
`==`, `!=`, `else` / `elif`, `in` and `not in` (a literal tuple, set or list) narrow, in an `if`, a comprehension,
the rest of a function after an early `return`, and a `case` of a `match` on the tag.

Not narrowed: a variable read before the test (`data = ob.data`), which is another binding;
an add-on's own node or socket, whose `bl_idname` no stub class declares; and the tag `'CUSTOM'`, which every
add-on-defined node, socket and tree has. A `bl_idname` test does not narrow its `else` branch: an add-on class
derived from a built-in one (`ShaderNodeCustomGroup`) has its own `bl_idname`.

| Addon | Variant |
| --- | --- |
| `narrow_values` | modifier in a loop over `ob.modifiers`, constraint, strip, light, node `bl_idname`, socket `type` (many-to-one); `elif`, `!=` with an early return, `in {...}`, `not in (...)`, `match`; not narrowed: an add-on's own node |
| `narrow_views` | `ob.data` after `ob.type == 'MESH'`, after a call, after `!= 'FONT'` with an early return, in a comprehension; `match`; Fluid `domain_settings`; not narrowed: `data = ob.data` before the test |

The narrowing markers are in the add-ons' `__init__.py` (the reference stubs cannot express narrowing); the
guards in `check_*.py` hold without the checker (`bare-ok`). Only Blender main's stubs declare the Type tags: 5.2
fails every narrowing marker, and fake-bpy-module leaves out the tag views, so it fails the sibling form. Both are
named exceptions in spec #75.
