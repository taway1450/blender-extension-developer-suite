"""What the editor shows for a math or array property that takes a sequence on assignment (check:ide; never imported):
hovering it still shows the type it reads as."""

from __future__ import annotations

from bpy.types import Image, Object


def hover(ob: Object, image: Image) -> None:
    ob.location
    #  ^hover
    #  ^hover-contains "Vector"
    ob.matrix_world
    #  ^hover-contains "Matrix"
    image.pixels
    #     ^hover
    #     ^hover-contains "bpy_prop_array[float]"
