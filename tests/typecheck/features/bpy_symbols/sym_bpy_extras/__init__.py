"""Feature test: operators that get properties from bpy_extras: ImportHelper, ExportHelper and
orientation_helper, imported in different ways."""

import bpy
import bpy_extras.io_utils as io_utils
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras import io_utils as io_utils_from
from bpy_extras.io_utils import ExportHelper, ImportHelper, orientation_helper


@orientation_helper(axis_forward="-Z", axis_up="Y")
class SYM_BPY_EXTRAS_OT_import(Operator, ImportHelper):
    bl_idname = "sym_bpy_extras.import_file"
    bl_label = "Import"

    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={"HIDDEN"})

    def execute(self, context):
        return {"FINISHED"}


class SYM_BPY_EXTRAS_OT_export(Operator, ExportHelper):
    bl_idname = "sym_bpy_extras.export_file"
    bl_label = "Export"

    filename_ext = ".txt"

    def execute(self, context):
        return {"FINISHED"}


@io_utils.orientation_helper()
class SYM_BPY_EXTRAS_OT_export_module(Operator, io_utils_from.ExportHelper):
    bl_idname = "sym_bpy_extras.export_module"
    bl_label = "Export (module import)"

    filename_ext = ".txt"

    def execute(self, context):
        return {"FINISHED"}


classes = (SYM_BPY_EXTRAS_OT_import, SYM_BPY_EXTRAS_OT_export, SYM_BPY_EXTRAS_OT_export_module)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
