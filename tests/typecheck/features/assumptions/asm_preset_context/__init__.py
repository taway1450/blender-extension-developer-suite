"""Feature test: a preset is a Python file that Blender runs with the context of the panel or menu that applies it
(`script.execute_preset` from a preset menu, `bpy.utils.execute_preset`), so a camera preset reads
`bpy.context.camera` at module level and finds the camera of the Properties editor's camera tab. Nothing in the file
says which panel runs it, so the checker takes such a module-level read in a file under a `presets` folder as not None
and reports it under blender-assumed-preset-context; `scene` and its siblings stay blender-assumed-context-member.
A read in a function of the preset, and in a file outside `presets`, keeps the stub type. The presets themselves are
in presets/asm_preset_context/."""

import bpy
from bpy.types import Camera, Context, Menu


def camera_of(context: Context) -> Camera | None:
    return context.camera  # outside a `presets` folder: not assumed


class ASM_PRESET_CONTEXT_MT_presets(Menu):
    bl_label = "Camera presets"
    preset_subdir = "asm_preset_context"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


classes = (ASM_PRESET_CONTEXT_MT_presets,)
register, unregister = bpy.utils.register_classes_factory(classes)
