# /// catalog
# title = "A property registered outside `register()`"
# section = "registered"
# status = "partial"
# safeguards = ["typechecker"]
# features = ["properties"]
# note = "The assignment that registers the property outside `register()` is reported as `missing-attribute`."
#
# [future]
# class = "possible"
# note = "Accept assigning a property to a Blender class anywhere in the add-on, while giving the attribute only after `hasattr`."
# ///
"""An add-on can register a property later than `register()`, say in an `update` callback when an option is turned
on. The checker knows the property only where `hasattr` has found it, and reports a plain read elsewhere. It also
reports the assignment that registers the property, which is legal there, as `missing-attribute`: outside
`register()`, `Scene` has no such attribute yet."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.props import BoolProperty, IntProperty
from bpy.types import PropertyGroup, Scene

bl_info = {
    "name": "Catalog: a property registered outside register()",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


def enable_counter(self, context):
    # gap: the registration outside `register()` is reported
    bpy.types.Scene.on_demand_count = IntProperty()


class ON_DEMAND_PROPERTY_Settings(PropertyGroup):
    counting: BoolProperty(update=enable_counter)


def example(scene: Scene) -> None:
    if hasattr(scene, "on_demand_count"):
        assert_type(scene.on_demand_count, int)
    print(scene.on_demand_count)  # ty: ignore[missing-attribute]


def register():
    bpy.utils.register_class(ON_DEMAND_PROPERTY_Settings)


def unregister():
    bpy.utils.unregister_class(ON_DEMAND_PROPERTY_Settings)
