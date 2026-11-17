"""Feature test: an area's type names its active space (a Type tag).

An area's first space is the space of the area's type (ED_area_newspace puts the new space first, and Area.type is
spacetype of that first space), so after area.type == 'VIEW_3D' on any area, area.spaces.active is a SpaceView3D. This
is ordinary narrowing of a Type tag test, so it is not reported.

The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Operator, Screen, Space, SpaceClipEditor, SpaceImageEditor, SpaceNodeEditor, SpaceView3D


def setup_spaces(screen: Screen) -> None:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            assert_type(space, SpaceView3D)  # oracle-skip: narrowed by the area's Type tag
            space.shading.type = "MATERIAL"
        elif area.type in {"IMAGE_EDITOR", "CLIP_EDITOR"}:
            assert_type(area.spaces.active, SpaceImageEditor | SpaceClipEditor)  # oracle-skip: a Type tag
        else:
            assert_type(area.spaces.active, Space | None)  # bare-ok: no test names the type here


def first_node_editor(screen: Screen):
    for area in screen.areas:
        if area.type != "NODE_EDITOR":
            continue
        assert_type(area.spaces.active, SpaceNodeEditor)  # oracle-skip: narrowed after the early continue
    shader = (a for a in screen.areas if a.type == "NODE_EDITOR" and assert_type(a.spaces.active, SpaceNodeEditor).tree_type == "ShaderNodeTree")  # oracle-skip: a Type tag before `and`
    return next(shader, None)


class PTR_AREA_OT_views(Operator):
    bl_idname = "ptr_area.views"
    bl_label = "Views"

    def execute(self, context):
        views = [area.spaces.active for area in bpy.data.screens["Layout"].areas if area.type == "VIEW_3D"]
        assert_type(views, list[SpaceView3D])  # oracle-skip: a Type tag in the comprehension's condition
        return {"FINISHED"}


classes = (PTR_AREA_OT_views,)
register, unregister = bpy.utils.register_classes_factory(classes)
