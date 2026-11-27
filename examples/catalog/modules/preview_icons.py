# /// catalog
# title = "Preview icons by name"
# section = "drawing"
# status = "not-handled"
# features = ["api_types"]
# later = "preview-icons"
#
# [future]
# class = "planned"
# note = "Type the previews of a `bpy.utils.previews` collection by name in the builtin stubs."
# tracked = "later/preview-icons"
#
# [differs]
# "fake-bpy-module/main" = "fake-bpy-module types a preview found by name, so its `icon_id` is an `int`."
# "fake-bpy-module/5.2" = "These stubs type a preview found by name, so its `icon_id` is an `int`."
# "builtin/5.2" = "Blender 5.2's builtin stubs give `ImagePreviewCollection` no `__getitem__`, so the lookup by name is reported too."
# ///
"""`bpy.utils.previews` holds the add-on's own icons, loaded from image files and found by name for `icon_value`. The
builtin stubs do not type a preview found by name, so its `icon_id` is unknown."""

# catalog: hide
from typing import assert_type

# catalog: show
import bpy.utils.previews

ICONS = bpy.utils.previews.new()
ICONS.load("ruler", "icons/ruler.png", "IMAGE")
# gap: a preview by name is not typed in the builtin stubs
assert_type(ICONS["ruler"].icon_id, int)
