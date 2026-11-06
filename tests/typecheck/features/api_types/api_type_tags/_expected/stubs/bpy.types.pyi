"""Reference stub delta: the Type tag of each refined subclass, the tag views of Object and FluidModifier, and the
keyframe strips of an action layer."""

from collections.abc import Iterator
from typing import Literal

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

class NodeSocketFloat:
    bl_idname: Literal['NodeSocketFloat']
    type: Literal['VALUE']

class NodeSocketFloatFactor:
    bl_idname: Literal['NodeSocketFloatFactor']
    type: Literal['VALUE']

class _Object_MESH(Object):
    type: Literal['MESH']
    data: Mesh

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
