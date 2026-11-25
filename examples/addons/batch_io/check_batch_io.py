"""The types the add-on's code relies on. Blender never imports this file (see ../README.md)."""

from __future__ import annotations

from typing import Literal, assert_type

import bpy
from bpy.types import Context, KeyMap, Object, Scene

from .settings import BatchIOPreferences, BatchSettings, ObjectExportSettings


def registered_properties(scene: Scene, ob: Object) -> None:
    assert_type(scene.batch_io, BatchSettings)
    assert_type(ob.batch_io, ObjectExportSettings)
    assert_type(scene.batch_io.file_format, Literal["OBJ", "STL", "GLTF"])
    # The items are a tuple that unpacks another one: `(("SCENE", ...), *FORMATS)`.
    # demo: later/enum-items-unpacked
    assert_type(ob.batch_io.file_format, Literal["SCENE", "OBJ", "STL", "GLTF"])


def another_addon(scene: Scene, ob: Object) -> None:
    # The manifest's `[tool.blender] uses` names Scatter Tools, so its registrations are known here.
    # demo: registration_checks
    assert_type(ob.is_scatter_copy, bool)
    assert_type(scene.scatter_tools.count, int)
    # Legacy Renamer is not named there.
    scene.legacy_renamer  # ty: ignore[missing-attribute]


def preferences(context: Context) -> None:
    prefs = context.preferences.addons[__package__].preferences
    assert_type(prefs, BatchIOPreferences)


def operator_calls() -> None:
    # A category of the add-on's own, and properties inherited from `AddPresetBase`, a class of a startup
    # module, which the builtin stubs do not have.
    # demo: later/startup-modules-in-builtin-stubs
    bpy.ops.batch_io.object_preset_add(name="Print", remove_active=False)
    bpy.ops.batch_io.object_preset_add(remove=True)  # ty: ignore[no-matching-overload]
    # A macro takes the properties of each step.
    # demo: operator_calls
    bpy.ops.object.batch_io_apply_and_export(
        OBJECT_OT_transform_apply={"location": False},
        EXPORT_SCENE_OT_batch_io={"use_selection": True},
    )
    bpy.ops.object.batch_io_apply_and_export(
        EXPORT_SCENE_OT_batch_io={"selection": True}  # ty: ignore[invalid-argument-type, unknown-typed-dict-constructor-key]
    )


def overridden_context(context: Context, ob: Object) -> None:
    assert_type(context.active_object, Object | None)
    with context.temp_override(active_object=ob):
        # demo: context_members
        assert_type(context.active_object, Object)


def keymap_item(keymap: KeyMap) -> None:
    # The properties of a key map item are those of the operator it names.
    # demo: operator_properties
    item = keymap.keymap_items.new("export_scene.batch_io", "E", "PRESS")
    assert_type(item.properties.use_selection, bool)
    item.properties.selection = True  # ty: ignore[invalid-assignment]


def callbacks() -> None:
    # A timer function returns the seconds until its next call, or None.
    # demo: bpy_symbols
    bpy.app.timers.register(lambda: "soon")  # ty: ignore[invalid-argument-type]
    bpy.app.handlers.save_post.append("not a function")  # ty: ignore[invalid-argument-type]

    # Blender passes a save handler the file's path, but the parameters of a handler have no type.
    def after_save(filepath, *_):
        # demo: later/handler-callback-types
        assert_type(filepath, str)

    bpy.app.handlers.save_post.append(after_save)
