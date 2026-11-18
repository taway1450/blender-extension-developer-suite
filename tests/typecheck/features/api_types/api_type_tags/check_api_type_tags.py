"""A refined subclass states its Type tag (value form); a private tag view states what the tag implies for its
siblings (sibling form); the strips of an action layer are keyframe strips; a layer tree node is a layer or a layer
group; the curve type of `curves.new()` names the subclass. These are stub facts."""

from __future__ import annotations

from typing import Literal, assert_type

from bpy.types import (ActionKeyframeStrip, ActionLayer, BlendDataCurves, BoidRuleGoal, CloudsTexture, ColorStrip,
                       CopyLocationConstraint, CrossStrip, Curve, EnumProperty, FloatAttribute, FluidDomainSettings,
                       FModifierNoise, GeometryNodeGroup, GreasePencil, GreasePencilLayer, GreasePencilLayerGroup,
                       GreasePencilOpacityModifier, IDViewerPathElem, Image, LightProbeSphere,
                       LineStyleAlphaModifier_Noise, LineStyleColorModifier_AlongStroke,
                       LineStyleGeometryModifier_Sampling, LineStyleThicknessModifier_Calligraphy, Mesh,
                       NodeSocketFloat, NodeSocketFloatFactor, NodeTreeInterfacePanel, NodeTreeInterfaceSocketFloat,
                       PointLight, Pose, ProjectVariableInteger, ShaderFxBlur, ShaderNodeMath, SpaceProperties,
                       SpaceView3D, SpreadsheetTable, SpreadsheetTableIDGeometry, SubsurfModifier, SurfaceCurve,
                       TextCurve, TextureNodeMath, _FluidModifier_DOMAIN, _Object_ARMATURE, _Object_EMPTY, _Object_FONT,
                       _Object_MESH, _Object_SURFACE)

def value_form(md: SubsurfModifier, gp_md: GreasePencilOpacityModifier, con: CopyLocationConstraint, light: PointLight,
               probe: LightProbeSphere, tex: CloudsTexture, color: ColorStrip, cross: CrossStrip, fx: ShaderFxBlur,
               fmod: FModifierNoise, attr: FloatAttribute, prop: EnumProperty) -> None:
    assert_type(md.type, Literal['SUBSURF'])  # bare-ok: a stub fact: a SUBSURF modifier is a SubsurfModifier
    assert_type(gp_md.type, Literal['GREASE_PENCIL_OPACITY'])  # bare-ok: a stub fact: Grease Pencil modifiers too
    assert_type(con.type, Literal['COPY_LOCATION'])  # bare-ok: a stub fact: constraints
    assert_type(light.type, Literal['POINT'])  # bare-ok: a stub fact: lights
    assert_type(probe.type, Literal['SPHERE'])  # bare-ok: a stub fact: light probes
    assert_type(tex.type, Literal['CLOUDS'])  # bare-ok: a stub fact: textures
    assert_type(color.type, Literal['COLOR'])  # bare-ok: a stub fact: strips
    assert_type(cross.type, Literal['CROSS'])  # bare-ok: a stub fact: effect strips with inputs
    assert_type(fx.type, Literal['FX_BLUR'])  # bare-ok: a stub fact: shader effects
    assert_type(fmod.type, Literal['NOISE'])  # bare-ok: a stub fact: F-Curve modifiers
    assert_type(attr.data_type, Literal['FLOAT'])  # bare-ok: a stub fact: attributes, by data_type
    assert_type(prop.type, Literal['ENUM'])  # bare-ok: a stub fact: RNA properties

def spaces(view3d: SpaceView3D, properties: SpaceProperties) -> None:
    assert_type(view3d.type, Literal['VIEW_3D'])  # bare-ok: a stub fact: a VIEW_3D space is a SpaceView3D
    assert_type(properties.type, Literal['PROPERTIES'])  # bare-ok: a stub fact: a PROPERTIES space is a SpaceProperties

def nodes(node: ShaderNodeMath, socket: NodeSocketFloat, factor: NodeSocketFloatFactor) -> None:
    assert_type(node.bl_idname, Literal['ShaderNodeMath'])  # bare-ok: a stub fact: a built-in node's bl_idname
    assert_type(socket.bl_idname, Literal['NodeSocketFloat'])  # bare-ok: a stub fact: a built-in socket's bl_idname
    assert_type(socket.type, Literal['VALUE'])  # bare-ok: a stub fact: a float socket's type
    assert_type(factor.type, Literal['VALUE'])  # bare-ok: a stub fact: socket subclasses share a type

def node_types(node: ShaderNodeMath, texture: TextureNodeMath, group: GeometryNodeGroup) -> None:
    assert_type(node.type, Literal['MATH'])  # bare-ok: a stub fact: a built-in node's legacy type
    assert_type(texture.type, Literal['MATH'])  # bare-ok: a stub fact: node classes share a legacy type
    assert_type(group.type, Literal['GROUP'])  # bare-ok: a stub fact: every group node's legacy type is GROUP

def refined_families(panel: NodeTreeInterfacePanel, socket: NodeTreeInterfaceSocketFloat, rule: BoidRuleGoal,
                     color: LineStyleColorModifier_AlongStroke, alpha: LineStyleAlphaModifier_Noise,
                     thickness: LineStyleThicknessModifier_Calligraphy, geometry: LineStyleGeometryModifier_Sampling,
                     elem: IDViewerPathElem, variable: ProjectVariableInteger, table: SpreadsheetTable) -> None:
    assert_type(panel.item_type, Literal['PANEL'])  # bare-ok: a stub fact: node tree interface items
    assert_type(socket.item_type, Literal['SOCKET'])  # bare-ok: a stub fact: every interface socket is a SOCKET
    assert_type(rule.type, Literal['GOAL'])  # bare-ok: a stub fact: boid rules
    assert_type(color.type, Literal['ALONG_STROKE'])  # bare-ok: a stub fact: line style color modifiers
    assert_type(alpha.type, Literal['NOISE'])  # bare-ok: a stub fact: line style alpha modifiers
    assert_type(thickness.type, Literal['CALLIGRAPHY'])  # bare-ok: a stub fact: line style thickness modifiers
    assert_type(geometry.type, Literal['SAMPLING'])  # bare-ok: a stub fact: line style geometry modifiers
    assert_type(elem.type, Literal['ID'])  # bare-ok: a stub fact: viewer path elements
    assert_type(variable.type, Literal['INTEGER'])  # bare-ok: a stub fact: project variables
    assert_type(table.id, SpreadsheetTableIDGeometry | None)  # bare-ok: a stub fact: the only table ID type

def layer_tree(grease_pencil: GreasePencil, layer: GreasePencilLayer) -> None:
    assert_type(grease_pencil.root_nodes[0], GreasePencilLayer | GreasePencilLayerGroup)  # bare-ok: a stub fact: a tree node is a layer or a group
    assert_type(layer.next_node, GreasePencilLayer | GreasePencilLayerGroup | None)  # bare-ok: a stub fact: a tree node is a layer or a group

def new_curves(curves: BlendDataCurves) -> None:
    assert_type(curves.new("Text", 'FONT'), TextCurve)  # bare-ok: a stub fact: the curve type names the subclass
    assert_type(curves.new("Surface", type='SURFACE'), SurfaceCurve)  # bare-ok: a stub fact: the curve type names the subclass
    assert_type(curves.new("Curve", 'CURVE'), Curve)  # bare-ok: a stub fact: a CURVE curve is no subclass

def sibling_form(mesh: _Object_MESH, font: _Object_FONT, surface: _Object_SURFACE, empty: _Object_EMPTY,
                 domain: _FluidModifier_DOMAIN) -> None:
    assert_type(mesh.type, Literal['MESH'])  # bare-ok: a stub fact: the tag view of a MESH object
    assert_type(mesh.data, Mesh)  # bare-ok: a stub fact: a MESH object's data is a Mesh, never None
    assert_type(font.data, TextCurve)  # bare-ok: a stub fact: a text object's curve is refined again
    assert_type(surface.data, SurfaceCurve)  # bare-ok: a stub fact: a surface object's curve is refined again
    assert_type(empty.data, Image | None)  # bare-ok: a stub fact: an empty has no data, or the image it displays
    assert_type(domain.fluid_type, Literal['DOMAIN'])  # bare-ok: a stub fact: the tag view of a fluid domain
    assert_type(domain.domain_settings, FluidDomainSettings)  # bare-ok: a stub fact: a domain has domain settings
    assert_type(domain.flow_settings, None)  # bare-ok: a stub fact: and no flow settings

def pose_views(armature: _Object_ARMATURE, mesh: _Object_MESH) -> None:
    assert_type(armature.pose, Pose | None)  # bare-ok: a stub fact: an armature's pose, None until it is built
    assert_type(mesh.pose, None)  # bare-ok: a stub fact: only an armature object has a pose

def action_strips(layer: ActionLayer) -> None:
    assert_type(layer.strips.new(), ActionKeyframeStrip)  # bare-ok: a stub fact: the only strip type Blender creates
    assert_type(layer.strips[0], ActionKeyframeStrip)  # bare-ok: a stub fact: the only strip type Blender creates
    for strip in layer.strips:
        assert_type(strip, ActionKeyframeStrip)  # bare-ok: a stub fact: the only strip type Blender creates
