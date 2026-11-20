"""Tests for the shared pieces of the source stub prototypes: the ``ast`` reader and the comparison."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.compare import difference_kind, normalize, read_stubs  # noqa: E402
from common.pysource import Imports, StubWriter  # noqa: E402


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
        RnaProperty(identifier="owner", type="pointer", struct_type="ID", parameter_flags=["required"], never_null=True),
    ]
    model = SourceModel(tool="t", source="s", commit="c")
    model.structs.append(RnaStruct(identifier="Thing", functions=[f]))
    text = rendered_types(model)
    assert "def ensure(self, data_path: str, index: int = 0, *, target: Object | None, owner: ID) -> None: ..." in text


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
