"""Reference stub delta: batch_for_shader's indices take a buffer (a NumPy array)."""

from collections.abc import Buffer, Sequence
from typing import Literal

from gpu.types import GPUBatch, GPUShader

def batch_for_shader(shader: GPUShader, type: Literal['POINTS', 'LINES', 'TRIS', 'LINE_STRIP', 'TRI_STRIP', 'LINES_ADJ', 'TRIS_ADJ', 'LINE_STRIP_ADJ'], content: dict[str, Buffer | Sequence[float] | Sequence[int] | Sequence[Sequence[float]] | Sequence[Sequence[int]]], *, indices: Buffer | Sequence[int] | Sequence[Sequence[int]] | None = None) -> GPUBatch: ...
