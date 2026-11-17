"""A sub-panel in another module of the add-on than its parent: the parent is found by idname in the add-on."""

from typing import assert_type

from bpy.types import Object, Panel


class NAR_REACH_PT_far(Panel):
    bl_label = "Far"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reach"
    bl_parent_id = "NAR_REACH_PT_parent"

    def draw(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-poll]
