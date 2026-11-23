"""Feature test: register() hands register_class a class it finds at runtime (getattr on the module), so the
register() walk gives up: every class and property of the add-on then counts as registered, and the checks that a
class is missing from register() are off. The checker reports that once per add-on, at the value it could not follow,
under blender-assumed-complete-registration. Nothing else is reported: the operator below is taken as registered,
also where the panel reads it back from bpy.types. The assert_type call is a no-op at runtime."""

import sys
from typing import assert_type

import bpy
from bpy.types import Operator, Panel

CLASS_NAMES = ("ASM_COMPLETE_REGISTRATION_OT_run", "ASM_COMPLETE_REGISTRATION_PT_panel")


class ASM_COMPLETE_REGISTRATION_OT_run(Operator):
    bl_idname = "asm_complete_registration.run"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class ASM_COMPLETE_REGISTRATION_PT_panel(Panel):
    bl_label = "Complete registration"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        self.layout.operator("asm_complete_registration.run")
        assert_type(bpy.types.ASM_COMPLETE_REGISTRATION_OT_run.bl_label, str)


class ASM_COMPLETE_REGISTRATION_OT_unused(Operator):
    """Never registered: with the walk given up, no blender-unregistered-class for it."""

    bl_idname = "asm_complete_registration.unused"
    bl_label = "Unused"

    def execute(self, context):
        bpy.ops.asm_complete_registration.run()
        return {"FINISHED"}


def register():
    module = sys.modules[__name__]
    for name in CLASS_NAMES:
        bpy.utils.register_class(getattr(module, name))  # ty: ignore[blender-assumed-complete-registration]


def unregister():
    module = sys.modules[__name__]
    for name in reversed(CLASS_NAMES):
        bpy.utils.unregister_class(getattr(module, name))
