"""The export operator, and a macro that applies the transforms first."""

from __future__ import annotations

import os

import bpy
from bpy.app.translations import pgettext_iface as iface_
from bpy.props import BoolProperty
from bpy.types import Context, Macro, Object, Operator

from .settings import BatchSettings, get_preferences

EXTENSIONS = {"OBJ": ".obj", "STL": ".stl", "GLTF": ".glb"}


def exported(ob: Object, settings: BatchSettings) -> bool:
    """Whether the batch exports this object."""
    if ob.type != "MESH" or not ob.batch_export_and_import.enabled:
        return False
    # The property is there only while Scatter Tools is enabled.
    # demo: registration_checks
    if settings.skip_scatter_copies and hasattr(ob, "is_scatter_copy"):
        return not ob.is_scatter_copy
    return True


def export_object(
    context: Context, ob: Object, path: str, file_format: str, apply_modifiers: bool
) -> None:
    """Export one object; the exporters take the selection from the context."""
    # demo: context_members
    with context.temp_override(active_object=ob, selected_objects=[ob]):
        if file_format == "OBJ":
            bpy.ops.wm.obj_export(
                filepath=path,
                export_selected_objects=True,
                apply_modifiers=apply_modifiers,
            )
        elif file_format == "STL":
            bpy.ops.wm.stl_export(
                filepath=path,
                export_selected_objects=True,
                apply_modifiers=apply_modifiers,
            )
        else:
            bpy.ops.export_scene.gltf(
                filepath=path, use_selection=True, export_apply=apply_modifiers
            )


class EXPORT_SCENE_OT_batch_export(Operator):
    """Export every mesh object to its own file"""

    bl_idname = "export_scene.batch_export"
    bl_label = "Batch Export"
    bl_options = {"REGISTER"}

    use_selection: BoolProperty(
        name="Selected Only",
        description="Export the selected objects instead of the whole scene",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        settings = context.scene.batch_export_and_import
        directory = bpy.path.abspath(settings.directory)
        os.makedirs(directory, exist_ok=True)

        if self.use_selection:
            objects = context.selected_objects
        else:
            objects = list(context.scene.objects)
        count = 0
        for ob in objects:
            if not exported(ob, settings):
                continue
            file_format = ob.batch_export_and_import.file_format
            if file_format == "SCENE":
                file_format = settings.file_format
            name = bpy.path.clean_name(ob.batch_export_and_import.file_name or ob.name)
            path = os.path.join(directory, name + EXTENSIONS[file_format])
            export_object(context, ob, path, file_format, settings.apply_modifiers)
            count += 1

        folder = directory if get_preferences(context).report_folder else ""
        self.report({"INFO"}, iface_("Exported {} objects to {}").format(count, folder))
        return {"FINISHED"}


# demo: operator_calls
class OBJECT_OT_apply_and_batch_export(Macro):
    """Apply rotation and scale to the selected objects, then export them"""

    bl_idname = "object.apply_and_batch_export"
    bl_label = "Apply and Batch Export"
    bl_options = {"REGISTER", "UNDO"}


def register():
    bpy.utils.register_class(EXPORT_SCENE_OT_batch_export)
    bpy.utils.register_class(OBJECT_OT_apply_and_batch_export)
    apply = OBJECT_OT_apply_and_batch_export.define("OBJECT_OT_transform_apply")
    apply.properties.location = False
    OBJECT_OT_apply_and_batch_export.define("EXPORT_SCENE_OT_batch_export")


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_apply_and_batch_export)
    bpy.utils.unregister_class(EXPORT_SCENE_OT_batch_export)
