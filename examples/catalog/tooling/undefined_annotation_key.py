# /// catalog
# title = "`F821` on a property annotation"
# section = "lint"
# status = "not-handled"
# features = ["property_wrappers"]
# see = ["blender/source/blender/python/intern/bpy_rna.cc"]
#
# [lint]
# rule = "F821"
# default = "reports"
# profile = "reports"
#
# [future]
# class = "out-of-scope"
# note = "ruff reads a string inside an annotation as a forward reference, and no setting changes that for one class; only ruff could change it. Until then, `# noqa: F821` on the line."
# ///
"""An annotation can take its property from a dictionary, `weight: PROPS["weight"]`, and Blender evaluates it as the
value it is when it registers the class. ruff reads the string `"weight"` in an annotation as the name of a type,
and `F821` reports it as an undefined name, with the linter profile too."""

from bpy.props import FloatProperty, StringProperty
from bpy.types import PropertyGroup

PROPS = {"weight": FloatProperty(), "label": StringProperty()}


class Settings(PropertyGroup):
    weight: PROPS["weight"]
