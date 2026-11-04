"""Generated addons for the ``bpy_symbols`` feature: the same small addon (a PropertyGroup, an Operator, registration
and a registered Scene property) written with each way of reaching ``bpy.props``, ``bpy.types`` and ``bpy.utils``.

The checker has to recognise the symbols by where they come from, not by how they are spelled, so every addon has
the same expected types.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ._common import OPERATOR_RESULT, manifest, ops_module_stub, ops_operator_stub, ops_package_delta, python_file

MODULE = "bpy_symbols"

PROPS = [
    "BoolProperty",
    "EnumProperty",
    "FloatProperty",
    "FloatVectorProperty",
    "IntProperty",
    "PointerProperty",
    "StringProperty",
]
TYPES = ["Operator", "PropertyGroup", "Scene"]
UTILS = ["register_class", "unregister_class"]


@dataclass
class Form:
    name: str
    doc: str
    imports: list[str]
    prop: str  # format string for a bpy.props function, {} = its name
    type: str  # format string for a bpy.types class
    util: str  # format string for a bpy.utils function
    modules: dict[str, str] = field(default_factory=dict)  # extra addon modules: file name -> text
    after_imports: list[str] = field(default_factory=list)
    check_preamble: list[str] = field(default_factory=list)  # module-level lines of the check file
    check_extra: list[str] = field(default_factory=list)  # more check functions


def compat_module(body: list[str]) -> str:
    return python_file(MODULE, "Re-exports of Blender symbols, as some addons keep them in one place.", "\n".join(body))


FORMS = [
    Form(
        "sym_dotted",
        "import bpy, then bpy.props.X / bpy.types.X / bpy.utils.X",
        ["import bpy"],
        "bpy.props.{}",
        "bpy.types.{}",
        "bpy.utils.{}",
    ),
    Form(
        "sym_submodule",
        "import bpy.props, import bpy.types, import bpy.utils",
        ["import bpy.props", "import bpy.types", "import bpy.utils"],
        "bpy.props.{}",
        "bpy.types.{}",
        "bpy.utils.{}",
    ),
    Form(
        "sym_module_alias",
        "import bpy.props as bp (and bpy.types as bt, bpy.utils as bu)",
        ["import bpy.props as bp", "import bpy.types as bt", "import bpy.utils as bu"],
        "bp.{}",
        "bt.{}",
        "bu.{}",
    ),
    Form(
        "sym_from_bpy",
        "from bpy import props, types, utils",
        ["from bpy import props, types, utils"],
        "props.{}",
        "types.{}",
        "utils.{}",
    ),
    Form(
        "sym_from_bpy_alias",
        "from bpy import props as P, types as T, utils as U",
        ["from bpy import props as P, types as T, utils as U"],
        "P.{}",
        "T.{}",
        "U.{}",
    ),
    Form(
        "sym_from_import",
        "from bpy.props import X, from bpy.types import X, from bpy.utils import X",
        [
            f"from bpy.props import {', '.join(PROPS)}",
            f"from bpy.types import {', '.join(TYPES)}",
            f"from bpy.utils import {', '.join(UTILS)}",
        ],
        "{}",
        "{}",
        "{}",
    ),
    Form(
        "sym_from_import_alias",
        "from bpy.props import X as Y (and so on)",
        [
            f"from bpy.props import {', '.join(f'{p} as My{p}' for p in PROPS)}",
            f"from bpy.types import {', '.join(f'{t} as My{t}' for t in TYPES)}",
            f"from bpy.utils import {', '.join(f'{u} as my_{u}' for u in UTILS)}",
        ],
        "My{}",
        "My{}",
        "my_{}",
    ),
    Form(
        "sym_star",
        "from bpy.props import * and from bpy.utils import *",
        ["import bpy", "from bpy.props import *", "from bpy.utils import *"],
        "{}",
        "bpy.types.{}",
        "{}",
        check_preamble=[
            "# At runtime this only binds the bpy_* base classes: bpy.types resolves the RNA classes",
            "# lazily and has no __all__. The stubs export every class, the checker must not.",
            "from bpy.types import *  # noqa: F403",
        ],
        check_extra=[
            "def star_import_of_bpy_types() -> None:",
            "    bpy_struct  # the base classes are there",
            "    PropertyGroup  # ty: ignore[unresolved-reference]  # oracle-skip: the stubs export all classes",
            "    Operator  # ty: ignore[unresolved-reference]  # oracle-skip: the stubs export all classes",
        ],
    ),
    Form(
        "sym_assigned_alias",
        "module-level aliases: P = bpy.props, Int = bpy.props.IntProperty, Group = ...",
        ["import bpy"],
        "Alias{}",
        "Alias{}",
        "alias_{}",
        after_imports=[
            *(f"Alias{p} = bpy.props.{p}" for p in PROPS),
            *(f"Alias{t} = bpy.types.{t}" for t in TYPES),
            *(f"alias_{u} = bpy.utils.{u}" for u in UTILS),
        ],
    ),
    Form(
        "sym_module_assigned",
        "module objects assigned to names: P = bpy.props, T = bpy.types",
        ["import bpy"],
        "P.{}",
        "T.{}",
        "U.{}",
        after_imports=["P = bpy.props", "T = bpy.types", "U = bpy.utils"],
    ),
    Form(
        "sym_reexport",
        "names re-exported by an addon module: from .compat import IntProperty",
        [f"from .compat import {', '.join([*PROPS, *TYPES, *UTILS])}"],
        "{}",
        "{}",
        "{}",
        modules={
            "compat.py": compat_module(
                [
                    f"from bpy.props import {', '.join(PROPS)}",
                    f"from bpy.types import {', '.join(TYPES)}",
                    f"from bpy.utils import {', '.join(UTILS)}",
                ]
            )
        },
    ),
    Form(
        "sym_reexport_star",
        "a star import of an addon module with __all__",
        ["from .compat import *"],
        "{}",
        "{}",
        "{}",
        modules={
            "compat.py": compat_module(
                [
                    "from bpy.props import *",
                    "from bpy.types import Operator, PropertyGroup, Scene",
                    "from bpy.utils import register_class, unregister_class",
                    "",
                    f"__all__ = {[*PROPS, *TYPES, *UTILS]!r}",
                ]
            )
        },
    ),
    Form(
        "sym_reexport_module",
        "module objects re-exported by an addon module: from .compat import props",
        ["from .compat import props, types, utils"],
        "props.{}",
        "types.{}",
        "utils.{}",
        modules={"compat.py": compat_module(["from bpy import props, types, utils"])},
    ),
    Form(
        "sym_nested_reexport",
        "names re-exported through two addon modules (a sub-package)",
        [f"from .lib.api import {', '.join([*PROPS, *TYPES, *UTILS])}"],
        "{}",
        "{}",
        "{}",
        modules={
            "lib/__init__.py": compat_module(["from .api import *  # noqa: F403"]),
            "lib/api.py": compat_module([f"from ..compat import {', '.join([*PROPS, *TYPES, *UTILS])}"]),
            "compat.py": compat_module(
                [
                    f"from bpy.props import {', '.join(PROPS)}",
                    f"from bpy.types import {', '.join(TYPES)}",
                    f"from bpy.utils import {', '.join(UTILS)}",
                ]
            ),
        },
    ),
]


def init_file(form: Form) -> str:
    p, t, u = form.prop.format, form.type.format, form.util.format
    prefix = form.name.upper()
    lines = [
        "from __future__ import annotations",
        "",
        *form.imports,
        *([""] + form.after_imports if form.after_imports else []),
        "",
        "",
        f"class {prefix}_Item({t('PropertyGroup')}):",
        f'    label: {p("StringProperty")}(name="Label")',
        "",
        "",
        f"class {prefix}_Settings({t('PropertyGroup')}):",
        f'    count: {p("IntProperty")}(name="Count", default=1)',
        f"    enabled: {p('BoolProperty')}()",
        f'    mode: {p("EnumProperty")}(items=[("A", "A", ""), ("B", "B", "")])',
        f'    offset: {p("FloatVectorProperty")}(subtype="TRANSLATION")',
        f"    item: {p('PointerProperty')}(type={prefix}_Item)",
        "",
        "",
        f"class {prefix}_OT_run({t('Operator')}):",
        f'    bl_idname = "{form.name}.run"',
        '    bl_label = "Run"',
        "",
        f"    factor: {p('FloatProperty')}(default=0.5)",
        "",
        "    def execute(self, context):",
        '        return {"FINISHED"}',
        "",
        "",
        f"classes = ({prefix}_Item, {prefix}_Settings, {prefix}_OT_run)",
        "",
        "",
        "def register():",
        "    for cls in classes:",
        f"        {u('register_class')}(cls)",
        f"    {t('Scene')}.{form.name} = {p('PointerProperty')}(type={prefix}_Settings)",
        "",
        "",
        "def unregister():",
        f"    del {t('Scene')}.{form.name}",
        "    for cls in reversed(classes):",
        f"        {u('unregister_class')}(cls)",
    ]
    return python_file(MODULE, f"Feature test: {form.doc}.", "\n".join(lines))


def check_file(form: Form) -> str:
    prefix = form.name.upper()
    lines = [
        "from __future__ import annotations",
        "",
        "from typing import Literal, assert_type",
        "",
        "import bpy",
        "from bpy.types import Scene",
        "from mathutils import Vector",
        "",
        f"from . import {prefix}_Item, {prefix}_OT_run, {prefix}_Settings",
        *form.check_preamble,
        "",
        "",
        f"def settings(s: {prefix}_Settings) -> None:",
        "    assert_type(s.count, int)",
        "    assert_type(s.enabled, bool)",
        '    assert_type(s.mode, Literal["A", "B"])',
        "    assert_type(s.offset, Vector)",
        f"    assert_type(s.item, {prefix}_Item)",
        "    assert_type(s.item.label, str)",
        '    s.count = "1"  # ty: ignore[invalid-assignment]',
        '    s.mode = "C"  # ty: ignore[invalid-assignment]',
        "",
        "",
        f"def operator(op: {prefix}_OT_run) -> None:",
        "    assert_type(op.factor, float)",
        "",
        "",
        "def calls() -> None:",
        f"    assert_type(bpy.ops.{form.name}.run(factor=1.0), {OPERATOR_RESULT})",
        f'    bpy.ops.{form.name}.run(factor="x")  # ty: ignore[invalid-argument-type]',
        "",
        "",
        "def registered(scene: Scene) -> None:",
        f"    assert_type(scene.{form.name}, {prefix}_Settings)",
        f"    assert_type(scene.{form.name}.count, int)",
        *(["", ""] + form.check_extra if form.check_extra else []),
    ]
    return python_file(MODULE, f"Expected types for an addon written with {form.doc}.", "\n".join(lines))


def addon_stub(form: Form) -> str:
    prefix = form.name.upper()
    lines = [
        "from typing import Literal",
        "",
        "from bpy.types import Operator, PropertyGroup",
        "from mathutils import Vector",
        "from collections.abc import Sequence",
        "",
        f"class {prefix}_Item(PropertyGroup):",
        "    label: str",
        "",
        f"class {prefix}_Settings(PropertyGroup):",
        "    count: int",
        "    enabled: bool",
        '    mode: Literal["A", "B"]',
        "    @property",
        "    def offset(self) -> Vector: ...",
        "    @offset.setter",
        "    def offset(self, value: Vector | Sequence[float]) -> None: ...",
        "    @property",
        f"    def item(self) -> {prefix}_Item: ...",
        "",
        f"class {prefix}_OT_run(Operator):",
        "    factor: float",
        "",
        f"classes: tuple[type[{prefix}_Item], type[{prefix}_Settings], type[{prefix}_OT_run]]",
        "",
        "def register() -> None: ...",
        "def unregister() -> None: ...",
    ]
    return python_file(MODULE, f"Reference stub: what the checker should see in {form.name}.", "\n".join(lines))


def generate() -> dict[str, str]:
    files = {}
    for form in FORMS:
        prefix = form.name.upper()
        base = form.name
        files[f"{base}/blender_manifest.toml"] = manifest(form.name, f"Feature test: {form.name}", form.doc)
        files[f"{base}/__init__.py"] = init_file(form)
        files[f"{base}/check_{form.name}.py"] = check_file(form)
        for rel, text in form.modules.items():
            files[f"{base}/{rel}"] = text
        files[f"{base}/_expected/addon/__init__.pyi"] = addon_stub(form)
        files[f"{base}/_expected/stubs/bpy.types.pyi"] = python_file(
            MODULE,
            f"Reference stub delta: bpy.types as {form.name} registers it.",
            f"from {form.name} import {prefix}_Settings\n\nclass Scene:\n    @property\n"
            f"    def {form.name}(self) -> {prefix}_Settings: ...",
        )
        files[f"{base}/_expected/stubs/bpy.ops.pyi"] = ops_package_delta(MODULE, [form.name])
        files[f"{base}/_expected/stubs/bpy.ops.{form.name}.pyi"] = ops_module_stub(
            MODULE,
            f"Reference stub: bpy.ops.{form.name} as the checker synthesises it.",
            [ops_operator_stub("run", f"{form.name}.run", [("factor", "float")])],
        )
    return files
