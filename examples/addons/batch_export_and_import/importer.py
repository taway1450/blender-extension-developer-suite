"""Import many OBJ and STL files at once, from the file browser or dropped into the 3D viewport."""

from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, CollectionProperty, StringProperty
from bpy.types import FileHandler, Operator, OperatorFileListElement
from bpy_extras.io_utils import ImportHelper


# demo: bpy_symbols
class IMPORT_SCENE_OT_batch_import(Operator, ImportHelper):
    """Import every chosen OBJ and STL file"""

    bl_idname = "import_scene.batch_import"
    bl_label = "Batch Import"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(default="*.obj;*.stl", options={"HIDDEN"})
    directory: StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})
    files: CollectionProperty(
        type=OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"}
    )
    new_collection: BoolProperty(
        name="New Collection",
        description="Put the imported objects into a collection of their own",
        default=True,
    )

    def invoke(self, context, event):
        # A drop into the viewport gives the files; only the menu entry needs the file browser.
        if self.directory and self.files:
            return self.execute(context)
        return super().invoke(context, event)

    def execute(self, context):
        # A file handler's import operator also runs for a collection importer, which has no scene.
        # demo: blender-assumed-context-member
        collection = context.collection
        if self.new_collection:
            collection = bpy.data.collections.new("Batch Import")
            context.scene.collection.children.link(collection)

        for file in self.files:
            path = os.path.join(self.directory, file.name)
            if path.lower().endswith(".obj"):
                bpy.ops.wm.obj_import(filepath=path)
            else:
                bpy.ops.wm.stl_import(filepath=path)
            # The importers leave what they imported selected.
            for ob in context.selected_objects:
                for other in ob.users_collection:
                    other.objects.unlink(ob)
                collection.objects.link(ob)
        return {"FINISHED"}


class IO_FH_batch_import(FileHandler):
    bl_idname = "IO_FH_batch_import"
    bl_label = "Batch Import"
    bl_import_operator = "import_scene.batch_import"
    bl_file_extensions = ".obj;.stl"

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"


classes = (IMPORT_SCENE_OT_batch_import, IO_FH_batch_import)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
