"""Viewport Tools: measure distances in the 3D viewport, and a gizmo for the energy of a light."""

import bpy

from . import gizmos, measure, overlay, tool, ui

# The message bus keeps a subscription for as long as its owner lives.
msgbus_owner = object()


def on_active_object_changed():
    # The measurement belongs to the object that was active when it was taken.
    overlay.points.clear()


def register():
    measure.register()
    gizmos.register()
    ui.register()
    bpy.utils.register_tool(tool.MeasureTool, after={"builtin.measure"}, separator=True)
    # A key is an RNA path, or a struct type with the name of one of its properties.
    # demo: later/msgbus-keys
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=msgbus_owner,
        args=(),
        notify=on_active_object_changed,
    )


def unregister():
    bpy.msgbus.clear_by_owner(msgbus_owner)
    bpy.utils.unregister_tool(tool.MeasureTool)
    ui.unregister()
    gizmos.unregister()
    measure.unregister()
    overlay.remove_handler()
