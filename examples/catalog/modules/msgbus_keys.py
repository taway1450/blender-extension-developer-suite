# /// catalog
# title = "msgbus keys"
# section = "callbacks"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["api_types"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type `key` as a `Property`, a `Struct` or a `(Struct, str)` pair: a `Vector` value is none of them, nor is a pair with a class, so the first two calls are reported."
# "fake-bpy-module/5.2" = "These stubs type `key` as a `Property`, a `Struct` or a `(Struct, str)` pair: a `Vector` value is none of them, nor is a pair with a class, so the first two calls are reported."
# ///
"""`bpy.msgbus.subscribe_rna` calls a function when a property changes. Its `key` is a property value with an owner,
such as `ob.location`, or a pair of a struct type and a property name, for that property on every struct of the type.
The stubs accept both forms and report a key of another kind."""

import bpy
from bpy.types import Object


def example(ob: Object) -> None:
    bpy.msgbus.subscribe_rna(key=ob.location, owner=ob, args=(), notify=print)
    bpy.msgbus.subscribe_rna(key=(Object, "location"), owner=ob, args=(), notify=print)
    bpy.msgbus.subscribe_rna(key="location", owner=ob, args=(), notify=print)  # ty: ignore[invalid-argument-type]
