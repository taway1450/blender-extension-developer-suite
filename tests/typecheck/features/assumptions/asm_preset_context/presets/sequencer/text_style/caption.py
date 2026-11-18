from typing import assert_type

import bpy
from bpy.types import TextStrip

# The sequencer's text-style presets apply from the Style panel, which shows only for a text strip.
strip = bpy.context.active_strip  # ty: ignore[blender-assumed-preset-context]
assert_type(strip, TextStrip)  # oracle-skip: stock ty keeps the stub type
strip.font_size = 50.0
strip.use_outline = True
