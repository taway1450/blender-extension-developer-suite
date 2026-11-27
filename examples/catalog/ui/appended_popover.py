# /// catalog
# title = "A popover opened by an appended function"
# section = "popovers"
# status = "not-handled"
# features = ["implied_narrowings"]
# later = "popover-opened-by-appended-function"
#
# [future]
# class = "planned"
# note = "Give a popover what the function appended to Blender's header checked before it opens it."
# tracked = "later/popover-opened-by-appended-function"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs have no `VIEW3D_HT_header` in `bpy.types`, so `append` and `remove` on it are reported."
# ///
"""What a function appended to one of Blender's headers checked before it opens a popover is not known in the popover.
A popover is drawn with the context of the editor that opened it, so what the opener checked in that context holds
there too. The checker reads this from the add-on's own headers, but not from an appended function: here the function
opens the popover only when there is an active object, and the popover's read of `context.object` is still
reported."""

import bpy
from bpy.types import Panel


class APPENDED_POPOVER_PT_object(Panel):
    bl_label = "Object"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        # gap: the check in the appended function is not known here
        self.layout.label(text=context.object.name)


def draw_popover(self, context):
    if context.object is not None:
        self.layout.popover("APPENDED_POPOVER_PT_object")


def register():
    bpy.utils.register_class(APPENDED_POPOVER_PT_object)
    bpy.types.VIEW3D_HT_header.append(draw_popover)


def unregister():
    bpy.types.VIEW3D_HT_header.remove(draw_popover)
    bpy.utils.unregister_class(APPENDED_POPOVER_PT_object)
