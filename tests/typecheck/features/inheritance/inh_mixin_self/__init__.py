"""Feature test: self in mixin methods, typed by the mixin's users in another module (mixins.py)."""

import unittest

import bpy
from bpy.types import Menu, Operator, Panel

from .mixins import DrawnMixin, MadeMixin, OperatorMixin, PanelMixin, SharedMixin, TestCaseMixin


class INH_MIXIN_SELF_PT_first(PanelMixin, Panel):
    bl_label = "Mixin self first"

    def draw(self, context):
        self.draw_common(context)


class INH_MIXIN_SELF_PT_second(PanelMixin, Panel):
    bl_label = "Mixin self second"

    def draw(self, context):
        self.draw_common(context)


class INH_MIXIN_SELF_OT_finish(OperatorMixin, Operator):
    bl_idname = "inh_mixin_self.finish"
    bl_label = "Finish"

    def execute(self, context):
        return self.finish(context)


class INH_MIXIN_SELF_PT_drawn(DrawnMixin, Panel):
    bl_label = "Drawn panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        self.draw_title(context)


class INH_MIXIN_SELF_MT_drawn(DrawnMixin, Menu):
    bl_label = "Drawn menu"

    def draw(self, context):
        self.draw_title(context)


class INH_MIXIN_SELF_PT_shared(SharedMixin, Panel):
    bl_label = "Shared panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        self.draw_title(context)


class INH_MIXIN_SELF_OT_shared(SharedMixin, Operator):
    bl_idname = "inh_mixin_self.shared"
    bl_label = "Shared operator"

    def execute(self, context):
        self.draw_title(context)
        return {"FINISHED"}


class CubeTest(TestCaseMixin, unittest.TestCase):
    """Never run: it gives TestCaseMixin a user."""

    def test_cube(self) -> None:
        self.check_cube()


class CubeAgainTest(TestCaseMixin, unittest.TestCase):
    def test_cube(self) -> None:
        self.check_cube()


def made_panels():
    for index in range(2):
        yield type(f"INH_MIXIN_SELF_PT_made_{index}", (MadeMixin, Panel), {
            "bl_label": f"Made {index}",
            "bl_space_type": "PROPERTIES",
            "bl_region_type": "WINDOW",
            "bl_context": "object",
        })


classes = (INH_MIXIN_SELF_PT_first, INH_MIXIN_SELF_PT_second, INH_MIXIN_SELF_OT_finish, INH_MIXIN_SELF_PT_drawn,
           INH_MIXIN_SELF_MT_drawn, INH_MIXIN_SELF_PT_shared, INH_MIXIN_SELF_OT_shared, *made_panels())
register, unregister = bpy.utils.register_classes_factory(classes)
