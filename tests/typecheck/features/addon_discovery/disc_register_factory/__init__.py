"""Feature test: register and unregister are assigned, not defined: register_classes_factory makes them."""

import bpy
from bpy.props import IntProperty
from bpy.types import Operator


class DISC_REGISTER_FACTORY_OT_run(Operator):
    bl_idname = "disc_register_factory.run"
    bl_label = "Run"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


classes = (DISC_REGISTER_FACTORY_OT_run,)

register, unregister = bpy.utils.register_classes_factory(classes)
