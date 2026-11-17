"""Reference stub delta: the thick-wrapped version arrays are tuples, every struct has bl_rna,
Operator.description may return None, a bpy.data collection takes a (name, library) key, the context store members Blender's UI sets, libraries.load and temp_data
are context managers, the render engine's update callbacks take positional arguments, a dynamic enum is a str and
Gizmo.target_set_value takes a value."""

import contextlib
from collections.abc import Sequence
from typing import Any, overload

class bpy_struct:
    bl_rna: Struct

class BlendData:
    version: tuple[int, int, int]
    @staticmethod
    def temp_data(*, filepath: str | bytes | None = None) -> contextlib.AbstractContextManager[BlendData]: ...

class BlendDataObjects:
    @overload
    def __getitem__(self, key: tuple[str, str | None], /) -> Object: ...

class BlendDataMaterials:
    @overload
    def __getitem__(self, key: tuple[str, str | None], /) -> Material: ...

class BlendDataLibraries:
    def load(self, filepath: str | bytes, *, link: bool = False, pack: bool = False, relative: bool = False, set_fake: bool = False, recursive: bool = False, reuse_local_id: bool = False, assets_only: bool = False, clear_asset_data: bool = False, create_liboverrides: bool = False, reuse_liboverrides: bool = False, create_liboverrides_runtime: bool = False) -> contextlib.AbstractContextManager[tuple[Any, Any]]: ...

class Context:
    constraint: Constraint | None
    keymap: KeyMap | None
    animated_id: ID | None
    freestyle_module: FreestyleModuleSettings | None
    tool: WorkSpaceTool | None
    asset_shelf: AssetShelf | None

class RenderEngine:
    def update_script_node(self, node: Node | None) -> None: ...
    def update_render_passes(self, scene: Scene | None, renderlayer: ViewLayer | None) -> None: ...
    def update_custom_camera(self, cam: Camera | None) -> None: ...

class NodeTreeInterface:
    def new_socket(self, name: str, *, description: str = "", in_out: str = "INPUT", socket_type: str = "DEFAULT", parent: NodeTreeInterfacePanel | None = None) -> NodeTreeInterfaceSocket: ...

class Gizmo:
    def target_set_value(self, target: str, value: float | Sequence[float]) -> None: ...

class Preferences:
    version: tuple[int, int, int]

class Library:
    version: tuple[int, int, int]

class Operator:
    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str | None: ...
