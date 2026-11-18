"""Reference stub delta: the thick-wrapped version arrays are tuples, every struct has bl_rna and rna_type,
Operator.description may return None, a bpy.data collection takes a (name, library) key, the context store members Blender's UI sets, libraries.load and temp_data
are context managers, the render engine's update callbacks take positional arguments, a dynamic enum is a str and
Gizmo.target_set_value takes a value. A string argument without PROP_NEVER_NULL takes None, an AnyType argument a
typed collection, foreach_get a list of ints or bools and libraries.write a set of one ID type; ID.copy and
evaluated_get return the type they are called on, context.property is a (data, path, index) tuple and the render
engine is a str."""

import contextlib
from collections.abc import Buffer, MutableSequence, Sequence
from typing import Any, Literal, Self, TypeVar, overload

_IDT = TypeVar('_IDT', bound=ID)

class bpy_struct:
    bl_rna: Struct
    @property
    def rna_type(self) -> Struct: ...

class bpy_prop_collection:
    def foreach_get(self, attr: str, seq: MutableSequence[bool] | MutableSequence[int] | MutableSequence[float] | Buffer) -> None: ...

class ID:
    def copy(self) -> Self: ...
    def evaluated_get(self, depsgraph: Depsgraph) -> Self: ...

class Area:
    def header_text_set(self, text: str | None) -> None: ...

class UILayout:
    def template_ID(self, data: bpy_struct | bpy_prop_collection, property: str, *, new: str='', open: str='', unlink: str='', filter: Literal['ALL', 'AVAILABLE']='ALL', live_icon: bool=False, text: str='', text_ctxt: str='', translate: bool=True) -> None: ...
    def prop_search(self, data: bpy_struct | bpy_prop_collection, property: str, search_data: bpy_struct | bpy_prop_collection, search_property: str, *, text: str='', text_ctxt: str='', translate: bool=True, icon: str='NONE', results_are_suggestions: bool=False, item_search_property: str='') -> None: ...

class RenderSettings:
    engine: str

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
    def write(self, filepath: str | bytes, datablocks: set[_IDT], *, path_remap: str='NONE', fake_user: bool=False, compress: bool=False) -> None: ...
    def load(self, filepath: str | bytes, *, link: bool = False, pack: bool = False, relative: bool = False, set_fake: bool = False, recursive: bool = False, reuse_local_id: bool = False, assets_only: bool = False, clear_asset_data: bool = False, create_liboverrides: bool = False, reuse_liboverrides: bool = False, create_liboverrides_runtime: bool = False) -> contextlib.AbstractContextManager[tuple[Any, Any]]: ...

class Context:
    constraint: Constraint | None
    keymap: KeyMap | None
    animated_id: ID | None
    freestyle_module: FreestyleModuleSettings | None
    tool: WorkSpaceTool | None
    asset_shelf: AssetShelf | None
    property: tuple[bpy_struct, str, int] | None

class RenderEngine:
    def update_script_node(self, node: Node | None) -> None: ...
    def update_render_passes(self, scene: Scene, renderlayer: ViewLayer) -> None: ...
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
