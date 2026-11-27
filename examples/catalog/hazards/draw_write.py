# /// catalog
# title = "Writes in a draw function"
# section = "restricted"
# status = "not-handled"
# see = ["blender/source/blender/python/intern/bpy_rna.cc", "blender/source/blender/makesrna/intern/rna_ui.cc"]
#
# [future]
# class = "possible"
# note = "The add-on typechecker could report an assignment to a data-block's property in a callback Blender calls read-only, such as `draw`."
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so every read of it is reported, and `layout.prop` rejects a scene that may be `None`."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so every read of it is reported."
# ///
"""Blender calls a panel's, menu's or header's `draw` with writes to data-blocks turned off: setting a property of a
scene, an object or any other data-block there raises `AttributeError` ("Writing to ID classes in this context is
not allowed"). Change data in an operator, or in a property's `update` callback. The checker does not report the
write; the marked line shows the result a check would give."""

from bpy.types import Panel


class SIMPLE_PT_frame(Panel):
    bl_label = "Frame"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.prop(context.scene, "frame_current")
        # gap: the write in `draw` is not reported
        context.scene.frame_current = 1  # ty: ignore[invalid-assignment]
