"""Area 5 and the runtime half of area 1: nodes registered in ``source/blender/nodes/**``.

Each registration function (the one calling ``geo_node_type_base(&ntype, "GeometryNodeX"_ustr, ...)``) is run with
``ntype`` bound to a node-type handle: ``ntype.ui_name``/``ui_description`` become the struct's UI text (as
``node_register_type`` does), ``ntype.declare = node_declare`` names the declaration function, and
``node_rna(ntype.rna_ext.srna)`` defines the node's runtime RNA properties through the same ``RNA_def_*`` handlers
(``RNA_def_node_enum`` and friends are executed from ``nodes/intern/node_rna_define.cc``).

Socket declarations are read from ``node_declare(NodeDeclarationBuilder &b)``: every ``.add_input<decl::T>("Name")``
/ ``.add_output<...>`` chain (on ``b`` or on a panel builder), with ``.identifier()`` / ``.subtype()``; sockets
declared inside a loop, a condition, a lambda or with a computed name are marked ``dynamic``. Helper functions that
receive the builder are followed.
"""

from __future__ import annotations

import re
from typing import Any

from common.model import NodeDecl, NodeSocket, RnaStruct, SourceModel
from ctok import CFile, FuncDef, Tok, Tree, call_args, match_close, string_value
from enums import EnumRegistry
from interp import MISSING, FuncRef, Interp, Raw, parse_statements
from rna_area import make_global_lookup, make_initializer_hook
from rnadef import RnaBuilder, make_handlers

BASES = {
    "geo_node_type_base": "GeometryNode",
    "geo_cmp_node_type_base": "GeometryNode",
    "sh_node_type_base": "ShaderNode",
    "sh_geo_node_type_base": "ShaderNode",
    "cmp_node_type_base": "CompositorNode",
    "fn_node_type_base": "FunctionNode",
    "fn_cmp_node_type_base": "FunctionNode",
    "tex_node_type_base": "TextureNode",
    "common_node_type_base": "",
    "node_type_base": "",
}
SOCK_DECL = {"SOCK_FLOAT": "Float", "SOCK_INT": "Int", "SOCK_BOOLEAN": "Bool", "SOCK_VECTOR": "Vector",
             "SOCK_RGBA": "Color", "SOCK_ROTATION": "Rotation", "SOCK_MATRIX": "Matrix", "SOCK_STRING": "String",
             "SOCK_MENU": "Menu", "SOCK_SHADER": "Shader", "SOCK_GEOMETRY": "Geometry", "SOCK_OBJECT": "Object",
             "SOCK_IMAGE": "Image", "SOCK_COLLECTION": "Collection", "SOCK_MATERIAL": "Material",
             "SOCK_TEXTURE": "Texture", "SOCK_BUNDLE": "Bundle", "SOCK_CLOSURE": "Closure"}


class NodeTypeH:
    """A ``bke::bNodeType`` being registered."""

    def __init__(self, builder: RnaBuilder) -> None:
        self.builder = builder
        self.idname = ""
        self.struct: RnaStruct | None = None
        self.declare: Any = None
        self.file: CFile | None = None
        self.src = ""
        self.ui_name = ""
        self.ui_description = ""

    def getmember(self, name: str, ip: Interp) -> Any:
        if name in {"rna_ext"}:
            return self
        if name == "srna":
            return self.struct
        if name == "idname":
            return self.idname
        return None

    def setmember(self, name: str, value: Any, ip: Interp, toks: list[Tok]) -> None:
        if name == "ui_name" and isinstance(value, str):
            self.ui_name = value
            if self.struct is not None:
                self.struct.name = value
        elif name == "ui_description" and isinstance(value, str):
            self.ui_description = value
            if self.struct is not None:
                self.struct.description = value
        elif name == "declare":
            self.declare = value
            self.file = ip.file


def node_files(tree: Tree) -> list[str]:
    return [r for r in tree.glob("source/blender/nodes/**/*.cc") if "/tests/" not in r and not r.endswith("_test.cc") and not r.endswith("_tests.cc")]


def extract_nodes(tree: Tree, model: SourceModel, state: dict[str, Any], extra: dict[str, Any]) -> Interp:
    enums: EnumRegistry = state.get("enums") or EnumRegistry(tree)
    builder: RnaBuilder = state.get("builder") or RnaBuilder(tree, model.structs, enums)
    state.setdefault("enums", enums)
    state.setdefault("builder", builder)
    handlers = make_handlers(builder)
    rna_names = {n for n in handlers if n.startswith("RNA_def")}

    def relevant(fd: FuncDef) -> bool:
        for t in fd.body:
            if t.kind == "id" and (t.text in rna_names or t.text in BASES or t.text.startswith("RNA_def_node")):
                return True
        return False

    ip = Interp(tree, handlers, relevant)
    ip.global_lookup = make_global_lookup(tree, enums, ip)
    handlers["__initializer__"] = make_initializer_hook(tree, enums)
    registered: list[NodeTypeH] = []

    def declare_hook(ip_: Interp, type_toks: list[Tok], name: str) -> Any:
        if any(t.text == "bNodeType" for t in type_toks):
            return NodeTypeH(builder)
        return None

    handlers["__declare__"] = declare_hook

    def type_base(fname: str):
        def h(ip_: Interp, vals: list[Any], toks: Any, pos: int) -> Any:
            nt = vals[0] if vals else None
            if not isinstance(nt, NodeTypeH):
                nt = NodeTypeH(builder)
                # bind the handle to the variable named by the first argument (``&ntype`` / ``ntype``)
                ids = [t.text for t in toks[0] if t.kind == "id"] if toks else []
                if ids:
                    ip_.frame.env.assign(ids[-1], nt, False)
            idname = vals[1] if len(vals) > 1 and isinstance(vals[1], str) else ""
            if not idname:
                ip_.warn("node idname not a constant string", ip_.src(pos))
                return None
            nt.idname = idname
            nt.src = ip_.src(pos)
            st = builder.struct(idname, create=False)
            if st is None:
                st = builder.struct(idname, src=ip_.src(pos))
                st.base = BASES.get(fname) or "Node"
                ip_.warn("node struct not defined by makesrna, created", idname)
            nt.struct = st
            registered.append(nt)
            return None
        return h

    for fname in BASES:
        handlers[fname] = type_base(fname)
    handlers["node_type_base_custom"] = lambda ip_, vals, toks, pos: None

    files = [tree.file(r) for r in node_files(tree)]
    for f in files:
        enums.scan(f)
        ip.add_file(f)
    ip.compute_relevance()

    # Registration functions: those calling a ``*_node_type_base``.
    utils = {"node_composite_util.cc", "node_function_util.cc", "node_geometry_util.cc", "node_shader_util.cc",
             "node_texture_util.cc", "node_util.cc"}
    for f in files:
        if f.rel.rsplit("/", 1)[-1] in utils:
            continue
        for name, defs in f.functions.items():
            for fd in defs:
                if fd.params and not all(p.name == "" for p in fd.params):
                    continue  # registration functions take no arguments
                body = fd.body
                if any(t.kind == "id" and t.text in BASES and k + 1 < len(body) and body[k + 1].text == "(" for k, t in enumerate(body)):
                    ip.run(fd, [])

    # Socket declarations.
    seen: set[str] = set()
    for nt in registered:
        if not nt.idname or nt.idname in seen:
            continue
        seen.add(nt.idname)
        decl = NodeDecl(idname=nt.idname, src=nt.src)
        fd = None
        if isinstance(nt.declare, FuncRef):
            fd = ip.lookup_function(nt.declare.name, nt.file)
        if fd is not None:
            reader = DeclReader(ip, decl)
            reader.read(fd, depth=0)
            decl.src = fd.file.src(fd.pos)
        if decl.inputs or decl.outputs or fd is not None:
            model.nodes.append(decl)
    extra["nodes_registered"] = len(registered)
    extra["node_types_with_runtime_rna"] = sum(1 for nt in registered if nt.struct is not None and nt.struct.properties)
    return ip


class DeclReader:
    """Reads ``add_input``/``add_output`` chains of a declaration function."""

    def __init__(self, ip: Interp, decl: NodeDecl) -> None:
        self.ip = ip
        self.decl = decl
        self.seen_funcs: set[int] = set()

    def read(self, fd: FuncDef, depth: int, dynamic: bool = False) -> None:
        if id(fd) in self.seen_funcs or depth > 3:
            return
        self.seen_funcs.add(id(fd))
        nodes = parse_statements(fd.file.tokens, fd.body_start, fd.body_end)
        builder_names = {p.name for p in fd.params if "Builder" in p.type and p.name}
        self.walk(fd.file, nodes, dynamic, builder_names, depth)

    def walk(self, f: CFile, nodes: list[tuple], dynamic: bool, builders: set[str], depth: int) -> None:
        for node in nodes:
            if node is None:
                continue
            kind = node[0]
            if kind == "expr" or kind == "return":
                self.statement(f, node[1], dynamic, builders, depth)
            elif kind == "block":
                self.walk(f, node[1], dynamic, builders, depth)
            elif kind == "if":
                self.walk(f, [node[2], node[3]], True, builders, depth)
            elif kind in {"loop", "switch"}:
                self.walk(f, [node[2]], True, builders, depth)

    def statement(self, f: CFile, toks: list[Tok], dynamic: bool, builders: set[str], depth: int) -> None:
        n = len(toks)
        # ``auto &panel = b.add_panel("X")`` makes ``panel`` a builder too.
        if n > 3 and any(t.text in {"add_panel", "add_layout"} for t in toks):
            eq = next((k for k, t in enumerate(toks) if t.text == "="), None)
            if eq is not None and eq > 0 and toks[eq - 1].kind == "id":
                builders.add(toks[eq - 1].text)
        in_lambda = False
        k = 0
        while k < n:
            t = toks[k]
            if t.text == "[" and k + 1 < n and toks[k + 1].text in {"&", "=", "]"}:
                in_lambda = True  # sockets inside a lambda body run later (dynamic)
            if t.kind == "id" and t.text in {"add_input", "add_output"} and k >= 1 and toks[k - 1].text in {".", "->"}:
                k = self.socket(f, toks, k, dynamic or in_lambda)
                continue
            # Helpers receiving the builder: ``node_declare_common(b)``.
            if t.kind == "id" and k + 1 < n and toks[k + 1].text == "(" and (k == 0 or toks[k - 1].text not in {".", "->"}):
                args, close = call_args(toks, k + 1)
                if any(len(a) == 1 and a[0].text in builders for a in args):
                    callee = self.ip.lookup_function(t.text, f)
                    if callee is not None:
                        self.read(callee, depth + 1, dynamic)
                k += 1
                continue
            k += 1

    def socket(self, f: CFile, toks: list[Tok], k: int, dynamic: bool) -> int:
        side = toks[k].text
        n = len(toks)
        j = k + 1
        typ = ""
        if j < n and toks[j].text == "<":
            close = j
            depth = 0
            while close < n:
                if toks[close].text == "<":
                    depth += 1
                elif toks[close].text == ">":
                    depth -= 1
                    if depth == 0:
                        break
                close += 1
            inner = [t.text for t in toks[j + 1 : close] if t.kind == "id"]
            typ = inner[-1] if inner else ""
            j = close + 1
        if j >= n or toks[j].text != "(":
            return k + 1
        args, close = call_args(toks, j)
        name = None
        ident = ""
        if not typ:
            # ``b.add_input(SOCK_FLOAT, "Name")`` / ``b.add_input(data_type, "Name")``
            first = args[0] if args else []
            typ = SOCK_DECL.get(first[0].text, "") if len(first) == 1 else ""
            if not typ:
                dynamic = True
                typ = "Custom"
            args = args[1:]
        if args:
            name = self.string(args[0])
            if len(args) > 1:
                ident = self.string(args[1]) or ""
        sock = NodeSocket(name=name or "", type=typ, identifier=ident, dynamic=dynamic or name is None,
                          src=f.src(toks[k].pos))
        # Chained modifiers.
        m = close + 1
        while m + 2 < n and toks[m].text == "." and toks[m + 1].kind == "id":
            meth = toks[m + 1].text
            if toks[m + 2].text != "(":
                break
            margs, mclose = call_args(toks, m + 2)
            if meth == "identifier" and margs:
                sock.identifier = self.string(margs[0]) or sock.identifier
            elif meth == "subtype" and margs:
                sub = [t.text for t in margs[0] if t.kind == "id"]
                if sub:
                    sock.subtype = sub[-1].removeprefix("PROP_").lower()
            m = mclose + 1
        if side == "add_input":
            self.decl.inputs.append(sock)
        else:
            self.decl.outputs.append(sock)
        return m

    def string(self, toks: list[Tok]) -> str | None:
        if not toks:
            return None
        if all(t.kind == "str" for t in toks):
            return "".join(string_value(t.text) for t in toks)
        if toks[0].text in {"N_", "IFACE_", "CTX_N_"} and len(toks) > 2:
            inner = [t for t in toks if t.kind == "str"]
            if inner:
                return string_value(inner[-1].text)
        return None
