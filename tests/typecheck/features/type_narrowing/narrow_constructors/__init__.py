"""Feature test: a constructor whose argument is a Type tag value returns the subclass the tag names, since Blender
refines the new struct like any other. `constraints.new('COPY_LOCATION')` gives a CopyLocationConstraint,
`lights.new(name, 'SPOT')` a SpotLight, `attributes.new(name, 'FLOAT', 'POINT')` a FloatAttribute: the parameter
and the tag share an `rna_enum_*` alias. `nodes.new(type=...)` and `gizmos.new(...)` take a `bl_idname`, a
built-in one or an add-on class's (`NarrowConstructorsGizmo.bl_idname`). A value no class declares, a non-literal
argument and an add-on node's `bl_idname` read from no class keep the stub type. The narrowing is silent. The
assert_type calls are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import (Constraint, CopyLocationConstraint, FloatAttribute, Gizmo, GizmoGroup, Light, Mesh, Node,
                       NodeTree, Object, ShaderNodeMath, SpotLight, SunLight, TrackToConstraint)


def follow(ob: Object, target: Object) -> None:
    con = ob.constraints.new('COPY_LOCATION')
    assert_type(con, CopyLocationConstraint)
    con.target = target
    track = ob.constraints.new(type='TRACK_TO', name="Aim")
    assert_type(track, TrackToConstraint)


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


classes = (NarrowConstructorsGizmo, NarrowConstructorsGizmoGroup)
register, unregister = bpy.utils.register_classes_factory(classes)
