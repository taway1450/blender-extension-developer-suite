"""Feature test: Blender refines a struct to the subclass its Type tag names, so a test of the tag tells which
subclass the struct is. A modifier whose type is 'SUBSURF' is a SubsurfModifier, a node whose bl_idname is
'ShaderNodeMath' is a ShaderNodeMath, and a socket whose type is 'STRING' is one of the string sockets. The
assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import (ArrayModifier, ColorStrip, Constraint, CopyLocationConstraint, Light, Modifier, MultiresModifier,
                       Node, NodeSocket, NodeSocketString, NodeSocketStringFilePath, Object, PointLight, SequenceEditor,
                       ShaderNodeMath, SpotLight, SubsurfModifier, SunLight)
from mathutils import Color


def subdivision_levels(ob: Object) -> int:
    """The highest viewport subdivision level of ``ob``'s modifiers."""
    levels = 0
    for md in ob.modifiers:
        if md.type == 'SUBSURF':
            assert_type(md, SubsurfModifier)
            levels = max(levels, md.levels)
        elif md.type == 'MULTIRES':
            assert_type(md, MultiresModifier)  # elif: the earlier tag is ruled out
            levels = max(levels, md.levels)
    return levels


def array_count(md: Modifier) -> int:
    if md.type != 'ARRAY':
        return 0
    assert_type(md, ArrayModifier)  # the rest of the function after `!=` ... return
    return md.count


def subdivided(md: Modifier) -> bool:
    if md.type in {'SUBSURF', 'MULTIRES'}:
        assert_type(md, SubsurfModifier | MultiresModifier)
        return md.levels > 0
    return False


def copied_location(con: Constraint) -> Object | None:
    if con.type == 'COPY_LOCATION':
        assert_type(con, CopyLocationConstraint)
        return con.target
    return None


def strip_colors(editor: SequenceEditor) -> list[Color]:
    colors = []
    for strip in editor.strips_all:
        if strip.type == 'COLOR':
            assert_type(strip, ColorStrip)
            colors.append(strip.color)
    return colors


def sun_angle(light: Light) -> float:
    if light.type == 'SUN':
        assert_type(light, SunLight)
        return light.angle
    return 0.0


def shadow_radius(light: Light) -> float:
    if light.type not in ('POINT', 'SPOT'):
        return 0.0
    assert_type(light, PointLight | SpotLight)  # the rest of the function after `not in` ... return
    return light.shadow_soft_size


def math_operation(node: Node) -> str:
    if node.bl_idname == 'ShaderNodeMath':
        assert_type(node, ShaderNodeMath)
        return node.operation
    return ''


def modifier_label(md: Modifier) -> str:
    match md.type:
        case 'SUBSURF':
            assert_type(md, SubsurfModifier)  # a match on the tag
            return f"Subdivision {md.levels}"
        case _:
            return md.name


def string_default(socket: NodeSocket) -> str:
    if socket.type == 'STRING':
        assert_type(socket, NodeSocketString | NodeSocketStringFilePath)  # several socket classes share a type
        return socket.default_value
    return ''


class NarrowValuesNode(Node):
    """An add-on's own node: no stub class declares its bl_idname."""

    bl_idname = 'NarrowValuesNode'
    bl_label = "Narrow Values"


def register():
    bpy.utils.register_class(NarrowValuesNode)


def unregister():
    bpy.utils.unregister_class(NarrowValuesNode)
