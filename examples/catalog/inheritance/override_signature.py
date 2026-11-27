# /// catalog
# title = "An override with another signature"
# section = "overrides"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
#
# [evidence]
# addon = "inheritance/generated/inh_invalid_execute_fewer"
# register = "fails"
# says = "2 args, found 1"
# ///
"""Blender checks each callback when it registers the class: the number of positional parameters (defaults
included), and whether it is a classmethod (`poll`) or a plain function (`execute`). Parameter names do not matter,
since Blender passes the arguments by position. The checker reports an override Blender would refuse, here an
`execute` without its `context` parameter."""

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: an override with another signature",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class OVERRIDE_SIGNATURE_OT_run(Operator):
    bl_idname = "override_signature.run"
    bl_label = "Run"

    def execute(self):  # ty: ignore[blender-invalid-override]
        return {"FINISHED"}


def register():
    bpy.utils.register_class(OVERRIDE_SIGNATURE_OT_run)


def unregister():
    bpy.utils.unregister_class(OVERRIDE_SIGNATURE_OT_run)
