# /// catalog
# title = "`register` and `unregister` from `register_classes_factory`"
# section = "entry-points"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["addon_discovery", "registration"]
# ///
"""`bpy.utils.register_classes_factory(classes)` returns a `register` and an `unregister` function for a tuple of
classes. The checker follows the assignment as it follows a `def register()`, so the operator it registers is known
in `bpy.ops` with its properties."""

import bpy
from bpy.props import IntProperty
from bpy.types import Operator

bl_info = {
    "name": "Catalog: register_classes_factory",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class CLASSES_FACTORY_OT_run(Operator):
    bl_idname = "classes_factory.run"
    bl_label = "Run"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


classes = (CLASSES_FACTORY_OT_run,)

register, unregister = bpy.utils.register_classes_factory(classes)


def example() -> None:
    bpy.ops.classes_factory.run(count=2)
    bpy.ops.classes_factory.run(count="2")  # ty: ignore[invalid-argument-type]
