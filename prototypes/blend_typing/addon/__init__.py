"""PROTOTYPE, throwaway (prototypes/blend_typing/): approach C, an overlay stub generated from a .blend.

`check_bare` reads `bpy.data` as every script does today. `check_overlay` reads the same names through the stub
generated from `usd_materials_export.blend`, which the script binds under TYPE_CHECKING. Run with
`mise run check:addons main prototype_blend_typing` and compare the revealed types.
"""

from typing import TYPE_CHECKING, reveal_type

import bpy

if TYPE_CHECKING:
    from ._blend.usd_materials_export import data
else:
    data = bpy.data


def check_bare() -> None:
    cube = bpy.data.objects["Cube"]
    reveal_type(cube.data)
    reveal_type(bpy.data.objects.get("Cube"))
    principled = bpy.data.materials["Material"].node_tree.nodes["Principled BSDF"]
    reveal_type(principled)
    reveal_type(principled.inputs["Base Color"])


def check_overlay() -> None:
    cube = data.objects["Cube"]
    reveal_type(cube.data)
    reveal_type(cube.data.vertices)
    reveal_type(data.objects.get("Cube"))
    reveal_type(data.objects.get("Missing"))
    principled = data.materials["Material"].node_tree.nodes["Principled BSDF"]
    reveal_type(principled)
    reveal_type(principled.inputs["Base Color"].default_value)
    reveal_type(data.objects["Missing"])
    data.objects["Cub"]  # a typo: an Object, no error (scripts create data, so a missing key is legal)


def register() -> None:
    pass


def unregister() -> None:
    pass
