"""Reference stub delta: pointers to structs embedded by value, the context's preferences and window manager, and the
callback parameters Blender always fills."""

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
