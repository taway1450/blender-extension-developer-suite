"""The rename operator and its helpers."""

import csv
import re

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper


def renamer_settings():
    # demo: assumptions
    # demo: blender-assumed-context-member
    return bpy.context.scene.legacy_renamer


def addon_preferences():
    return bpy.context.preferences.addons[__name__.partition(".")[0]].preferences


class OBJECT_OT_legacy_rename(bpy.types.Operator):
    """Rename the target objects: prefix and number, then the find/replace rules"""

    bl_idname = "object.legacy_rename"
    bl_label = "Batch Rename"
    bl_options = {"REGISTER", "UNDO"}

    # demo: imprecise_annotations
    # demo: blender-imprecise-operator-return
    def execute(self, context) -> set[str]:
        settings = renamer_settings()
        separator = addon_preferences().separator
        if settings.target == "SELECTED":
            objects = context.selected_objects
        elif settings.target == "ALL":
            objects = list(context.scene.objects)
        else:
            objects = list(bpy.data.collections[settings.target].objects)
        if not objects:
            self.report({"WARNING"}, "Nothing to rename")
            return {"CANCELLED"}

        objects.sort(key=lambda ob: ob.name)
        for number, ob in enumerate(objects, settings.start):
            name = ob.name
            if settings.prefix:
                name = settings.prefix + separator + str(number).zfill(settings.padding)
            for rule in settings.rules:
                if rule.enabled and rule.find:
                    name = re.sub(rule.find, rule.replace, name)
            if settings.case == "UPPER":
                name = name.upper()
            elif settings.case == "LOWER":
                name = name.lower()
            if not ob.legacy_original_name:
                # The list comes from three places, one of them untyped, so `ob` is only partly known.
                # The write is still checked against the property `register()` adds to `Object`.
                # demo: properties
                ob.legacy_original_name = ob.name
            ob.name = name

        if settings.tag_collections and bpy.app.version >= (2, 91, 0):
            color = f"COLOR_{len(settings.rules) % 8 + 1:02d}"
            # demo: blender-assumed-registration
            bpy.ops.object.legacy_tag_collections(color=color)
        return {"FINISHED"}


class OBJECT_OT_legacy_tag_collections(bpy.types.Operator):
    """Give the collections of the selected objects a color tag"""

    bl_idname = "object.legacy_tag_collections"
    bl_label = "Tag Collections"
    bl_options = {"REGISTER", "UNDO"}

    color: EnumProperty(
        name="Color",
        items=[(f"COLOR_{n:02d}", f"Color {n}", "") for n in range(1, 9)],
    )

    def execute(self, context):
        for ob in context.selected_objects:
            for collection in ob.users_collection:
                collection.color_tag = self.color
        return {"FINISHED"}


class OBJECT_OT_legacy_rule_add(bpy.types.Operator):
    """Add a rule that matches the active object's name"""

    bl_idname = "object.legacy_rule_add"
    bl_label = "Add Rule"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        settings = context.scene.legacy_renamer
        rule = settings.rules.add()
        # demo: blender-assumed-internal-operator
        rule.find = re.escape(context.object.name)
        settings.active_rule = len(settings.rules) - 1
        return {"FINISHED"}


class OBJECT_OT_legacy_rule_remove(bpy.types.Operator):
    """Remove the active rule"""

    bl_idname = "object.legacy_rule_remove"
    bl_label = "Remove Rule"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        settings = context.scene.legacy_renamer
        settings.rules.remove(settings.active_rule)
        settings.active_rule = max(0, settings.active_rule - 1)
        return {"FINISHED"}


class IMPORT_OT_legacy_rules(bpy.types.Operator, ImportHelper):
    """Read find/replace rules from a CSV file with two columns"""

    bl_idname = "import_scene.legacy_rules"
    bl_label = "Import Rename Rules"

    filename_ext = ".csv"
    # demo: blender-legacy-property
    filter_glob = StringProperty(default="*.csv", options={"HIDDEN"})

    def execute(self, context):
        settings = context.scene.legacy_renamer
        with open(self.filepath, newline="", encoding="utf-8") as file:
            for find, replace in csv.reader(file):
                rule = settings.rules.add()
                rule.find = find
                rule.replace = replace
        return {"FINISHED"}


# OBJECT_OT_legacy_tag_collections is registered by register(), for the versions that have color tags.
classes = (
    OBJECT_OT_legacy_rename,
    OBJECT_OT_legacy_rule_add,
    OBJECT_OT_legacy_rule_remove,
    IMPORT_OT_legacy_rules,
)
