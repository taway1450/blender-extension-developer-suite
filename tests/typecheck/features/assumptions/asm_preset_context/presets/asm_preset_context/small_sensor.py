from typing import assert_type

import bpy
from bpy.types import Camera, Object

camera = bpy.context.camera  # ty: ignore[blender-assumed-preset-context]
assert_type(camera, Camera)
camera.sensor_width = 13.2
camera.sensor_fit = 'HORIZONTAL'
bpy.context.object.name = "Camera"  # ty: ignore[blender-assumed-preset-context]
bpy.context.scene.render.fps = 24  # ty: ignore[blender-assumed-context-member]

if bpy.context.active_object is not None:  # tested for None only: not reported
    print(bpy.context.active_object.name)


def later() -> None:
    assert_type(bpy.context.object, Object | None)  # bare-ok: a function of the preset may run elsewhere
