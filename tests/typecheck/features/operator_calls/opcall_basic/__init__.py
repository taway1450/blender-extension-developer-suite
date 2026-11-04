"""Feature test: an addon operator called as bpy.ops.<category>.<name>(...): one keyword argument per property, of
the type Blender converts from (checked in Blender 5.4), and the two positional arguments execution context and
undo. A PointerProperty to an ID type is not allowed on operators: Blender reports it and drops that property and
every property after it."""

import bpy
from bpy.props import (BoolProperty, BoolVectorProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, IntVectorProperty, PointerProperty, StringProperty)
from bpy.types import Object, Operator, PropertyGroup

AB = [("A", "A", ""), ("B", "B", "")]


def dynamic_items(self, context):
    return AB


class OPCALL_BASIC_Group(PropertyGroup):
    count: IntProperty()


class OPCALL_BASIC_OT_all(Operator):
    bl_idname = "opcall_basic.all"
    bl_label = "All"

    int_value: IntProperty()
    float_value: FloatProperty()
    bool_value: BoolProperty()
    string_value: StringProperty()
    enum_value: EnumProperty(items=AB)
    flag_value: EnumProperty(items=AB, options={"ENUM_FLAG"})
    dynamic_value: EnumProperty(items=dynamic_items)
    vector_value: FloatVectorProperty(size=3)
    int_vector_value: IntVectorProperty(size=2)
    bool_vector_value: BoolVectorProperty(size=2)
    matrix_value: FloatVectorProperty(size=(2, 2))
    group_value: PointerProperty(type=OPCALL_BASIC_Group)
    items_value: CollectionProperty(type=OPCALL_BASIC_Group)
    hidden_value: IntProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_BASIC_OT_empty(Operator):
    bl_idname = "opcall_basic.empty"
    bl_label = "Empty"

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_BASIC_OT_dropped(Operator):
    bl_idname = "opcall_basic.dropped"
    bl_label = "Dropped"

    before: IntProperty()
    target: PointerProperty(type=Object)  # ty: ignore[blender-invalid-operator-property]
    after: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


classes = (OPCALL_BASIC_Group, OPCALL_BASIC_OT_all, OPCALL_BASIC_OT_empty, OPCALL_BASIC_OT_dropped)
register, unregister = bpy.utils.register_classes_factory(classes)
