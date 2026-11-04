"""Feature test: the idname given to UILayout.operator in different forms: a literal (both forms), a module
constant, the operator class's bl_idname and an f-string of constants. Blender's own operators have their
properties too. A str the checker cannot evaluate keeps the stub type; an idname no operator has is reported."""

import bpy
from bpy.props import FloatProperty
from bpy.types import Operator, Panel

STEP_IDNAME = "opprops_idnames.step"
CATEGORY = "opprops_idnames"


class OPPROPS_IDNAMES_OT_step(Operator):
    bl_idname = STEP_IDNAME
    bl_label = "Step"

    factor: FloatProperty()

    def execute(self, context):
        return {"FINISHED"}


class OPPROPS_IDNAMES_PT_panel(Panel):
    bl_label = "Idnames"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.operator(OPPROPS_IDNAMES_OT_step.bl_idname).factor = 0.5
        self.layout.operator("object.select_all").action = "SELECT"


classes = (OPPROPS_IDNAMES_OT_step, OPPROPS_IDNAMES_PT_panel)
register, unregister = bpy.utils.register_classes_factory(classes)
