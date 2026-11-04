"""Feature test: blender-invalid-base. A class with two Blender bases registers as the first one (here an
Operator; checked in Blender 5.4), which is never what was meant. The cases that fail before registration (a
mixin with a metaclass, __slots__) or at it (a base that does not support registration) are in
check_inh_bases.py, which is never imported."""

import bpy
from bpy.types import Operator, Panel


class INH_BASES_OT_two(Operator, Panel):  # ty: ignore[blender-invalid-base]
    bl_idname = "inh_bases.two"
    bl_label = "Two bases"

    def execute(self, context):
        return {"FINISHED"}


classes = (INH_BASES_OT_two,)
register, unregister = bpy.utils.register_classes_factory(classes)
