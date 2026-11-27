# /// catalog
# title = "The properties of add-ons Blender enables by default"
# section = "other-addons"
# status = "not-handled"
# features = ["assumptions"]
# later = "default-addon-properties"
#
# [future]
# class = "planned"
# note = "Give the stubs the registrations of the add-ons Blender enables by default, so the read is known without their source."
# tracked = "later/default-addon-properties"
#
# [differs]
# "builtin/5.2" = "Blender 5.2's stubs declare `scene.cycles` as `Any | None`, so the read is reported on `None` instead."
# ///
"""Some properties come from an add-on Blender enables by default, not from Blender itself: `scene.cycles` is
Cycles'. Code that reads them works in a default Blender, but the stubs do not have them. The checker knows them
only when the default add-on's source is on its search path (it then reports the read as an Assumption,
`blender-assumed-default-addon`); with the stubs alone, as here, the read is reported as missing."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Scene


def example(scene: Scene) -> None:
    # gap: the default add-on's properties are not known
    assert_type(scene.cycles.samples, int)
