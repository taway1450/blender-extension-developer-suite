# /// catalog
# title = "The add-ons it relies on: `[tool.blender] uses`"
# section = "other-addons"
# status = "handled"
# safeguards = ["typechecker"]
# features = ["registration_checks"]
# ///
"""An add-on that reads what another add-on registers lists that add-on's module in its manifest, under
`[tool.blender] uses`, a table Blender ignores. The checker then counts the other add-on's Registered properties as
this one's; without the line it reports them as missing. Here `scene.render_presets` comes from the add-on in
`addons/_render_presets` (no entry of its own, hence the `_`)."""

# catalog: hide
from typing import assert_type

# catalog: show
from bpy.types import Scene


def samples(scene: Scene) -> int:
    # catalog: hide
    assert_type(scene.render_presets.samples, int)
    # catalog: show
    return scene.render_presets.samples


def register():
    pass


def unregister():
    pass
