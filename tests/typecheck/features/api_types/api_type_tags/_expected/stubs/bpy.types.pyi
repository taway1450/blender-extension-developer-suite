"""Reference stub delta: the Type tag of each refined subclass, the tag views of Object and FluidModifier, the
keyframe strips of an action layer, the two kinds of layer tree node and the curve types of curves.new()."""

from collections.abc import Iterator
from typing import Literal, overload

class SubsurfModifier:
    type: Literal['SUBSURF']

class GreasePencilOpacityModifier:
    type: Literal['GREASE_PENCIL_OPACITY']

class CopyLocationConstraint:
    type: Literal['COPY_LOCATION']

class PointLight:
    type: Literal['POINT']

class LightProbeSphere:
    type: Literal['SPHERE']

class CloudsTexture:
    type: Literal['CLOUDS']

class ColorStrip:
    type: Literal['COLOR']

class CrossStrip:
    type: Literal['CROSS']

class ShaderFxBlur:
    type: Literal['FX_BLUR']

class FModifierNoise:
    type: Literal['NOISE']

class FloatAttribute:
    data_type: Literal['FLOAT']

class EnumProperty:
    type: Literal['ENUM']

class SpaceView3D:
    type: Literal['VIEW_3D']

class SpaceProperties:
    type: Literal['PROPERTIES']

class ShaderNodeMath:
    bl_idname: Literal['ShaderNodeMath']
    type: Literal['MATH']

class TextureNodeMath:
    type: Literal['MATH']

class GeometryNodeGroup:
    type: Literal['GROUP']

class NodeTreeInterfacePanel:
    item_type: Literal['PANEL']

class NodeTreeInterfaceSocket:
    item_type: Literal['SOCKET']

class BoidRuleGoal:
    type: Literal['GOAL']

class LineStyleColorModifier_AlongStroke:
    type: Literal['ALONG_STROKE']

class LineStyleAlphaModifier_Noise:
    type: Literal['NOISE']

class LineStyleThicknessModifier_Calligraphy:
    type: Literal['CALLIGRAPHY']

class LineStyleGeometryModifier_Sampling:
    type: Literal['SAMPLING']

class IDViewerPathElem:
    type: Literal['ID']

class ProjectVariableInteger:
    type: Literal['INTEGER']

class SpreadsheetTable:
    id: SpreadsheetTableIDGeometry | None

class GreasePencil:
    root_nodes: bpy_prop_collection[GreasePencilLayer | GreasePencilLayerGroup]

class GreasePencilTreeNode:
    next_node: GreasePencilLayer | GreasePencilLayerGroup | None

class BlendDataCurves:
    @overload
    def new(self, name: str, type: Literal['CURVE']) -> Curve: ...
    @overload
    def new(self, name: str, type: Literal['SURFACE']) -> SurfaceCurve: ...
    @overload
    def new(self, name: str, type: Literal['FONT']) -> TextCurve: ...

class NodeSocketFloat:
    bl_idname: Literal['NodeSocketFloat']
    type: Literal['VALUE']

class NodeSocketFloatFactor:
    bl_idname: Literal['NodeSocketFloatFactor']
    type: Literal['VALUE']

class _Object_MESH(Object):
    type: Literal['MESH']
    data: Mesh
    pose: None

class _Object_ARMATURE(Object):
    type: Literal['ARMATURE']
    data: Armature
    pose: Pose | None

class _Object_FONT(Object):
    type: Literal['FONT']
    data: TextCurve

class _Object_SURFACE(Object):
    type: Literal['SURFACE']
    data: SurfaceCurve

class _Object_EMPTY(Object):
    type: Literal['EMPTY']
    data: Image | None

class _FluidModifier_DOMAIN(FluidModifier):
    fluid_type: Literal['DOMAIN']
    domain_settings: FluidDomainSettings
    flow_settings: None
    effector_settings: None

class ActionStrips:
    def new(self, *, type: Literal['KEYFRAME'] = 'KEYFRAME') -> ActionKeyframeStrip: ...
    def __getitem__(self, key: int | str) -> ActionKeyframeStrip: ...
    def __iter__(self) -> Iterator[ActionKeyframeStrip]: ...
