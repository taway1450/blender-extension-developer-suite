# /// catalog
# title = "A mixin listed after the Blender base"
# section = "mixins"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["inheritance"]
#
# [runtime]
# register = "ok"
#
# [[runtime.probe]]
# code = "addon.MIXIN_ORDER_OT_last.as_keywords.__qualname__"
# expect = "Operator.as_keywords"
# reason = "the Operator base's own method wins over the mixin's"
# ///
"""Blender finds callbacks, `bl_*` variables and property annotations anywhere among a class's bases, so for them the
order does not matter. It matters for the helper methods Blender's own Python base classes define
(`Operator.as_keywords`, `Menu.append`): a mixin listed after the Blender base loses to them, without a word. The
checker reports the order."""

import bpy
from bpy.types import Operator

bl_info = {
    "name": "Catalog: a mixin listed after the Blender base",
    "author": "Blender Extension Developer Suite",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "category": "Development",
}


class KeywordsMixin:
    def as_keywords(self, *, ignore=()):
        return {"mode": "mixin"}


class MIXIN_ORDER_OT_first(KeywordsMixin, Operator):
    bl_idname = "mixin_order.first"
    bl_label = "Mixin first"

    def execute(self, context):
        return {"FINISHED"}


class MIXIN_ORDER_OT_last(Operator, KeywordsMixin):  # ty: ignore[blender-mixin-order]
    bl_idname = "mixin_order.last"
    bl_label = "Mixin last"

    def execute(self, context):
        return {"FINISHED"}


classes = (MIXIN_ORDER_OT_first, MIXIN_ORDER_OT_last)
register, unregister = bpy.utils.register_classes_factory(classes)
