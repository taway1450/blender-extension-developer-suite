# /// catalog
# title = "`F821` in the reload guard"
# section = "lint"
# status = "not-handled"
# features = ["registration"]
# see = ["blender/scripts/addons_core/io_anim_bvh/__init__.py"]
#
# [lint]
# rule = "F821"
# default = "reports"
# profile = "reports"
#
# [future]
# class = "out-of-scope"
# note = "ruff reads the module as it runs the first time, when the guard is skipped; only ruff could change it. Until then, `# noqa: F821` on the line."
# ///
"""Blender's own add-ons start with a guard that reloads their submodules when Blender re-enables the add-on: the
module runs again in its old namespace, so `ops` is still bound (see
[Reloading with `importlib.reload`](addons.md#reload-guard)). ruff reads the module as one run, where `ops` is only
imported below the guard, and `F821` reports it as an undefined name, with the linter profile too."""

if "bpy" in locals():
    import importlib

    importlib.reload(ops)

import bpy

from . import ops


def register():
    ops.register()


def unregister():
    ops.unregister()
