# IDE results, builtin stubs, Blender main

Written by `mise run check:ide main --update`; the task fails when this file would change.
Each section is one marker, `path | ^marker @column | queried line`, and what ty's language server returned.

## features/addon_preferences/prefs_ext/ide_prefs_ext.py | ^completion scale @51 | preferences.addons[__package__].preferences.sc

````text
- scale: detail: float
  documentation: (none)
````

## features/addon_preferences/prefs_ext/ide_prefs_ext.py | ^hover-contains "PREFS_EXT_Preferences" @37 | preferences.addons[__package__].preferences

````text
PASS
````

## features/addon_preferences/prefs_legacy/ide_prefs_legacy.py | ^hover-contains "prefs_legacy" @7 | __package__

````text
PASS
````

## features/api_types/api_setters/ide_api_setters.py | ^hover @8 | ob.location

````text
```python
Vector
```
````

## features/api_types/api_setters/ide_api_setters.py | ^hover-contains "Vector" @8 | ob.location

````text
PASS
````

## features/api_types/api_setters/ide_api_setters.py | ^hover-contains "Matrix" @8 | ob.matrix_world

````text
PASS
````

## features/api_types/api_setters/ide_api_setters.py | ^hover @11 | image.pixels

````text
```python
bpy_prop_array[float]
```
````

## features/api_types/api_setters/ide_api_setters.py | ^hover-contains "bpy_prop_array[float]" @11 | image.pixels

````text
PASS
````

## features/assumptions/asm_added_object/ide_asm_added_object.py | ^hover @16 | if context.object:

````text
```python
Object
```
````

## features/assumptions/asm_context_member/ide_asm_context_member.py | ^hover @17 | bpy.context.scene

````text
```python
Scene
```
````

## features/assumptions/asm_internal_operator/ide_asm_internal_operator.py | ^hover @20 | if context.screen is None:

````text
```python
Screen
```
````

## features/assumptions/asm_list_item/ide_asm_list_item.py | ^hover @13 | item

````text
```python
bpy_struct
```
````

## features/assumptions/asm_list_item/ide_asm_list_item.py | ^hover @13 | item #2

````text
```python
MaterialSlot
```
````

## features/assumptions/asm_subclass_member/ide_asm_subclass_member.py | ^hover @23 | ob.constraints[0].target  # ty: ignore[blender-assumed-subclass-member]

````text
```python
Object | None
```
````

## features/bpy_symbols/sym_bpy_extras/ide_sym_bpy_extras.py | ^hover-contains "-Z" @9 | imp.axis_up

````text
PASS
````

## features/bpy_symbols/sym_bpy_extras/ide_sym_bpy_extras.py | ^completion axis_forward axis_up @14 | imp.axis_

````text
- axis_forward: detail: Literal["X", "Y", "Z", "-X", "-Y", "-Z"]
  documentation: (none)
- axis_up: detail: Literal["X", "Y", "Z", "-X", "-Y", "-Z"]
  documentation: (none)
````

## features/implied_narrowings/nar_bl_context/ide_nar_bl_context.py | ^hover @17 | context.object  # ty: ignore[blender-narrowed-by-bl-context]

````text
```python
Object
```
````

## features/implied_narrowings/nar_bl_context/ide_nar_bl_context.py | ^hover @24 | context.object.pose  # ty: ignore[blender-narrowed-by-bl-context]

````text
```python
Pose
```
````

## features/implied_narrowings/nar_menu_prefix/ide_nar_menu_prefix.py | ^hover-contains "SpaceClipEditor" @17 | context.space_data

````text
PASS
````

## features/implied_narrowings/nar_mode/ide_nar_mode.py | ^hover @31 | context.tool_settings.sculpt

````text
```python
Sculpt
```
````

## features/implied_narrowings/nar_mode/ide_nar_mode.py | ^hover @24 | context.object.pose

````text
```python
Pose
```
````

## features/implied_narrowings/nar_poll/ide_nar_poll.py | ^hover @17 | context.object

````text
```python
Object
```
````

## features/implied_narrowings/nar_poll/ide_nar_poll.py | ^hover-contains "SpaceNodeEditor" @17 | context.space_data

````text
PASS
````

## features/implied_narrowings/nar_poll_reach/ide_nar_poll_reach.py | ^hover @17 | context.object

````text
```python
Object
```
````

## features/implied_narrowings/nar_poll_reach/ide_nar_poll_reach.py | ^hover @17 | context.active_object

````text
```python
Object
```
````

## features/implied_narrowings/nar_popover/ide_nar_popover.py | ^hover-contains "SpaceView3D" @17 | context.space_data

````text
PASS
````

## features/imprecise_annotations/imp_callback_parameter/ide_imp_callback_parameter.py | ^hover-contains "Armature" @9 | data.name

````text
PASS
````

## features/imprecise_annotations/imp_operator_return/ide_imp_operator_return.py | ^hover-contains "set[Literal[" @8 | op.execute(context)

````text
PASS
````

## features/inheritance/inh_mixin_self/ide_inh_mixin_self.py | ^hover @14 | self.layout

````text
```python
UILayout
```
````

## features/inheritance/inh_mixin_self/ide_inh_mixin_self.py | ^hover-contains "str" @14 | self.bl_label

````text
PASS
````

## features/inheritance/inh_mixin_self/ide_inh_mixin_self.py | ^completion layout @17 | self.lay

````text
- layout: detail: UILayout | None
  documentation: (none)
````

## features/inheritance/inh_overrides/ide_inh_overrides.py | ^hover-contains "Context" @11 | ctx

````text
PASS
````

## features/inheritance/inh_overrides/ide_inh_overrides.py | ^completion mouse_x @21 | event.mouse_

````text
- mouse_x: detail: int
  documentation: int([x]) -&gt; integer<HB>
````

## features/inheritance/inh_overrides/ide_inh_overrides.py | ^hover-contains "UILayout" @11 | layout

````text
PASS
````

## features/inheritance/inh_overrides/ide_inh_overrides.py | ^signature @16 | op.execute(context)

````text
label: (ctx: Context) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]
active parameter: 0
parameters:
- ctx: Context: (no documentation)
documentation:
(none)
````

## features/operator_calls/opcall_basic/ide_opcall_basic.py | ^signature @30 | bpy.ops.opcall_basic.all()

````text
label: (execution_context: Literal["INVOKE_DEFAULT", "INVOKE_REGION_WIN", "INVOKE_REGION_CHANNELS", "INVOKE_REGION_PREVIEW", "INVOKE_AREA", ... omitted 7 literals] = ..., undo: int = ..., /, *, int_value: int = ..., float_value: float = ..., bool_value: bool = ..., string_value: str = ..., enum_value: Literal["A", "B"] = ..., flag_value: set[Literal["A", "B"]] = ..., dynamic_value: str = ..., vector_value: Sequence[float] = ..., int_vector_value: Sequence[int] = ..., bool_vector_value: Sequence[bool] = ..., matrix_value: Sequence[Sequence[float]] = ..., group_value: <TypedDict with items 'count', 'name'> = ..., items_value: Sequence[<TypedDict with items 'count', 'name'>] = ..., hidden_value: int = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]
active parameter: 0
parameters:
- execution_context: Literal["INVOKE_DEFAULT", "INVOKE_REGION_WIN", "INVOKE_REGION_CHANNELS", "INVOKE_REGION_PREVIEW", "INVOKE_AREA", ... omitted 7 literals] = ...: (no documentation)
- undo: int = ...: (no documentation)
- int_value: int = ...: (no documentation)
- float_value: float = ...: (no documentation)
- bool_value: bool = ...: (no documentation)
- string_value: str = ...: (no documentation)
- enum_value: Literal["A", "B"] = ...: (no documentation)
- flag_value: set[Literal["A", "B"]] = ...: (no documentation)
- dynamic_value: str = ...: (no documentation)
- vector_value: Sequence[float] = ...: (no documentation)
- int_vector_value: Sequence[int] = ...: (no documentation)
- bool_vector_value: Sequence[bool] = ...: (no documentation)
- matrix_value: Sequence[Sequence[float]] = ...: (no documentation)
- group_value: <TypedDict with items 'count', 'name'> = ...: (no documentation)
- items_value: Sequence[<TypedDict with items 'count', 'name'>] = ...: (no documentation)
- hidden_value: int = ...: (no documentation)
documentation:
(none)
````

## features/operator_calls/opcall_basic/ide_opcall_basic.py | ^completion all @28 | bpy.ops.opcall_basic.al

````text
- all: detail: <Protocol with members '__call__', 'get_rna_type', 'idname', 'idname_py', 'poll'>
  documentation: (none)
````

## features/operator_calls/opcall_basic/ide_opcall_basic.py | ^completion int_value= @35 | bpy.ops.opcall_basic.all(int_v)

````text
- int_value=: detail: int
  documentation: (none)
````

## features/operator_calls/opcall_basic/ide_opcall_basic.py | ^completion before= @35 | bpy.ops.opcall_basic.dropped(e)

````text
- before=: detail: int
  documentation: (none)
````

## features/operator_calls/opcall_basic/ide_opcall_basic.py | ^hover @26 | bpy.ops.opcall_basic.all

````text
Operator `opcall_basic.all` (`OPCALL_BASIC_OT_all`): All<HB>
<HB>
```python
bpy.ops.opcall_basic.all(execution_context, undo, *, int_value: int, float_value: float, bool_value: bool, string_value: str, enum_value: Literal["A", "B"], flag_value: set[Literal["A", "B"]], dynamic_value: str, vector_value: Sequence[float], int_vector_value: Sequence[int], bool_vector_value: Sequence[bool], matrix_value: Sequence[Sequence[float]], group_value: <TypedDict with items 'count', 'name'>, items_value: Sequence[<TypedDict with items 'count', 'name'>], hidden_value: int)
```
````

## features/operator_calls/opcall_basic/ide_opcall_basic.py | ^hover-contains "OPCALL_BASIC_OT_all" @30 | bpy.ops.opcall_basic.all.idname()

````text
PASS
````

## features/operator_calls/opcall_category/ide_opcall_category.py | ^hover @16 | bpy.ops.wm.call_menu("INVOKE_DEFAULT", name="VIEW3D_MT_add")

````text
Operator `wm.call_menu` (`WM_OT_call_menu`)<HB>
<HB>
```python
bpy.ops.wm.call_menu(execution_context, undo, *, name: str)
```
````

## features/operator_calls/opcall_category/ide_opcall_category.py | ^hover-contains "bpy.ops.wm.call_menu(execution_context, undo, *, name: str)" @16 | bpy.ops.wm.call_menu("INVOKE_DEFAULT", name="VIEW3D_MT_add")

````text
PASS
````

## features/operator_calls/opcall_category/ide_opcall_category.py | ^signature @53 | bpy.ops.object.select_all("EXEC_DEFAULT", True, action="SELECT")

````text
label: (execution_context: Literal["INVOKE_DEFAULT", "INVOKE_REGION_WIN", "INVOKE_REGION_CHANNELS", "INVOKE_REGION_PREVIEW", "INVOKE_AREA", ... omitted 7 literals] = ..., undo: int = ..., /, *, action: Literal["TOGGLE", "SELECT", "DESELECT", "INVERT"] = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]
active parameter: 2
parameters:
- execution_context: Literal["INVOKE_DEFAULT", "INVOKE_REGION_WIN", "INVOKE_REGION_CHANNELS", "INVOKE_REGION_PREVIEW", "INVOKE_AREA", ... omitted 7 literals] = ...: (no documentation)
- undo: int = ...: (no documentation)
- action: Literal["TOGGLE", "SELECT", "DESELECT", "INVERT"] = ...: (no documentation)
documentation:
(none)
````

## features/operator_calls/opcall_macro/ide_opcall_macro.py | ^signature @32 | bpy.ops.opcall_macro.combo()

````text
label: (execution_context: Literal["INVOKE_DEFAULT", "INVOKE_REGION_WIN", "INVOKE_REGION_CHANNELS", "INVOKE_REGION_PREVIEW", "INVOKE_AREA", ... omitted 7 literals] = ..., undo: int = ..., /, *, OPCALL_MACRO_OT_step: <TypedDict with items 'amount'> = ..., OPCALL_MACRO_OT_label: <TypedDict with items 'text'> = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]
active parameter: 0
parameters:
- execution_context: Literal["INVOKE_DEFAULT", "INVOKE_REGION_WIN", "INVOKE_REGION_CHANNELS", "INVOKE_REGION_PREVIEW", "INVOKE_AREA", ... omitted 7 literals] = ...: (no documentation)
- undo: int = ...: (no documentation)
- OPCALL_MACRO_OT_step: <TypedDict with items 'amount'> = ...: (no documentation)
- OPCALL_MACRO_OT_label: <TypedDict with items 'text'> = ...: (no documentation)
documentation:
(none)
````

## features/operator_properties/opprops_sinks/ide_opprops_sinks.py | ^completion opprops_sinks.step opprops_sinks.bare @36 | layout.operator("opprops_sinks.")

````text
- opprops_sinks.step: detail: Literal["opprops_sinks.step"]
  documentation: (none)
- opprops_sinks.bare: detail: Literal["opprops_sinks.bare"]
  documentation: (none)
````

## features/operator_properties/opprops_sinks/ide_opprops_sinks.py | ^completion opprops_sinks.step opprops_sinks.bare @38 | keymap.keymap_items.new("opprops_", "A", "PRESS")

````text
- opprops_sinks.step: detail: Literal["opprops_sinks.step"]
  documentation: (none)
- opprops_sinks.bare: detail: Literal["opprops_sinks.bare"]
  documentation: (none)
````

## features/operator_properties/opprops_sinks/ide_opprops_sinks.py | ^completion amount @45 | layout.operator("opprops_sinks.step").am

````text
- amount: detail: int
  documentation: int([x]) -&gt; integer<HB>
````

## features/operator_properties/opprops_sinks/ide_opprops_sinks.py | ^hover-contains "Literal" @43 | layout.operator("opprops_sinks.step").mode

````text
PASS
````

## features/operator_properties/opprops_sinks/ide_opprops_sinks.py | ^hover-contains "Step" @22 | layout.operator("opprops_sinks.step")

````text
PASS
````

## features/pointer_aliases/ptr_area_type/ide_ptr_area_type.py | ^hover @25 | area.spaces.active

````text
```python
SpaceView3D
```
````

## features/pointer_aliases/ptr_brush/ide_ptr_brush.py | ^hover @51 | context.tool_settings.gpencil_paint.brush.gpencil_settings

````text
```python
BrushGpencilSettings
```
````

## features/pointer_aliases/ptr_node_editor/ide_ptr_node_editor.py | ^hover-contains "NodeTree" @28 | context.space_data.edit_tree

````text
PASS
````

## features/pointer_aliases/ptr_node_editor/ide_ptr_node_editor.py | ^hover @44 | context.space_data.edit_tree.nodes.active

````text
```python
Node
```
````

## features/pointer_aliases/ptr_temp_override/ide_ptr_temp_override.py | ^hover @21 | bpy.context.area

````text
```python
Area
```
````

## features/properties/props_callbacks/ide_props_callbacks.py | ^hover @7 | s.count

````text
```python
int
```
````

## features/properties/props_callbacks/ide_props_callbacks.py | ^hover-contains "int" @7 | s.count

````text
PASS
````

## features/properties/props_callbacks/ide_props_callbacks.py | ^hover-contains "Object" @7 | s.target

````text
PASS
````

## features/properties/props_callbacks/ide_props_callbacks.py | ^hover-contains "float" @7 | s.ratio

````text
PASS
````

## features/properties/props_callbacks/ide_props_callbacks.py | ^completion count @10 | s.cou

````text
- count: detail: int
  documentation: int([x]) -&gt; integer<HB>
````

## features/properties/props_callbacks/ide_props_callbacks.py | ^completion lambda_update lambda_poll lambda_items lambda_get @14 | s.lambda_

````text
- lambda_update: detail: int
  documentation: int([x]) -&gt; integer<HB>
- lambda_poll: detail: Object | None
  documentation: (none)
- lambda_items: detail: str
  documentation: str(object='') -&gt; str<HB>
- lambda_get: detail: int
  documentation: int([x]) -&gt; integer<HB>
````

## features/properties/props_registered/ide_props_registered.py | ^hover @11 | scene.reg_int

````text
```python
int
```
````

## features/properties/props_registered/ide_props_registered.py | ^hover-contains "int" @11 | scene.reg_int

````text
PASS
````

## features/properties/props_registered/ide_props_registered.py | ^hover-contains "Literal" @11 | scene.reg_mode

````text
PASS
````

## features/properties/props_registered/ide_props_registered.py | ^hover-contains "int" @9 | obj.reg_id

````text
PASS
````

## features/properties/props_registered/ide_props_registered.py | ^completion reg_int reg_mode reg_group reg_items reg_object reg_id @15 | scene.reg_

````text
- reg_int: detail: int
  documentation: int([x]) -&gt; integer<HB>
- reg_mode: detail: Literal["A", "B"]
  documentation: (none)
- reg_group: detail: PROPS_REGISTERED_Item
  documentation: (none)
- reg_items: detail: bpy_prop_collection_idprop[PROPS_REGISTERED_Item]
  documentation: (none)
- reg_object: detail: Object | None
  documentation: (none)
- reg_id: detail: int
  documentation: int([x]) -&gt; integer<HB>
````

## features/property_wrappers/wrap_values/ide_wrap_values.py | ^hover-contains "int" @7 | s.common_a

````text
PASS
````

## features/property_wrappers/wrap_values/ide_wrap_values.py | ^hover-contains "float" @7 | s.alias

````text
PASS
````

## features/property_wrappers/wrap_values/ide_wrap_values.py | ^hover-contains "Color" @7 | s.partial_color

````text
PASS
````

## features/property_wrappers/wrap_values/ide_wrap_values.py | ^hover-contains "Vector" @7 | s.wrapped_size

````text
PASS
````

## features/property_wrappers/wrap_values/ide_wrap_values.py | ^completion from_dict from_dict_str from_tuple from_tuple_bool @12 | s.from_

````text
- from_dict: detail: float
  documentation: (none)
- from_dict_str: detail: str
  documentation: str(object='') -&gt; str<HB>
- from_tuple: detail: int
  documentation: int([x]) -&gt; integer<HB>
- from_tuple_bool: detail: bool
  documentation: Returns True when the argument is true, False otherwise.<HB>
````

## features/property_wrappers/wrap_values/ide_wrap_values.py | ^completion unknown_options unknown_pointer @15 | s.unknown_

````text
- unknown_options: detail: Any
  documentation: Special type indicating an unconstrained type.<HB>
- unknown_pointer: detail: Any
  documentation: Special type indicating an unconstrained type.<HB>
````

## features/registration/reg_explicit/ide_reg_explicit.py | ^completion reg_explicit @20 | bpy.ops.reg_exp

````text
- reg_explicit: detail: <Protocol with members 'alias', 'dotted', 'imported'>
  documentation: (none)
````

## features/registration/reg_explicit/ide_reg_explicit.py | ^completion dotted imported alias @26 | bpy.ops.reg_explicit.

````text
- dotted: detail: <Protocol with members '__call__', 'get_rna_type', 'idname', 'idname_py', 'poll'>
  documentation: (none)
- imported: detail: <Protocol with members '__call__', 'get_rna_type', 'idname', 'idname_py', 'poll'>
  documentation: (none)
- alias: detail: <Protocol with members '__call__', 'get_rna_type', 'idname', 'idname_py', 'poll'>
  documentation: (none)
````

## features/registration/reg_explicit/ide_reg_explicit.py | ^hover @26 | bpy.ops.reg_explicit.dotted

````text
Operator `reg_explicit.dotted` (`REG_EXPLICIT_OT_dotted`): Run<HB>
<HB>
```python
bpy.ops.reg_explicit.dotted(execution_context, undo, *, count: int)
```
````

## features/registration/reg_explicit/ide_reg_explicit.py | ^hover-contains "count" @26 | bpy.ops.reg_explicit.dotted

````text
PASS
````

## features/type_narrowing/narrow_constructors/ide_narrow_constructors.py | ^hover @6 | con = ob.constraints.new('COPY_LOCATION')

````text
```python
CopyLocationConstraint
```
````
