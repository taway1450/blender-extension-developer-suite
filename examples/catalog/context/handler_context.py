# /// catalog
# title = "`bpy.context` in an application handler"
# section = "outside-callbacks"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["assumptions"]
# ///
"""A function in `bpy.app.handlers` runs when Blender reaches that moment: after a file loads, before a frame
changes. Its `bpy.context.scene` is the loaded file's scene, set in ordinary use but not guaranteed. The checker takes
it as set and reports the read as an Assumption."""

import bpy
from bpy.app.handlers import persistent


@persistent
def on_load(filepath, _):
    print(bpy.context.scene.name)  # ty: ignore[blender-assumed-context-member]


def register() -> None:
    bpy.app.handlers.load_post.append(on_load)


def unregister() -> None:
    bpy.app.handlers.load_post.remove(on_load)
