"""What the editor shows for overrides without annotations (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

from bpy.types import Context, Operator, UIList

from . import INH_OVERRIDES_OT_variants


class IDE_OT_hover(Operator):
    bl_idname = "inh_overrides.ide_hover"
    bl_label = "Hover"

    def invoke(self, ctx, event):
        ctx
        # ^hover-contains "Context"
        event.mouse_x
        #     ^completion mouse_x
        return {"FINISHED"}


class IDE_UL_hover(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data):
        layout
        # ^hover-contains "UILayout"


def signature(op: INH_OVERRIDES_OT_variants, context: Context) -> None:
    op.execute(context)
    #          ^signature
