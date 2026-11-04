"""What the editor shows for an addon's own properties (check:ide; never imported)."""

from __future__ import annotations

from . import PROPS_ANNOTATIONS_Settings


def own_properties(s: PROPS_ANNOTATIONS_Settings) -> None:
    s.count
    # ^hover
    # ^hover-contains "int"
    s.target
    # ^hover-contains "Object"
