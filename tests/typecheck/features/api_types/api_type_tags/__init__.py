"""Feature test: Blender refines a struct to the subclass its Type tag names. A modifier of type 'SUBSURF' is a
SubsurfModifier, an object of type 'MESH' has a Mesh as its data, a space of type 'VIEW_3D' is a SpaceView3D, and
the strips of an action layer are ActionKeyframeStrip. The stubs must state it (check_api_type_tags.py); the helpers
below build the instances for the runtime probes (_expected/runtime.toml)."""

import bpy


def _mesh_object():
    return bpy.data.objects.new("api_type_tags", bpy.data.meshes.new("api_type_tags"))


def modifier(modifier_type):
    """The class name of a new modifier of ``modifier_type`` and its type."""
    md = _mesh_object().modifiers.new("api_type_tags", modifier_type)
    if md is None:
        return None
    return f"{type(md).__name__} {md.type}"


def object_data(object_type):
    """The class name of the data of a new object of ``object_type``, None for an empty."""
    makers = {
        "MESH": lambda: bpy.data.meshes.new("api_type_tags"),
        "FONT": lambda: bpy.data.curves.new("api_type_tags", "FONT"),
        "SURFACE": lambda: bpy.data.curves.new("api_type_tags", "SURFACE"),
        "EMPTY": lambda: None,
    }
    ob = bpy.data.objects.new("api_type_tags", makers[object_type]())
    assert ob.type == object_type
    return type(ob.data).__name__


def fluid_settings(fluid_type):
    """The class names of a fluid modifier's three settings pointers once its fluid_type is ``fluid_type``."""
    md = _mesh_object().modifiers.new("api_type_tags", "FLUID")
    if not isinstance(md, bpy.types.FluidModifier):
        return None
    md.fluid_type = fluid_type
    return " ".join(type(getattr(md, name)).__name__ for name in ("domain_settings", "flow_settings", "effector_settings"))


def space(space_type):
    """The class name of an area's active space once the area's type is ``space_type``. Only an area of a window's
    screen changes its space (also in --background, where the factory startup has one window)."""
    window_manager = bpy.context.window_manager
    if window_manager is None:
        return None
    area = window_manager.windows[0].screen.areas[0]
    area.type = space_type
    active = area.spaces.active
    if active is None:
        return None
    return f"{type(active).__name__} {active.type}"


def action_strip():
    """The class names of a new strip of an action layer, and of the layer's strips."""
    layer = bpy.data.actions.new("api_type_tags").layers.new("api_type_tags")
    strip = layer.strips.new()
    return " ".join(type(s).__name__ for s in (strip, *layer.strips))


def node(tree_type, node_type, side, index):
    """A new node's class name and bl_idname, and the class name, bl_idname and type of one of its sockets."""
    tree = bpy.data.node_groups.new("api_type_tags", tree_type)
    if tree is None:
        return None
    node = tree.nodes.new(node_type)
    socket = getattr(node, side)[index]
    return f"{type(node).__name__} {node.bl_idname} {type(socket).__name__} {socket.bl_idname} {socket.type}"


def register():
    pass


def unregister():
    pass
