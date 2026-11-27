# /// catalog
# title = "Two Blender bases"
# section = "bases"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
#
# [runtime]
# register = "ok"
#
# [[runtime.probe]]
# code = "addon.TWO_BASES_OT_two.bl_rna.base.identifier"
# expect = "Operator"
# reason = "Blender registers the class as its first Blender base"
# ///
"""A class that derives from two Blender classes, say `Operator` and `Panel`, registers as the first of them only;
the other base's callbacks are never called. The checker reports the class. Mixins that are no Blender class are
fine."""

import bpy
from bpy.types import Operator, Panel

bl_info = {
    "name": "Catalog: two Blender bases",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class TWO_BASES_OT_two(Operator, Panel):  # ty: ignore[blender-invalid-base]
    bl_idname = "two_bases.two"
    bl_label = "Two bases"

    def execute(self, context):
        return {"FINISHED"}


def register():
    bpy.utils.register_class(TWO_BASES_OT_two)


def unregister():
    bpy.utils.unregister_class(TWO_BASES_OT_two)
