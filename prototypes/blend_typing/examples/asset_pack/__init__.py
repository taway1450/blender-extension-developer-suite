"""PROTOTYPE, throwaway (prototypes/blend_typing/): an asset add-on that appends from the .blend it ships.

`append` brings the material, node group and object of ``assets.blend`` into the open file; the `check_*` functions
read them the way such an add-on does. `check_bare` reads ``bpy.data`` as every script does today; `check_overlay`
reads the same names through the overlay generated from ``assets.blend`` (approach C), which the add-on binds under
TYPE_CHECKING. Approach A types ``check_bare`` without the overlay (``reader_check.py``).
"""

import os
from typing import TYPE_CHECKING, reveal_type

import bpy

if TYPE_CHECKING:
    from ._blend.assets import data
else:
    data = bpy.data

ASSETS = os.path.join(os.path.dirname(__file__), "assets.blend")


def append() -> None:
    with bpy.data.libraries.load(ASSETS) as (source, target):
        target.materials = ["Rust"]
        target.node_groups = ["Scatter Points"]
        target.objects = ["Rock"]


def check_bare() -> None:
    principled = bpy.data.materials["Rust"].node_tree.nodes["Principled BSDF"]
    reveal_type(principled)
    reveal_type(principled.inputs["Base Color"])
    reveal_type(bpy.data.node_groups["Scatter Points"])
    rock = bpy.data.objects["Rock"]
    reveal_type(rock.data)
    reveal_type(rock.modifiers["Bevel"])


def check_overlay() -> None:
    principled = data.materials["Rust"].node_tree.nodes["Principled BSDF"]
    reveal_type(principled)
    reveal_type(principled.inputs["Base Color"])
    reveal_type(principled.inputs["Base Color"].default_value)
    noise = data.materials["Rust"].node_tree.nodes["Rust Noise"]
    reveal_type(noise.outputs["Color"])
    scatter = data.node_groups["Scatter Points"]
    reveal_type(scatter)
    reveal_type(scatter.nodes["Distribute Points on Faces"].inputs["Density"])
    rock = data.objects["Rock"]
    reveal_type(rock.data)
    reveal_type(rock.type)
    reveal_type(data.objects.get("Rock"))
    reveal_type(data.objects.get("Boulder"))  # not in the file: the stubs' `Object | None`


def register() -> None:
    pass


def unregister() -> None:
    pass
