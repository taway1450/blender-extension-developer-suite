# operator_calls

**The checker must:** make `bpy.ops.<category>.<name>` callable with one keyword argument per property of the
registered operator, typed as Blender converts it, after the positional execution context and undo flag; and give
it `poll()`, `idname()`, `idname_py()` and `get_rna_type()`.

| Property | Argument type |
| --- | --- |
| Int / Float / Bool / String | `int` / `float` / `bool` / `str` |
| Enum, static items / `ENUM_FLAG` / dynamic items | `Literal[...]` / `set[Literal[...]]` (not a list or tuple) / `str` |
| Float / Int / Bool vector | a sequence of the item type (`Vector` too); a matrix: nested sequences or `Matrix` |
| PointerProperty to a PropertyGroup | a dict of its properties, all optional |
| CollectionProperty | a sequence of dicts with every property of the item, `name` included |
| PointerProperty to an ID type | not allowed: Blender drops it **and every property after it** |

| Addon | Variant |
| --- | --- |
| `opcall_basic` | every property kind, every execution context, wrong arguments, the dropped properties, the operator functions |
| `opcall_category` | an operator in Blender's `object` category next to the built-in ones; two operators in one new category |
| `opcall_inherit` | properties from base operators and mixins, a redeclared property |
| `opcall_idname_forms` | `bl_idname` from a constant, a concatenation, an f-string, another class, a mixin; a runtime value gives nothing |
| `opcall_macro` | a Macro: one dict argument per step, named by the step's `_OT_` idname |

**Runtime facts (Blender 5.4):** more than two positional arguments raise `ValueError`, an unknown keyword or
execution context `TypeError`; `idname()` is the `CATEGORY_OT_name` form.

**Rules:** `blender-invalid-operator-property` (an ID pointer on an operator); wrong calls are ty's own
`invalid-argument-type`, `unknown-argument`, `too-many-positional-arguments`, `positional-only-parameter-as-kwarg`.
