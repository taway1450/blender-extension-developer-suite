"""Feature test: blender-invalid-idname. An operator idname is category.name in lower case letters, digits and
underscores; Blender refuses others (each checked on its own in Blender 5.4), and an operator without bl_idname
gets its class name, which is not valid either. Panel and menu idnames need _PT_ / _MT_ (Blender warns); without
bl_idname the class name is used."""

import bpy
from bpy.types import Menu, Operator, Panel


class REGCHK_IDNAME_OT_upper_form(Operator):
    bl_idname = "REGCHK_IDNAME_OT_upper_form"  # ty: ignore[blender-invalid-idname]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_upper_name(Operator):
    bl_idname = "regchk_idname.Upper"  # ty: ignore[blender-invalid-idname]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_two_dots(Operator):
    bl_idname = "regchk_idname.a.b"  # ty: ignore[blender-invalid-idname]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_dash(Operator):
    bl_idname = "regchk_idname.has-dash"  # ty: ignore[blender-invalid-idname]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_empty(Operator):
    bl_idname = ""  # ty: ignore[blender-invalid-idname]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_no_category(Operator):
    bl_idname = "nocategory"  # ty: ignore[blender-invalid-idname]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_no_category_name(Operator):
    bl_idname = ".name"  # ty: ignore[blender-invalid-idname]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_no_name(Operator):
    bl_idname = "regchk_idname."  # ty: ignore[blender-invalid-idname]
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_missing(Operator):  # ty: ignore[blender-invalid-idname]
    bl_label = "Missing"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_OT_valid(Operator):
    bl_idname = "regchk_idname.valid_name_2"
    bl_label = "Run"

    def execute(self, context):
        return {"FINISHED"}


class REGCHK_IDNAME_PT_valid(Panel):
    bl_label = "Valid"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


class REGCHK_IDNAME_PT_explicit(Panel):
    bl_idname = "REGCHK_IDNAME_PT_other_name"
    bl_label = "Explicit"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


class RegchkIdnamePanel(Panel):  # ty: ignore[blender-invalid-idname]
    bl_label = "Class name"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


class REGCHK_IDNAME_PT_bad(Panel):
    bl_idname = "regchk_idname_panel"  # ty: ignore[blender-invalid-idname]
    bl_label = "Bad"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        pass


class REGCHK_IDNAME_MT_valid(Menu):
    bl_label = "Valid"

    def draw(self, context):
        pass


class REGCHK_IDNAME_MT_bad(Menu):
    bl_idname = "regchk_idname.menu"  # ty: ignore[blender-invalid-idname]
    bl_label = "Bad"

    def draw(self, context):
        pass


classes = (
    REGCHK_IDNAME_OT_valid,
    REGCHK_IDNAME_PT_valid,
    REGCHK_IDNAME_PT_explicit,
    RegchkIdnamePanel,
    REGCHK_IDNAME_PT_bad,
    REGCHK_IDNAME_MT_valid,
    REGCHK_IDNAME_MT_bad,
    REGCHK_IDNAME_OT_upper_form,
    REGCHK_IDNAME_OT_upper_name,
    REGCHK_IDNAME_OT_two_dots,
    REGCHK_IDNAME_OT_dash,
    REGCHK_IDNAME_OT_empty,
    REGCHK_IDNAME_OT_no_category,
    REGCHK_IDNAME_OT_no_category_name,
    REGCHK_IDNAME_OT_no_name,
    REGCHK_IDNAME_OT_missing,
)

register, unregister = bpy.utils.register_classes_factory(classes)
