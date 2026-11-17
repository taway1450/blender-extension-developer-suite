"""Hover shows the subclass a constructor's Type tag argument names."""

from bpy.types import Object


def helper(ob: Object):
    con = ob.constraints.new('COPY_LOCATION')
    #^hover
