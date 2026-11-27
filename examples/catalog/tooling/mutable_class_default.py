# /// catalog
# title = "`bl_options` as a set"
# section = "lint"
# status = "handled"
# safeguards = ["linter-profile"]
# see = ["blender/scripts/templates_py/Operator/mesh_add.py"]
#
# [lint]
# rule = "RUF012"
# default = "reports"
# profile = "silent"
# ///
"""An operator's `bl_options` is a set literal on the class, as in Blender's own templates. `RUF012` takes every
mutable class attribute for a shared default that should be a `ClassVar`, so it reports nearly every operator; the
linter profile turns it off."""

from bpy.types import Operator


class SIMPLE_OT_scale(Operator):
    bl_idname = "simple.scale"
    bl_label = "Scale"
    bl_options = {"REGISTER", "UNDO"}
