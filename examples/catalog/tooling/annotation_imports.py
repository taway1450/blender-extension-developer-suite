# /// catalog
# title = "Imports only property annotations use"
# section = "lint"
# status = "handled"
# safeguards = ["linter-profile"]
# see = ["blender/source/blender/python/intern/bpy_rna.cc"]
#
# [lint]
# rule = "TC002"
# default = "reports"
# profile = "silent"
# ///
"""With `from __future__ import annotations`, an import that only annotations use looks needed for typing alone, and
`TC002` asks to move it under `if TYPE_CHECKING:`. Blender evaluates a registered class's annotations when it
registers it (with `typing.get_type_hints`), so the import must stay. The linter profile lists Blender's base
classes in `runtime-evaluated-base-classes`: when a class in the file derives from one of them, ruff keeps the imports
its annotations use."""

from __future__ import annotations

from bpy.props import IntProperty
from bpy.types import PropertyGroup


class Settings(PropertyGroup):
    count: IntProperty(min=0)
