"""The panels in the Properties editor, the object presets and the File menu entries."""

from __future__ import annotations

import bpy

# demo: later/startup-modules-in-builtin-stubs
from bl_operators.presets import AddPresetBase
from bpy.types import Menu, Operator, Panel


class BATCH_EXPORT_AND_IMPORT_MT_object_presets(Menu):
    bl_label = "Object Export Presets"
    preset_subdir = "batch_export_and_import/object"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class BATCH_EXPORT_AND_IMPORT_OT_object_preset_add(AddPresetBase, Operator):
    """Add or remove an object export preset"""

    bl_idname = "batch_export_and_import.object_preset_add"
    bl_label = "Add Object Export Preset"
    preset_menu = "BATCH_EXPORT_AND_IMPORT_MT_object_presets"
    preset_defines = ["settings = bpy.context.object.batch_export_and_import"]
    preset_values = ["settings.enabled", "settings.file_format"]
    preset_subdir = "batch_export_and_import/object"


class OBJECT_PT_batch_export_and_import(Panel):
    bl_label = "Batch Export"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        # demo: blender-narrowed-by-bl-context
        settings = context.object.batch_export_and_import

        row = layout.row(align=True)
        row.menu(
            "BATCH_EXPORT_AND_IMPORT_MT_object_presets",
            text=BATCH_EXPORT_AND_IMPORT_MT_object_presets.bl_label,
        )
        row.operator("batch_export_and_import.object_preset_add", text="", icon="ADD")
        remove = row.operator(
            "batch_export_and_import.object_preset_add", text="", icon="REMOVE"
        )
        remove.remove_active = True

        layout.prop(settings, "enabled")
        column = layout.column()
        column.active = settings.enabled
        column.prop(settings, "file_name")
        column.prop(settings, "file_format")


class SCENE_PT_batch_export_and_import(Panel):
    bl_label = "Batch Export"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        settings = context.scene.batch_export_and_import
        layout.prop(settings, "directory")
        layout.prop(settings, "file_format")
        layout.prop(settings, "apply_modifiers")
        layout.prop(settings, "skip_scatter_copies")
        layout.prop(settings, "export_on_save")

        layout.operator("export_scene.batch_export", icon="EXPORT")
        whole_scene = layout.operator("export_scene.batch_export", text="Export Scene")
        whole_scene.use_selection = False
        layout.operator("object.apply_and_batch_export")


def draw_export_menu(self, context):
    self.layout.operator(
        "export_scene.batch_export", text="Batch Export (one file per object)"
    )


def draw_import_menu(self, context):
    self.layout.operator("import_scene.batch_import", text="Batch Import (.obj, .stl)")


classes = (
    BATCH_EXPORT_AND_IMPORT_MT_object_presets,
    BATCH_EXPORT_AND_IMPORT_OT_object_preset_add,
    OBJECT_PT_batch_export_and_import,
    SCENE_PT_batch_export_and_import,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(draw_export_menu)
    bpy.types.TOPBAR_MT_file_import.append(draw_import_menu)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(draw_import_menu)
    bpy.types.TOPBAR_MT_file_export.remove(draw_export_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
