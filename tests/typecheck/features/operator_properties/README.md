# operator_properties

**The checker must:** map an operator idname given as a string to that operator's properties, in every Blender
function that takes one, accepting both forms (`category.name` and `CATEGORY_OT_name`):

| Sink | Known idname | Stub type kept for |
| --- | --- | --- |
| `UILayout.operator`, `operator_menu_hold`, `operator_menu_enum` | the properties, not `None` | an idname that is not a known literal |
| `UILayout.operator_enum`, `operator_menu_enum` | the property argument must be an enum property | |
| `KeyMapItems.new(...).properties` | the properties (never `None` at runtime) | |
| `WindowManager.operator_properties_last` | the properties (`None` only for unknown operators) | |
| `Gizmo.target_set_operator`, `WorkSpaceTool.operator_properties` | the properties | |
| `Macro.define(...).properties` | the properties | |
| `Operator.properties` (`self.properties`) | the operator's own properties | |
| `WorkSpaceTool.bl_keymap` tuples | property names and values are checked | |

The idname is evaluated (constants, `Cls.bl_idname`, f-strings of constants). Blender's own operators have their
properties too (`layout.operator("object.select_all").action`). The properties object has the operator's
properties only: unknown attributes are errors even though fake-bpy-module's `OperatorProperties` accepts any.

| Addon | Variant |
| --- | --- |
| `opprops_sinks` | every sink, both idname forms, an operator without properties, `bl_keymap` |
| `opprops_idnames` | idname forms, built-in operators, a dynamic idname, unknown idnames (also another add-on's) |

**Rules:** `blender-unknown-operator`, `blender-invalid-operator-property`.
