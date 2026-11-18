"""Reference stub delta: pointers to structs embedded by value, the context's preferences and window manager, and the
callback parameters Blender always fills, the pointers and function results Blender always sets."""

from typing import Literal

from idprop.types import IDPropertyUIManager


class Camera:
    dof: CameraDOFSettings

class Scene:
    view_settings: ColorManagedViewSettings
    eevee: SceneEEVEE

class RenderSettings:
    ffmpeg: FFmpegSettings

class ToolSettings:
    image_paint: ImagePaint
    sculpt: Sculpt | None

class Context:
    preferences: Preferences
    window_manager: WindowManager

class Object:
    pose: Pose | None
    animation_data: AnimData | None

class Menu:
    @classmethod
    def poll(cls, context: Context) -> bool: ...
    def draw(self, context: Context) -> None: ...

class Header:
    def draw(self, context: Context) -> None: ...

class UIList:
    def draw_item(self, context: Context, layout: UILayout, data: bpy_struct, item: bpy_struct | None, icon: int, active_data: bpy_struct | None, active_property: str, index: int, flt_flag: int) -> None: ...
    def draw_filter(self, context: Context, layout: UILayout) -> None: ...
    def filter_items(self, context: Context, data: bpy_struct, property: str) -> tuple[bpy_prop_array[int], bpy_prop_array[int]]: ...

class RenderEngine:
    def update(self, data: BlendData | None, depsgraph: Depsgraph) -> None: ...
    def render(self, depsgraph: Depsgraph) -> None: ...
    def view_update(self, context: Context, depsgraph: Depsgraph) -> None: ...
    def view_draw(self, context: Context | None, depsgraph: Depsgraph) -> None: ...

class KeyingSetInfo:
    def iterator(self, context: Context, ks: KeyingSet) -> None: ...
    def generate(self, context: Context, ks: KeyingSet, data: bpy_struct) -> None: ...

class AssetShelf:
    @classmethod
    def asset_poll(cls, asset: AssetRepresentation) -> bool: ...
    @classmethod
    def draw_context_menu(cls, context: Context, asset: AssetRepresentation, layout: UILayout) -> None: ...

class XrSessionState:
    viewfinder: XrViewfinderState

class WindowManager:
    xr_session_state: XrSessionState | None

class KeyConfigurations:
    active: KeyConfig
    default: KeyConfig
    addon: KeyConfig
    user: KeyConfig

class NodeLink:
    from_node: Node
    to_node: Node
    from_socket: NodeSocket
    to_socket: NodeSocket

class NodeInternalLink:
    from_socket: NodeSocket
    to_socket: NodeSocket

class Bone:
    color: BoneColor

class PoseBone:
    color: BoneColor

class EditBone:
    color: BoneColor

class MovieTracking:
    reconstruction: MovieTrackingReconstruction

class MovieTrackingObject:
    reconstruction: MovieTrackingReconstruction

class MovieTrackingObjects:
    active: MovieTrackingObject

class SpaceView3D:
    region_3d: RegionView3D

class AssetRepresentation:
    metadata: AssetMetaData

class Depsgraph:
    scene: Scene
    scene_eval: Scene
    view_layer: ViewLayer
    view_layer_eval: ViewLayer

class DepsgraphObjectInstance:
    object: Object
    instance_object: Object | None
    parent: Object | None

class DepsgraphUpdate:
    id: ID

class Material:
    node_tree: NodeTree

class World:
    node_tree: NodeTree

class BlendDataNodeTrees:
    def new(self, name: str, type: Literal['GeometryNodeTree', 'CompositorNodeTree', 'ShaderNodeTree', 'TextureNodeTree']) -> NodeTree: ...

class AssetLibraryCollection:
    @classmethod
    def new(cls, *, name: str = '', directory: str = '', remote_url: str = '', extension_id: str = '') -> UserAssetLibrary: ...

class bpy_struct:
    def id_properties_ui(self, key: str, /) -> IDPropertyUIManager: ...
