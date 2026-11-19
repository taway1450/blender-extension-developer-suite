"""PROTOTYPE, throwaway (prototypes/blend_typing/): an add-on over the Sculpting template's ``startup.blend``.

``startup.blend`` is a copy of Blender's own ``bl_app_templates_system/Sculpting/startup.blend``, saved by an older
Blender than the one that loads it, so a reader of the file (approach B) and Blender's loaded state (approach G) can
disagree: Blender versions the file when it loads it. The probe's summary lists where they do.
"""

from typing import TYPE_CHECKING, reveal_type

import bpy

if TYPE_CHECKING:
    from ._blend.startup import data
else:
    data = bpy.data


def check_bare() -> None:
    reveal_type(bpy.data.objects["Camera"].data)
    reveal_type(bpy.data.materials["Material"].node_tree.nodes["Principled BSDF"].inputs["Base Color"])


def check_overlay() -> None:
    reveal_type(data.objects["Camera"].data)
    principled = data.materials["Material"].node_tree.nodes["Principled BSDF"]
    reveal_type(principled.inputs["Base Color"])
    reveal_type(principled.inputs["Emission Color"])


def register() -> None:
    pass


def unregister() -> None:
    pass
