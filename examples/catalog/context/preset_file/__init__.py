# /// catalog
# title = "The context of a preset file"
# section = "outside-callbacks"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions"]
# see = ["blender/scripts/startup/bl_operators/presets.py"]
#
# [evidence]
# addon = "assumptions/asm_preset_context"
# rule = "blender-assumed-preset-context"
# lenient = "warn"
# default = "warn"
# strict = "error"
#
# [differs]
# "builtin/5.2" = "In Blender 5.2's builtin stubs `Menu.draw_preset` takes a `Context` and `Menu.draw` a `Context | None`, so assigning one as the other is reported as an incompatible override, and `context.camera` is typed `Camera`, so nothing is assumed."
# "fake-bpy-module/5.2" = "In these stubs `Menu.draw_preset` takes a `Context` and `Menu.draw` a `Context | None`, so assigning one as the other is reported as an incompatible override."
# ///
"""A preset is a Python file that Blender runs with the context of the panel or menu that applies it, so a camera
preset reads `bpy.context.camera` at module level and finds the camera of the Properties editor's camera tab.
Nothing in the file says which panel runs it: the checker takes a module-level read in a file under a `presets`
folder as not `None` and reports it as an Assumption. A read in a function of the preset keeps the stub type."""

import bpy
from bpy.types import Menu


class PRESET_FILE_MT_presets(Menu):
    bl_label = "Camera presets"
    preset_subdir = "preset_file"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


classes = (PRESET_FILE_MT_presets,)
register, unregister = bpy.utils.register_classes_factory(classes)
