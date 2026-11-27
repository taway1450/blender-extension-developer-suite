# /// catalog
# title = "`UP037` on a dictionary key in an annotation"
# section = "lint"
# status = "handled"
# safeguards = ["linter-profile"]
# features = ["property_wrappers"]
#
# [lint]
# rule = "UP037"
# default = "reports"
# profile = "silent"
# ///
"""With `from __future__ import annotations`, `UP037` takes the key in `weight: PROPS["weight"]` for a quoted type
and its fix rewrites it to `PROPS[weight]`, which breaks the add-on. The linter profile lists Blender's base classes in
`runtime-evaluated-base-classes`, which stops it for a class that derives from one of them in the same file."""

from __future__ import annotations

from bpy.props import FloatProperty
from bpy.types import PropertyGroup

PROPS = {"weight": FloatProperty()}


class Settings(PropertyGroup):
    weight: PROPS["weight"]
