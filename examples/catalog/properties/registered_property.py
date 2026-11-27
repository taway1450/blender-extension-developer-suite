# /// catalog
# title = "A property assigned to a Blender class"
# section = "registered"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""`bpy.types.Scene.x = PointerProperty(...)` adds a Registered property to every scene. The checker reads the
assignment wherever the add-on (or here, the script) makes it, and gives the attribute its Value type; `del` removes it
again."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.props import IntProperty, PointerProperty
from bpy.types import PropertyGroup, Scene


class RenderPasses(PropertyGroup):
    count: IntProperty(default=1)


def register() -> None:
    bpy.utils.register_class(RenderPasses)
    bpy.types.Scene.render_passes = PointerProperty(type=RenderPasses)


def unregister() -> None:
    del bpy.types.Scene.render_passes
    bpy.utils.unregister_class(RenderPasses)


def pass_count(scene: Scene) -> int:
    # catalog: hide
    assert_type(scene.render_passes, RenderPasses)
    # catalog: show
    return scene.render_passes.count
