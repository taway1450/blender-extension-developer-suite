"""Feature test: a constructor whose argument is a Type tag value returns the subclass the tag names, since Blender
refines the new struct like any other. `constraints.new('COPY_LOCATION')` gives a CopyLocationConstraint,
`lights.new(name, 'SPOT')` a SpotLight, `attributes.new(name, 'FLOAT', 'POINT')` a FloatAttribute: the parameter
and the tag share an `rna_enum_*` alias. `nodes.new(type=...)` and `gizmos.new(...)` take a `bl_idname`, a
built-in one or an add-on class's (`NarrowConstructorsGizmo.bl_idname`), and so do a node's `inputs.new(...)`
and `outputs.new(...)` (a socket's) and `bpy.data.node_groups.new(name, ...)` (a tree's). A node tree interface's
`new_socket(socket_type=...)` takes a socket's `bl_idname` and returns its interface socket
(`NodeTreeInterfaceSocketFloat` for `NodeSocketFloat`); a socket type the tree does not support raises `TypeError`.
`bpy.data.objects.new(name, data)` takes the object type from
the data, so it returns that type's tag view (`_Object_CAMERA` for a camera, `_Object_EMPTY` for None). A value no
class declares, a non-literal argument and an add-on node's `bl_idname` read from no class keep the stub type.
`driver_add(path)` returns one F-Curve when `path` names a property of the struct that is no array
(`bone.driver_add("bbone_segments")`), and a list of them, one per item, for an array (`location`). The
narrowing is silent. The assert_type calls are no-ops at runtime."""

from typing import Literal, assert_type

import bpy
from bpy.types import (ID, Bone, Camera, Constraint, CopyLocationConstraint, Driver, FloatAttribute, Gizmo,
                       GizmoGroup, Light, Mesh, Node, NodeSocket, NodeSocketColor, NodeSocketFloat, NodeTree,
                       NodeTreeInterfaceSocket, NodeTreeInterfaceSocketFloat, Object, ShaderNodeMath, ShaderNodeTree,
                       SpotLight, SunLight, TrackToConstraint)


def follow(ob: Object, target: Object) -> None:
    con = ob.constraints.new('COPY_LOCATION')
    assert_type(con, CopyLocationConstraint)
    con.target = target
    track = ob.constraints.new(type='TRACK_TO', name="Aim")
    assert_type(track, TrackToConstraint)


def bbone_driver(bone: Bone) -> Driver:
    fcu = bone.driver_add("bbone_segments", -1)
    assert_type(fcu.data_path, str)  # one F-Curve: `bbone_segments` is no array
    return fcu.driver


def hide_driver(ob: Object) -> Driver:
    return ob.driver_add("hide_viewport").driver  # no array: one F-Curve


def location_drivers(ob: Object) -> None:
    fcus = ob.driver_add("location")
    print(fcus.data_path)  # ty: ignore[missing-union-attribute]  # bare-ok: `location` is an array, so a list


def any_constraint(ob: Object, kind: str) -> None:
    con = ob.constraints.new(kind)  # ty: ignore[blender-imprecise-enum-value]
    assert_type(con, Constraint)  # bare-ok: a non-literal argument names no subclass


def key_light(name: str) -> SpotLight:
    light = bpy.data.lights.new(name, 'SPOT')
    assert_type(light, SpotLight)
    light.spot_size = 0.8
    return light


def sun_or_spot(name: str, sun: bool) -> None:
    light = bpy.data.lights.new(name, 'SUN' if sun else 'SPOT')
    assert_type(light, SunLight | SpotLight)


def weight(mesh: Mesh) -> None:
    attribute = mesh.attributes.new("weight", 'FLOAT', 'POINT')
    assert_type(attribute, FloatAttribute)


def math_node(tree: NodeTree) -> None:
    node = tree.nodes.new(type='ShaderNodeMath')
    assert_type(node, ShaderNodeMath)
    node.operation = 'MULTIPLY'
    other = tree.nodes.new('ShaderNodeMath')
    assert_type(other, ShaderNodeMath)


def interface_sockets(tree: NodeTree) -> None:
    socket = tree.interface.new_socket("Factor", in_out='INPUT', socket_type='NodeSocketFloat')
    assert_type(socket, NodeTreeInterfaceSocketFloat)
    socket.min_value = 0.0
    unknown = tree.interface.new_socket("Own", socket_type='NarrowConstructorsUnknown')
    assert_type(unknown, NodeTreeInterfaceSocket)  # bare-ok: no interface socket for this bl_idname


def objects(camera: Camera, mesh: Mesh | None, data: ID) -> None:
    ob = bpy.data.objects.new("Camera", camera)
    assert_type(ob.data, Camera)
    assert_type(ob.type, Literal['CAMERA'])
    empty = bpy.data.objects.new("Empty", None)
    assert_type(empty.type, Literal['EMPTY'])
    maybe = bpy.data.objects.new("Mesh", mesh)
    assert_type(maybe.type, Literal['MESH', 'EMPTY'])
    other = bpy.data.objects.new("Other", data)
    assert_type(other, Object)  # bare-ok: any ID names no object type


def unknown_node(tree: NodeTree) -> None:
    node = tree.nodes.new('NarrowConstructorsUnknown')
    assert_type(node, Node)  # bare-ok: no class declares this bl_idname


class NarrowConstructorsGizmo(Gizmo):
    bl_idname = "NARROW_CONSTRUCTORS_GT_dial"

    def draw(self, context):
        pass


class NarrowConstructorsGizmoGroup(GizmoGroup):
    bl_idname = "NARROW_CONSTRUCTORS_GGT_dial"
    bl_label = "Dial"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D'}

    def setup(self, context):
        dial = self.gizmos.new(NarrowConstructorsGizmo.bl_idname)
        assert_type(dial, NarrowConstructorsGizmo)
        arrow = self.gizmos.new("GIZMO_GT_arrow_3d")
        assert_type(arrow, Gizmo)  # bare-ok: a C gizmo type has no class of its own


class NarrowConstructorsTree(NodeTree):
    bl_idname = "NarrowConstructorsTree"
    bl_label = "Narrow Constructors"
    bl_icon = 'NODETREE'


class NarrowConstructorsSocket(NodeSocket):
    bl_idname = "NarrowConstructorsSocket"
    bl_label = "Narrow Constructors"

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (1.0, 1.0, 1.0, 1.0)


class NarrowConstructorsNode(Node):
    bl_idname = "NarrowConstructorsNode"
    bl_label = "Narrow Constructors"

    def init(self, context):
        value = self.inputs.new("NodeSocketFloat", "Value")
        assert_type(value, NodeSocketFloat)
        color = self.inputs.new(type='NodeSocketColor', name="Color")
        assert_type(color, NodeSocketColor)
        own = self.outputs.new(NarrowConstructorsSocket.bl_idname, "Own")
        assert_type(own, NarrowConstructorsSocket)
        by_value = self.outputs.new("NarrowConstructorsSocket", "By value")
        assert_type(by_value, NarrowConstructorsSocket)


def trees() -> None:
    shader = bpy.data.node_groups.new("Shader", 'ShaderNodeTree')
    assert_type(shader, ShaderNodeTree)
    # The stubs list the built-in tree types; Blender's enum also has every registered one.
    own = bpy.data.node_groups.new("Own", NarrowConstructorsTree.bl_idname)
    assert_type(own, NarrowConstructorsTree)


classes = (NarrowConstructorsGizmo, NarrowConstructorsGizmoGroup, NarrowConstructorsTree, NarrowConstructorsSocket,
           NarrowConstructorsNode)
register, unregister = bpy.utils.register_classes_factory(classes)
