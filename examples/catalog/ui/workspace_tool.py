# /// catalog
# title = "A workspace tool"
# section = "gizmos-tools"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["operator_properties"]
# ///
"""A `WorkSpaceTool`'s `bl_keymap` names the operators the tool runs, with their property values, in plain tuples.
To the type system they are only tuples, so the checker reads them itself: it checks each idname and each property
value against the operator, and reports a value the property cannot take."""

from bpy.types import WorkSpaceTool


class SelectTool(WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = "workspace_tool.select"
    bl_label = "Select"
    bl_keymap = (
        ("object.select_all", {"type": "LEFTMOUSE", "value": "PRESS"}, {"properties": [("action", "SELECT")]}),
        ("object.select_all", {"type": "RIGHTMOUSE", "value": "PRESS"},
         {"properties": [("action", "ALL")]}),  # ty: ignore[blender-invalid-operator-property]
    )
