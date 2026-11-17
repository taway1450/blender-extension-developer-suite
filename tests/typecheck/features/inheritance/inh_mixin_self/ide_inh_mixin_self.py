"""What the editor shows for self in a mixin (check:ide; never imported)."""

from bpy.types import Panel

from .mixins import PanelMixin


class HoverMixin(PanelMixin):
    def draw_hover(self, context):
        self.layout
        #    ^hover
        self.bl_label
        #    ^hover-contains "str"
        self.lay
        #       ^completion layout


class INH_MIXIN_SELF_PT_hover(HoverMixin, Panel):
    bl_label = "Hover"

    def draw(self, context):
        self.draw_hover(context)
