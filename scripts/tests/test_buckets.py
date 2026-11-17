"""The cause report of check:blender. Each case is a diagnostic as `check:blender main` prints it with Blender's own
stubs (`.cache/ty-results/main-builtin.txt`), with the source line it points at and, where the cause depends on it,
the enclosing class and function; refresh them when a rebase of the fork changes ty's wording."""

import textwrap

import pytest

from _buckets import CAUSES, GROUPS, Diagnostic, Scope, area, read_diagnostics, summary

SHIPPED = "scripts/startup/bl_ui/space_view3d.py"
TESTS = "tests/python/bl_pyapi_idprop.py"


def diagnostic(rule, msg, text="", path=SHIPPED, **scope):
    return Diagnostic(path, 1, rule, msg, text, scope=Scope(**scope))


PANEL = {"cls": "DATA_PT_camera_dof", "bases": "Panel"}
POLLED_PANEL = {**PANEL, "has_poll": True}


@pytest.mark.parametrize(
    ("d", "expected"),
    [
        # Blender fixes (BF1: runtime failures, BF2: annotations)
        pytest.param(
            diagnostic(
                "unresolved-reference",
                "Name `QuantitativeInvisibilityF1D` used when not defined",
                "self.__func = QuantitativeInvisibilityF1D()",
                path="scripts/freestyle/modules/freestyle/predicates.py",
            ),
            "undefined-name",
            id="bf1-undefined-name",
        ),
        pytest.param(
            diagnostic(
                "unresolved-reference",
                "Name `panel0` used when not defined",
                "tree.interface.move(panel0, 0)",
                path="tests/python/bl_node_group_interface.py",
            ),
            "unsorted",
            id="bf1-undefined-name-not-in-tests",
        ),
        pytest.param(
            diagnostic(
                "unresolved-reference",
                "Name `export_anim` used when not defined",
                "importlib.reload(export_anim)",
                path="scripts/addons_core/io_scene_gltf2/__init__.py",
            ),
            "reload-idiom",
            id="debt-reload-idiom",
        ),
        pytest.param(
            diagnostic(
                "missing-argument",
                "No argument provided for required parameter `use_ktx_loader` of function `create`",
                "BlenderImage.create(gltf, img_idx)",
                path="scripts/addons_core/io_scene_gltf2/blender/imp/blender_gltf.py",
            ),
            "missing-argument",
            id="bf1-missing-argument",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Material` has no attribute `texture_slots`",
                "for slot in mat.texture_slots:",
                path="scripts/modules/_bpy_types.py",
            ),
            "dead-api",
            id="bf1-dead-api",
        ),
        pytest.param(
            diagnostic(
                "invalid-return-type",
                "Return type does not match returned value: expected `set[Literal['RUNNING_MODAL', 'CANCELLED', "
                "'FINISHED', 'PASS_THROUGH', 'INTERFACE']]`, found `set[Literal['OPERATOR_CANCELLED']]`",
                "return {'OPERATOR_CANCELLED'}",
                path="scripts/startup/bl_operators/anim.py",
                cls="ARMATURE_OT_copy_bone_color_to_selected",
                function="execute",
            ),
            "operator-return-misuse",
            id="bf1-operator-return",
        ),
        pytest.param(
            diagnostic(
                "blender-unsupported-property-host",
                "Blender ignores property annotations on a `Panel`: `prepend` does not become a property",
                "prepend: StringProperty(",
                path="scripts/addons_core/node_wrangler/interface.py",
            ),
            "property-on-panel",
            id="bf1-property-on-panel",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `head` is not defined on `None` in union `EditBone | PoseBone | None`",
                "self.get_bone(self.bones.ctrl.master).head = head",
                path="scripts/addons_core/rigify/rigs/limbs/limb_rigs.py",
            ),
            "rigify-get-bone",
            id="bf2-rigify-get-bone",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Class `ToolDef` has no attribute `from_dict`",
                "tool_def = ToolDef.from_dict({",
            ),
            "tooldef",
            id="bf2-tooldef",
        ),
        pytest.param(
            diagnostic(
                "invalid-argument-type",
                "Argument to function `gather_animation_fcurves_channels` is incorrect: Expected `str`, found `None`",
                "None,",
                path="scripts/addons_core/io_scene_gltf2/blender/exp/animation/action.py",
            ),
            "none-for-non-optional",
            id="bf2-none-argument",
        ),
        pytest.param(
            diagnostic(
                "invalid-parameter-default",
                "Default value of type `None` is not assignable to annotated parameter type `Context`",
                "def get_instance(context: Context = None):",
                path="scripts/addons_core/rigify/__init__.py",
            ),
            "none-for-non-optional",
            id="bf2-none-default",
        ),
        pytest.param(
            diagnostic(
                "invalid-type-form",
                "Variable of type `Context` is not allowed in a type expression",
                "def get_actions(context: bpy.context):",
                path="scripts/addons_core/viewport_vr_preview/action_map.py",
            ),
            "wrong-annotation",
            id="bf2-wrong-annotation",
        ),
        pytest.param(
            diagnostic(
                "invalid-return-type",
                "Return type does not match returned value: expected `str`, found `None`",
                "return None",
                path="scripts/addons_core/io_scene_gltf2/blender/com/data_path.py",
                function="get_target_property_name",
            ),
            "return-annotation",
            id="bf2-return-annotation",
        ),
        # Typechecker fixes (S1: RNA never-None, S2: stub generator, S3: ty_blender)
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `addons` is not defined on `None` in union `Preferences | None`",
                "prefs = bpy.context.preferences.addons[__package__].preferences",
                path="intern/cycles/blender/addon/properties.py",
            ),
            "context-never-none",
            id="s1-preferences",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `bones` is not defined on `None` in union `bpy_struct | None`",
                "for bone in data.bones:",
                function="draw_item",
                params=("self", "_context", "layout", "data", "item", "icon", "_active_data", "_active_propname"),
            ),
            "callback-never-none",
            id="s1-draw-item-data",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `bl_idname` is not defined on `None` in union `KeyingSet | None`",
                "ks.bl_idname",
                path="scripts/startup/keyingsets_builtins.py",
                function="generate",
                params=("self", "context", "ks", "data"),
            ),
            "callback-never-none",
            id="s1-keying-set",
        ),
        pytest.param(
            diagnostic(
                "invalid-method-override",
                "Invalid override of method `asset_poll`: Definition is incompatible with `AssetShelf.asset_poll`",
                "def asset_poll(cls, asset: AssetRepresentation):",
                path="scripts/addons_core/pose_library/gui.py",
            ),
            "callback-never-none",
            id="s1-asset-poll-override",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `BMEdge` has no attribute `vert`",
                "for l in v.link_loops: l.vert",
                path="tests/python/bl_pyapi_bmesh.py",
            ),
            "bmesh-elem-seq",
            id="s2-bmesh-elem-seq",
        ),
        pytest.param(
            diagnostic(
                "no-matching-overload",
                "No overload of bound method `__getitem__` matches arguments: argument of type `tuple[str, None]`",
                "ob = bpy.data.objects[name, None]",
                path="scripts/modules/_bl_previews_utils/bl_previews_render.py",
            ),
            "blend-data-lib-key",
            id="s2-blend-data-lib-key",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Context` has no attribute `constraint`",
                "constraint = context.constraint",
                path="scripts/startup/bl_operators/constraint.py",
            ),
            "context-store-member",
            id="s2-context-store-member",
        ),
        pytest.param(
            diagnostic(
                "invalid-method-override",
                "Invalid override of method `traverse`: Definition is incompatible with `ChainingIterator.traverse`",
                "def traverse(self, iter):",
                path="scripts/freestyle/modules/freestyle/chainingiterators.py",
            ),
            "freestyle-positional",
            id="s2-freestyle",
        ),
        pytest.param(
            diagnostic(
                "invalid-method-override",
                "Invalid override of method `update`: Definition is incompatible with `RenderEngine.update`",
                "def update(self, data, depsgraph):",
                path="intern/cycles/blender/addon/__init__.py",
            ),
            "render-engine-positional",
            id="s2-render-engine",
        ),
        pytest.param(
            diagnostic(
                "invalid-argument-type",
                "Argument to bound method `menu_contents` is incorrect: Expected `Literal['DEFAULT']`, found `str`",
                "props.slot = str(i + 1)",
            ),
            "dynamic-enum",
            id="s2-dynamic-enum",
        ),
        pytest.param(
            diagnostic(
                "invalid-context-manager",
                "Object of type `tuple[BlendDataLibraries, BlendDataLibraries]` cannot be used with `with`",
                "with bpy.data.libraries.load(filepath) as (data_from, data_to):",
            ),
            "stub-context-manager",
            id="s2-libraries-load",
        ),
        pytest.param(
            diagnostic(
                "redundant-condition",
                "Condition is always falsy",
                "if not keyconfig_set(filepath, report=self.report):",
                path="scripts/startup/bl_operators/userpref.py",
            ),
            "stub-docstring",
            id="s2-keyconfig-set",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `operator` is not defined on `None` in union `UILayout | None`",
                "self.layout.operator('sequencer.split')",
                cls="SEQUENCER_MT_context_menu",
                bases="Menu",
                function="draw_generic",
            ),
            "layout-in-helper",
            id="s3-layout-in-helper",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `label` is not defined on `None` in union `UILayout | None`",
                "self.layout.label(text='Drop')",
                path="scripts/addons_core/bl_pkg/bl_extension_ops.py",
                cls="EXTENSIONS_OT_package_install",
                bases="Operator",
                function="_draw_for_drop",
            ),
            "layout-in-operator-helper",
            id="debt-operator-layout-helper",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Unresolved attribute `test_prop` on type `<class 'Scene'>`.",
                "bpy.types.Scene.test_prop = bpy.props.IntProperty()",
                path=TESTS,
            ),
            "file-registered-property",
            id="s3-registered-property-assignment",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Scene` has no attribute `test_prop`",
                "self.assertEqual(scene.test_prop, 1)",
                path=TESTS,
                registers=frozenset({"test_prop"}),
            ),
            "file-registered-property",
            id="s3-registered-property-read",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Property` has no attribute `enum_items`",
                'items = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items',
            ),
            "bl-rna-property",
            id="s3-bl-rna-property",
        ),
        pytest.param(
            diagnostic(
                "blender-invalid-idname",
                "Menu class `ArmatureSubMenu` has no `bl_idname`",
                "class ArmatureSubMenu(bpy.types.Menu):",
                path="scripts/addons_core/rigify/metarig_menu.py",
            ),
            "type-call-bases",
            id="s3-type-call-bases",
        ),
        pytest.param(
            diagnostic(
                "invalid-return-type",
                "Return type does not match returned value: expected `tuple[bpy_prop_array[int], "
                "bpy_prop_array[int]]`, found `tuple[list[int], list[int]]`",
                "return flt_flags, flt_neworder",
                function="filter_items",
            ),
            "filter-items-tuple",
            id="s3-filter-items",
        ),
        # Imprecise annotations (S4)
        pytest.param(
            diagnostic(
                "invalid-method-override",
                "Invalid override of method `execute`: Definition is incompatible with `Operator.execute`",
                "def execute(self, context: Context) -> set[str]:",
                path="scripts/startup/bl_operators/copy_global_transform.py",
            ),
            "imprecise-operator-return",
            id="s4-operator-return",
        ),
        pytest.param(
            diagnostic(
                "invalid-return-type",
                "Return type does not match returned value: expected `set[Literal['RUNNING_MODAL', 'CANCELLED', "
                "'FINISHED', 'PASS_THROUGH', 'INTERFACE']]`, found `set[str]`",
                "return ret",
                function="execute",
            ),
            "imprecise-operator-return",
            id="s4-operator-return-variable",
        ),
        pytest.param(
            diagnostic(
                "invalid-assignment",
                "Object of type `str` is not assignable to attribute `mode` of type `Literal['OBJECT', 'EDIT']`",
                "ob.mode = mode",
            ),
            "imprecise-enum-value",
            id="s4-enum-value",
        ),
        pytest.param(
            diagnostic(
                "invalid-method-override",
                "Invalid override of method `draw_item`: Definition is incompatible with `UIList.draw_item`",
                "def draw_item(self, context, layout, data: Armature, item, icon, active_data, active_propname):",
            ),
            "imprecise-callback-parameter",
            id="s4-callback-parameter",
        ),
        pytest.param(
            diagnostic("blender-imprecise-enum-value", "A `str` value where the stubs have an enum literal"),
            "imprecise-enum-value",
            id="s4-rule",
        ),
        # Implied narrowings (S5)
        pytest.param(
            diagnostic(
                "invalid-argument-type",
                "Argument to bound method `prop` is incorrect: Expected `AnyType`, found `Material | None`",
                'layout.prop(context.object.active_material, "diffuse_color")',
                function="draw",
                **POLLED_PANEL,
            ),
            "narrowed-by-poll",
            id="s5-poll",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `use_dof` is not defined on `None` in union `CameraDOFSettings | None`",
                "layout.active = dof.use_dof",
                function="draw",
                **PANEL,
            ),
            "unchecked-pointer",
            id="unsorted-no-poll",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `use_dof` is not defined on `None` in union `CameraDOFSettings | None`",
                "layout.active = dof.use_dof",
                function="modal",
                cls="VIEW3D_OT_walk",
                bases="Operator",
                has_poll=True,
            ),
            "unchecked-pointer",
            id="unsorted-modal-not-gated",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Space` has no attribute `clip`",
                "clip = context.space_data.clip",
                path="scripts/startup/bl_ui/space_clip.py",
                cls="CLIP_MT_track",
                bases="Menu",
                function="draw",
            ),
            "narrowed-by-menu-prefix",
            id="s5-menu-prefix",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Space` has no attribute `overlay`",
                "overlay = context.space_data.overlay",
                cls="VIEW3D_PT_overlay",
                bases="Panel",
                function="draw",
            ),
            "narrowed-by-popover",
            id="s5-popover",
        ),
        # Assumptions (S6)
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `render` is not defined on `None` in union `Scene | None`",
                "bpy.context.scene.render.engine = 'CYCLES'",
                path="scripts/presets/cycles/integrator/Default.py",
            ),
            "assumed-context-member",
            id="s6-context-member",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `name` is not defined on `None` in union `bpy_struct | None`",
                "layout.prop(vgroup, 'name', text='')",
                function="draw_item",
                params=("self", "_context", "layout", "_data", "item", "icon", "_active_data", "_active_propname"),
            ),
            "assumed-list-item",
            id="s6-list-item",
        ),
        pytest.param(
            diagnostic("blender-assumed-registration", "`OBJECT_OT_x` is registered only on a branch"),
            "assumed-registration",
            id="s6-rule",
        ),
        # Typing debt (out of scope)
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Self@__call__` has no attribute `_get_dup_num_id`",
                "cls._get_dup_num_id(bdata)))",
            ),
            "mixin-self",
            id="debt-mixin-self",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Scene | None` has no attribute `cycles`",
                "cycles = bpy.context.scene.cycles",
                path="scripts/presets/cycles/sampling/Final.py",
            ),
            "cross-file-registered-property",
            id="debt-cycles-property",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `is_cache_baking_any` is not defined on `None` in union `FluidDomainSettings | None`",
                "is_baking_any = domain.is_cache_baking_any",
                function="draw",
                **POLLED_PANEL,
            ),
            "type-enum-sub-pointer",
            id="debt-settings-pointer",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `ID | None` has no attribute `uv_layers`",
                "return obj is not None and obj.type == 'MESH' and obj.data.uv_layers",
            ),
            "object-data-untagged",
            id="debt-object-data",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `NodeSocket` has no attribute `socket`",
                "blender_shader_sockets[0].socket.id_data.library,",
            ),
            "base-class-subtype",
            id="debt-base-class",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Module `bpy.ops.wm` has no member `exit_blender`",
                "bpy.ops.wm.exit_blender()",
            ),
            "operator-call",
            id="debt-operator-call",
        ),
        pytest.param(
            diagnostic("import-not-found", "Cannot resolve imported module `_cycles`", "import _cycles"),
            "unresolved-import",
            id="debt-unresolved-import",
        ),
        pytest.param(
            diagnostic(
                "unused-type-ignore-comment", "Unused blanket `type: ignore` directive", "x = 1  # type: ignore"
            ),
            "general-typing",
            id="debt-general",
        ),
        # Unchecked pointers: Blender bugs, sub-pointers and plain Python Optionals
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `bl_idname` is not defined on `None` in union `KeyingSet | None`",
                'f.write("# Keying Set: {:s}\\n".format(ks.bl_idname))',
                path="scripts/startup/bl_operators/anim.py",
                cls="ANIM_OT_keying_set_export",
                bases="Operator",
                function="execute",
            ),
            "unchecked-pointer-bug",
            id="bf1-unchecked-pointer",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `location` is not defined on `None` in union `Object | None`",
                "cam.location = location",
                path="scripts/addons_core/viewport_vr_preview/operators.py",
                cls="VIEW3D_OT_vr_location_scouting_active_camera_to_capture",
                bases="Operator",
                function="execute",
                has_poll=True,
            ),
            "unchecked-pointer-bug",
            id="bf1-unchecked-pointer-poll-checks-something-else",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Space | None` has no attribute `clip`",
                "clip = sc.clip",
                path="scripts/startup/bl_ui/space_clip.py",
                cls="CLIP_MT_tracking_editor_menus",
                bases="Menu",
                function="draw",
            ),
            "narrowed-by-menu-prefix",
            id="s5-menu-prefix-alias",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `bones` is not defined on `None` in union `Pose | None`",
                "pose_bones = rig.pose.bones",
                path="scripts/addons_core/rigify/ui.py",
                function="fk_to_ik",
            ),
            "type-enum-sub-pointer",
            id="debt-pose-pointer",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `name` is not defined on `None` in union `PoseBone | None`",
                "print(pb.name)",
            ),
            "unchecked-pointer",
            id="unsorted-pose-bone-is-no-sub-pointer",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `brush` is not defined on `None` in union `VertexPaint | None`",
                "brush = context.tool_settings.vertex_paint.brush",
                cls="VIEW3D_PT_paint_vertex_context_menu",
                bases="Panel",
                function="draw",
            ),
            "type-enum-sub-pointer",
            id="debt-paint-mode-settings",
        ),
        pytest.param(
            diagnostic(
                "invalid-assignment",
                'Object of type `Literal["LINE"]` is not assignable to attribute `mode` on type '
                "`MaterialGPencilStyle | None`",
                "gpcolor.mode = 'LINE'",
                path="scripts/presets/gpencil_material/Fill_Only.py",
            ),
            "type-enum-sub-pointer",
            id="debt-grease-pencil-material",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `nodes` is not defined on `None` in union `NodeTree | None`",
                "material.node_tree.nodes.clear()",
                path="scripts/startup/bl_operators/image_as_planes.py",
                function="create_cycles_material",
            ),
            "type-enum-sub-pointer",
            id="debt-node-tree-pointer",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `reshape` is not defined on `None` in union `None | ndarray[Unknown, Unknown]`",
                "data = data.reshape(-1, length)",
                path="scripts/addons_core/io_scene_gltf2/blender/exp/attribute_utils.py",
            ),
            "python-optional",
            id="debt-python-optional",
        ),
        pytest.param(
            diagnostic(
                "invalid-argument-type",
                "Argument to function `pgettext_tip` is incorrect: Expected `str`, found `str | None`",
                "return tip_(EXTENSIONS_OT_package_uninstall.__doc__)",
                function="description",
                cls="EXTENSIONS_OT_package_uninstall_system",
                bases="Operator",
            ),
            "python-optional",
            id="debt-python-optional-builtin",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `name` is not defined on `None` in union `None | Unknown`",
                "context.scene.NWLazySource = node1.name",
                cls="NODE_OT_lazy_connect",
                bases="Operator, NWBase",
                function="execute",
                has_poll=True,
            ),
            "python-optional",
            id="debt-python-optional-before-poll",
        ),
        # Typing debt the research leaves out of scope
        pytest.param(
            diagnostic(
                "invalid-attribute-override",
                "Invalid override of attribute `MchBones`: Type `<class 'MchBones'>` is not assignable to inherited "
                "type `<class 'MchBones'>`",
                "class MchBones(BaseRig.MchBones):",
                path="scripts/addons_core/rigify/rigs/basic/pivot.py",
            ),
            "untyped-python",
            id="debt-untyped-python-rigify",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `VExportNode` has no attribute `uuid`",
                "self.add_children(parent_uuid, node.uuid)",
                path="scripts/addons_core/io_scene_gltf2/blender/exp/tree.py",
            ),
            "untyped-python",
            id="debt-untyped-python-gltf",
        ),
        pytest.param(
            diagnostic(
                "invalid-assignment",
                "Invalid subscript assignment with key of type `str` and value of type `Unknown` on object of type "
                "`ndarray[tuple[int], dtype[float64]]`",
                "dots['joint%dx' % i] = joints[:, 0]",
                path="scripts/addons_core/io_scene_fbx/import_fbx.py",
            ),
            "untyped-python",
            id="debt-untyped-python-numpy",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Module `bpy.app.handlers` has no member `_extension_repos_update_pre`",
                "handlers = bpy.app.handlers._extension_repos_update_pre",
                path="scripts/addons_core/bl_pkg/__init__.py",
            ),
            "private-member",
            id="debt-private-member",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Unresolved attribute `gopsize` on type `FFmpegSettings`",
                "bpy.context.scene.render.ffmpeg.gopsize = 18",
                path="scripts/presets/ffmpeg/H264_in_MP4.py",
            ),
            "build-option-gap",
            id="debt-build-without-ffmpeg",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Unresolved attribute `custom_float` on type `Material`",
                "bpy.data.materials[0].custom_float = 5.0",
                path="doc/python_api/examples/bpy.props.0.py",
                registers=frozenset({"custom_float"}),
            ),
            "file-registered-property",
            id="s3-registered-property-instance-assignment",
        ),
        pytest.param(
            diagnostic(
                "invalid-argument-type",
                'Argument is incorrect: Expected `dict[Unknown, Unknown]`, found `tuple[tuple[Literal["option"], '
                "float*]]`",
                "Hotkey(\"node.nw_factor\", n_(\"Increase Mix Factor by 0.1\"), key='RIGHT_ARROW', props=(('option', 0.1),)),",
                path="scripts/addons_core/node_wrangler/preferences.py",
            ),
            "wrong-annotation",
            id="bf2-wrong-annotation-dict-for-tuple",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Space & ~AlwaysFalsy` has no attribute `local_view`",
                "if view and view.local_view:",
                cls="VIEW3D_MT_object_context_menu",
                bases="Menu",
                function="draw",
            ),
            "narrowed-by-menu-prefix",
            id="s5-menu-prefix-truthy",
        ),
        pytest.param(
            diagnostic(
                "invalid-assignment",
                "Object of type `_PropertyDeferred` is not assignable to attribute `addon_search` of type `str`",
                "WindowManager.addon_search = StringProperty(",
                path="scripts/startup/bl_ui/__init__.py",
                function="register",
            ),
            "file-registered-property",
            id="s3-registered-property-imported-class",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `Strip & ~EffectStrip` has no attribute `content_trim_start`",
                "str(round(strip.content_trim_start, 0)),",
                path="scripts/startup/bl_ui/properties_strip.py",
            ),
            "base-class-subtype",
            id="debt-base-class-narrowed",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Object of type `LightProbe` has no attribute `parallax_type`",
                "if probe.parallax_type == 'ELIPSOID':",
                path="scripts/startup/bl_ui/properties_data_lightprobe.py",
            ),
            "base-class-subtype",
            id="debt-base-class-light-probe",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Unresolved attribute `use_fill` on type `dict[str, Any]`",
                "props.MESH_OT_rip.use_fill = False",
                cls="VIEW3D_MT_edit_mesh_vertices",
                bases="Menu",
                function="draw",
            ),
            "operator-call",
            id="debt-operator-call-macro-properties",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Function `keymap_fn` has no attribute `keymap_data`",
                "if keymap_fn.keymap_data:",
                path="scripts/startup/bl_ui/space_toolsystem_common.py",
            ),
            "general-typing",
            id="debt-function-attribute",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Unresolved attribute `__addon_enabled__` on type `ModuleType`",
                "mod.__addon_enabled__ = False",
                path="scripts/modules/addon_utils.py",
            ),
            "general-typing",
            id="debt-module-attribute",
        ),
        pytest.param(
            diagnostic(
                "unresolved-attribute",
                "Attribute `render` is not defined on `None` in union `None | Scene`",
                "bpy.context.scene.render.engine = 'CYCLES'",
                path="scripts/presets/cycles/integrator/Default.py",
            ),
            "assumed-context-member",
            id="s6-context-member-none-first",
        ),
        # Unsorted
        pytest.param(
            diagnostic("not-iterable", "Object of type `ImBufBuffer` is not iterable", "for p in buf:"),
            "stub-gap",
            id="unsorted-stub-gap",
        ),
        pytest.param(
            diagnostic(
                "invalid-argument-type",
                "Argument to function `bake_animation` is incorrect: Expected `str`, found `int`",
                "animation = bake_animation(obj_uuid, obj_uuid, export_settings)",
            ),
            "unsorted",
            id="unsorted-everything-else",
        ),
    ],
)
def test_cause(d, expected):
    assert d.cause.name == expected


def test_every_cause_has_a_known_group_and_a_unique_name():
    assert {c.group for c in CAUSES} <= set(GROUPS)
    assert len({c.name for c in CAUSES}) == len(CAUSES)
    assert CAUSES[-1].name == "unsorted"


@pytest.mark.parametrize(
    ("name", "group", "slice_"),
    [
        ("undefined-name", "blender-fix", "BF1"),
        ("tooldef", "blender-fix", "BF2"),
        ("context-never-none", "typechecker-fix", "S1"),
        ("bmesh-elem-seq", "typechecker-fix", "S2"),
        ("layout-in-helper", "typechecker-fix", "S3"),
        ("imprecise-operator-return", "imprecise-annotation", "S4"),
        ("narrowed-by-poll", "implied-narrowing", "S5"),
        ("assumed-context-member", "assumption", "S6"),
        ("mixin-self", "typing-debt", ""),
        ("unsorted", "unsorted", ""),
    ],
)
def test_cause_group_and_slice(name, group, slice_):
    cause = next(c for c in CAUSES if c.name == name)
    assert (cause.group, cause.slice) == (group, slice_)


def test_read_diagnostics_gives_severity_and_enclosing_scope(tmp_path):
    source = tmp_path / "scripts" / "startup" / "bl_ui"
    source.mkdir(parents=True)
    (source / "space_x.py").write_text(
        textwrap.dedent(
            """\
            import bpy
            from bpy.types import Panel, UIList


            class X_PT_panel(XButtonsPanel, Panel):
                bl_label = "X"

                @classmethod
                def poll(cls, context):
                    return context.object

                def draw(self, context):
                    layout = self.layout
                    if True:
                        layout.prop(context.object.active_material, "diffuse_color")


            class X_UL_list(UIList):
                def draw_item(self, _context, layout, data,
                              item, icon, _active_data, _active_propname):
                    layout.prop(item, "name")


            bpy.types.Scene.x_prop = bpy.props.IntProperty()
            """
        ),
        encoding="utf-8",
    )
    output = (
        "scripts/startup/bl_ui/space_x.py:15:9: error[invalid-argument-type] Argument is incorrect\n"
        "scripts\\startup\\bl_ui\\space_x.py:21:9: warning[blender-assumed-list-item] `item` taken as not None\n"
        "scripts/startup/bl_ui/space_x.py:24:1: error[unresolved-attribute] Unresolved attribute\n"
    )
    first, second, third = read_diagnostics(output, tmp_path)

    assert first.severity == "error"
    assert first.scope == Scope(
        cls="X_PT_panel",
        bases="XButtonsPanel, Panel",
        function="draw",
        params=("self", "context"),
        has_poll=True,
        registers=frozenset({"x_prop"}),
    )
    assert second.severity == "warning"
    assert second.scope.cls == "X_UL_list"
    assert second.scope.function == "draw_item"
    assert second.scope.params == (
        "self",
        "_context",
        "layout",
        "data",
        "item",
        "icon",
        "_active_data",
        "_active_propname",
    )
    assert second.scope.has_poll is False
    assert (third.scope.cls, third.scope.function) == ("", "")


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


def test_summary_has_every_cause_by_group_group_totals_and_warnings_apart():
    diagnostics = [
        ("narrowed-by-poll", "shipped", "invalid-argument-type", "error"),
        ("narrowed-by-poll", "presets", "blender-narrowed-by-poll", "warning"),
        ("tooldef", "shipped", "unresolved-attribute", "error"),
        ("unsorted", "other", "invalid-argument-type", "error"),
    ]
    text = summary("# check:blender main, builtin stubs, Blender abc1234567", diagnostics)
    lines = text.splitlines()

    assert lines[0] == "# check:blender main, builtin stubs, Blender abc1234567"
    assert lines[1].split() == ["cause", "group", "slice", "shipped", "presets", "other", "total"]
    rows = {line.split()[0]: line.split()[1:] for line in lines[2:] if line.strip()}
    # every cause has a row, also when zero, listed by group
    assert [line.split()[0] for line in lines[2 : 2 + len(CAUSES)]] == [
        c.name for g in GROUPS for c in CAUSES if c.group == g
    ]
    assert rows["narrowed-by-poll"] == ["implied-narrowing", "S5", "1", "1", "0", "2"]
    assert rows["tooldef"] == ["blender-fix", "BF2", "1", "0", "0", "1"]
    assert rows["mixin-self"] == ["typing-debt", "-", "0", "0", "0", "0"]
    # a total per group, every group listed
    group_header = lines.index(next(line for line in lines if line.split()[:1] == ["group"]))
    assert [line.split()[0] for line in lines[group_header + 1 : group_header + 1 + len(GROUPS)]] == GROUPS
    assert rows["implied-narrowing"] == ["1", "1", "0", "2"]
    assert rows["blender-fix"] == ["1", "0", "0", "1"]
    assert rows["assumption"] == ["0", "0", "0", "0"]
    # errors and warnings on separate total lines
    assert rows["errors"] == ["2", "0", "1", "3"]
    assert rows["warnings"] == ["0", "1", "0", "1"]
    # rules sorted by name, with a column per severity
    rule_header = lines.index(next(line for line in lines if line.split()[:1] == ["rule"]))
    assert lines[rule_header].split() == ["rule", "error", "warning"]
    assert lines[rule_header + 1 :] == [
        f"{'blender-narrowed-by-poll':<40}{0:>8}{1:>8}",
        f"{'invalid-argument-type':<40}{2:>8}{0:>8}",
        f"{'unresolved-attribute':<40}{1:>8}{0:>8}",
    ]
