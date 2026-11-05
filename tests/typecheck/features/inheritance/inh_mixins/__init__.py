"""Feature test: mixin classes. Blender finds callbacks, bl_ attributes and property annotations anywhere in the
MRO, so for them the order of the bases does not matter (checked in Blender 4.2 and 5.4). It matters for the
methods Blender's own Python base classes define (Operator.as_keywords, Node.poll, Menu.append, ...): a mixin
listed after the Blender base loses to them, silently. That is blender-mixin-order.

A plain mixin's methods have no Blender parent, so their parameters are not typed from one; a base that derives
from the Blender class itself gets the parent's types."""

from typing import Any, assert_type

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import Context, Event, Menu, Node, NodeTree, Operator


class ExecuteMixin:
    bl_options = {"REGISTER", "UNDO"}

    count: IntProperty()

    def execute(self, context):
        assert_type(context, Any)  # no Blender parent: nothing to take the type from  # bare-ok: without a Blender parent the type stays unknown
        return {"FINISHED"}


class LabelMixin(ExecuteMixin):
    label: StringProperty()


class INH_MIXINS_OT_base(Operator):
    """Not registered: a base that is a Blender class, so its overrides are typed from Operator."""

    def invoke(self, context, event):
        assert_type(context, Context)
        assert_type(event, Event)
        return self.execute(context)


class INH_MIXINS_OT_first(LabelMixin, Operator):
    bl_idname = "inh_mixins.first"
    bl_label = "Mixin first"


class INH_MIXINS_OT_last(Operator, LabelMixin):
    bl_idname = "inh_mixins.last"
    bl_label = "Mixin last"


class INH_MIXINS_OT_based(ExecuteMixin, INH_MIXINS_OT_base):
    bl_idname = "inh_mixins.based"
    bl_label = "Blender base"


class PollMixin:
    @classmethod
    def poll(cls, context):
        return True


class INH_MIXINS_OT_poll_last(Operator, PollMixin):
    """Operator defines no poll in Python, so the mixin's poll is used in either order."""

    bl_idname = "inh_mixins.poll_last"
    bl_label = "Poll last"

    def execute(self, context):
        return {"FINISHED"}


class KeywordsMixin:
    def as_keywords(self, *, ignore=()):
        return {}


class INH_MIXINS_OT_keywords_first(KeywordsMixin, Operator):
    bl_idname = "inh_mixins.keywords_first"
    bl_label = "Keywords first"

    def execute(self, context):
        return {"FINISHED"}


class INH_MIXINS_OT_keywords_last(Operator, KeywordsMixin):  # ty: ignore[blender-mixin-order]
    bl_idname = "inh_mixins.keywords_last"
    bl_label = "Keywords last"

    def execute(self, context):
        return {"FINISHED"}


class AppendMixin:
    """Menu (bpy_types._GenericUI) defines append, prepend and remove itself."""

    @classmethod
    def append(cls, draw_func):
        print("never called on INH_MIXINS_MT_append_last")


class INH_MIXINS_MT_append_first(AppendMixin, Menu):
    bl_label = "Append first"

    def draw(self, context):
        pass


class INH_MIXINS_MT_append_last(Menu, AppendMixin):  # ty: ignore[blender-mixin-order]
    bl_label = "Append last"

    def draw(self, context):
        pass


class INH_MIXINS_Tree(NodeTree):
    bl_idname = "INH_MIXINS_Tree"
    bl_label = "Mixin tree"
    bl_icon = "NODETREE"


class INH_MIXINS_OtherTree(NodeTree):
    bl_idname = "INH_MIXINS_OtherTree"
    bl_label = "Other tree"
    bl_icon = "NODETREE"


class TreePollMixin:
    @classmethod
    def poll(cls, ntree):
        return ntree is not None and ntree.bl_idname == "INH_MIXINS_Tree"


class INH_MIXINS_NodeFirst(TreePollMixin, Node):
    bl_idname = "INH_MIXINS_NodeFirst"
    bl_label = "Mixin first"


class INH_MIXINS_NodeLast(Node, TreePollMixin):  # ty: ignore[blender-mixin-order]
    bl_idname = "INH_MIXINS_NodeLast"
    bl_label = "Mixin last"


classes = (INH_MIXINS_OT_first, INH_MIXINS_OT_last, INH_MIXINS_OT_based, INH_MIXINS_OT_poll_last,
           INH_MIXINS_OT_keywords_first, INH_MIXINS_OT_keywords_last, INH_MIXINS_MT_append_first,
           INH_MIXINS_MT_append_last, INH_MIXINS_Tree, INH_MIXINS_OtherTree, INH_MIXINS_NodeFirst,
           INH_MIXINS_NodeLast)
register, unregister = bpy.utils.register_classes_factory(classes)
