# /// catalog
# title = "Class names Blender requires"
# section = "lint"
# status = "handled"
# safeguards = ["linter-profile"]
# see = ["blender/source/blender/makesrna/intern/rna_ui.cc"]
#
# [lint]
# rule = "N801"
# default = "reports"
# profile = "silent"
# ///
"""A panel's or menu's `bl_idname` defaults to its class name, and Blender wants `_PT_` or `_MT_` in it, so these
classes are named `CATEGORY_PT_name`; operators follow the same convention, `CATEGORY_OT_name`. pep8-naming's `N801`
wants CapWords and reports each such name; the linter profile lists Blender's patterns in its `ignore-names`."""

from bpy.types import Operator, Panel


class SIMPLE_OT_run(Operator):
    bl_idname = "simple.run"
    bl_label = "Run"


class SIMPLE_PT_tools(Panel):
    bl_label = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
