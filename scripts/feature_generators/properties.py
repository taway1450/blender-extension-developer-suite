"""Generated addons for the ``properties`` feature: every property function with every option that changes the
type of the value, on a PropertyGroup that is also registered on ``Scene``.

The expected types are what Blender returns at runtime (probed in Blender 5.4, see
``tests/typecheck/features/properties/README.md``), not what the bpy stubs say.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ._common import manifest, python_file

MODULE = "properties"

ARRAY = "bpy_prop_array[{}]"
NESTED = "bpy_prop_array[bpy_prop_array[{}]]"
MATHUTILS = ("Color", "Euler", "Matrix", "Quaternion", "Vector")


@dataclass
class Field:
    name: str
    call: str  # the bpy.props call
    type: str  # the type of the value at runtime
    setter: str | None = None  # what can be assigned, if it is not `type` (None: same as `type`)
    readonly: bool = False
    good: list[str] = field(default_factory=list)  # values that can be assigned
    bad: list[str] = field(default_factory=list)  # values that must be rejected (invalid-assignment)
    extra: list[str] = field(default_factory=list)  # more check lines, with `s` the PropertyGroup
    comment: str = ""


@dataclass
class Addon:
    name: str
    title: str
    doc: str
    fields: list[Field]
    preamble: list[str] = field(default_factory=list)  # module-level code before the classes
    item: bool = False  # define a <PREFIX>_Item PropertyGroup (for pointers and collections)
    check_params: str = ""  # extra parameters of the assignment check, e.g. ", obj: Object"
    check_imports: list[str] = field(default_factory=list)
    stub_preamble: list[str] = field(default_factory=list)

    @property
    def prefix(self) -> str:
        return self.name.upper()


# --- scalars ------------------------------------------------------------------------------------------------------

NUMBER_SUBTYPES = [
    "NONE",
    "PIXEL",
    "UNSIGNED",
    "PERCENTAGE",
    "FACTOR",
    "ANGLE",
    "TIME",
    "TIME_ABSOLUTE",
    "DISTANCE",
    "DISTANCE_CAMERA",
    "POWER",
    "TEMPERATURE",
    "WAVELENGTH",
    "COLOR_TEMPERATURE",
    "FREQUENCY",
]
FLOAT_UNITS = [
    "NONE",
    "LENGTH",
    "AREA",
    "VOLUME",
    "ROTATION",
    "TIME",
    "TIME_ABSOLUTE",
    "VELOCITY",
    "ACCELERATION",
    "MASS",
    "CAMERA",
    "POWER",
    "TEMPERATURE",
    "WAVELENGTH",
    "COLOR_TEMPERATURE",
    "FREQUENCY",
]
STRING_SUBTYPES = ["NONE", "FILE_PATH", "DIR_PATH", "FILE_NAME", "BYTE_STRING", "PASSWORD"]


def scalar_fields() -> list[Field]:
    fields = [
        Field("b", "BoolProperty()", "bool", good=["True", "False"], bad=['"yes"']),
        Field("b_default", "BoolProperty(default=True)", "bool"),
        Field(
            "i",
            "IntProperty()",
            "int",
            good=["3", "-1"],
            bad=['"3"', "1.5"],
            comment="an int property rejects a float at runtime (TypeError)",
        ),
        Field("i_minmax", "IntProperty(default=5, min=0, max=10, soft_min=1, soft_max=9, step=2)", "int"),
        Field(
            "f",
            "FloatProperty()",
            "float",
            good=["1.5", "1"],
            bad=['"1.5"'],
            comment="an int is accepted for a float property",
        ),
        Field("f_precision", "FloatProperty(default=0.5, min=0.0, max=1.0, precision=3, step=10)", "float"),
        Field("s", "StringProperty()", "str", good=['"text"'], bad=["1", "None"]),
        Field("s_maxlen", 'StringProperty(default="x", maxlen=8)', "str"),
    ]
    fields += [Field(f"i_{sub.lower()}", f'IntProperty(subtype="{sub}")', "int") for sub in NUMBER_SUBTYPES]
    fields += [Field(f"f_{sub.lower()}", f'FloatProperty(subtype="{sub}")', "float") for sub in NUMBER_SUBTYPES]
    fields += [Field(f"f_unit_{unit.lower()}", f'FloatProperty(unit="{unit}")', "float") for unit in FLOAT_UNITS]
    fields += [Field(f"s_{sub.lower()}", f'StringProperty(subtype="{sub}")', "str") for sub in STRING_SUBTYPES]
    return fields


# --- vectors ------------------------------------------------------------------------------------------------------

VECTOR_SUBTYPES = [
    "NONE",
    "COLOR",
    "COLOR_GAMMA",
    "TRANSLATION",
    "DIRECTION",
    "VELOCITY",
    "ACCELERATION",
    "MATRIX",
    "EULER",
    "QUATERNION",
    "AXISANGLE",
    "XYZ",
    "XYZ_LENGTH",
    "COORDINATES",
    "LAYER",
    "LAYER_MEMBER",
]
VECTOR_SIZES: list[int | tuple[int, int] | None] = [None, 2, 3, 4, 16, (2, 2), (3, 3), (4, 4)]  # None: default (3)
VECTOR_LIKE = {"TRANSLATION", "DIRECTION", "VELOCITY", "ACCELERATION", "XYZ", "XYZ_LENGTH", "COORDINATES"}


def float_vector_type(subtype: str, size: int | tuple[int, int] | None) -> str:
    """The value Blender 5.4 returns for FloatVectorProperty(subtype=..., size=...); see the README."""
    n = 3 if size is None else size
    if isinstance(n, tuple):
        if subtype == "MATRIX" and n in ((3, 3), (4, 4)):
            return "Matrix"
        return NESTED.format("float")
    if subtype in ("COLOR", "COLOR_GAMMA") and n == 3:
        return "Color"
    if subtype in VECTOR_LIKE and n in (2, 3, 4):
        return "Vector"
    if subtype == "MATRIX" and n == 16:
        return "Matrix"
    if subtype in ("EULER", "QUATERNION") and n in (3, 4):
        return "Euler" if n == 3 else "Quaternion"  # the size decides, not the subtype
    return ARRAY.format("float")


def size_name(size: int | tuple[int, int] | None) -> str:
    if size is None:
        return "dflt"
    return f"{size[0]}x{size[1]}" if isinstance(size, tuple) else str(size)


def size_arg(size: int | tuple[int, int] | None) -> str:
    return "" if size is None else f", size={size}"


def sample(size: int | tuple[int, int] | None, value: str) -> str:
    n = 3 if size is None else size
    if isinstance(n, tuple):
        row = "(" + ", ".join([value] * n[1]) + ")"
        return "(" + ", ".join([row] * n[0]) + ")"
    return "(" + ", ".join([value] * n) + ("," if n == 1 else "") + ")"


def setter_type(value_type: str, size: int | tuple[int, int] | None, element: str) -> str:
    nested = isinstance(size, tuple)
    sequence = f"Sequence[Sequence[{element}]]" if nested else f"Sequence[{element}]"
    if value_type == "Matrix":
        return "Matrix | Sequence[Sequence[float]] | Sequence[float]"
    if value_type in MATHUTILS:
        return f"{value_type} | {sequence}"
    return sequence


def vector_fields() -> list[Field]:
    fields = []
    for subtype in VECTOR_SUBTYPES:
        for size in VECTOR_SIZES:
            value_type = float_vector_type(subtype, size)
            fields.append(
                Field(
                    f"f_{subtype.lower()}_{size_name(size)}",
                    f'FloatVectorProperty(subtype="{subtype}"{size_arg(size)})',
                    value_type,
                    setter=setter_type(value_type, size, "float"),
                    good=[sample(size, "1.0")]
                    if subtype in ("NONE", "COLOR", "TRANSLATION", "MATRIX", "EULER")
                    else [],
                )
            )
    fields += [
        Field(
            "f_no_subtype",
            "FloatVectorProperty()",
            "bpy_prop_array[float]",
            setter="Sequence[float]",
            good=["(1.0, 2.0, 3.0)", "[1.0, 2.0, 3.0]"],
            bad=['"xyz"', "1.0"],
        ),
        Field(
            "f_translation_default",
            'FloatVectorProperty(subtype="TRANSLATION", default=(0.0, 0.0, 1.0))',
            "Vector",
            setter="Vector | Sequence[float]",
            good=["Vector((1.0, 2.0, 3.0))"],
            extra=[
                "assert_type(s.f_translation_default.x, float)",
                "assert_type(s.f_translation_default.length, float)",
            ],
        ),
        Field(
            "f_color_4_clamped",
            'FloatVectorProperty(subtype="COLOR", size=4, min=0.0, max=1.0)',
            "bpy_prop_array[float]",
            setter="Sequence[float]",
            comment="only a 3-component color is a mathutils.Color",
            extra=["assert_type(s.f_color_4_clamped[3], float)"],
        ),
    ]
    for size in [None, 2, 3, 4, 32, (2, 2), (3, 3)]:
        value_type = (NESTED if isinstance(size, tuple) else ARRAY).format("int")
        fields.append(
            Field(
                f"i_vec_{size_name(size)}",
                f"IntVectorProperty({size_arg(size)[2:]})",
                value_type,
                setter=setter_type(value_type, size, "int"),
                good=[sample(size, "1")],
                bad=[sample(size, '"1"')] if size == 2 else [],
            )
        )
    fields.append(Field("i_vec_xyz", 'IntVectorProperty(subtype="XYZ")', ARRAY.format("int"), setter="Sequence[int]"))
    for subtype, size in [("NONE", None), ("NONE", 2), ("NONE", (2, 2)), ("LAYER", 20), ("LAYER_MEMBER", 20)]:
        value_type = (NESTED if isinstance(size, tuple) else ARRAY).format("bool")
        fields.append(
            Field(
                f"b_vec_{subtype.lower()}_{size_name(size)}",
                f'BoolVectorProperty(subtype="{subtype}"{size_arg(size)})',
                value_type,
                setter=setter_type(value_type, size, "bool"),
                good=[sample(size, "True")],
            )
        )
    for f in fields:
        if f.type.startswith("bpy_prop_array"):
            element = f.type.removeprefix("bpy_prop_array[").removesuffix("]")
            f.extra.insert(0, f"assert_type(s.{f.name}[0], {element})")
    return fields


# --- enums --------------------------------------------------------------------------------------------------------

AB = '[("A", "A", ""), ("B", "B", "")]'
ENUM_PREAMBLE = [
    'ENUM_ITEMS = [("RED", "Red", "The red one"), ("GREEN", "Green", "")]',
    'ENUM_ITEMS_TUPLE = (("ONE", "One", ""), ("TWO", "Two", ""))',
    "",
    "",
    "def enum_items_callback(self, context):",
    '    return [("DYN_A", "Dynamic A", ""), ("DYN_B", "Dynamic B", "")]',
]


def enum_fields() -> list[Field]:
    ab = 'Literal["A", "B"]'
    return [
        Field(
            "e_list",
            f"EnumProperty(items={AB})",
            ab,
            good=['"A"', '"B"'],
            bad=['"C"', "1"],
            comment="an identifier that is not in the items raises TypeError at runtime",
        ),
        Field("e_tuple", 'EnumProperty(items=(("A", "A", ""), ("B", "B", "")))', ab),
        Field("e_numbers", 'EnumProperty(items=[("A", "A", "", 1), ("B", "B", "", 5)])', ab),
        Field("e_icons", 'EnumProperty(items=[("A", "A", "", "MESH_CUBE", 1), ("B", "B", "", "NONE", 2)])', ab),
        Field(
            "e_separator",
            'EnumProperty(items=[("A", "A", ""), None, ("B", "B", "")])',
            ab,
            comment="None is a separator in the menu, not an item",
        ),
        Field("e_default", f'EnumProperty(items={AB}, default="B")', ab),
        Field("e_default_number", 'EnumProperty(items=[("A", "A", "", 1), ("B", "B", "", 5)], default=5)', ab),
        Field("e_single", 'EnumProperty(items=[("ONLY", "Only", "")])', 'Literal["ONLY"]'),
        Field(
            "e_constant",
            "EnumProperty(items=ENUM_ITEMS)",
            'Literal["RED", "GREEN"]',
            comment="items from a module-level constant are still known",
        ),
        Field("e_constant_tuple", "EnumProperty(items=ENUM_ITEMS_TUPLE)", 'Literal["ONE", "TWO"]'),
        Field(
            "e_comprehension",
            'EnumProperty(items=[(k, k.title(), "") for k in ("X", "Y")])',
            "str",
            good=['"X"', '"ANYTHING"'],
            comment="computed items: only str is known",
        ),
        Field("e_callback", "EnumProperty(items=enum_items_callback)", "str", good=['"DYN_A"']),
        Field("e_lambda", 'EnumProperty(items=lambda self, context: [("L", "L", "")])', "str"),
        Field(
            "e_flag",
            f'EnumProperty(items={AB}, options={{"ENUM_FLAG"}})',
            'set[Literal["A", "B"]]',
            good=['{"A"}', '{"A", "B"}', "set()"],
            bad=['{"C"}', '"A"', '["A"]'],
            comment="ENUM_FLAG: a set of identifiers; a list or a single str raises TypeError",
        ),
        Field(
            "e_flag_default",
            f'EnumProperty(items={AB}, default={{"A", "B"}}, options={{"ENUM_FLAG"}})',
            'set[Literal["A", "B"]]',
        ),
        Field(
            "e_flag_constant",
            'EnumProperty(items=ENUM_ITEMS, options={"ENUM_FLAG", "ANIMATABLE"})',
            'set[Literal["RED", "GREEN"]]',
        ),
        Field("e_flag_callback", 'EnumProperty(items=enum_items_callback, options={"ENUM_FLAG"})', "set[str]"),
        Field(
            "e_other_options",
            f'EnumProperty(items={AB}, options={{"HIDDEN", "SKIP_SAVE"}})',
            ab,
            comment="options other than ENUM_FLAG do not change the type",
        ),
    ]


# --- pointers and collections ---------------------------------------------------------------------------------------

ID_TYPES = [
    "Object",
    "Material",
    "Image",
    "Collection",
    "Mesh",
    "NodeTree",
    "Text",
    "World",
    "Camera",
    "Action",
    "Scene",
]


def pointer_fields(prefix: str) -> list[Field]:
    item, inner = f"{prefix}_Item", f"{prefix}_Inner"
    fields = [Field(f"p_{t.lower()}", f"PointerProperty(type=bpy.types.{t})", f"{t} | None") for t in ID_TYPES]
    fields[0].good = ["obj", "None"]
    fields[0].bad = ["material"]
    fields[0].extra = ["if s.p_object is not None:", "    assert_type(s.p_object.name, str)"]
    fields += [
        Field("p_alias", "PointerProperty(type=Obj)", "Object | None", comment="the type through an import alias"),
        Field(
            "p_group",
            f"PointerProperty(type={item})",
            item,
            readonly=True,
            bad=["None", "s.p_group"],
            comment="a PropertyGroup pointer is never None and is read-only (AttributeError at runtime)",
            extra=["assert_type(s.p_group.label, str)", "assert_type(s.p_group.inner.value, int)"],
        ),
        Field(
            "c_items",
            f"CollectionProperty(type={item})",
            f"bpy_prop_collection_idprop[{item}]",
            readonly=True,
            bad=["[]"],
            extra=[
                f"assert_type(s.c_items.add(), {item})",
                f"assert_type(s.c_items[0], {item})",
                f'assert_type(s.c_items["name"], {item})',
                "assert_type(len(s.c_items), int)",
                "for entry in s.c_items:",
                f"    assert_type(entry, {item})",
                "s.c_items.remove(0)",
                "s.c_items.move(0, 1)",
                "s.c_items.clear()",
                f"items: bpy_prop_collection[{item}] = s.c_items",
            ],
        ),
        Field(
            "c_inner",
            f'CollectionProperty(type={inner}, name="Inner items")',
            f"bpy_prop_collection_idprop[{inner}]",
            readonly=True,
            extra=["assert_type(s.c_inner.add().value, int)"],
        ),
    ]
    return fields


def addons() -> list[Addon]:
    pointer = Addon(
        "props_pointer",
        "pointer and collection properties",
        "PointerProperty to ID types and PropertyGroups, CollectionProperty",
        [],
        preamble=["from bpy.types import Object as Obj"],
        item=True,
        check_params=", obj: Object, material: Material",
        check_imports=[f"from bpy.types import {', '.join(sorted({*ID_TYPES, 'Material', 'Object'}))}"],
    )
    pointer.fields = pointer_fields(pointer.prefix)
    return [
        Addon(
            "props_scalar",
            "scalar properties",
            "Bool, Int, Float and String properties with all subtypes and units",
            scalar_fields(),
        ),
        Addon(
            "props_vector",
            "vector properties",
            "FloatVector, IntVector and BoolVector properties: every subtype with every size",
            vector_fields(),
            check_imports=["from mathutils import Color, Euler, Matrix, Quaternion, Vector"],
        ),
        Addon(
            "props_enum",
            "enum properties",
            "EnumProperty: item forms, ENUM_FLAG, dynamic items",
            enum_fields(),
            preamble=ENUM_PREAMBLE,
        ),
        pointer,
    ]


# --- rendering ------------------------------------------------------------------------------------------------------


def item_classes(prefix: str) -> list[str]:
    return [
        f"class {prefix}_Inner(PropertyGroup):",
        "    value: IntProperty()",
        "",
        "",
        f"class {prefix}_Item(PropertyGroup):",
        "    label: StringProperty()",
        f"    inner: PointerProperty(type={prefix}_Inner)",
        "",
        "",
    ]


def init_file(addon: Addon) -> str:
    values = f"{addon.prefix}_Values"
    lines = [
        "from __future__ import annotations",
        "",
        "import bpy",
        "from bpy.props import (BoolProperty, BoolVectorProperty, CollectionProperty, EnumProperty, FloatProperty,",
        "                       FloatVectorProperty, IntProperty, IntVectorProperty, PointerProperty, StringProperty)",
        "from bpy.types import PropertyGroup",
        *addon.preamble,
        "",
        "",
    ]
    if addon.item:
        lines += item_classes(addon.prefix)
    lines.append(f"class {values}(PropertyGroup):")
    for f in addon.fields:
        if f.comment:
            lines.append(f"    # {f.comment}")
        lines.append(f"    {f.name}: {f.call}")
    classes = ([f"{addon.prefix}_Inner", f"{addon.prefix}_Item"] if addon.item else []) + [values]
    lines += [
        "",
        "",
        f"classes = ({', '.join(classes)},)",
        "",
        "",
        "def register() -> None:",
        "    for cls in classes:",
        "        bpy.utils.register_class(cls)",
        f"    bpy.types.Scene.{addon.name} = PointerProperty(type={values})",
        "",
        "",
        "def unregister() -> None:",
        f"    del bpy.types.Scene.{addon.name}",
        "    for cls in reversed(classes):",
        "        bpy.utils.unregister_class(cls)",
    ]
    return python_file(MODULE, f"Feature test: {addon.doc}.", "\n".join(lines))


def check_file(addon: Addon) -> str:
    values = f"{addon.prefix}_Values"
    imports = [
        "from __future__ import annotations",
        "",
        "from typing import Literal, assert_type",
        "",
        "from bpy.types import Scene, bpy_prop_array, bpy_prop_collection, bpy_prop_collection_idprop",
        *addon.check_imports,
        "",
        f"from . import {values}",
    ]
    if addon.item:
        imports[-1] = f"from . import {addon.prefix}_Inner, {addon.prefix}_Item, {values}"
    lines = [*imports, "", "", f"def values(s: {values}) -> None:"]
    for f in addon.fields:
        lines.append(f"    assert_type(s.{f.name}, {f.type})")
        lines += [f"    {line}" for line in f.extra]
    lines += ["", "", f"def assignments(s: {values}{addon.check_params}) -> None:"]
    body = []
    for f in addon.fields:
        body += [f"    s.{f.name} = {v}" for v in f.good]
        body += [f"    s.{f.name} = {v}  # ty: ignore[invalid-assignment]" for v in f.bad]
    lines += body or ["    pass"]
    lines += [
        "",
        "",
        "def registered(scene: Scene) -> None:",
        f"    assert_type(scene.{addon.name}, {values})",
        f"    scene.{addon.name} = None  # ty: ignore[invalid-assignment]",
    ]
    return python_file(MODULE, f"Expected types of {addon.title}, as they are at runtime in Blender.", "\n".join(lines))


def stub_member(f: Field) -> list[str]:
    if f.readonly:
        return ["    @property", f"    def {f.name}(self) -> {f.type}: ..."]
    if f.setter is None:
        return [f"    {f.name}: {f.type}"]
    return [
        "    @property",
        f"    def {f.name}(self) -> {f.type}: ...",
        f"    @{f.name}.setter",
        f"    def {f.name}(self, value: {f.setter}) -> None: ...",
    ]


def addon_stub(addon: Addon) -> str:
    lines = [
        "from collections.abc import Sequence",
        "from typing import Literal",
        "",
        "from bpy.types import (Action, Camera, Collection, Image, Material, Mesh, NodeTree, Object, PropertyGroup,",
        "                       Scene, Text, World, bpy_prop_array, bpy_prop_collection_idprop)",
        "from mathutils import Color, Euler, Matrix, Quaternion, Vector",
        "",
    ]
    if addon.name == "props_enum":
        lines += ["ENUM_ITEMS: list[tuple[str, str, str]]", "ENUM_ITEMS_TUPLE: tuple[tuple[str, str, str], ...]", ""]
    if addon.item:
        lines += [
            f"class {addon.prefix}_Inner(PropertyGroup):",
            "    value: int",
            "",
            f"class {addon.prefix}_Item(PropertyGroup):",
            "    label: str",
            "    @property",
            f"    def inner(self) -> {addon.prefix}_Inner: ...",
            "",
        ]
    lines.append(f"class {addon.prefix}_Values(PropertyGroup):")
    for f in addon.fields:
        lines += stub_member(f)
    lines += ["", "def register() -> None: ...", "def unregister() -> None: ..."]
    return python_file(MODULE, f"Reference stub: what the checker should see in {addon.name}.", "\n".join(lines))


def types_delta(addon: Addon) -> str:
    values = f"{addon.prefix}_Values"
    lines = [
        f"from {addon.name} import {values}",
        "",
        "class Scene:",
        "    @property",
        f"    def {addon.name}(self) -> {values}: ...",
    ]
    return python_file(MODULE, f"Reference stub delta: bpy.types as {addon.name} registers it.", "\n".join(lines))


def generate() -> dict[str, str]:
    files = {}
    for addon in addons():
        files[f"{addon.name}/blender_manifest.toml"] = manifest(addon.name, f"Feature test: {addon.title}", addon.doc)
        files[f"{addon.name}/__init__.py"] = init_file(addon)
        files[f"{addon.name}/check_{addon.name}.py"] = check_file(addon)
        files[f"{addon.name}/_expected/addon/__init__.pyi"] = addon_stub(addon)
        files[f"{addon.name}/_expected/stubs/bpy.types.pyi"] = types_delta(addon)
    return files
