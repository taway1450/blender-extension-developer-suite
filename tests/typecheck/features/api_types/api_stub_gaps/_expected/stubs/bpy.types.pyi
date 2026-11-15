"""Reference stub delta: the thick-wrapped version arrays are tuples, every struct has bl_rna, and
Operator.description may return None."""

class bpy_struct:
    bl_rna: Struct

class BlendData:
    version: tuple[int, int, int]

class Preferences:
    version: tuple[int, int, int]

class Library:
    version: tuple[int, int, int]

class Operator:
    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str | None: ...
