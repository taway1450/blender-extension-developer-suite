"""Feature test: property arguments Blender rejects when the class is registered (ValueError), each checked on its own
in Blender 5.4: defaults that do not fit the property, a set callback without get, callbacks with the wrong number of
parameters, a name starting with "_", a pointer or collection type of the wrong kind, out-of-range sizes, too many
ENUM_FLAG items and a data-block pointer on add-on preferences. Also arguments it accepts."""

import bpy
from bpy.props import (BoolProperty, BoolVectorProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, IntVectorProperty, PointerProperty, StringProperty)
from bpy.types import AddonPreferences, Object, Operator, PropertyGroup

AB = [("A", "A", ""), ("B", "B", "")]
# ENUM_FLAG items are bits of an int: at most 32. Written out, so the count can be read from the literal.
ITEMS_33 = [
    ("I00", "", ""), ("I01", "", ""), ("I02", "", ""), ("I03", "", ""), ("I04", "", ""), ("I05", "", ""),
    ("I06", "", ""), ("I07", "", ""), ("I08", "", ""), ("I09", "", ""), ("I10", "", ""), ("I11", "", ""),
    ("I12", "", ""), ("I13", "", ""), ("I14", "", ""), ("I15", "", ""), ("I16", "", ""), ("I17", "", ""),
    ("I18", "", ""), ("I19", "", ""), ("I20", "", ""), ("I21", "", ""), ("I22", "", ""), ("I23", "", ""),
    ("I24", "", ""), ("I25", "", ""), ("I26", "", ""), ("I27", "", ""), ("I28", "", ""), ("I29", "", ""),
    ("I30", "", ""), ("I31", "", ""), ("I32", "", ""),
]


def dynamic_items(self, context):
    return AB


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
    bool_set_without_get: BoolProperty(set=lambda self, value: None)  # ty: ignore[blender-invalid-property]
    float_set_without_get: FloatProperty(set=lambda self, value: None)  # ty: ignore[blender-invalid-property]
    string_set_without_get: StringProperty(set=lambda self, value: None)  # ty: ignore[blender-invalid-property]
    enum_set_without_get: EnumProperty(items=AB, set=lambda self, value: None)  # ty: ignore[blender-invalid-property]
    bool_vector_set_without_get: BoolVectorProperty(set=lambda self, value: None)  # ty: ignore[blender-invalid-property]
    int_vector_set_without_get: IntVectorProperty(set=lambda self, value: None)  # ty: ignore[blender-invalid-property]
    float_vector_set_without_get: FloatVectorProperty(set=lambda self, value: None)  # ty: ignore[blender-invalid-property]
    _underscore: IntProperty()  # ty: ignore[blender-invalid-property]
    pointer_to_operator: PointerProperty(type=Operator)  # ty: ignore[invalid-argument-type]
    collection_of_ids: CollectionProperty(type=Object)  # ty: ignore[invalid-argument-type]
    function_items_str_default: EnumProperty(items=dynamic_items, default="A")  # ty: ignore[blender-invalid-property]
    flag_too_many_items: EnumProperty(items=ITEMS_33, options={"ENUM_FLAG"})  # ty: ignore[blender-invalid-property]
    size_too_big: IntVectorProperty(size=33)  # ty: ignore[blender-invalid-property]
    size_zero: IntVectorProperty(size=0)  # ty: ignore[blender-invalid-property]
    size_four_dimensions: FloatVectorProperty(size=(2, 2, 2, 2))  # ty: ignore[blender-invalid-property]
    # Blender checks how many parameters a callback takes.
    update_one_parameter: IntProperty(update=lambda self: None)  # ty: ignore[invalid-argument-type]
    get_two_parameters: IntProperty(get=lambda self, extra: 0)  # ty: ignore[invalid-argument-type]
    poll_one_parameter: PointerProperty(type=Object, poll=lambda self: True)  # ty: ignore[invalid-argument-type]
    items_one_parameter: EnumProperty(items=lambda self: [])  # ty: ignore[invalid-argument-type]


class PROPS_DEFAULTS_Preferences(AddonPreferences):
    bl_idname = __package__

    # Add-on preferences cannot hold data-block pointers.
    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-property]


def register():
    bpy.utils.register_class(PROPS_DEFAULTS_Valid)
    bpy.utils.register_class(PROPS_DEFAULTS_Invalid)
    bpy.utils.register_class(PROPS_DEFAULTS_Preferences)


def unregister():
    bpy.utils.unregister_class(PROPS_DEFAULTS_Preferences)
    bpy.utils.unregister_class(PROPS_DEFAULTS_Invalid)
    bpy.utils.unregister_class(PROPS_DEFAULTS_Valid)
