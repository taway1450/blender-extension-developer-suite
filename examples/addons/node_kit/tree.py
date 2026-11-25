"""The calculator: a node tree type of the add-on's own, whose nodes compute one number."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, FloatProperty
from bpy.types import Node, NodeSocket, NodeTree, Operator


class KitNodeTree(NodeTree):
    """Compute a number from value and math nodes"""

    bl_idname = "KitNodeTree"
    bl_label = "Kit Calculator"
    bl_icon = "NODETREE"


class KitFloatSocket(NodeSocket):
    bl_idname = "KitFloatSocket"
    bl_label = "Number"

    value: FloatProperty(name="Value")

    def draw(self, context, layout, node, text):
        if self.is_output or self.is_linked:
            layout.label(text=text)
        else:
            layout.prop(self, "value", text=text)

    @classmethod
    def draw_color_simple(cls):
        return (0.4, 0.7, 0.9, 1.0)


class KitNode:
    """For the calculator's nodes: they can only be added to a calculator tree."""

    @classmethod
    def poll(cls, node_tree):
        return node_tree.bl_idname == "KitNodeTree"


# demo: inheritance
class KitValueNode(KitNode, Node):
    bl_idname = "KitValueNode"
    bl_label = "Value"

    value: FloatProperty(name="Value", default=1.0)

    def init(self, context):
        self.outputs.new("KitFloatSocket", "Value")

    def draw_buttons(self, context, layout):
        layout.prop(self, "value", text="")

    def evaluate(self) -> float:
        return self.value


class KitMathNode(KitNode, Node):
    bl_idname = "KitMathNode"
    bl_label = "Math"

    operation: EnumProperty(
        name="Operation",
        items=(
            ("ADD", "Add", "A + B"),
            ("MULTIPLY", "Multiply", "A * B"),
            ("MAXIMUM", "Maximum", "The larger of A and B"),
        ),
        default="ADD",
    )

    def init(self, context):
        self.inputs.new("KitFloatSocket", "A")
        self.inputs.new("KitFloatSocket", "B")
        self.outputs.new("KitFloatSocket", "Result")

    def draw_buttons(self, context, layout):
        layout.prop(self, "operation", text="")

    def draw_label(self):
        return self.operation.title()

    def evaluate(self) -> float:
        a = input_value(self.inputs["A"])
        b = input_value(self.inputs["B"])
        if self.operation == "ADD":
            return a + b
        if self.operation == "MULTIPLY":
            return a * b
        return max(a, b)


def input_value(socket: NodeSocket) -> float:
    """The number an input has: what the node linked to it computes, or the socket's own value."""
    if socket.is_linked:
        source = socket.links[0].from_node
        if isinstance(source, (KitValueNode, KitMathNode)):
            return source.evaluate()
    return socket.value if isinstance(socket, KitFloatSocket) else 0.0


class CalculatorEditor:
    """For operators of a node editor that shows calculator trees."""

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == "NODE_EDITOR"
            and space.tree_type == "KitNodeTree"
        )


class NODE_OT_kit_new_tree(CalculatorEditor, Operator):
    """Add a calculator tree that multiplies two values, and show it"""

    bl_idname = "node.kit_new_tree"
    bl_label = "New Calculator"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # demo: later/own-node-tree-types
        tree = bpy.data.node_groups.new("Calculator", "KitNodeTree")
        # demo: type_narrowing
        value = tree.nodes.new("KitValueNode")
        value.value = 2.0
        math = tree.nodes.new("KitMathNode")
        math.operation = "MULTIPLY"
        math.location = (200.0, 0.0)
        tree.links.new(value.outputs["Value"], math.inputs["A"])
        tree.nodes.active = math
        context.space_data.node_tree = tree
        return {"FINISHED"}


class NODE_OT_kit_evaluate(CalculatorEditor, Operator):
    """Report the number the active node computes"""

    bl_idname = "node.kit_evaluate"
    bl_label = "Evaluate"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.active_node is not None

    def execute(self, context):
        node = context.active_node
        if isinstance(node, (KitValueNode, KitMathNode)):
            self.report({"INFO"}, f"{node.name} = {node.evaluate():.3f}")
        return {"FINISHED"}


classes = (
    KitNodeTree,
    KitFloatSocket,
    KitValueNode,
    KitMathNode,
    NODE_OT_kit_new_tree,
    NODE_OT_kit_evaluate,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
