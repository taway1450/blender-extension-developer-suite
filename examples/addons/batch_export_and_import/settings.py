"""What to export and where: the scene's settings, the per-object overrides and the preferences."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, Context, PropertyGroup

FORMATS = (
    ("OBJ", "Wavefront (.obj)", "Text format, one mesh per file"),
    ("STL", "STL (.stl)", "Triangles only, for 3D printing"),
    ("GLTF", "glTF Binary (.glb)", "Meshes with materials, for game engines"),
)


class ObjectExportSettings(PropertyGroup):
    enabled: BoolProperty(
        name="Export", description="Include the object in the batch", default=True
    )
    file_name: StringProperty(
        name="File Name", description="Empty uses the object's name"
    )
    # demo: later/enum-items-unpacked
    file_format: EnumProperty(
        name="Format",
        items=(("SCENE", "Scene", "Use the scene's format"), *FORMATS),
        default="SCENE",
    )


class BatchSettings(PropertyGroup):
    directory: StringProperty(name="Folder", subtype="DIR_PATH", default="//export")
    file_format: EnumProperty(name="Format", items=FORMATS, default="GLTF")
    apply_modifiers: BoolProperty(name="Apply Modifiers", default=True)
    export_on_save: BoolProperty(
        name="Export on Save",
        description="Export the whole scene every time the file is saved",
    )
    skip_scatter_copies: BoolProperty(
        name="Skip Scatter Copies",
        description="Leave out the copies the Scatter Tools add-on made",
        default=True,
    )


class BatchExportAndImportPreferences(AddonPreferences):
    bl_idname = __package__

    report_folder: BoolProperty(
        name="Report Folder",
        description="Name the folder in the report of an export",
        default=True,
    )

    def draw(self, context):
        self.layout.prop(self, "report_folder")


def get_preferences(context: Context) -> BatchExportAndImportPreferences:
    return context.preferences.addons[__package__].preferences


classes = (ObjectExportSettings, BatchSettings, BatchExportAndImportPreferences)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.batch_export_and_import = PointerProperty(type=BatchSettings)
    bpy.types.Object.batch_export_and_import = PointerProperty(
        type=ObjectExportSettings
    )


def unregister():
    del bpy.types.Object.batch_export_and_import
    del bpy.types.Scene.batch_export_and_import
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
