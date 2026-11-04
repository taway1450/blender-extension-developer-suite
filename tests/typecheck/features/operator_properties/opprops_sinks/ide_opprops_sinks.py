"""What the editor shows for operator idnames and their properties (check:ide; never imported).

The code under a ^completion marker is unfinished, as the user types it; check:features does not check ide_*.py
files, so the errors it causes do not count.
"""

from __future__ import annotations

from bpy.types import KeyMap, UILayout


def idname_completion(layout: UILayout, keymap: KeyMap) -> None:
    layout.operator("opprops_sinks.")
    #                              ^completion opprops_sinks.step opprops_sinks.bare
    keymap.keymap_items.new("opprops_", "A", "PRESS")
    #                                ^completion opprops_sinks.step opprops_sinks.bare


def properties(layout: UILayout) -> None:
    layout.operator("opprops_sinks.step").am
    #                                       ^completion amount
    layout.operator("opprops_sinks.step").mode
    #                                     ^hover-contains "Literal"
    layout.operator("opprops_sinks.step")
    #                ^hover-contains "Step"
