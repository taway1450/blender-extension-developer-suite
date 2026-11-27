# /// catalog
# title = "The `bl_context` of a panel"
# section = "narrowings"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["implied_narrowings"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs type the callback's `context` as `Context | None`, so every read of it is reported, and the narrowing is applied to `active_object` too."
# "fake-bpy-module/5.2" = "These stubs type the callback's `context` as `Context | None`, so every read of it is reported and the narrowing is not applied."
# ///
"""A panel of the Properties editor with `bl_context = "object"` is drawn only in the Object tab, which Blender shows
only while there is an object. So `context.object` is set in its `poll` and `draw`. The checker narrows it and
reports the read as an Implied narrowing. The tab's object is not always the active one, so `active_object` stays
`Object | None`."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Object, Panel


class ObjectNotes(Panel):
    bl_label = "Notes"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-bl-context]
        assert_type(context.active_object, Object | None)
