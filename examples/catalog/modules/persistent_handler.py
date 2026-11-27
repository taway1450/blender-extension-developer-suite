# /// catalog
# title = "`@persistent`"
# section = "callbacks"
# status = "handled"
# safeguards = ["stub-generator"]
# features = ["bpy_symbols"]
# blender-docs = ["bpy.app.handlers"]
#
# [differs]
# "builtin/5.2" = "Blender 5.2's builtin stubs do not keep the signature through `persistent`, so the wrong call is not reported."
# ///
"""Blender removes the handlers when it loads another file, except those marked `@persistent`. The decorator returns
the function as it is, and the stubs type it so: the function keeps its signature, and a call with the wrong
arguments is still reported. A handler that takes no parameters is reported, since Blender passes some."""

from bpy.app.handlers import persistent

import bpy


@persistent
def on_load(filepath, _):
    print(filepath)


def no_arguments():
    pass


def register() -> None:
    bpy.app.handlers.load_post.append(on_load)
    bpy.app.handlers.load_post.append(no_arguments)  # ty: ignore[invalid-argument-type]
    on_load(1)  # ty: ignore[missing-argument]
