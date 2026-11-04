"""Deprecated API: should be marked in hover and as a diagnostic (check:ide; never imported).

Brush.falloff_angle is deprecated since Blender 5.3, removal planned in 6.0 (RNA is_deprecated).
"""

from __future__ import annotations

from bpy.types import Brush


def deprecated_property(brush: Brush) -> None:
    brush.falloff_angle
    #     ^hover
    #     ^hover-contains "Deprecated"
    #     ^deprecated
