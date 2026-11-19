"""Reference stub delta: a struct's id_data is the ID that owns it, the thick-wrapped version arrays are tuples, every struct has bl_rna and rna_type,
Operator.description may return None, a bpy.data collection takes a (name, library) key, the context store members Blender's UI sets, libraries.load and temp_data
are context managers, the render engine's update callbacks take positional arguments, a dynamic enum is a str and
Gizmo.target_set_value takes a value. A string argument without PROP_NEVER_NULL takes None, an AnyType argument a
typed collection, foreach_get a list of ints or bools and libraries.write a set of one ID type; ID.copy and
evaluated_get return the type they are called on, context.property is a (data, path, index) tuple and the render
engine is a str.
animation_data_create gives an ID type with animation data its AnimData, the gpu buffers' protocols, the pointers Blender
always allocates (a strip's transform and crop, an area's active space, the Graph and NLA editors' dope sheet), a
collection's items and values, a shape key's points, the iTaSC parameters, the members every subclass of a refined base
declares, a bone collection's armature, the enums the OCIO configuration or the curve dimensions fill, a collection
struct's bl_rna and rna_type, the RNA function and ID property metaclass types, and UI_UL_list taking a collection."""

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

class Node:
    id_data: NodeTree

class PoseBone:
    id_data: Object

class Modifier:
    id_data: Object

class MeshVertex:
    id_data: Mesh

class AttributeGroupMesh:
    id_data: Mesh

class Strip:
    id_data: Scene

class bpy_prop_array:
    def foreach_get(self, seq: MutableSequence[Any] | Buffer) -> None: ...
    def foreach_set(self, seq: Sequence[Any] | Buffer) -> None: ...

class Object:
    def animation_data_create(self) -> AnimData: ...

class Material:
    def animation_data_create(self) -> AnimData: ...

class Scene:
    def animation_data_create(self) -> AnimData: ...

class ImageStrip:
    @property
    def transform(self) -> StripTransform: ...
    @property
    def crop(self) -> StripCrop: ...

class AreaSpaces:
    @property
    def active(self) -> Space: ...

class SpaceGraphEditor:
    @property
    def dopesheet(self) -> DopeSheet: ...

class SpaceNLA:
    @property
    def dopesheet(self) -> DopeSheet: ...

class BlendDataObjects:
    def items(self) -> list[tuple[str, Object]]: ...
    def values(self) -> list[Object]: ...

class ShapeKey:
    @property
    def data(self) -> bpy_prop_collection[ShapeKeyPoint | ShapeKeyCurvePoint | ShapeKeyBezierPoint]: ...

class Pose:
    @property
    def ik_param(self) -> Itasc | None: ...

class Light:
    shadow_maximum_resolution: float

class UserAssetLibrary:
    path: str

class Attribute:
    @property
    def data(self) -> bpy_prop_collection[BoolAttributeValue] | bpy_prop_collection[ByteColorAttributeValue] | bpy_prop_collection[ByteIntAttributeValue] | bpy_prop_collection[Float2AttributeValue] | bpy_prop_collection[Float4AttributeValue] | bpy_prop_collection[Float4x4AttributeValue] | bpy_prop_collection[FloatAttributeValue] | bpy_prop_collection[FloatColorAttributeValue] | bpy_prop_collection[FloatVectorAttributeValue] | bpy_prop_collection[Int2AttributeValue] | bpy_prop_collection[IntAttributeValue] | bpy_prop_collection[QuaternionAttributeValue] | bpy_prop_collection[Short2AttributeValue] | bpy_prop_collection[StringAttributeValue]: ...

class BoneCollection:
    id_data: Armature

class ColorManagedViewSettings:
    view_transform: str
    look: str

class ColorManagedDisplaySettings:
    display_device: str

class Curve:
    fill_mode: str

class BlendDataCurves:
    bl_rna: Struct
    @property
    def rna_type(self) -> Struct: ...

class bpy_func:
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

class bpy_struct_meta_idprop(type): ...

class UI_UL_list:
    @staticmethod
    def filter_items_by_name(pattern: str, bitflag: int, items: Sequence[Any] | bpy_prop_collection, propname: str = 'name', flags: Sequence[int] | None = None, reverse: bool = False) -> list[int]: ...
    @classmethod
    def sort_items_by_name(cls, items: Sequence[Any] | bpy_prop_collection, propname: str = 'name') -> list[int]: ...
