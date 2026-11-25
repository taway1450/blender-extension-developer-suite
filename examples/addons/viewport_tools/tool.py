"""The measure tool of the 3D viewport's toolbar."""

from bpy.types import WorkSpaceTool


class MeasureTool(WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"

    bl_idname = "viewport_tools.measure"
    bl_label = "Measure Distance"
    bl_description = "Click two points to measure the distance between them"
    bl_icon = "ops.view3d.ruler"
    bl_widget = None
    # The properties of a key map entry are checked against the operator it names.
    # demo: operator_properties
    bl_keymap = (
        (
            "view3d.viewport_tools_measure",
            {"type": "LEFTMOUSE", "value": "PRESS"},
            {"properties": [("snap", False)]},
        ),
        (
            "view3d.viewport_tools_measure",
            {"type": "LEFTMOUSE", "value": "PRESS", "ctrl": True},
            {"properties": [("snap", True)]},
        ),
    )

    def draw_settings(context, layout, tool):
        props = tool.operator_properties("view3d.viewport_tools_measure")
        layout.prop(props, "snap")
