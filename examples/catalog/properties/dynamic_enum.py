# /// catalog
# title = "Enum properties with dynamic items"
# section = "value-types"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["properties"]
# ///
"""When `items` is a function, Blender calls it each time it needs the list, so the identifiers are only known at
runtime. The value is a `str`. Blender may call the function with `context=None`, and the stubs say so: a callback
annotated with `Context` alone is reported where it is passed."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.props import EnumProperty
from bpy.types import Context, PropertyGroup


def camera_items(self, context: Context | None):
    return [(o.name, o.name, "") for o in bpy.data.objects if o.type == "CAMERA"]


def light_items(self, context: Context):
    return [(o.name, o.name, "") for o in bpy.data.objects if o.type == "LIGHT"]


class Settings(PropertyGroup):
    camera: EnumProperty(items=camera_items)
    light: EnumProperty(items=light_items)  # ty: ignore[invalid-argument-type]


def example(settings: Settings) -> None:
    assert_type(settings.camera, str)
