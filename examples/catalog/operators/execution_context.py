# /// catalog
# title = "An execution context as the first argument"
# section = "calls"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["operator_calls"]
#
# [runtime]
# register = "ok"
#
# [[runtime.probe]]
# code = "bpy.ops.wm.call_menu('INVOKE_WRONG', name='VIEW3D_MT_add')"
# expect = "raises"
# reason = "an unknown execution context raises"
# ///
"""Before the keywords, an operator call takes an execution context, such as `"INVOKE_DEFAULT"` to run `invoke` as a
click would, and an undo flag. The checker accepts both and reports an execution context Blender does not know."""

import bpy

bl_info = {
    "name": "Catalog: an execution context as the first argument",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


def example() -> None:
    bpy.ops.wm.call_menu("INVOKE_DEFAULT", name="VIEW3D_MT_add")
    bpy.ops.wm.call_menu("INVOKE_DEFAULT", True, name="VIEW3D_MT_add")
    bpy.ops.wm.call_menu("INVOKE_WRONG", name="VIEW3D_MT_add")  # ty: ignore[no-matching-overload]


def register():
    pass


def unregister():
    pass
