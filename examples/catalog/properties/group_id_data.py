# /// catalog
# title = "The data-block that owns a group"
# section = "registered"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["properties"]
# ///
"""Every `PropertyGroup` instance knows the data-block it is stored on, `id_data`. The stubs can only say `ID`; the
checker narrows it to the types the group is registered on, here `Object`."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.props import FloatProperty, PointerProperty
from bpy.types import Object, PropertyGroup


class Physics(PropertyGroup):
    mass: FloatProperty(default=1.0)


def register() -> None:
    bpy.utils.register_class(Physics)
    bpy.types.Object.physics = PointerProperty(type=Physics)


def owner_name(physics: Physics) -> str:
    # catalog: hide
    assert_type(physics.id_data, Object)
    # catalog: show
    return physics.id_data.name
