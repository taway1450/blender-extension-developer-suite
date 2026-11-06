"""Reference stub delta: pointers to structs embedded by value and the callback contexts Blender always passes."""

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
    def draw_item(self, context: Context, layout: UILayout, data: bpy_struct | None, item: bpy_struct | None, icon: int, active_data: bpy_struct | None, active_property: str, index: int, flt_flag: int) -> None: ...
    def draw_filter(self, context: Context, layout: UILayout) -> None: ...

class RenderEngine:
    def view_update(self, context: Context, depsgraph: Depsgraph | None) -> None: ...
    def view_draw(self, context: Context | None, depsgraph: Depsgraph | None) -> None: ...
