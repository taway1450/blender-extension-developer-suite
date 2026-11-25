"""The types the add-on's code relies on. Blender never imports this file (see ../README.md)."""

from typing import Literal, assert_type

import bpy
from bpy.types import Context, Scene, bpy_prop_collection_idprop

from . import LegacyRenamerPreferences
from .props import RenamerSettings, RenameRule


def registered_properties(scene: Scene) -> None:
    # demo: registration
    assert_type(scene.legacy_renamer, RenamerSettings)
    # The items of `target` come from a function, so any string can be one.
    assert_type(scene.legacy_renamer.target, str)
    assert_type(scene.legacy_renamer.case, Literal["KEEP", "UPPER", "LOWER"])
    assert_type(scene.legacy_renamer.rules, bpy_prop_collection_idprop[RenameRule])


def preferences(context: Context) -> None:
    # demo: addon_preferences
    assert_type(
        context.preferences.addons["legacy_renamer"].preferences,
        LegacyRenamerPreferences,
    )
    assert_type(context.preferences.addons["legacy_renamer"].preferences.separator, str)


def operator_calls() -> None:
    bpy.ops.import_scene.legacy_rules(filepath="rules.csv")
    # `filter_glob = StringProperty(...)` is no property, so the operator has no such argument.
    bpy.ops.import_scene.legacy_rules(filter_glob="*.txt")  # ty: ignore[no-matching-overload]
