# /// catalog
# title = "An edit-mode mesh's data"
# section = "stale-data"
# status = "not-handled"
# blender-docs = ["info_gotchas_meshes", "info_gotchas_crashes"]
#
# [future]
# class = "not-checkable"
# note = "Whether the mesh is in Edit Mode is known only while Blender runs."
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs have `BMVertSeq.__iter__` return the sequence itself, which has no `__next__`, so iterating the vertices is reported."
# ///
"""In Edit Mode a mesh has its own edit data, written back to the mesh only when Blender leaves Edit Mode: the mesh's
`vertices` are out of sync until then. Read the edit mesh with `bmesh.from_edit_mesh` instead. Switching the mode
also re-allocates the mesh's data, so a `vertices` or `polygons` read before the switch is stale after it."""

import bmesh
from bpy.types import Mesh


def selected_count(mesh: Mesh) -> int:
    if mesh.is_editmode:
        edit = bmesh.from_edit_mesh(mesh)
        return sum(v.select for v in edit.verts)
    return sum(v.select for v in mesh.vertices)
