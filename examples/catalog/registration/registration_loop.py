# /// catalog
# title = "Registration in a loop over a tuple"
# section = "reach"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration"]
# ///
"""The usual `register()` loops over a tuple of classes, and `unregister()` over the same tuple reversed. The checker
reads the loop as one registration per class: the operators are in `bpy.ops`, and each class counts as registered
and unregistered."""

import bpy
from bpy.props import IntProperty
from bpy.types import Operator, Panel

bl_info = {
    "name": "Catalog: registration in a loop over a tuple",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class REGISTRATION_LOOP_OT_run(Operator):
    bl_idname = "registration_loop.run"
    bl_label = "Run"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class REGISTRATION_LOOP_PT_tools(Panel):
    bl_label = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.operator("registration_loop.run")


classes = (REGISTRATION_LOOP_OT_run, REGISTRATION_LOOP_PT_tools)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def example() -> None:
    bpy.ops.registration_loop.run(count=2)
    bpy.ops.registration_loop.run(count="2")  # ty: ignore[invalid-argument-type]
