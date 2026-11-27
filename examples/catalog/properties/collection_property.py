# /// catalog
# title = "Collection properties"
# section = "value-types"
# status = "handled"
# handled-by = ["typechecker"]
# features = ["properties"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs have no generic `bpy_prop_collection_idprop`, so the Value type cannot be written."
# ///
"""A `CollectionProperty` holds a list of `PropertyGroup` instances that Blender owns: `add()` creates one and returns
it, and items are looked up by index or by their `name`."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.props import CollectionProperty, StringProperty
from bpy.types import PropertyGroup, bpy_prop_collection_idprop


class Tag(PropertyGroup):
    colour: StringProperty()


class Library(PropertyGroup):
    tags: CollectionProperty(type=Tag)


def example(library: Library) -> None:
    assert_type(library.tags, bpy_prop_collection_idprop[Tag])
    assert_type(library.tags.add(), Tag)
