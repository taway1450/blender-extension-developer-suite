"""Blender's Python (``scripts/modules``, ``scripts/startup``, ``scripts/addons_core``, the Cycles add-on) read with
``ast``: a ``.pyi`` per module, the classes it defines, the operators and properties it registers.

Shared by all three prototypes: whatever tool reads the C/C++, Python source is read the same way. This is
fake-bpy-module's "route B" (stubs from source rather than ``inspect``), which keeps ``__init__``, instance
attributes, constants and decorated functions that introspection loses.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path

from .model import EnumItem, PyClass, PyClassMember, PyModuleSource, Registration, RnaProperty, SourceModel

ROOTS = (
    ("modules", Path("scripts/modules")),
    ("startup", Path("scripts/startup")),
    ("addons_core", Path("scripts/addons_core")),
    ("cycles", Path("intern/cycles/blender/addon")),
)
PROP_FUNCS = {
    "BoolProperty": ("boolean", False),
    "BoolVectorProperty": ("boolean", True),
    "IntProperty": ("int", False),
    "IntVectorProperty": ("int", True),
    "FloatProperty": ("float", False),
    "FloatVectorProperty": ("float", True),
    "StringProperty": ("string", False),
    "EnumProperty": ("enum", False),
    "PointerProperty": ("pointer", False),
    "CollectionProperty": ("collection", False),
}


def module_name(group: str, root: Path, path: Path) -> tuple[str, bool]:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    package = parts[-1] == "__init__"
    if package:
        parts.pop()
    if group == "cycles":
        parts.insert(0, "cycles")
    return ".".join(parts), package


def const(node: ast.AST | None) -> object:
    try:
        return ast.literal_eval(node) if node is not None else None
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def literal_type(node: ast.AST) -> str:
    value = const(node)
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float, str, bytes)):
        return type(value).__name__
    if isinstance(node, ast.Tuple):
        return "tuple[Any, ...]"
    if isinstance(node, (ast.List, ast.ListComp)):
        return "list[Any]"
    if isinstance(node, (ast.Dict, ast.DictComp)):
        return "dict[Any, Any]"
    if isinstance(node, (ast.Set, ast.SetComp)):
        return "set[Any]"
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"frozenset", "set", "dict", "list", "tuple"}
    ):
        return {
            "frozenset": "frozenset[Any]",
            "set": "set[Any]",
            "dict": "dict[Any, Any]",
            "list": "list[Any]",
            "tuple": "tuple[Any, ...]",
        }[node.func.id]
    return "Any"


def stub_args(args: ast.arguments) -> str:
    args = copy.deepcopy(args)
    args.defaults = [ast.Constant(value=...) for _ in args.defaults]
    args.kw_defaults = [None if d is None else ast.Constant(value=...) for d in args.kw_defaults]
    return ast.unparse(args)


class Imports:
    """Local name -> dotted name, from a module's imports."""

    def __init__(self, tree: ast.Module, module: str, package: bool) -> None:
        self.names: dict[str, str] = {}
        base = module if package else module.rpartition(".")[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.names[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else alias.name.split(".")[0]
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if node.level:
                    parts = base.split(".") if base else []
                    if node.level > 1:
                        parts = parts[: len(parts) - (node.level - 1)]
                    mod = ".".join([*parts, mod] if mod else parts)
                for alias in node.names:
                    self.names[alias.asname or alias.name] = f"{mod}.{alias.name}" if mod else alias.name

    def resolve(self, node: ast.AST) -> str:
        text = ast.unparse(node)
        head, _, rest = text.partition(".")
        if head in self.names:
            return self.names[head] + ("." + rest if rest else "")
        return text


def read_property(
    call: ast.Call, imports: Imports, module: str, identifier: str, local_classes: set[str]
) -> RnaProperty | None:
    func = imports.resolve(call.func)
    short = func.rpartition(".")[2]
    if short not in PROP_FUNCS or not (func.startswith("bpy.props") or func == short):
        return None
    ptype, is_vector = PROP_FUNCS[short]
    kw = {k.arg: k.value for k in call.keywords if k.arg}
    p = RnaProperty(identifier=identifier, type=ptype, src=f"{module}:{call.lineno}")
    name = const(kw.get("name"))
    p.name = name if isinstance(name, str) else ""
    desc = const(kw.get("description"))
    p.description = desc if isinstance(desc, str) else ""
    sub = const(kw.get("subtype"))
    if isinstance(sub, str):
        p.subtype = sub.lower()
    if is_vector:
        size = const(kw.get("size"))
        if isinstance(size, int):
            p.array = [size]
        elif isinstance(size, (tuple, list)) and all(isinstance(n, int) for n in size):
            p.array = list(size)
        else:
            p.array = [3]
    default = const(kw.get("default"))
    if default is not None:
        p.default = default
    if ptype == "enum":
        items = kw.get("items")
        if items is None and call.args:
            items = call.args[0]
        value = const(items)
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, (tuple, list)) and item and isinstance(item[0], str):
                    p.items.append(EnumItem(identifier=item[0], name=str(item[1]) if len(item) > 1 else ""))
        elif items is not None:
            p.itemf = ast.unparse(items)
        options = const(kw.get("options"))
        if isinstance(options, (set, frozenset)) and "ENUM_FLAG" in options:
            p.enum_flag = True
    if ptype in {"pointer", "collection"}:
        target = kw.get("type")
        if target is not None:
            name = imports.resolve(target)
            if name in local_classes:
                name = f"{module}.{name}"
            elif name.startswith("bpy.types."):
                name = name.removeprefix("bpy.types.")
            p.struct_type = name
    options = const(kw.get("options"))
    if isinstance(options, (set, frozenset)):
        p.flags = sorted(o.lower() for o in options)
    return p


class StubWriter:
    def __init__(self, tree: ast.Module, imports: Imports, module: str) -> None:
        self.tree = tree
        self.imports = imports
        self.module = module
        self.classes: list[PyClass] = []
        self.local_classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}

    def function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str) -> list[str]:
        lines = []
        for dec in node.decorator_list:
            text = ast.unparse(dec)
            if text in {"staticmethod", "classmethod", "property", "overload", "typing.overload"} or text.endswith(
                (".setter", ".deleter")
            ):
                lines.append(f"{indent}@{text}")
        returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        lines.append(f"{indent}{prefix} {node.name}({stub_args(node.args)}){returns}: ...")
        return lines

    def assign(self, node: ast.AST, indent: str) -> list[str]:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return [f"{indent}{node.target.id}: {ast.unparse(node.annotation)}"]
        if isinstance(node, ast.Assign):
            out = []
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.append(f"{indent}{target.id}: {literal_type(node.value)}")
            return out
        return []

    def class_def(self, node: ast.ClassDef, indent: str) -> list[str]:
        bases = [ast.unparse(b) for b in node.bases]
        keywords = [ast.unparse(k) for k in node.keywords]
        head = ", ".join(bases + keywords)
        lines = [f"{indent}class {node.name}({head}):" if head else f"{indent}class {node.name}:"]
        info = PyClass(
            module=self.module,
            name=node.name,
            bases=[self.imports.resolve(b) for b in node.bases],
            doc=(ast.get_docstring(node) or "").split("\n")[0][:200],
            src=f"{self.module}:{node.lineno}",
        )
        body: list[str] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body += self.function(item, indent + "    ")
                decs = {ast.unparse(d) for d in item.decorator_list}
                kind = (
                    "property"
                    if "property" in decs
                    else "classmethod"
                    if "classmethod" in decs
                    else "staticmethod"
                    if "staticmethod" in decs
                    else "method"
                )
                info.members.append(
                    PyClassMember(
                        name=item.name,
                        kind=kind,
                        annotation=ast.unparse(item.returns) if item.returns and kind == "property" else "",
                        signature=f"({stub_args(item.args)})"
                        + (f" -> {ast.unparse(item.returns)}" if item.returns else ""),
                        src=f"{self.module}:{item.lineno}",
                    )
                )
            elif isinstance(item, ast.ClassDef):
                body += self.class_def(item, indent + "    ")
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                body += self.assign(item, indent + "    ")
                info.members.append(
                    PyClassMember(
                        name=item.target.id,
                        kind="attribute",
                        annotation=ast.unparse(item.annotation),
                        src=f"{self.module}:{item.lineno}",
                    )
                )
                if isinstance(item.annotation, ast.Call):
                    prop = read_property(item.annotation, self.imports, self.module, item.target.id, self.local_classes)
                    if prop:
                        info.properties.append(prop)
            elif isinstance(item, ast.Assign):
                body += self.assign(item, indent + "    ")
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        info.members.append(
                            PyClassMember(
                                name=target.id,
                                kind="attribute",
                                value=ast.unparse(item.value)[:120],
                                src=f"{self.module}:{item.lineno}",
                            )
                        )
                        if target.id == "bl_idname" and isinstance(const(item.value), str):
                            info.bl_idname = const(item.value)
        if indent == "":
            self.classes.append(info)
        return lines + (body or [f"{indent}    ..."])

    def render(self) -> str:
        out: list[str] = []
        for node in self.tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    continue
                out.append(ast.unparse(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out += self.function(node, "")
            elif isinstance(node, ast.ClassDef):
                out += self.class_def(node, "")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                out += self.assign(node, "")
            elif isinstance(node, ast.If):
                # Top-level conditionals (``if TYPE_CHECKING``, platform checks): take the first branch's definitions.
                for item in node.body:
                    if isinstance(item, (ast.Import, ast.ImportFrom)):
                        out.append(ast.unparse(item))
                    elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out += self.function(item, "")
                    elif isinstance(item, ast.ClassDef):
                        out += self.class_def(item, "")
                    elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                        out += self.assign(item, "")
            elif isinstance(node, ast.Try):
                for item in node.body:
                    if isinstance(item, (ast.Import, ast.ImportFrom)):
                        out.append(ast.unparse(item))
        return "\n".join(out) + "\n"

    def registrations(self) -> list[Registration]:
        regs = []
        # ``bpy.types.X.y = PointerProperty(type=cls)`` inside a classmethod of class C means ``type=C``.
        owner_class: dict[int, str] = {}
        for cls_node in ast.walk(self.tree):
            if isinstance(cls_node, ast.ClassDef):
                for inner in ast.walk(cls_node):
                    owner_class[id(inner)] = cls_node.name  # ast.walk reaches inner classes last
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            enclosing = owner_class.get(id(node))
            if enclosing:
                for kw in node.value.keywords:
                    if kw.arg == "type" and isinstance(kw.value, ast.Name) and kw.value.id == "cls":
                        kw.value = ast.Name(id=enclosing, ctx=ast.Load())
            for target in node.targets:
                if not isinstance(target, ast.Attribute):
                    continue
                owner = self.imports.resolve(target.value)
                struct = owner.removeprefix("bpy.types.") if owner.startswith("bpy.types.") else None
                if struct is None or "." in struct:
                    continue
                prop = read_property(node.value, self.imports, self.module, target.attr, self.local_classes)
                if prop:
                    regs.append(
                        Registration(
                            struct=struct, property=prop, module=self.module, src=f"{self.module}:{node.lineno}"
                        )
                    )
        return regs


def read_python(source: Path, model: SourceModel) -> None:
    for group, rel in ROOTS:
        root = source / rel
        if not root.is_dir():
            model.coverage.warnings.append(f"python: {rel} not found")
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts or any(p.startswith(".") for p in path.relative_to(root).parts):
                continue
            name, package = module_name(group, root, path)
            if not name or not all(part.isidentifier() for part in name.split(".")):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError) as ex:
                model.coverage.warnings.append(f"python: {path.relative_to(source)}: {ex}")
                continue
            writer = StubWriter(tree, Imports(tree, name, package), name)
            stub = writer.render()
            model.python.append(
                PyModuleSource(
                    name=name,
                    path=str(path.relative_to(source)),
                    stub=stub,
                    classes=writer.classes,
                    package=package,
                    group=group,
                )
            )
            model.registrations += writer.registrations()
