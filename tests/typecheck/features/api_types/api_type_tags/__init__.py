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


def node_type(tree_type, node_type):
    """A new node's class name and its legacy type."""
    node = bpy.data.node_groups.new("api_type_tags", tree_type).nodes.new(node_type)
    return f"{type(node).__name__} {node.type}"


def interface_items():
    """The class names and item types of a new panel and a new float socket of a node tree's interface."""
    interface = bpy.data.node_groups.new("api_type_tags", "GeometryNodeTree").interface
    items = (interface.new_panel("Panel"), interface.new_socket("Value", socket_type="NodeSocketFloat"))
    return " ".join(f"{type(item).__name__} {item.item_type}" for item in items)


def boid_rule(rule_type):
    """The class name and type of a new boid rule of ``rule_type`` (only the operator adds one)."""
    settings = bpy.data.particles.new("api_type_tags")
    settings.physics_type = 'BOIDS'
    with bpy.context.temp_override(particle_settings=settings):
        bpy.ops.boid.rule_add(type=rule_type)
    if settings.boids is None:
        return None
    rule = settings.boids.states[0].rules[-1]
    return f"{type(rule).__name__} {rule.type}"


def linestyle_modifier(collection, modifier_type):
    """The class name and type of a new line style modifier in ``collection`` (``color_modifiers``, ...)."""
    modifier = getattr(bpy.data.linestyles.new("api_type_tags"), collection).new("api_type_tags", modifier_type)
    return f"{type(modifier).__name__} {modifier.type}"


def spreadsheet_tables():
    """The class names and types of the table IDs of the factory startup's spreadsheets."""
    return " ".join(sorted({
        f"{type(table.id).__name__} {table.id.type}"
        for screen in bpy.data.screens for area in screen.areas for space in area.spaces
        if space.type == 'SPREADSHEET' for table in space.tables if table.id is not None
    }))


def viewer_path_elems():
    """The class names and types of the viewer path elements of the factory startup's spreadsheets."""
    return " ".join(sorted({
        f"{type(elem).__name__} {elem.type}"
        for screen in bpy.data.screens for area in screen.areas for space in area.spaces
        if space.type == 'SPREADSHEET' for elem in space.viewer_path.path
    }))


def project_variables(directory):
    """The class names and types of a new project variable of each type, in a new project in ``directory``."""
    if bpy.data.project is None:
        bpy.ops.project.new(directory=directory)
    project = bpy.data.project
    if project is None:
        return None
    names = []
    for value in ('STRING', 'INTEGER', 'FLOAT'):
        variable = project.variables.new("api_type_tags_" + value.lower(), type=value)
        names.append("None" if variable is None else f"{type(variable).__name__} {variable.type}")
    return " ".join(names)


def layer_tree():
    """The class names of the root nodes of a Grease Pencil with a layer and a layer group."""
    grease_pencil = bpy.data.grease_pencils.new("api_type_tags")
    grease_pencil.layers.new("Layer")
    grease_pencil.layer_groups.new("Group")
    return " ".join(type(node).__name__ for node in grease_pencil.root_nodes)


def object_pose():
    """The pose of a new armature object (built only by a depsgraph update), of one whose armature is assigned
    after it was made (which builds the pose), and of a mesh object."""
    fresh = bpy.data.objects.new("api_type_tags", bpy.data.armatures.new("api_type_tags"))
    assigned = bpy.data.objects.new("api_type_tags", bpy.data.armatures.new("api_type_tags"))
    assigned.data = bpy.data.armatures.new("api_type_tags")
    return " ".join(type(ob.pose).__name__ for ob in (fresh, assigned, _mesh_object()))


def new_curve(curve_type):
    """The class name of a new curve of ``curve_type``."""
    return type(bpy.data.curves.new("api_type_tags", curve_type)).__name__


def register():
    pass


def unregister():
    pass
