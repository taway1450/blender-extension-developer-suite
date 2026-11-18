"""Reference stub delta: the matrix stack and an off-screen binding are context managers; entering them gives None.
A vertex format's attr_add returns the attribute's index, and a shader's uniform_float takes a matrix."""

from collections.abc import Sequence
from typing import Literal

from mathutils import Matrix

class GPUVertFormat:
    def attr_add(self, id: str, comp_type: Literal['I8', 'U8', 'I16', 'U16', 'I32', 'U32', 'F32', 'I10'], len: int, fetch_mode: Literal['FLOAT', 'INT', 'INT_TO_FLOAT_UNIT']) -> int: ...

class GPUShader:
    def uniform_float(self, name: str, value: float | Sequence[float] | Matrix) -> None: ...

class MatrixStackContext:
    def __enter__(self) -> None: ...
    def __exit__(self, exc_type: type | None, exc_value: BaseException | None, traceback: BaseException | None, /) -> bool: ...

class OffScreenStackContext:
    def __enter__(self) -> None: ...
    def __exit__(self, exc_type: type | None, exc_value: BaseException | None, traceback: BaseException | None, /) -> bool: ...
