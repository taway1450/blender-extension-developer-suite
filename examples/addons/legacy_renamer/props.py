"""The renamer's settings, stored on the scene."""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)

# Blender does not keep the strings of dynamic enum items alive, so the last list stays here.
_target_items = []


def target_items(self, context):
    _target_items[:] = [
        ("SELECTED", "Selected", "The selected objects"),
        ("ALL", "All", "Every object of the scene"),
    ]
    _target_items.extend(
        (collection.name, collection.name, "The objects of this collection")
        for collection in bpy.data.collections
    )
    return _target_items


class RenameRule(bpy.types.PropertyGroup):
    find: StringProperty(name="Find", description="Regular expression to look for")
    replace: StringProperty(name="Replace")
    enabled: BoolProperty(name="Enabled", default=True)


class RenamerSettings(bpy.types.PropertyGroup):
    prefix: StringProperty(
        name="Prefix", description="New base name; empty keeps the old names"
    )
    start: IntProperty(name="Start", default=1, min=0)
    padding: IntProperty(name="Padding", default=3, min=1, max=6)
    # demo: properties
    target: EnumProperty(name="Target", items=target_items)
    case: EnumProperty(
        name="Case",
        items=[
            ("KEEP", "Keep", "Leave the case as it is"),
            ("UPPER", "Upper", "Upper case"),
            ("LOWER", "Lower", "Lower case"),
        ],
        default="KEEP",
    )
    tag_collections: BoolProperty(
        name="Tag Collections",
        description="Give the collections of the renamed objects a color tag",
    )
    rules: CollectionProperty(type=RenameRule)
    active_rule: IntProperty()
