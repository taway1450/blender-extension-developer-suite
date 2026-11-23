from typing import assert_type

import bpy
from bpy.types import AnimData, Material, MaterialGPencilStyle

# The Grease Pencil material presets apply from the Surface panel, which shows only for a Grease Pencil material.
material = bpy.context.material  # ty: ignore[blender-assumed-preset-context]
assert_type(material, Material)  # oracle-skip: stock ty keeps the stub type
gpcolor = material.grease_pencil  # ty: ignore[blender-assumed-preset-context]
assert_type(gpcolor, MaterialGPencilStyle)  # oracle-skip: stock ty keeps the stub type
gpcolor.show_fill = False
assert_type(material.animation_data, AnimData | None)  # bare-ok: only grease_pencil is taken as set
