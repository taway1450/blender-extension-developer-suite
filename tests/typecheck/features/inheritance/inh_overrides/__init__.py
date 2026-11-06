"""Feature test: callbacks written without annotations get their parameter types from the Blender class they
override, by position (Blender passes them positionally, so the names do not matter). Extra parameters Blender
accepts (keyword-only, *args after the required ones, **kwargs) keep their own types, explicit annotations win,
and UIList.draw_item may drop its last three parameters (Blender accepts 7 to 10 positional parameters there).
The assert_type calls in the bodies are no-ops at runtime."""

from collections.abc import Callable
from typing import Any, TypeVar, assert_type, cast

import bpy
from bpy.props import IntProperty
from bpy.types import (Context, Event, Header, Menu, Node, NodeSocket, NodeTree, Operator, OperatorProperties,
                       Panel, UILayout, UIList)


class INH_OVERRIDES_OT_all(Operator):
    bl_idname = "inh_overrides.all"
    bl_label = "All callbacks"

    count: IntProperty()

    @classmethod
    def poll(cls, context):
        assert_type(context, Context)
        return True

    @classmethod
    def description(cls, context, properties):
        assert_type(context, Context)
        assert_type(properties, OperatorProperties)
        return "Every Operator callback"

    def invoke(self, context, event):
        assert_type(context, Context)
        assert_type(event, Event)
        return self.execute(context)

    def execute(self, context):
        assert_type(context, Context)
        return {"FINISHED"}

    def modal(self, context, event):
        assert_type(event, Event)
        return {"PASS_THROUGH"}

    def check(self, context):
        assert_type(context, Context)
        return True

    def draw(self, context):
        assert_type(context, Context)
        self.layout.prop(self, "count")

    def cancel(self, context):
        assert_type(context, Context)


class INH_OVERRIDES_OT_variants(Operator):
    bl_idname = "inh_overrides.variants"
    bl_label = "Signature variants"

    def execute(self, ctx):  # renamed parameter
        assert_type(ctx, Context)
        return {"FINISHED"}

    def invoke(self, context: Context, event):  # partly annotated
        assert_type(event, Event)
        return {"FINISHED"}

    def modal(self, context, event, *args):  # *args after the required parameters
        assert_type(event, Event)
        assert_type(args, tuple[Any, ...])  # bare-ok: *args has no parent parameter to take a type from
        return {"FINISHED"}

    def check(self, context, *, verbose=False):  # keyword-only extra parameter
        assert_type(context, Context)
        assert_type(verbose, bool)
        return verbose

    def draw(self, context, **kwargs):
        assert_type(context, Context)
        assert_type(kwargs, dict[str, Any])  # bare-ok: **kwargs has no parent parameter to take a type from

    def cancel(self, context: "Context"):  # string annotation
        assert_type(context, Context)  # bare-ok: an explicit annotation wins over the parent's


F = TypeVar("F", bound=Callable[..., Any])


def without_extra(function: F) -> F:
    """Typed as giving back the method, but Blender registers the wrapper, which has two parameters."""
    def wrapper(self, context):
        return function(self, context, None)
    return cast(F, wrapper)


class INH_OVERRIDES_OT_decorated(Operator):
    bl_idname = "inh_overrides.decorated"
    bl_label = "Decorated callback"

    @without_extra  # neither classmethod nor staticmethod: the def is not what Blender checks
    def execute(self, context, extra=None):
        return {"FINISHED"}


class INH_OVERRIDES_PT_panel(Panel):
    bl_label = "Overrides"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    @classmethod
    def poll(cls, context):
        assert_type(context, Context)
        return True

    def draw_header(self, context):
        assert_type(context, Context)

    def draw(self, context):
        assert_type(context, Context)
        assert_type(self.layout, UILayout)


class INH_OVERRIDES_MT_menu(Menu):
    bl_label = "Overrides"

    def draw(self, context):
        assert_type(context, Context | None)  # the stubs' type for Menu.draw


class INH_OVERRIDES_HT_header(Header):
    bl_space_type = "VIEW_3D"

    def draw(self, context):
        assert_type(context, Context | None)


class INH_OVERRIDES_UL_full(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        assert_type(layout, UILayout)

    def draw_filter(self, context, layout):
        assert_type(layout, UILayout)


class INH_OVERRIDES_UL_short(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data):  # Blender passes only as many arguments as there are parameters
        assert_type(layout, UILayout)


class INH_OVERRIDES_Tree(NodeTree):
    bl_idname = "INH_OVERRIDES_Tree"
    bl_label = "Overrides tree"
    bl_icon = "NODETREE"

    @classmethod
    def poll(cls, context):
        assert_type(context, Context)
        return True


class INH_OVERRIDES_Socket(NodeSocket):
    bl_idname = "INH_OVERRIDES_Socket"
    bl_label = "Overrides socket"

    def draw(self, context, layout, node, text):
        assert_type(layout, UILayout)
        assert_type(node, Node)
        assert_type(text, str)


class INH_OVERRIDES_Node(Node):
    bl_idname = "INH_OVERRIDES_Node"
    bl_label = "Overrides node"

    @classmethod
    def poll(cls, ntree):
        assert_type(ntree, NodeTree | None)
        return ntree is not None

    def init(self, context):
        assert_type(context, Context)

    def draw_buttons(self, context, layout):
        assert_type(context, Context)
        assert_type(layout, UILayout)

    def draw_label(self):
        return "Overrides"

    def update(self):
        pass


classes = (INH_OVERRIDES_OT_all, INH_OVERRIDES_OT_variants, INH_OVERRIDES_OT_decorated, INH_OVERRIDES_PT_panel,
           INH_OVERRIDES_MT_menu, INH_OVERRIDES_HT_header, INH_OVERRIDES_UL_full, INH_OVERRIDES_UL_short,
           INH_OVERRIDES_Tree, INH_OVERRIDES_Socket, INH_OVERRIDES_Node)
register, unregister = bpy.utils.register_classes_factory(classes)
