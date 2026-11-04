"""WorkSpaceTool.bl_keymap names operators and their property values in tuples; the checker checks them against
the operator (only the checker can: they are plain tuples to the type system)."""

from bpy.types import WorkSpaceTool


class OPPROPS_SINKS_Tool(WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = "opprops_sinks.tool"
    bl_label = "Tool"
    bl_keymap = (
        ("opprops_sinks.step", {"type": "LEFTMOUSE", "value": "PRESS"}, {"properties": [("amount", 1), ("mode", "B")]}),
        ("OPPROPS_SINKS_OT_step", {"type": "RIGHTMOUSE", "value": "PRESS"}, None),
        ("opprops_sinks.step", {"type": "A", "value": "PRESS"},
         {"properties": [("amount", "1")]}),  # ty: ignore[blender-invalid-operator-property]
        ("opprops_sinks.step", {"type": "B", "value": "PRESS"},
         {"properties": [("mode", "C")]}),  # ty: ignore[blender-invalid-operator-property]
        ("opprops_sinks.step", {"type": "C", "value": "PRESS"},
         {"properties": [("missing", 1)]}),  # ty: ignore[blender-invalid-operator-property]
        ("opprops_sinks.missing", {"type": "D", "value": "PRESS"}, None),  # ty: ignore[blender-unknown-operator]
    )
