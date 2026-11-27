# /// catalog
# title = "A subclass of a registered class"
# section = "bases"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
#
# [runtime]
# register = "ok"
#
# [[runtime.probe]]
# code = "healthy(addon.REGISTERED_SUBCLASS_OT_parent)"
# expect = false
# reason = "registering the subclass detached the parent's Python class"
#
# [[runtime.probe]]
# code = "healthy(addon.REGISTERED_SUBCLASS_OT_child)"
# expect = true
# reason = "the subclass works"
# ///
"""A registered class must not derive from another registered class. Registering the subclass after its parent
detaches the parent: Blender no longer calls its callbacks, and only logs a warning. Share code through an
unregistered base or a mixin instead. The checker reports the subclass."""

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: a subclass of a registered class",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class REGISTERED_SUBCLASS_OT_parent(Operator):
    bl_idname = "registered_subclass.parent"
    bl_label = "Parent"

    def execute(self, context):
        return {"FINISHED"}


class REGISTERED_SUBCLASS_OT_child(REGISTERED_SUBCLASS_OT_parent):  # ty: ignore[blender-registered-base]
    bl_idname = "registered_subclass.child"
    bl_label = "Child"


classes = (REGISTERED_SUBCLASS_OT_parent, REGISTERED_SUBCLASS_OT_child)
register, unregister = bpy.utils.register_classes_factory(classes)
