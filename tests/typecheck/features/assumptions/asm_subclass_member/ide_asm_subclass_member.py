"""Hover shows the union of the subclass declarations a read through a refined base is typed as."""

from bpy.types import Object


def helper(ob: Object):
    ob.constraints[0].target  # ty: ignore[blender-assumed-subclass-member]
    #                 ^hover
