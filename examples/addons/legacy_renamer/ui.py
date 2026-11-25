"""The sidebar panel and the list of rules."""

import bpy

from .props import RenameRule

TYPE_ICONS = {
    "MESH": "MESH_DATA",
    "CURVE": "CURVE_DATA",
    "LIGHT": "LIGHT_DATA",
    "CAMERA": "CAMERA_DATA",
    "EMPTY": "EMPTY_DATA",
}


class LEGACY_UL_rules(bpy.types.UIList):
    # demo: blender-imprecise-callback-parameter
    def draw_item(
        self,
        context,
        layout,
        data,
        item: RenameRule,
        icon,
        active_data,
        active_propname,
    ):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "find", text="", emboss=False)
        row.label(icon="FORWARD")
        row.prop(item, "replace", text="", emboss=False)


class VIEW3D_PT_legacy_renamer(bpy.types.Panel):
    bl_label = "Legacy Renamer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rename"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.legacy_renamer

        ob = context.object
        if ob:
            # demo: blender-imprecise-enum-value
            layout.label(text=ob.name, icon=TYPE_ICONS.get(ob.type, "OBJECT_DATA"))

        col = layout.column(align=True)
        col.prop(settings, "target")
        col.prop(settings, "prefix")
        col.prop(settings, "start")
        col.prop(settings, "padding")
        col.prop(settings, "case")
        col.prop(settings, "tag_collections")

        row = layout.row()
        row.template_list(
            "LEGACY_UL_rules", "", settings, "rules", settings, "active_rule", rows=3
        )
        col = row.column(align=True)
        col.operator("object.legacy_rule_add", icon="ADD", text="")
        col.operator("object.legacy_rule_remove", icon="REMOVE", text="")

        layout.operator("import_scene.legacy_rules", icon="IMPORT")
        layout.operator("object.legacy_rename")


classes = (LEGACY_UL_rules, VIEW3D_PT_legacy_renamer)
