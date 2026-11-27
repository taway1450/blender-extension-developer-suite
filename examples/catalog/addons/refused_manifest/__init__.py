# /// catalog  # ty: ignore[blender-invalid-addon-metadata]
# title = "A manifest Blender refuses"
# section = "metadata"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["addon_discovery"]
# see = ["blender/scripts/addons_core/bl_pkg/cli/blender_ext.py"]
# ///
"""Blender validates an extension's `blender_manifest.toml` before it runs any of its code: `id` must be there and be
a Python identifier, and `type` must be one of the types it supports. This manifest has no `id` and a `type` of
`"add-in"`. The checker reads the manifest too and reports both on the first line of `__init__.py`, since a TOML file
cannot carry a marker."""


def register():
    pass


def unregister():
    pass
