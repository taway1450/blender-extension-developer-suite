"""Reference stub delta: the properties reg_classmethod's PropertyGroup.register() adds to Blender's classes."""

from reg_classmethod import REG_CLASSMETHOD_PG_object, REG_CLASSMETHOD_PG_scene

class Scene:
    @property
    def reg_classmethod(self) -> REG_CLASSMETHOD_PG_scene: ...

class Object:
    @property
    def reg_classmethod(self) -> REG_CLASSMETHOD_PG_object: ...
