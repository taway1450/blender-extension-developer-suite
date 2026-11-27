# /// catalog
# title = "`context.temp_override`"
# section = "calls"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["context_members"]
# ///
"""Inside a `with context.temp_override(member=value)` block the checker gives the member the value's type. An operator
acts on the context it is called in, and `temp_override` replaces members for the length of the block, to run an
operator on another object or in another editor."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy
from bpy.types import Context, Object


def edit(context: Context, ob: Object) -> None:
    with context.temp_override(object=ob, active_object=ob):
        assert_type(context.object, Object)
        bpy.ops.object.mode_set(mode="EDIT")
