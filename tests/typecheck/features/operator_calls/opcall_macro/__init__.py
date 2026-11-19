"""Feature test: a Macro operator. Its call takes one keyword argument per step operator, named by the step's
OT idname, holding a dict of the step's properties (checked in Blender 5.4). define() returns an OperatorMacro.
The properties a layout gives for a built-in macro (`layout.operator("mesh.rip_move")`) hold one properties
object per step, named the same way, so `props.MESH_OT_rip.use_fill` is the rip step's property, through nested
macros too."""

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import Macro, Operator, UILayout


class OPCALL_MACRO_OT_step(Operator):
    bl_idname = "opcall_macro.step"
    bl_label = "Step"
    bl_options = {"REGISTER", "UNDO"}

    amount: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_MACRO_OT_label(Operator):
    bl_idname = "opcall_macro.label"
    bl_label = "Label"
    bl_options = {"REGISTER", "UNDO"}

    text: StringProperty()

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_MACRO_OT_combo(Macro):
    bl_idname = "opcall_macro.combo"
    bl_label = "Combo"
    bl_options = {"REGISTER", "UNDO"}


def draw_rip(layout: UILayout) -> None:
    props = layout.operator("mesh.rip_move", text="Rip Vertices and Fill")
    props.MESH_OT_rip.use_fill = True
    props = layout.operator("node.duplicate_move")
    props.NODE_OT_translate_attach.TRANSFORM_OT_translate.view2d_edge_pan = True
    props.MESH_OT_rip.use_fill = True  # ty: ignore[missing-attribute]  # bare-ok: no step of this macro


def register():
    bpy.utils.register_class(OPCALL_MACRO_OT_step)
    bpy.utils.register_class(OPCALL_MACRO_OT_label)
    bpy.utils.register_class(OPCALL_MACRO_OT_combo)
    OPCALL_MACRO_OT_combo.define("OPCALL_MACRO_OT_step")
    OPCALL_MACRO_OT_combo.define("opcall_macro.label")


def unregister():
    bpy.utils.unregister_class(OPCALL_MACRO_OT_combo)
    bpy.utils.unregister_class(OPCALL_MACRO_OT_label)
    bpy.utils.unregister_class(OPCALL_MACRO_OT_step)
