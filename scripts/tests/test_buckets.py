"""The bucket report of check:blender. Each case is a real diagnostic from `check:blender main` with Blender's own
stubs (`.cache/ty-results/main-builtin.txt`) and the source line it points at; refresh them when a rebase of the
fork changes ty's wording."""

import pytest

from _buckets import area, bucket, summary


@pytest.mark.parametrize(
    ("rule", "msg", "text", "expected"),
    [
        pytest.param(
            "import-not-found",
            "Cannot resolve imported module `numpy`",
            "import numpy as np",
            "check-setup",
            id="1-unresolved-import",
        ),
        pytest.param(
            "unresolved-attribute",
            "Object of type `Scene | None` has no attribute `cycles`",
            "cycles = bpy.context.scene.cycles",
            "check-setup",
            id="1-cycles-property",
        ),
        pytest.param(
            "unresolved-attribute",
            "Object of type `Self@__call__` has no attribute `_get_dup_num_id`",
            "cls._get_dup_num_id(bdata)))",
            "dynamic",
            id="2-self-in-mixin",
        ),
        pytest.param(
            "unresolved-attribute",
            "Class `ToolDef` has no attribute `from_dict`",
            "tool_def = ToolDef.from_dict({",
            "dynamic",
            id="2-tooldef",
        ),
        pytest.param(
            "unresolved-attribute",
            "Module `bpy.ops.wm` has no member `exit_blender`",
            "bpy.ops.wm.exit_blender()",
            "operator-call",
            id="3-bpy-ops-line",
        ),
        pytest.param(
            "unresolved-attribute",
            "Object of type `OperatorProperties` has no attribute `use_active_only`",
            "if props.use_active_only:",
            "operator-call",
            id="3-operator-properties",
        ),
        pytest.param(
            "too-many-positional-arguments",
            "Too many positional arguments to function `extrude_region_move`: expected 0, got 1",
            "'INVOKE_REGION_WIN',",
            "operator-call",
            id="3-positional-execution-context",
        ),
        pytest.param(
            "unresolved-attribute",
            "Object of type `ID | None` has no attribute `uv_layers`",
            "return obj is not None and obj.type == 'MESH' and obj.data.uv_layers",
            "type-tag",
            id="4-object-data",
        ),
        pytest.param(
            "unresolved-attribute",
            "Attribute `objects` is not defined on `None` in union `Collection | None`",
            "bpy.context.collection.objects.link(obj)",
            "context-member",
            id="5-attribute-of-context-member",
        ),
        pytest.param(
            "unresolved-attribute",
            "Attribute `keying_sets` is not defined on `None` in union `Scene | None`",
            "ks = scene.keying_sets.active",
            "context-member",
            id="5-context-type",
        ),
        pytest.param(
            "invalid-argument-type",
            "Argument to function `verify_armature_obj` is incorrect: Expected `Object`, found `Object | None`",
            "temp_obj = verify_armature_obj(context.view_layer.objects.active)",
            "context-member",
            id="5-object-from-context",
        ),
        pytest.param(
            "unresolved-attribute",
            "Attribute `is_cache_baking_any` is not defined on `None` in union `FluidDomainSettings | None`",
            "is_baking_any = domain.is_cache_baking_any",
            "type-tag",
            id="6-settings-pointer",
        ),
        pytest.param(
            "unresolved-attribute",
            "Attribute `use_dof` is not defined on `None` in union `CameraDOFSettings | None`",
            "layout.active = dof.use_dof",
            "pointer-none",
            id="7-pointer",
        ),
        pytest.param(
            "unresolved-attribute",
            "Object of type `NodeSocket` has no attribute `socket`",
            "blender_shader_sockets[0].socket.id_data.library,",
            "type-tag",
            id="8-base-class",
        ),
        pytest.param(
            "not-iterable",
            "Object of type `BMVertSeq` is not iterable",
            "for v in bm.verts:",
            "stub-gap",
            id="9-protocol",
        ),
        pytest.param(
            "invalid-method-override",
            "Invalid override of method `update`: Definition is incompatible with `RenderEngine.update`",
            "def update(self, data, depsgraph):",
            "stub-gap",
            id="9-override",
        ),
        pytest.param(
            "unresolved-attribute",
            "Class `ShapeKey` has no attribute `bl_rna`",
            'SHAPE_KEY_SLIDER_HARD_MIN = bpy.types.ShapeKey.bl_rna.properties["slider_min"].hard_min',
            "stub-gap",
            id="9-bl-rna",
        ),
        pytest.param(
            "unresolved-attribute",
            "Module `os` has no member `getuid`",
            "if os.getuid() == 0:",
            "stub-gap",
            id="9-module-member",
        ),
        pytest.param(
            "blender-unsupported-property-host",
            "Blender ignores property annotations on a `Panel`: `prepend` does not become a property",
            "prepend: StringProperty(",
            "rest",
            id="10-blender-rule",
        ),
        pytest.param(
            "invalid-argument-type",
            "Argument to function `bake_animation` is incorrect: Expected `str`, found `int`",
            "animation = bake_animation(obj_uuid, obj_uuid, export_settings)",
            "rest",
            id="10-everything-else",
        ),
    ],
)
def test_bucket(rule, msg, text, expected):
    assert bucket(rule, msg, text) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("scripts/startup/bl_operators/anim.py", "shipped"),
        ("scripts\\addons_core\\io_scene_fbx\\fbx_utils.py", "shipped"),
        ("intern\\cycles\\blender\\addon\\ui.py", "shipped"),
        ("scripts\\presets\\cycles\\integrator\\Default.py", "presets"),
        ("intern\\cycles\\app\\io_export_cycles_xml.py", "other"),
        ("doc\\python_api\\examples\\gpu.4.py", "other"),
    ],
)
def test_area(path, expected):
    assert area(path) == expected


def test_summary_has_every_bucket_and_rules_sorted_by_name():
    diagnostics = [
        ("pointer-none", "shipped", "unresolved-attribute"),
        ("pointer-none", "presets", "unresolved-attribute"),
        ("check-setup", "other", "import-not-found"),
        ("rest", "shipped", "blender-unsupported-property-host"),
    ]
    assert summary("# check:blender main, builtin stubs, Blender abc1234567", diagnostics) == (
        "# check:blender main, builtin stubs, Blender abc1234567\n"
        "bucket            shipped  presets    other    total\n"
        "context-member          0        0        0        0\n"
        "pointer-none            1        1        0        2\n"
        "type-tag                0        0        0        0\n"
        "stub-gap                0        0        0        0\n"
        "operator-call           0        0        0        0\n"
        "check-setup             0        0        1        1\n"
        "dynamic                 0        0        0        0\n"
        "rest                    1        0        0        1\n"
        "total                   2        1        1        4\n"
        "\n"
        "rule                                 count\n"
        "blender-unsupported-property-host        1\n"
        "import-not-found                         1\n"
        "unresolved-attribute                     2\n"
    )
