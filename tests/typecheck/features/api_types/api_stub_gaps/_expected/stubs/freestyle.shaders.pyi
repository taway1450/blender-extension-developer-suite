"""Reference stub delta: Freestyle C shaders have their base."""

from freestyle.types import StrokeShader

class ConstantThicknessShader(StrokeShader):
    def __init__(self, thickness: float) -> None: ...

class SamplingShader(StrokeShader):
    def __init__(self, sampling: float) -> None: ...
