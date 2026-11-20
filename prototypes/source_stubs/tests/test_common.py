"""Tests for the shared pieces of the source stub prototypes: the ``ast`` reader and the comparison."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.compare import difference_kind, expand_aliases, normalize, operator_call, read_stubs, type_aliases
from common.pysource import Imports, StubWriter


def writer(code: str, module: str = "cycles.properties") -> StubWriter:
    tree = ast.parse(code)
    return StubWriter(tree, Imports(tree, module, "cycles"), module)


def test_registration_type_cls_is_the_enclosing_class() -> None:
    w = writer(
        "import bpy\n"
        "from bpy.props import PointerProperty\n"
        "class Settings(bpy.types.PropertyGroup):\n"
        "    @classmethod\n"
        "    def register(cls):\n"
        "        bpy.types.Camera.cycles_custom = PointerProperty(type=cls)\n"
    )
    (reg,) = w.registrations()
    assert reg.struct == "Camera"
    assert reg.property.identifier == "cycles_custom"
    assert reg.property.struct_type.endswith("Settings")


def test_normalize_drops_qualifiers_and_orders_unions() -> None:
    assert normalize("bpy.types.Object | None") == normalize("None | Object")
    assert normalize("Optional[mathutils.Vector]") == normalize("Vector | None")
    assert normalize("(a: int) -> None | bpy.types.Mesh") == normalize("(a: int) -> Mesh | None")


def test_difference_kinds() -> None:
    assert difference_kind("Object|None", "Object") == "nullability (X | None vs X)"
    assert difference_kind(normalize("Marker | None"), normalize("Marker")) == "nullability (X | None vs X)"
    assert difference_kind("str", "Literal['A','B']") == "Literal vs str (dynamic enum)"
    assert difference_kind("(a:int)->None", "(a:int)*->None") == "parameter kinds (positional-only / keyword-only)"
    assert difference_kind("(a:int)->Mesh|None", "(a:int)->Mesh") == "return type: nullability (X | None vs X)"


def test_untyped_parameters_are_their_own_kind() -> None:
    assert difference_kind("(path:?)->?", "(path:str|bytes)->str") == "one side untyped"


def test_read_stubs_collects_module_and_class_members(tmp_path: Path) -> None:
    (tmp_path / "bpy-stubs" / "types").mkdir(parents=True)
    (tmp_path / "bpy-stubs" / "types" / "__init__.pyi").write_text(
        "class Object:\n    name: str\n    @property\n    def users(self) -> int: ...\n    def select_get(self, view_layer: ViewLayer | None = None) -> bool: ...\n"
        "def f(x: int, /) -> None: ...\n"
    )
    stubs = read_stubs(tmp_path)
    assert stubs["bpy.types"]["Object"] == {
        "name": "str",
        "users": "int",
        "select_get": "(view_layer: ViewLayer | None) -> bool",
    }
    assert stubs["bpy.types"][""]["f"] == "(x: int)/ -> None"


def test_parameter_nullability_and_duplicate_union_members() -> None:
    assert normalize("None | str | None") == normalize("str | None")
    a, b = normalize("(aov: AOV) -> None"), normalize("(aov: bpy.types.AOV | None) -> None")
    assert difference_kind(a, b) == "parameter nullability"


def rendered_types(model) -> str:
    from common.render import Renderer

    return Renderer(model).render()["bpy.types"]


def test_rna_function_keeps_declaration_order_and_nullable_pointers() -> None:
    from common.model import RnaFunction, RnaProperty, RnaStruct, SourceModel

    f = RnaFunction(identifier="ensure")
    f.parameters = [
        RnaProperty(identifier="data_path", type="string", parameter_flags=["required"]),
        RnaProperty(identifier="index", type="int", default=0),
        RnaProperty(identifier="target", type="pointer", struct_type="Object", parameter_flags=["required"]),
        RnaProperty(
            identifier="owner", type="pointer", struct_type="ID", parameter_flags=["required"], never_null=True
        ),
    ]
    model = SourceModel(tool="t", source="s", commit="c")
    model.structs.append(RnaStruct(identifier="Thing", functions=[f]))
    text = rendered_types(model)
    assert "def ensure(self, data_path: str, *, index: int = 0, target: Object | None, owner: ID) -> None: ..." in text


def test_byte_strings_and_nested_arrays() -> None:
    from common.model import RnaProperty, RnaStruct, SourceModel

    model = SourceModel(tool="t", source="s", commit="c")
    model.structs.append(
        RnaStruct(
            identifier="Thing",
            properties=[
                RnaProperty(identifier="path", type="string", subtype="byte_string"),
                RnaProperty(identifier="box", type="float", array=[8, 3]),
            ],
        )
    )
    text = rendered_types(model)
    assert "path: bytes" in text
    assert "box: bpy_prop_array[bpy_prop_array[float]]" in text


def test_math_subtypes_follow_pyrna() -> None:
    from common.model import RnaProperty, RnaStruct, SourceModel

    model = SourceModel(tool="t", source="s", commit="c")
    model.structs.append(
        RnaStruct(
            identifier="Thing",
            properties=[
                RnaProperty(identifier="rot3", type="float", subtype="quaternion", array=[3]),
                RnaProperty(identifier="rot4", type="float", subtype="euler", array=[4]),
                RnaProperty(identifier="axis", type="float", subtype="axisangle", array=[4]),
                RnaProperty(identifier="mat", type="float", subtype="matrix", array=[4, 4], default=[1.0, 0.0] * 8),
            ],
        )
    )
    text = rendered_types(model)
    assert "rot3: mathutils.Euler" in text
    assert "rot4: mathutils.Quaternion" in text
    assert "axis: bpy_prop_array[float]" in text
    assert "mat: mathutils.Matrix" in text


def test_defaults() -> None:
    from common.model import RnaProperty
    from common.render import Renderer, literal_default

    assert literal_default("0") == "0"
    assert literal_default("'XYZ'") == "'XYZ'"
    assert literal_default("Vector((0, 0, 0))") == "..."
    p = RnaProperty(identifier="m", type="float", array=[2, 2], default=[1.0, 0.0, 0.0, 1.0])
    assert Renderer.default_text(None, p) == "((1.0, 0.0), (0.0, 1.0))"  # type: ignore[arg-type]


def test_operator_call_drops_execution_context() -> None:
    ours = normalize("(execution_context: int | str | None, undo: bool | None, only_unused: bool)/* -> set[str]")
    theirs = normalize("(only_unused: bool)* -> set[str]")
    assert operator_call(ours) == operator_call(theirs)
    assert (
        operator_call(normalize("(execution_context: int | str | None, undo: bool | None)/ -> set[str]"))
        == "()->set[str]"
    )


def test_enum_aliases_are_spelled_out(tmp_path: Path) -> None:
    (tmp_path / "_rna_enums").mkdir()
    (tmp_path / "_rna_enums" / "__init__.pyi").write_text(
        "from typing import Literal, TypeAlias\nrna_enum_x_items: TypeAlias = Literal['A', 'B']\n"
    )
    modules = {"bpy.types": {"T": {"p": "_rna_enums.rna_enum_x_items", "q": "set[rna_enum_x_items]"}}}
    expand_aliases(modules, type_aliases(tmp_path))
    assert modules["bpy.types"]["T"] == {"p": "Literal['A', 'B']", "q": "set[Literal['A', 'B']]"}


def test_read_stubs_reads_fake_bpy_operator_classes_as_functions(tmp_path: Path) -> None:
    (tmp_path / "bpy-stubs" / "ops" / "mesh").mkdir(parents=True)
    (tmp_path / "bpy-stubs" / "ops" / "mesh" / "__init__.pyi").write_text(
        "import bpy\n"
        "class beautify_fill(bpy.ops._BPyOpsSubModOp):\n"
        "    def __new__(cls, execution_context: int | str | None = None, undo: bool | None = None, /, *,"
        " angle_limit: float | None = 3.14) -> set[str]: ...\n"
    )
    stubs = read_stubs(tmp_path)
    assert "beautify_fill" not in stubs["bpy.ops.mesh"]
    assert stubs["bpy.ops.mesh"][""]["beautify_fill"].startswith("(execution_context:")


def test_fake_bpy_type_statement_aliases(tmp_path: Path) -> None:
    (tmp_path / "rna_enums.pyi").write_text("import typing\ntype OperatorReturnItems = typing.Literal['A', 'B']\n")
    modules = {"bpy.ops.x": {"": {"op": "() -> set[typing.Literal[bpy.stub_internal.rna_enums.OperatorReturnItems]]"}}}
    expand_aliases(modules, type_aliases(tmp_path))
    assert modules["bpy.ops.x"][""]["op"] == "() -> set[typing.Literal['A', 'B']]"


def test_array_arguments_take_sequences() -> None:
    from common.model import RnaFunction, RnaProperty, RnaStruct, SourceModel

    f = RnaFunction(identifier="f")
    f.parameters = [
        RnaProperty(identifier="loc", type="float", subtype="translation", array=[3], parameter_flags=["required"]),
        RnaProperty(identifier="m", type="float", subtype="matrix", array=[4, 4], parameter_flags=["required"]),
        RnaProperty(identifier="flags", type="boolean", array=[4], parameter_flags=["required"]),
    ]
    model = SourceModel(tool="t", source="s", commit="c")
    model.structs.append(RnaStruct(identifier="Thing", functions=[f]))
    text = rendered_types(model)
    assert (
        "def f(self, loc: mathutils.Vector | Sequence[float], m: mathutils.Matrix | Sequence[Sequence[float]],"
        " flags: Sequence[bool]) -> None: ..." in text
    )


def test_dynamic_flag_makes_an_array() -> None:
    """The text readers see ``PROP_DYNAMIC`` only as a flag; it is RNA's dynamic-array flag (``Image.pixels``)."""
    from common.model import RnaFunction, RnaProperty, RnaStruct, SourceModel

    f = RnaFunction(identifier="normals")
    f.parameters = [RnaProperty(identifier="out", type="float", flags=["dynamic"], parameter_flags=["output"])]
    model = SourceModel(tool="t", source="s", commit="c")
    model.structs.append(
        RnaStruct(
            identifier="Image",
            properties=[RnaProperty(identifier="pixels", type="float", flags=["editable", "dynamic"])],
            functions=[f],
        )
    )
    text = rendered_types(model)
    assert "pixels: bpy_prop_array[float]" in text
    assert "def normals(self) -> bpy_prop_array[float]: ..." in text


def test_pointer_returns_follow_the_classified_c_body() -> None:
    from common.model import RnaFunction, RnaProperty, RnaStruct, SourceModel

    def function(name: str, verdict: str) -> RnaFunction:
        ret = RnaProperty(identifier="result", type="pointer", struct_type="FCurve", parameter_flags=["output"])
        return RnaFunction(identifier=name, parameters=[ret], returns="result", returns_null=verdict)

    model = SourceModel(tool="t", source="s", commit="c")
    verdicts = {"new": "raises", "ensure": "never", "find": "null", "get": "unknown", "old": ""}
    model.structs.append(RnaStruct(identifier="FCurves", functions=[function(n, v) for n, v in verdicts.items()]))
    model.structs.append(RnaStruct(identifier="FCurve"))
    text = rendered_types(model)
    assert "def new(self) -> FCurve: ..." in text
    assert "def ensure(self) -> FCurve: ..." in text
    assert "def find(self) -> FCurve | None: ..." in text
    assert "def get(self) -> FCurve | None: ..." in text
    assert "def old(self) -> FCurve | None: ..." in text


def test_entry_points_import() -> None:
    """Each reader's ``run.py`` and the probe import (a linter once dropped an import one of them needed)."""
    import importlib.util

    import pytest

    root = Path(__file__).resolve().parents[1]
    scripts = [root / "probe.py", root / "regex" / "run.py", root / "makesrna" / "run.py"]
    if importlib.util.find_spec("clang") is not None:
        scripts.append(root / "libclang" / "run.py")
    for path in scripts:
        spec = importlib.util.spec_from_file_location(f"_entry_{path.parent.name}", path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except ImportError as ex:
            pytest.fail(f"{path.relative_to(root)}: {ex}")


def test_python_operators_inherit_mixin_properties() -> None:
    from common.model import PyClass, PyModuleSource, RnaProperty, SourceModel
    from common.render import Renderer

    base = PyClass(
        module="bl_operators.presets", name="AddPresetBase", properties=[RnaProperty(identifier="name", type="string")]
    )
    op = PyClass(
        module="bl_operators.presets",
        name="AddPresetCamera",
        bases=["AddPresetBase", "bpy.types.Operator"],
        bl_idname="camera.preset_add",
        properties=[RnaProperty(identifier="use_focal_length", type="boolean")],
    )
    model = SourceModel(tool="t", source="s", commit="c")
    model.python.append(
        PyModuleSource(name="bl_operators.presets", path="p", group="modules", stub="", classes=[base, op])
    )
    text = Renderer(model).render()["bpy.ops.camera"]
    assert "name: str = ..., use_focal_length: bool = ..." in text


def test_macro_steps_are_dicts() -> None:
    from common.model import Operator, RnaProperty, SourceModel
    from common.render import Renderer

    model = SourceModel(tool="t", source="s", commit="c")
    model.operators.append(
        Operator(
            idname="ACTION_OT_duplicate_move",
            properties=[
                RnaProperty(identifier="ACTION_OT_duplicate", type="pointer", struct_type="ACTION_OT_duplicate")
            ],
        )
    )
    assert "ACTION_OT_duplicate: dict[str, Any] = ..." in Renderer(model).render()["bpy.ops.action"]
