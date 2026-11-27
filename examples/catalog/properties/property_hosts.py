# /// catalog
# title = "Classes that ignore property annotations"
# section = "declaring"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""Only some Blender classes are Property hosts: `PropertyGroup`, `Operator`, `Macro`, `AddonPreferences`, `UIList`,
`Node`, `NodeSocket`, `NodeTree`, `Gizmo` and a few more. A `Panel`, `Menu`, `Header` or `RenderEngine` registers with
its annotations silently dropped, so the checker reports a property declared on one."""

from bpy.props import BoolProperty
from bpy.types import Operator, Panel


class VIEW3D_PT_tools(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_label = "Tools"

    expanded: BoolProperty()  # ty: ignore[blender-unsupported-property-host]


class OBJECT_OT_tidy(Operator):
    bl_idname = "object.tidy"
    bl_label = "Tidy"

    recursive: BoolProperty()
