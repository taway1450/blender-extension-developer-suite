"""Feature test: property arguments Blender rejects when the class is registered (ValueError): defaults that do not
fit the property, a set callback without get, and callbacks with the wrong number of parameters (each checked on its
own in Blender 5.4). Also arguments it accepts."""

import bpy
from bpy.props import EnumProperty, FloatVectorProperty, IntProperty, IntVectorProperty, PointerProperty
from bpy.types import Object, PropertyGroup


class PROPS_DEFAULTS_Valid(PropertyGroup):
    ints_for_floats: FloatVectorProperty(size=3, default=(1, 2, 3))
    enum_by_identifier: EnumProperty(items=[("A", "A", ""), ("B", "B", "")], default="B")
    enum_by_number: EnumProperty(items=[("A", "A", "", 1), ("B", "B", "", 7)], default=7)
    flag_set: EnumProperty(items=[("A", "A", ""), ("B", "B", "")], default={"A", "B"}, options={"ENUM_FLAG"})
    matrix: FloatVectorProperty(size=(2, 2), default=((1.0, 0.0), (0.0, 1.0)))


class PROPS_DEFAULTS_Invalid(PropertyGroup):
    enum_unknown: EnumProperty(items=[("A", "A", ""), ("B", "B", "")], default="C")  # ty: ignore[blender-invalid-property]
    enum_number_unknown: EnumProperty(items=[("A", "A", "", 1)], default=2)  # ty: ignore[blender-invalid-property]
    flag_not_a_set: EnumProperty(items=[("A", "A", ""), ("B", "B", "")], default="A", options={"ENUM_FLAG"})  # ty: ignore[blender-invalid-property]
    flag_unknown: EnumProperty(items=[("A", "A", ""), ("B", "B", "")], default={"C"}, options={"ENUM_FLAG"})  # ty: ignore[blender-invalid-property]
    plain_set: EnumProperty(items=[("A", "A", ""), ("B", "B", "")], default={"A"})  # ty: ignore[blender-invalid-property]
    vector_length: FloatVectorProperty(size=3, default=(1.0, 2.0))  # ty: ignore[blender-invalid-property]
    int_vector_length: IntVectorProperty(size=2, default=(1, 2, 3))  # ty: ignore[blender-invalid-property]
    matrix_shape: FloatVectorProperty(size=(2, 2), default=(1.0, 0.0, 0.0, 1.0))  # ty: ignore[blender-invalid-property]
    int_float: IntProperty(default=1.5)  # ty: ignore[invalid-argument-type]
    set_without_get: IntProperty(set=lambda self, value: None)  # ty: ignore[blender-invalid-property]
    # Blender checks how many parameters a callback takes.
    update_one_parameter: IntProperty(update=lambda self: None)  # ty: ignore[invalid-argument-type]
    get_two_parameters: IntProperty(get=lambda self, extra: 0)  # ty: ignore[invalid-argument-type]
    poll_one_parameter: PointerProperty(type=Object, poll=lambda self: True)  # ty: ignore[invalid-argument-type]
    items_one_parameter: EnumProperty(items=lambda self: [])  # ty: ignore[invalid-argument-type]


def register():
    bpy.utils.register_class(PROPS_DEFAULTS_Valid)
    bpy.utils.register_class(PROPS_DEFAULTS_Invalid)


def unregister():
    bpy.utils.unregister_class(PROPS_DEFAULTS_Invalid)
    bpy.utils.unregister_class(PROPS_DEFAULTS_Valid)
