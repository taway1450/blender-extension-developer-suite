"""Feature test: operator properties declared on base operators and on mixins are keyword arguments too; a
subclass can redeclare a property with another type. A registered base operator keeps its own properties."""

import bpy
from bpy.props import FloatProperty, IntProperty, StringProperty
from bpy.types import Operator


class CountMixin:
    count: IntProperty()


class OPCALL_INHERIT_OT_base(Operator):
    bl_idname = "opcall_inherit.base"
    bl_label = "Base"

    size: FloatProperty()
    mode: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_INHERIT_OT_derived(CountMixin, OPCALL_INHERIT_OT_base):
    bl_idname = "opcall_inherit.derived"
    bl_label = "Derived"

    mode: StringProperty()
    label: StringProperty()


classes = (OPCALL_INHERIT_OT_base, OPCALL_INHERIT_OT_derived)
register, unregister = bpy.utils.register_classes_factory(classes)
