# /// catalog
# title = "`layout.prop(data, \"name\")`"
# section = "draw"
# status = "not-handled"#
# [future]
# class = "possible"
# note = "Check the property name against the properties of `data`'s type."
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so `context.object` is not narrowed and passing it to `layout.prop` is reported."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so its reads are reported."
# ///
"""`layout.prop` draws one property of `data`, named by a string, which Blender looks up only while it draws. The stubs
type the name as a plain `str`, so a misspelt name is not reported today: the marked line shows the result a check
would give."""

from bpy.types import Panel


class LocationPanel(Panel):
    bl_label = "Location"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        if context.object is not None:
            # gap: the name is not checked against the Object's properties
            self.layout.prop(context.object, "locaton")  # ty: ignore[invalid-argument-type]
