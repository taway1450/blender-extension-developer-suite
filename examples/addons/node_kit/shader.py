"""Helpers for the shader editor, and the assets the kit ships in a .blend file."""

from __future__ import annotations

import os

import bpy
from bpy.props import FloatVectorProperty
from bpy.types import Operator

ASSETS = os.path.join(os.path.dirname(__file__), "assets.blend")


class ShaderEditor:
    """For operators of a node editor that shows a material's nodes."""

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == "NODE_EDITOR"
            and space.tree_type == "ShaderNodeTree"
            and space.node_tree is not None
        )


class NODE_OT_kit_principled_setup(ShaderEditor, Operator):
    """Add a Principled BSDF with an image texture for its base color"""

    bl_idname = "node.kit_principled_setup"
    bl_label = "Principled Setup"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # The poll checked `node_tree`; Blender keeps `edit_tree` set whenever that one is.
        # demo: pointer_aliases
        tree = context.space_data.edit_tree

        # demo: type_narrowing
        shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
        shader.subsurface_method = "BURLEY"
        # demo: api_types
        shader.inputs["Roughness"].default_value = 0.6

        texture = tree.nodes.new("ShaderNodeTexImage")
        texture.location = (-320.0, 0.0)
        texture.interpolation = "Smart"
        tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
        tree.nodes.active = shader
        return {"FINISHED"}


class NODE_OT_kit_tint_active(ShaderEditor, Operator):
    """Set the color of the active node"""

    bl_idname = "node.kit_tint_active"
    bl_label = "Tint Active Node"
    bl_options = {"REGISTER", "UNDO"}

    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        size=4,
        default=(1.0, 0.5, 0.2, 1.0),
        min=0.0,
        max=1.0,
    )

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.active_node is not None

    def execute(self, context):
        node = context.active_node
        if node.type == "BSDF_PRINCIPLED":
            socket = node.inputs["Base Color"]
            socket.default_value = self.tinted(socket.default_value)
        elif node.type == "RGB":
            socket = node.outputs["Color"]
            socket.default_value = self.tinted(socket.default_value)
        else:
            # Any other node: its "Color" input is taken to be a color socket.
            socket = node.inputs["Color"]
            # demo: blender-assumed-subclass-member
            color = self.tinted(socket.default_value)
            # demo: later/subclass-member-writes
            socket.default_value = color
        return {"FINISHED"}

    def tinted(self, color) -> list[float]:
        return [a * b for a, b in zip(color, self.color, strict=True)]


class NODE_OT_kit_append_assets(Operator):
    """Append the kit's rust material and its scatter node group"""

    bl_idname = "node.kit_append_assets"
    bl_label = "Append Kit Assets"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        with bpy.data.libraries.load(ASSETS) as (_source, target):
            target.materials = ["Rust"]
            target.node_groups = ["Scatter Points"]

        # The names are those of assets.blend, where the material has nodes.
        # demo: later/blend-file-typing
        rust = bpy.data.materials["Rust"]
        principled = rust.node_tree.nodes["Principled BSDF"]
        principled.inputs["Roughness"].default_value = 0.9
        if context.object is not None and context.object.type == "MESH":
            context.object.data.materials.append(rust)
        return {"FINISHED"}


classes = (
    NODE_OT_kit_principled_setup,
    NODE_OT_kit_tint_active,
    NODE_OT_kit_append_assets,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
