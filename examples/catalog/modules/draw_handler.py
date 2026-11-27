# /// catalog
# title = "A draw callback"
# section = "drawing"
# status = "partial"
# safeguards = ["stub-generator"]
# features = ["api_types"]
# blender-docs = ["bpy.types.Space"]
# note = "The region and the draw stage of `draw_handler_add` are plain strings: a misspelt one is not reported."
#
# [future]
# class = "possible"
# note = "Type the region and the draw stage of `draw_handler_add` as their enums in the stubs."
# ///
"""`SpaceView3D.draw_handler_add` makes Blender call a function each time it draws the 3D Viewport, with `gpu` to draw
in it. The stubs type the `gpu` module, but the region and the draw stage are plain strings, so a misspelt one is not
reported; the marked line shows the result a check would give."""

# catalog: hide
from typing import assert_type

# catalog: show
import gpu
from bpy.types import SpaceView3D
from gpu.types import GPUShader

SHADER = gpu.shader.from_builtin("UNIFORM_COLOR")
assert_type(SHADER, GPUShader)


def draw_dot() -> None:
    SHADER.bind()


def register() -> None:
    SpaceView3D.draw_handler_add(draw_dot, (), "WINDOW", "POST_VIEW")
    # gap: the draw stage is a plain string
    SpaceView3D.draw_handler_add(draw_dot, (), "WINDOW", "POST_VEIW")  # ty: ignore[invalid-argument-type]
