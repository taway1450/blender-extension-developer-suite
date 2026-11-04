"""Feature test: the Blender functions that take an operator idname as a string and return (or hold) that
operator's properties: UILayout.operator, operator_menu_hold, operator_menu_enum, KeyMapItems.new(...).properties,
WindowManager.operator_properties_last, Gizmo.target_set_operator, WorkSpaceTool.operator_properties, the
OperatorMacro of Macro.define and an operator's own self.properties. With a known idname (either form,
category.name or CATEGORY_OT_name) the result has the operator's properties and is not None (checked in Blender
5.4; kmi.properties is never None). operator_enum and operator_menu_enum also name an enum property of the
operator."""

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty
from bpy.types import Macro, Operator, Panel

AB = [("A", "A", ""), ("B", "B", "")]


class OPPROPS_SINKS_OT_step(Operator):
    bl_idname = "opprops_sinks.step"
    bl_label = "Step"
    bl_options = {"REGISTER", "UNDO"}

    amount: IntProperty()
    mode: EnumProperty(items=AB)
    label: StringProperty()
    flags: EnumProperty(items=AB, options={"ENUM_FLAG"})

    def execute(self, context):
        self.properties.amount += 1
        return {"FINISHED"}


class OPPROPS_SINKS_OT_bare(Operator):
    bl_idname = "opprops_sinks.bare"
    bl_label = "Bare"

    def execute(self, context):
        return {"FINISHED"}


class OPPROPS_SINKS_OT_combo(Macro):
    bl_idname = "opprops_sinks.combo"
    bl_label = "Combo"
    bl_options = {"REGISTER", "UNDO"}


class OPPROPS_SINKS_PT_panel(Panel):
    bl_label = "Operator properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        layout.operator("opprops_sinks.step").amount = 1
        layout.operator("OPPROPS_SINKS_OT_step", text="Other form").mode = "B"
        layout.operator_menu_enum("opprops_sinks.step", "mode").label = "menu"
        layout.operator_enum("opprops_sinks.step", "mode")
        layout.operator("opprops_sinks.bare")


addon_keymaps = []


def register():
    bpy.utils.register_class(OPPROPS_SINKS_OT_step)
    bpy.utils.register_class(OPPROPS_SINKS_OT_bare)
    bpy.utils.register_class(OPPROPS_SINKS_OT_combo)
    bpy.utils.register_class(OPPROPS_SINKS_PT_panel)
    OPPROPS_SINKS_OT_combo.define("OPPROPS_SINKS_OT_step").properties.amount = 2
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is not None:
        keymap = keyconfig.keymaps.new(name="3D View", space_type="VIEW_3D")
        item = keymap.keymap_items.new("opprops_sinks.step", "S", "PRESS", ctrl=True)
        item.properties.amount = 3
        item.properties.mode = "B"
        addon_keymaps.append((keymap, item))


def unregister():
    for keymap, item in addon_keymaps:
        keymap.keymap_items.remove(item)
    addon_keymaps.clear()
    bpy.utils.unregister_class(OPPROPS_SINKS_PT_panel)
    bpy.utils.unregister_class(OPPROPS_SINKS_OT_combo)
    bpy.utils.unregister_class(OPPROPS_SINKS_OT_bare)
    bpy.utils.unregister_class(OPPROPS_SINKS_OT_step)
