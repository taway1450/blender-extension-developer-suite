"""Hover over RNA properties: the RNA description should be shown (check:ide; never imported)."""

from __future__ import annotations

from bpy.types import Context, Object, Scene


def object_props(obj: Object) -> None:
    obj.location
    #   ^hover
    #   ^hover-contains "Location of the object"
    obj.parent
    #   ^hover-contains "Parent object"
    obj.data
    #   ^hover-contains "Object data"


def scene_props(scene: Scene) -> None:
    scene.frame_current
    #     ^hover
    #     ^hover-contains "Current frame"


def context_members(context: Context) -> None:
    context.active_object
    #       ^hover
    context.scene
    #       ^hover


def classes(obj: Object) -> None:
    Object
    # ^hover-contains "Object data-block defining an object in a scene"
