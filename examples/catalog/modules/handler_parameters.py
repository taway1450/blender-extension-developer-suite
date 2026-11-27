# /// catalog
# title = "A handler's parameters"
# section = "callbacks"
# status = "not-handled"
# features = ["bpy_symbols"]
# later = "handler-callback-types"
# blender-docs = ["bpy.app.handlers"]
#
# [future]
# class = "planned"
# note = "Type a handler's parameters by the list it is appended to: a save handler's file path as `str`."
# tracked = "later/handler-callback-types"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs type a `save_pre` handler as `(str) -> None`, so `on_save`, which takes two parameters, is reported."
# ///
"""A function in `bpy.app.handlers` gets parameters that depend on the list: a frame-change handler the scene and the
depsgraph, a save handler the file path. The stubs check that a handler takes parameters, but nothing types them from
the list yet, so they are unknown in the function and a wrong use of one is not reported; the marked line shows the
result a check would give."""

import bpy


def on_save(filepath, _):
    # gap: the file path is not typed as `str`
    print(filepath.upper_case())  # ty: ignore[missing-attribute]


def register() -> None:
    bpy.app.handlers.save_pre.append(on_save)
