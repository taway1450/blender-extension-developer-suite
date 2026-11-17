"""Feature test: a Panel's bl_context narrows what Blender enforces before it polls the panel.

Blender adds a top-level panel to a region only when the region's contexts name its bl_context (panel_add_check in
area.cc), before it calls the panel's poll; a sub-panel is drawn only inside its parent. Two kinds of region enforce it:
- the Properties editor's main region draws the panels of the active tab ("object", "physics", ...;
  buttons_main_region_context_string in space_buttons.cc), and a tab is active only while its context path exists
  (buttons_context_compute in buttons_context.cc). The object, physics, constraint, modifier, shaderfx and
  bone_constraint paths need an object (pinned or active), so context.object is set there; "data", "material" and
  "particle" also take pinned data, a material or particle settings without an object;
- the 3D viewport's sidebar and toolbar draw the panels of the current mode (CTX_data_mode_string in context.cc), so
  "mesh_edit" gives what context.mode == 'EDIT_MESH' does: an edit object of the mesh type.
Not narrowed: the display-only contexts (".objectmode", ".mesh_edit", ...: the tool-settings groups the tool header
also draws as popovers, where no context is checked), "objectmode" (no object needed), a mode context in an editor
whose regions check none, and a panel the add-on opens as a popover.

Reported under blender-narrowed-by-bl-context. The assert_type calls in the bodies are no-ops at runtime."""

from typing import assert_type

import bpy
from bpy.types import Mesh, Object, Panel, Pose


class ObjectButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"


class NAR_BL_CONTEXT_PT_object(ObjectButtonsPanel, Panel):
    bl_label = "Object"

    def draw(self, context):
        assert_type(context.object, Object)  # ty: ignore[blender-narrowed-by-bl-context]
        context.active_object.name  # ty: ignore[missing-union-attribute]  # bare-ok: the tab's object, not the active one


class NAR_BL_CONTEXT_PT_object_poll(ObjectButtonsPanel, Panel):
    bl_label = "Object poll"

    @classmethod
    def poll(cls, context):
        ob = context.object  # ty: ignore[blender-narrowed-by-bl-context]
        return ob.type in {"MESH", "EMPTY"}

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[blender-narrowed-by-poll]


class NAR_BL_CONTEXT_PT_object_sub(ObjectButtonsPanel, Panel):
    bl_label = "Object sub-panel"
    bl_parent_id = "NAR_BL_CONTEXT_PT_object"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[blender-narrowed-by-bl-context]


class NAR_BL_CONTEXT_PT_physics(Panel):
    bl_label = "Physics"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "physics"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[blender-narrowed-by-bl-context]


class NAR_BL_CONTEXT_PT_data(Panel):
    bl_label = "Data"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[missing-union-attribute]  # bare-ok: pinned data has no object


class NAR_BL_CONTEXT_PT_mesh_edit(Panel):
    bl_label = "Mesh edit"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mode"
    bl_context = "mesh_edit"

    def draw(self, context):
        assert_type(context.object.data, Mesh)  # ty: ignore[blender-narrowed-by-bl-context]
        assert_type(context.edit_object.data, Mesh)  # ty: ignore[blender-narrowed-by-bl-context]


class NAR_BL_CONTEXT_PT_posemode(Panel):
    bl_label = "Pose"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = "posemode"

    def draw(self, context):
        assert_type(context.object.pose, Pose)  # ty: ignore[blender-narrowed-by-bl-context]


class NAR_BL_CONTEXT_PT_objectmode_tools(Panel):
    bl_label = "Object mode tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_context = ".objectmode"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[missing-union-attribute]  # bare-ok: display-only context


class NAR_BL_CONTEXT_PT_mesh_edit_tools(Panel):
    bl_label = "Mesh edit tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_context = ".mesh_edit"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[missing-union-attribute]  # bare-ok: display-only context


class NAR_BL_CONTEXT_PT_objectmode(Panel):
    bl_label = "Object mode"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mode"
    bl_context = "objectmode"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[missing-union-attribute]  # bare-ok: object mode needs no object


class NAR_BL_CONTEXT_PT_image_mesh_edit(Panel):
    bl_label = "Image editor"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Mode"
    bl_context = "mesh_edit"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[missing-union-attribute]  # bare-ok: the image editor checks no mode


class NAR_BL_CONTEXT_PT_popover(Panel):
    bl_label = "Popover"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mode"
    bl_context = "mesh_edit"

    def draw(self, context):
        self.layout.label(text=context.object.name)  # ty: ignore[missing-union-attribute]  # bare-ok: opened as a popover below


class NAR_BL_CONTEXT_PT_opener(Panel):
    bl_label = "Opener"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Mode"

    def draw(self, context):
        self.layout.popover("NAR_BL_CONTEXT_PT_popover")


classes = (
    NAR_BL_CONTEXT_PT_object,
    NAR_BL_CONTEXT_PT_object_poll,
    NAR_BL_CONTEXT_PT_object_sub,
    NAR_BL_CONTEXT_PT_physics,
    NAR_BL_CONTEXT_PT_data,
    NAR_BL_CONTEXT_PT_mesh_edit,
    NAR_BL_CONTEXT_PT_posemode,
    NAR_BL_CONTEXT_PT_objectmode_tools,
    NAR_BL_CONTEXT_PT_mesh_edit_tools,
    NAR_BL_CONTEXT_PT_objectmode,
    NAR_BL_CONTEXT_PT_image_mesh_edit,
    NAR_BL_CONTEXT_PT_popover,
    NAR_BL_CONTEXT_PT_opener,
)
register, unregister = bpy.utils.register_classes_factory(classes)
