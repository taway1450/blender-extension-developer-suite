# /// catalog
# title = "Enum items that unpack another tuple"
# section = "value-types"
# status = "not-handled"
# later = "enum-items-unpacked"
# features = ["properties"]
#
# [future]
# class = "planned"
# note = "Read `*NAME` inside static `items` through the constant, as items joined with `+` already are."
# tracked = "later/enum-items-unpacked"
# ///
"""Static `items` give the property a `Literal` Value type. When the sequence unpacks another one, `(first, *OTHERS)`,
the checker no longer reads the identifiers and the value is a plain `str`."""

# catalog: hide
from typing import Literal, assert_type

# catalog: show
from bpy.props import EnumProperty
from bpy.types import PropertyGroup

FORMATS = (("OBJ", "Wavefront", ""), ("STL", "STL", ""))


class ExportSettings(PropertyGroup):
    file_format: EnumProperty(items=(("SCENE", "Scene", ""), *FORMATS), default="SCENE")


def example(settings: ExportSettings) -> None:
    # gap: the unpacked identifiers are not read
    assert_type(settings.file_format, Literal["SCENE", "OBJ", "STL"])
