"""Not an add-on (no manifest, no bl_info): a script like Blender's doc examples, templates and tests, which defines
its own operators and calls them, through bpy.ops and by idname (layout.operator), as an add-on does. An operator may
be defined at module level or inside a function, as a test defines one in its test method. Another script's
operators stay unknown to it. The assert_type calls are no-ops at runtime."""

import unittest
from typing import Literal, TypeAlias, assert_type

import bpy
from bpy.props import IntProperty

Result: TypeAlias = set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]


class OPCALL_SCRIPT_OWN_OT_simple(bpy.types.Operator):
    bl_idname = "opcall_script_own.simple"
    bl_label = "Simple"

    count: IntProperty()

    def execute(self, context):
        return {"FINISHED"}


class OPCALL_SCRIPT_OWN_PT_panel(bpy.types.Panel):
    bl_label = "Script"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        props = self.layout.operator("opcall_script_own.simple")
        assert_type(props.count, int)
        props.count = 2


def run() -> None:
    assert_type(bpy.ops.opcall_script_own.simple(count=2), Result)
    bpy.ops.opcall_script_own.simple(count="2")  # ty: ignore[invalid-argument-type]


class OpcallScriptOwnTest(unittest.TestCase):
    def test_nested(self) -> None:
        class OPCALL_SCRIPT_OWN_OT_nested(bpy.types.Operator):
            bl_idname = "opcall_script_own.nested"
            bl_label = "Nested"

            def execute(self, context):
                return {"FINISHED"}

        bpy.utils.register_class(OPCALL_SCRIPT_OWN_OT_nested)
        assert_type(bpy.ops.opcall_script_own.nested(), Result)
        bpy.utils.unregister_class(OPCALL_SCRIPT_OWN_OT_nested)


if __name__ == "__main__":
    bpy.utils.register_class(OPCALL_SCRIPT_OWN_OT_simple)
    run()
