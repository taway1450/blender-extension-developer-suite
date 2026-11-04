"""What the editor shows for properties registered on Blender's classes (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

from bpy.types import Object, Scene


def hover(scene: Scene, obj: Object) -> None:
    scene.reg_int
    #     ^hover
    #     ^hover-contains "int"
    scene.reg_mode
    #     ^hover-contains "Literal"
    obj.reg_id
    #   ^hover-contains "int"


def completion(scene: Scene) -> None:
    scene.reg_
    #         ^completion reg_int reg_mode reg_group reg_items reg_object reg_id
