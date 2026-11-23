"""PROTOTYPE, throwaway (prototypes/blend_typing/): an add-on whose code runs against the scene it ships.

Like an application template, the add-on's operators assume the objects of ``startup.blend``: the camera, the key
light and the cube. `check_bare` reads them as every script does today; `check_overlay` through the overlay generated
from ``startup.blend`` (approach C). Approach A types ``check_bare`` without the overlay (``reader_check.py``).
"""

from typing import TYPE_CHECKING, reveal_type

import bpy

if TYPE_CHECKING:
    from ._blend.startup import data
else:
    data = bpy.data


def check_bare() -> None:
    camera = bpy.data.objects["Camera"]
    reveal_type(camera.data)
    light = bpy.data.objects.get("Key Light")
    reveal_type(light)
    cube = bpy.data.objects["Cube"]
    reveal_type(cube.modifiers["Subdivision"])
    reveal_type(bpy.data.materials["Ground"].node_tree.nodes["Principled BSDF"])


def check_overlay() -> None:
    camera = data.objects["Camera"]
    reveal_type(camera.data)
    reveal_type(camera.data.lens)
    light = data.objects.get("Key Light")
    reveal_type(light)
    reveal_type(light.data)
    cube = data.objects["Cube"]
    reveal_type(cube.data.vertices)
    reveal_type(cube.modifiers["Subdivision"])
    reveal_type(cube.modifiers["Subdivision"].levels)
    principled = data.materials["Ground"].node_tree.nodes["Principled BSDF"]
    reveal_type(principled.inputs["Roughness"])


def register() -> None:
    pass


def unregister() -> None:
    pass
