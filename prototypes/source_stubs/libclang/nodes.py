"""Nodes: registration functions, socket declarations and the RNA nodes define at registration time.

Every function that calls ``bke::node_register_type(ntype)`` is run: ``*_node_type_base(&ntype, "ShaderNodeMix"_ustr,
...)`` names the node, ``ntype.ui_name`` / ``ui_description`` / ``declare`` are plain assignments, and the
intrinsic for ``node_register_type`` creates the node's RNA struct (base from its tree: ``ShaderNode``,
``GeometryNode``, ...) and runs its ``declare`` function with a symbolic ``NodeDeclarationBuilder``:
``b.add_input<decl::Float>("Name").identifier("x").subtype(PROP_FACTOR)`` is a chain of member calls whose template
argument clang resolved (``decl::Float``). Sockets declared under a condition or in a loop the interpreter cannot
decide (``if (node->storage...)``) are marked dynamic. ``node_rna(ntype.rna_ext.srna)`` then defines the node's
properties on that struct, through ``RNA_def_node_enum`` and friends run from ``node_rna_define.cc``.
"""

from __future__ import annotations

import re

from common.model import NodeDecl, NodeSocket

from .interp import UNKNOWN, FuncRef, Interp, Obj

PREFIX_BASES = (
    ("GeometryNode", "GeometryNode"),
    ("ShaderNode", "ShaderNode"),
    ("CompositorNode", "CompositorNode"),
    ("TextureNode", "TextureNode"),
    ("FunctionNode", "FunctionNode"),
    ("Node", "NodeInternal"),
)
_DECL = re.compile(r"decl::(\w+)")
# ``eNodeSocketDatatype`` (DNA_node_types.h) -> socket declaration type
SOCK_TYPES = {
    0: "Float",
    1: "Vector",
    2: "Color",
    3: "Shader",
    4: "Bool",
    6: "Int",
    7: "String",
    8: "Object",
    9: "Image",
    10: "Geometry",
    11: "Collection",
    12: "Texture",
    13: "Material",
    14: "Rotation",
    15: "Menu",
    16: "Matrix",
    17: "Bundle",
    18: "Closure",
    19: "Font",
    20: "Scene",
    21: "Text",
    22: "Mask",
}


class Nodes:
    def __init__(self, interp: Interp, rna, model) -> None:
        self.i = interp
        self.rna = rna
        self.model = model
        self.decls: dict[str, NodeDecl] = {}
        self.registered = 0
        I = interp.intrinsics
        I["node_register_type"] = self.register_type
        I["node_type_storage"] = lambda i, a, e, c: None
        M = interp.methods
        M["member:local"] = self.local_member
        for name in ("add_input", "add_output"):
            M[f"builder.{name}"] = self.add_socket
            M[f"panel.{name}"] = self.add_socket
        M["builder.add_panel"] = self.add_panel
        M["panel.add_panel"] = self.add_panel
        M["builder.*"] = lambda i, base, a, e: UNKNOWN
        M["panel.*"] = lambda i, base, a, e: base
        M["socket.*"] = self.socket_method

    def node_type_base(self, i, a, e, call):
        if a and isinstance(a[0], Obj) and len(a) > 1 and isinstance(a[1], str):
            a[0].fields["idname"] = a[1]

    def install_type_base(self) -> None:
        for name in self.i.p.by_name:
            if name.endswith("node_type_base"):
                self.i.intrinsics[name] = self.node_type_base

    def local_member(self, interp, base: Obj, name: str, e):
        if name == "rna_ext" and isinstance(base.fields.get("idname"), str):
            sub = Obj("local", "ExtensionRNA", {"srna": self.struct_for(base.fields["idname"])})
            base.fields["rna_ext"] = sub
            return sub
        return UNKNOWN

    def struct_for(self, idname: str) -> Obj:
        base = next((b for p, b in PREFIX_BASES if idname.startswith(p)), "NodeInternal")
        return self.rna.struct_handle(idname, base, "")

    # ----------------------------------------------------------------------------------------------------------------
    def register_type(self, i, a, e, call):
        nt = a[0] if a else None
        if not isinstance(nt, Obj):
            return
        idname = nt.fields.get("idname")
        if not isinstance(idname, str):
            return
        self.registered += 1
        h = self.struct_for(idname)
        s = h.data
        if not s.src:
            s.src = i.src(call[4])
        if isinstance(nt.fields.get("ui_name"), str) and not s.name:
            s.name = nt.fields["ui_name"]
        if isinstance(nt.fields.get("ui_description"), str) and not s.description:
            s.description = nt.fields["ui_description"]
        declare = nt.fields.get("declare")
        if isinstance(declare, FuncRef) and idname not in self.decls:
            fn = i.p.functions.get(declare.usr)
            decl = NodeDecl(idname=idname, src=f"{fn.file}:{fn.line}" if fn else "")
            self.decls[idname] = decl
            if fn is not None:
                saved = i.speculative
                i.speculative = 0
                try:
                    i.call_function(fn, [Obj("builder", decl)])
                finally:
                    i.speculative = saved
        return

    def add_socket(self, i, base: Obj, a, e):
        decl: NodeDecl = base.data
        stype = _decl_type(e)
        if a and not isinstance(a[0], str) and stype == "BaseSocketDeclaration":
            # ``b.add_input(data_type, "Value")``: the socket type is an ``eNodeSocketDatatype`` argument.
            kind, a = a[0], a[1:]
            stype = (
                SOCK_TYPES.get(int(kind), "Custom")
                if isinstance(kind, int) and not isinstance(kind, bool)
                else "Custom"
            )
        name = a[0] if a and isinstance(a[0], str) else ""
        ident = a[1] if len(a) > 1 and isinstance(a[1], str) else ""
        sock = NodeSocket(
            name=name, type=stype, identifier=ident, dynamic=bool(i.speculative) or not name, src=i.src(e[4])
        )
        (decl.inputs if e[1] == "add_input" else decl.outputs).append(sock)
        return Obj("socket", sock)

    def add_panel(self, i, base: Obj, a, e):
        return Obj("panel", base.data)

    def socket_method(self, i, base: Obj, a, e):
        sock: NodeSocket = base.data
        name = e[1]
        if name == "identifier" and a and isinstance(a[0], str):
            sock.identifier = a[0]
        elif name == "subtype" and a:
            names = getattr(a[0], "names", ())
            if names:
                sock.subtype = next(iter(names)).removeprefix("PROP_").lower()
        return base

    # ----------------------------------------------------------------------------------------------------------------
    def run(self, files: set[str]) -> None:
        self.install_type_base()
        for fn in list(self.i.p.functions.values()):
            if fn.file not in files:
                continue
            if _calls(fn.body, "node_register_type") and not fn.params:
                self.i.call_function(fn, [])
        self.model.nodes.extend(self.decls.values())


def _decl_type(e: list) -> str:
    """The socket declaration type of ``b.add_input<decl::Float>(...)``. libclang spells the specialization
    ``add_input<>`` without its argument, so it is read from the call's return type: ``decl::Float::Builder`` is
    ``FloatBuilder`` (``CustomTypeBuilder`` for ``decl::Custom``), and declarations without their own builder
    return ``SocketDeclarationBuilder<decl::Object>`` (record ``Object>``)."""
    m = _DECL.search(e[5] or "")
    if m:
        return m.group(1)
    record = (e[6] if len(e) > 6 else "") or ""
    record = record.rstrip(">& ")
    if record == "CustomTypeBuilder":
        return "Custom"
    if record.endswith("Builder") and record != "Builder":
        return record.removesuffix("Builder")
    return record or "Custom"


def _calls(body, name: str) -> bool:
    stack = [body]
    while stack:
        x = stack.pop()
        if isinstance(x, list):
            if len(x) > 2 and x[0] == "c" and x[2] == name:
                return True
            stack.extend(y for y in x if isinstance(y, list))
    return False
