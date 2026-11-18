"""The cause report of check:blender. Each case is a diagnostic as `check:blender main` prints it with Blender's own
stubs (`.cache/ty-results/main-builtin.txt`), with the source line it points at and, where the cause depends on it,
the enclosing class and function; refresh them when a rebase of the fork changes ty's wording."""

import dataclasses
import textwrap

import pytest

from _buckets import CAUSES, GROUPS, Diagnostic, Scope, area, read_diagnostics, summary

SHIPPED = "scripts/startup/bl_ui/space_view3d.py"
TESTS = "tests/python/bl_pyapi_idprop.py"


def diagnostic(rule, msg, text="", path=SHIPPED, **scope):
    return Diagnostic(path, 1, rule, msg, text, scope=Scope(**scope))


PANEL = {"cls": "DATA_PT_camera_dof", "bases": "Panel"}
POLLED_PANEL = {**PANEL, "has_poll": True}


CASES = [
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
            "missing-attribute",
            "Object of type `Material` has no attribute `texture_slots`",
            "for slot in mat.texture_slots:",
            path="scripts/modules/_bpy_types.py",
        ),
        "dead-api",
        id="bf1-dead-api",
    ),
    pytest.param(
        diagnostic(
            "invalid-explicit-return",
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
            "missing-union-attribute",
            "Attribute `head` is not defined on `None` in union `EditBone | PoseBone | None`",
            "self.get_bone(self.bones.ctrl.master).head = head",
            path="scripts/addons_core/rigify/rigs/limbs/limb_rigs.py",
        ),
        "rigify-get-bone",
        id="bf2-rigify-get-bone",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `use_connect` is not defined on `PoseBone`, `Object` in union `PoseBone | EditBone | Object`",
            "if item.use_connect:",
            path="scripts/startup/bl_operators/object.py",
            cls="SelectPattern",
            bases="Operator",
            function="execute",
        ),
        "correlated-union",
        id="debt-correlated-union-not-rigify",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            "Object of type `Literal[True]` is not assignable to attribute `select` on type "
            "`PoseBone | EditBone | Object`",
            "item.select = True",
            path="scripts/startup/bl_operators/object.py",
            cls="SelectPattern",
            bases="Operator",
            function="execute",
        ),
        "correlated-union",
        id="debt-correlated-union-assignment",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            "Object of type `int` is not assignable to attribute `ui_shortcut` on type `(CompositorNodeViewer & "
            "~AlwaysFalsy) | (GeometryNodeViewer & ~AlwaysFalsy) | (TextureNodeViewer & ~AlwaysFalsy) | "
            "(Unknown & ~AlwaysFalsy)`",
            "viewer_node.ui_shortcut = self.viewer_index",
            path="scripts/startup/bl_operators/node.py",
            cls="NODE_OT_viewer_shortcut_set",
            bases="Operator",
            function="execute",
        ),
        "correlated-union",
        id="debt-correlated-union-truthy-members",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to bound method `UILayout.prop` is incorrect: Expected `bpy_struct`, found "
            "`PoseBone | EditBone | None | Bone`",
            'col.prop(bbone, "bbone_curveinx", text="Curve In X")',
            path="scripts/startup/bl_ui/properties_data_bone.py",
            cls="BONE_PT_curved",
            bases="BoneButtonsPanel, Panel",
            function="draw",
            has_poll=False,
        ),
        "ui-draw-pointer",
        id="debt-ui-draw-pointer-poll-disjunction",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
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
        "untyped-python",
        id="debt-none-argument-in-untyped-package",
    ),
    pytest.param(
        diagnostic(
            "invalid-parameter-default",
            "Default value of type `None` is not assignable to annotated parameter type `Context`",
            "def get_instance(context: Context = None):",
            path="scripts/startup/bl_operators/presets.py",
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
            "invalid-explicit-return",
            "Return type does not match returned value: expected `str`, found `None`",
            "return None",
            path="scripts/addons_core/io_scene_gltf2/blender/com/data_path.py",
            function="get_target_property_name",
        ),
        "untyped-python",
        id="debt-return-annotation-in-untyped-package",
    ),
    pytest.param(
        diagnostic(
            "invalid-implicit-return",
            "Function always implicitly returns `None`, which is not assignable to return type `int`",
            "def main() -> int:",
            path="release/lts/create_release_notes.py",
        ),
        "return-annotation",
        id="bf2-return-annotation",
    ),
    # Typechecker fixes (S1: RNA never-None, S2: stub generator, S3: ty_blender)
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `addons` is not defined on `None` in union `Preferences | None`",
            "prefs = bpy.context.preferences.addons[__package__].preferences",
            path="intern/cycles/blender/addon/properties.py",
        ),
        "context-never-none",
        id="s1-preferences",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
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
            "missing-union-attribute",
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
            "incompatible-method-override",
            "Invalid override of method `asset_poll`: Definition is incompatible with `AssetShelf.asset_poll`",
            "def asset_poll(cls, asset: AssetRepresentation):",
            path="scripts/addons_core/pose_library/gui.py",
        ),
        "callback-never-none",
        id="s1-asset-poll-override",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `show_viewport` is not defined on `None` in union `Modifier | None`",
            "ob.modifiers.new(name, 'SUBSURF').show_viewport = False",
            path="scripts/startup/bl_operators/object.py",
        ),
        "modifiers-new",
        id="debt-modifiers-new",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `modifiers` is not defined on `None` in union `TypedObject[Curve] | None`",
            "hook = self.spline_obj.modifiers.new(ctrl, 'HOOK')",
            path="scripts/addons_core/rigify/rigs/limbs/spline_tentacle.py",
        ),
        "untyped-python",
        id="debt-modifiers-new-receiver",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `NodesModifierProperties | None` has no attribute `inputs`",
            "radius_modifier.properties.inputs.Input_3.value = self.radius",
            path="scripts/startup/bl_operators/object_quick_effects.py",
        ),
        "type-enum-sub-pointer",
        id="debt-nodes-modifier-properties",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
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
            "missing-attribute",
            "Object of type `Context` has no attribute `constraint`",
            "constraint = context.constraint",
            path="scripts/startup/bl_operators/constraint.py",
        ),
        "context-store-member",
        id="s2-context-store-member",
    ),
    pytest.param(
        diagnostic(
            "lost-keyword-for-regular-parameter",
            "Override of method `traverse` disallows keyword arguments allowed by the method on the base class: "
            "Definition is incompatible with `ChainingIterator.traverse`",
            "def traverse(self, iter):",
            path="scripts/freestyle/modules/freestyle/chainingiterators.py",
        ),
        "freestyle-positional",
        id="s2-freestyle",
    ),
    pytest.param(
        diagnostic(
            "lost-keyword-for-regular-parameter",
            "Override of method `update` disallows keyword arguments allowed by the method on the base class: "
            "Definition is incompatible with `RenderEngine.update`",
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
            "missing-union-attribute",
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
            "missing-union-attribute",
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
            "missing-attribute",
            "Unresolved attribute `test_prop` on type `<class 'Scene'>`.",
            "bpy.types.Scene.test_prop = bpy.props.IntProperty()",
            path=TESTS,
        ),
        "file-registered-property",
        id="s3-registered-property-assignment",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
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
            "missing-attribute",
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
            "invalid-explicit-return",
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
            "incompatible-method-override",
            "Invalid override of method `execute`: Definition is incompatible with `Operator.execute`",
            "def execute(self, context: Context) -> set[str]:",
            path="scripts/startup/bl_operators/copy_global_transform.py",
        ),
        "general-typing",
        id="debt-operator-override-is-general-typing",
    ),
    pytest.param(
        diagnostic(
            "invalid-explicit-return",
            "Return type does not match returned value: expected `set[Literal['RUNNING_MODAL', 'CANCELLED', "
            "'FINISHED', 'PASS_THROUGH', 'INTERFACE']]`, found `set[str]`",
            "return ret",
            function="execute",
        ),
        "operator-return-misuse",
        id="s4-operator-return-error-falls-through",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            "Object of type `str` is not assignable to attribute `mode` of type `Literal['OBJECT', 'EDIT']`",
            "ob.mode = mode",
        ),
        "unsorted",
        id="s4-enum-value-error-falls-through",
    ),
    pytest.param(
        diagnostic(
            "incompatible-method-override",
            "Invalid override of method `draw_item`: Definition is incompatible with `UIList.draw_item`",
            "def draw_item(self, context, layout, data: Armature, item, icon, active_data, active_propname):",
        ),
        "general-typing",
        id="debt-callback-parameter-override-is-general-typing",
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
        "ui-draw-pointer",
        id="s5-pointer-the-poll-did-not-narrow",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `use_dof` is not defined on `None` in union `CameraDOFSettings | None`",
            "layout.active = dof.use_dof",
            function="draw",
            **PANEL,
        ),
        "ui-draw-pointer",
        id="debt-ui-draw-pointer-no-poll",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
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
            "missing-attribute",
            "Object of type `Space` has no attribute `clip`",
            "clip = context.space_data.clip",
            path="scripts/startup/bl_ui/space_clip.py",
            cls="CLIP_MT_track",
            bases="Menu",
            function="draw",
        ),
        "base-class-subtype",
        id="s5-menu-space-error-falls-through",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `Space` has no attribute `overlay`",
            "overlay = context.space_data.overlay",
            cls="VIEW3D_PT_overlay",
            bases="Panel",
            function="draw",
        ),
        "base-class-subtype",
        id="s5-popover-space-error-falls-through",
    ),
    # Assumptions (S6)
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `render` is not defined on `None` in union `Scene | None`",
            "bpy.context.scene.render.engine = 'CYCLES'",
            path="scripts/presets/cycles/integrator/Default.py",
        ),
        "preset-context-member",
        id="s6-context-member-error-in-preset",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `name` is not defined on `None` in union `bpy_struct | None`",
            "layout.prop(vgroup, 'name', text='')",
            function="draw_item",
            params=("self", "_context", "layout", "_data", "item", "icon", "_active_data", "_active_propname"),
        ),
        "unchecked-pointer",
        id="s6-list-item-error-falls-through",
    ),
    pytest.param(
        diagnostic("blender-assumed-registration", "`OBJECT_OT_x` is registered only on a branch"),
        "assumed-registration",
        id="s6-rule",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `header_text_set` is not defined on `None` in union `Area | None`",
            "context.area.header_text_set(None)",
            path="scripts/templates_py/Operator/modal_view3d.py",
            cls="ViewOperator",
            bases="bpy.types.Operator",
            function="modal",
        ),
        "editor-context-member",
        id="debt-editor-context-member-modal",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `tag_redraw` is not defined on `None` in union `Area | None`",
            "context.area.tag_redraw()",
            path="scripts/startup/bl_operators/userpref.py",
            cls="PREFERENCES_OT_addon_remove",
            bases="Operator",
            function="execute",
        ),
        "context-member-outside-callback",
        id="unsorted-editor-context-member-in-execute",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `data` is not defined on `None` in union `Object | None`",
            "me = bpy.context.object.data",
            path="scripts/templates_py/bmesh_simple.py",
        ),
        "script-context-member",
        id="debt-script-context-member-template",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `objects` is not defined on `None` in union `Collection | None`",
            "bpy.context.collection.objects.link(obj)",
            path="doc/python_api/examples/bmesh.ops.1.py",
        ),
        "script-context-member",
        id="debt-script-context-member-example",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `rotation_mode` is not defined on `None` in union `Object | None`",
            "if obj.rotation_mode == 'QUATERNION':",
            path="doc/python_api/examples/mathutils.Matrix.LocRotScale.0.py",
        ),
        "script-context-member",
        id="debt-script-context-member-alias-at-module-level",
    ),
    pytest.param(
        diagnostic(
            "not-subscriptable",
            "Cannot subscript object of type `None` with no `__getitem__` method",
            "x = self._point[0]",
            path="scripts/addons_core/io_curve_svg/import_svg.py",
            cls="SVGPathParser",
            function="_pathLineTo",
        ),
        "general-typing",
        id="debt-python-types-only",
    ),
    pytest.param(
        diagnostic(
            "not-callable",
            "Object of type `EllipsisType` is not callable",
            "end_offset = read_fbx_elem_uint(read)",
            path="scripts/addons_core/io_scene_fbx/fbx2json.py",
            function="read_elem",
        ),
        "general-typing",
        id="debt-python-types-only-ellipsis",
    ),
    pytest.param(
        diagnostic(
            "not-iterable",
            "Object of type `BlendData` is not iterable",
            "for datablock in datablocks:",
            path="scripts/modules/_bpy_internal/assets/remote_library/cli_listing_generator_asset_finder.py",
            function="_find_assets",
        ),
        "stub-gap",
        id="unsorted-blender-type-is-no-python-type",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `data` is not defined on `None` in union `Object | None`",
            "mesh = bpy.context.object.data",
            path="scripts/startup/bl_operators/object.py",
        ),
        "context-member-outside-callback",
        id="unsorted-script-context-member-only-in-examples",
    ),
    pytest.param(
        diagnostic("blender-narrowed-by-poll", "`context.object` is not None: the class's `poll()` checked it"),
        "narrowed-by-poll",
        id="s5-rule",
    ),
    pytest.param(
        diagnostic("blender-assumed-context-member", "`context.scene` taken as not None outside a callback"),
        "assumed-context-member",
        id="s6-context-member-rule",
    ),
    # Typing debt (out of scope)
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `Self@__call__` has no attribute `_get_dup_num_id`",
            "cls._get_dup_num_id(bdata)))",
        ),
        "mixin-self",
        id="debt-mixin-self",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `<super: <class 'FixToCameraCommon'>, FixToCameraCommon>` has no attribute `report`",
            "super().report(type, message)",
            path="scripts/startup/bl_operators/copy_global_transform.py",
            cls="FixToCameraCommon",
            function="report",
        ),
        "mixin-self",
        id="debt-mixin-self-super",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            'Argument is incorrect: Expected `set[Literal["DEBUG", "INFO", "OPERATOR", "PROPERTY", "WARNING", ... '
            "omitted 4 literals]]`, found `set[str]`: a name in the set is not an enum item",
            "self.report({'ERROR'}, \"Unsupported mode: {!r}\".format(mode))",
            path="scripts/startup/bl_operators/copy_global_transform.py",
            cls="FixToCameraCommon",
            function="execute",
        ),
        "mixin-self",
        id="debt-mixin-self-set-literal",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `panel` is not defined on `None` in union `UILayout | None`",
            'header, body = layout.panel("import_image_plane_material", default_closed=False)',
            path="scripts/startup/bl_operators/image_as_planes.py",
            cls="MaterialProperties_MixIn",
            function="draw_material_config",
            params=("self", "context"),
        ),
        "layout-in-operator-helper",
        id="debt-mixin-layout-operator-user",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            "Object of type `Literal[True]` is not assignable to attribute `unselected` on type "
            "`OperatorProperties | None`",
            'layout.operator("{:s}.hide".format(self._operator_name), text="Hide Unselected").unselected = True',
            cls="ShowHideMenu",
            function="draw",
        ),
        "runtime-operator-idname",
        id="debt-runtime-operator-idname",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `Scene | None` has no attribute `cycles`",
            "cycles = bpy.context.scene.cycles",
            path="scripts/presets/cycles/sampling/Final.py",
        ),
        "cross-file-registered-property",
        id="debt-cycles-property",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
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
            "missing-attribute",
            "Object of type `ID | None` has no attribute `uv_layers`",
            "return obj is not None and obj.type == 'MESH' and obj.data.uv_layers",
        ),
        "object-data-untagged",
        id="debt-object-data",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `NodeSocket` has no attribute `socket`",
            "blender_shader_sockets[0].socket.id_data.library,",
        ),
        "base-class-subtype",
        id="debt-base-class",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
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
        diagnostic("unused-type-ignore-comment", "Unused blanket `type: ignore` directive", "x = 1  # type: ignore"),
        "general-typing",
        id="debt-general",
    ),
    # Unchecked pointers: Blender bugs, sub-pointers and plain Python Optionals
    pytest.param(
        diagnostic(
            "missing-union-attribute",
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
            "missing-union-attribute",
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
            "missing-attribute",
            "Object of type `Space | None` has no attribute `clip`",
            "clip = sc.clip",
            path="scripts/startup/bl_ui/space_clip.py",
            cls="CLIP_MT_tracking_editor_menus",
            bases="Menu",
            function="draw",
        ),
        "ui-draw-pointer",
        id="s5-menu-prefix-alias-error-falls-through",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
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
            "missing-union-attribute",
            "Attribute `name` is not defined on `None` in union `PoseBone | None`",
            "print(pb.name)",
        ),
        "unchecked-pointer",
        id="unsorted-pose-bone-is-no-sub-pointer",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
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
            "missing-union-attribute",
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
            "missing-union-attribute",
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
            "missing-union-attribute",
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
            "incompatible-attribute-override",
            "Invalid override of attribute `bones`: Type `ToplevelBones[str, CtrlBones, MchBones, str]` is not "
            "assignable to inherited type `ToplevelBones[str | list[str] | BoneDict, str | list[str] | BoneDict, "
            "str | list[str] | BoneDict, str | list[str] | BoneDict]`",
            "bones: BaseRig.ToplevelBones[",
            path="scripts/addons_core/rigify/rigs/basic/pivot.py",
        ),
        "untyped-python",
        id="debt-untyped-python-rigify",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
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
            "missing-attribute",
            "Module `bpy.app.handlers` has no member `_extension_repos_update_pre`",
            "handlers = bpy.app.handlers._extension_repos_update_pre",
            path="scripts/addons_core/bl_pkg/__init__.py",
        ),
        "private-member",
        id="debt-private-member",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Unresolved attribute `gopsize` on type `FFmpegSettings`",
            "bpy.context.scene.render.ffmpeg.gopsize = 18",
            path="scripts/presets/ffmpeg/H264_in_MP4.py",
        ),
        "build-option-gap",
        id="debt-build-without-ffmpeg",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
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
            'Argument is incorrect: Expected `dict[Unknown, Unknown]`, found `tuple[tuple[Literal["option"], float*]]`',
            "Hotkey(\"node.nw_factor\", n_(\"Increase Mix Factor by 0.1\"), key='RIGHT_ARROW', props=(('option', 0.1),)),",
            path="scripts/addons_core/node_wrangler/preferences.py",
        ),
        "wrong-annotation",
        id="bf2-wrong-annotation-dict-for-tuple",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `Space & ~AlwaysFalsy` has no attribute `local_view`",
            "if view and view.local_view:",
            cls="VIEW3D_MT_object_context_menu",
            bases="Menu",
            function="draw",
        ),
        "base-class-subtype",
        id="s5-menu-prefix-truthy-error-falls-through",
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
            "missing-attribute",
            "Object of type `Strip & ~EffectStrip` has no attribute `content_trim_start`",
            "str(round(strip.content_trim_start, 0)),",
            path="scripts/startup/bl_ui/properties_strip.py",
        ),
        "base-class-subtype",
        id="debt-base-class-narrowed",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `LightProbe` has no attribute `parallax_type`",
            "if probe.parallax_type == 'ELIPSOID':",
            path="scripts/startup/bl_ui/properties_data_lightprobe.py",
        ),
        "base-class-subtype",
        id="debt-base-class-light-probe",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `bpy_struct` has no attribute `frame`",
            "row.label(text=str(item.frame))",
            path="doc/python_api/examples/bpy.types.UIList.3.py",
        ),
        "base-class-subtype",
        id="debt-base-class-list-item-narrowed",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `bpy_struct[Unknown]` has no attribute `frame`",
            "row.label(text=str(item.frame))",
            path="doc/python_api/examples/bpy.types.UIList.3.py",
        ),
        "base-class-subtype",
        id="debt-base-class-list-item-generic",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
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
            "missing-attribute",
            "Function `keymap_fn` has no attribute `keymap_data`",
            "if keymap_fn.keymap_data:",
            path="scripts/startup/bl_ui/space_toolsystem_common.py",
        ),
        "general-typing",
        id="debt-function-attribute",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Unresolved attribute `__addon_enabled__` on type `ModuleType`",
            "mod.__addon_enabled__ = False",
            path="scripts/modules/addon_utils.py",
        ),
        "general-typing",
        id="debt-module-attribute",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `render` is not defined on `None` in union `None | Scene`",
            "bpy.context.scene.render.engine = 'CYCLES'",
            path="scripts/presets/cycles/integrator/Default.py",
        ),
        "preset-context-member",
        id="s6-context-member-none-first-in-preset",
    ),
    # Spec #95's site-by-site sorting: one site from Blender's own scripts per cause it added
    pytest.param(
        diagnostic(
            "blender-assumed-preferences",
            "The add-on's preferences are taken as its preferences class, but this read runs while the class is not registered (in `register()` before `register_class`, or in `unregister()` after `unregister_class`), where `preferences` is `None`",
            "prefs = (context or bpy.context).preferences.addons[__package__].preferences",
            path="scripts/addons_core/rigify/__init__.py",
        ),
        "assumed-preferences",
        id="assumed-preferences",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to function `spin` is incorrect: Expected `list[BMVert | BMEdge | BMFace]`, found `list[BMEdge | BMVert]`",
            "geom=geom_start_a,",
            path="doc/python_api/examples/bmesh.ops.1.py",
        ),
        "stub-signature-gap",
        id="stub-signature-gap",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to bound method `GPUShader.uniform_float` is incorrect: Expected `float | Sequence[float]`, found `Matrix`",
            'shader.uniform_float("u_ViewProjectionMatrix", matrix)',
            path="doc/python_api/examples/gpu.10.py",
        ),
        "mathutils-protocol-stub",
        id="mathutils-protocol-stub",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Module `bpy.types` has no member `POSELIB_OT_restore_previous_action`",
            "if bpy.types.POSELIB_OT_restore_previous_action.poll(context):",
            path="scripts/addons_core/pose_library/gui.py",
        ),
        "registered-class-in-bpy-types",
        id="registered-class-in-bpy-types",
    ),
    # fake-bpy-module declares the registered class, so the site shows up one step further: its method, borrowed as
    # another operator's callback, takes that class as its unannotated first parameter.
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument is incorrect: Expected `Iterable[tuple[str, str, str] | None] | ((EXTENSIONS_OT_package_install_files, "
            "Context | None, /) -> Iterable[tuple[str, str, str] | None])`, found `def _target_path_items(_self, "
            "context) -> Unknown`",
            "items=bpy.types.PREFERENCES_OT_addon_install._target_path_items,",
            path="scripts/addons_core/bl_pkg/bl_extension_ops.py",
            cls="EXTENSIONS_OT_package_install_files",
        ),
        "registered-class-in-bpy-types",
        id="registered-class-method-borrowed-as-callback",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to bound method `NodeTreeInterface.move_to_parent` is incorrect: Expected `NodeTreeInterfacePanel | None`, found `NodeTreeInterfaceItem & ~AlwaysFalsy`",
            "interface.move_to_parent(item, active_item, len(active_item.interface_items))",
            path="scripts/startup/bl_operators/node.py",
        ),
        "item-type-tag-narrowing",
        id="item-type-tag-narrowing",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `ProjectVariable` has no attribute `value`",
            "col.label(text=str(item.value))",
            path="scripts/startup/bl_ui/space_project.py",
        ),
        "item-type-tag-narrowing",
        id="item-type-tag-narrowing-project-variable",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `name` is not defined on `None` in union `Object | None`",
            'print(f"Object {obj.name} at {object_instance.matrix_world}")',
            path="doc/python_api/examples/bpy.types.Depsgraph.3.py",
            function="execute",
            source='            obj = object_instance.object\n            # `is_instance` denotes whether the object is coming from instances (as an opposite of\n            # being an emitting object. )\n            if not object_instance.is_instance:\n                print(f"Object {obj.name} at {object_instance.matrix_world}")',
        ),
        "rna-never-none",
        id="rna-never-none",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `type` is not defined on `None` in union `Object | None`",
            "return (ob.type in {'MESH', 'EMPTY', 'FONT'})",
            path="scripts/startup/bl_ui/properties_object.py",
            function="poll",
            attributes='bl_context = "object"',
        ),
        "bl-context-implies-member",
        id="bl-context-implies-member",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `type` is not defined on `None` in union `Object | None`",
            "if ob.type != 'GREASEPENCIL':",
            path="scripts/startup/bl_ui/space_view3d_toolbar.py",
            function="poll",
            attributes='bl_context = ".grease_pencil_paint"\nbl_parent_id = "VIEW3D_PT_tools_grease_pencil_v3_brush_settings"',
        ),
        "bl-context-implies-member",
        id="c6-bl-context-display-only-falls-through",
    ),
    pytest.param(
        diagnostic(
            "blender-narrowed-by-bl-context",
            '`context.object` is taken as `Object` because `ObjectButtonsPanel` has `bl_context = "object"`',
            "ob = context.object",
            path="scripts/startup/bl_ui/properties_object.py",
            function="draw",
            attributes='bl_context = "object"',
        ),
        "narrowed-by-bl-context",
        id="c6-narrowed-by-bl-context",
    ),
    pytest.param(
        diagnostic(
            "blender-assumed-subclass-member",
            "`Constraint` has no member `target`, only its subclasses `ActionConstraint`, `ArmatureConstraint`, "
            "`ChildOfConstraint` and 17 more declare it: the struct is taken to be one, so it is `Object | None`",
            "target = con.target",
            path="scripts/startup/bl_operators/constraint.py",
            function="execute",
        ),
        "assumed-subclass-member",
        id="c7-assumed-subclass-member",
    ),
    pytest.param(
        diagnostic(
            "not-subscriptable",
            "Cannot subscript object of type `None` with no `__getitem__` method",
            'core_shader.inputs["Emission Strength"].default_value = self.emit_strength',
            path="scripts/startup/bl_operators/image_as_planes.py",
            function="create_cycles_material",
        ),
        "fake-bpy-node-sockets",
        id="c7-fake-bpy-node-sockets",
    ),
    pytest.param(
        diagnostic(
            "invalid-return-type",
            "Return type does not match returned value: expected `FileAssetSelectParams`, found "
            "`FileSelectParams | None`",
            "return space_data.params",
            path="scripts/addons_core/pose_library/asset_browser.py",
            function="params",
        ),
        "helper-checks-none",
        id="c7-helper-checks-asset-browser-params",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            'Method `__getitem__` of type `Overload[(key: Literal[0, "Factor"]) -> NodeSocketFloatFactor, (key: '
            'Literal[1, "Shader"]) -> NodeSocketShader, (key: Literal[2, "Shader"]) -> NodeSocketShader]` cannot be '
            'called with key of type `Literal["Fac"]` on object of type `_ShaderNodeMixShader_NodeInputs`',
            'node_tree.links.new(mix_shader.inputs["Fac"], tex_image.outputs["Alpha"])',
            path="scripts/startup/bl_operators/image_as_planes.py",
            function="create_cycles_material",
        ),
        "fake-bpy-node-sockets",
        id="c7-fake-bpy-node-socket-identifier",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            'Object of type `Literal["Background"]` is not assignable to attribute `layer` of type '
            '`Literal["PLACEHOLDER"]`',
            'rlayer_bg.layer = "Background"',
            path="scripts/startup/bl_operators/clip.py",
            function="_setupNodes",
        ),
        "dynamic-enum",
        id="c7-dynamic-enum-placeholder",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Object of type `ID` has no attribute `vertices`",
            "verts = block.vertices",
            path="scripts/startup/bl_operators/object.py",
            function="execute",
        ),
        "base-class-subtype",
        id="c7-no-subclass-member-on-id-falls-through",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            "Object of type `Text` is not assignable to attribute `script` on type `FreestyleModuleSettings | None`",
            "self.freestyle_module.script = text",
            path="scripts/startup/bl_operators/freestyle.py",
        ),
        "set-by-ui-button",
        id="set-by-ui-button",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `objects` is not defined on `None` in union `Collection | None`",
            "bpy.context.collection.objects.unlink(bpy.context.object)",
            path="scripts/addons_core/io_scene_gltf2/blender/imp/node.py",
        ),
        "window-context-in-execute",
        id="window-context-in-execute",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `location` is not defined on `None` in union `Object | None`",
            "context.object.location.x = self.init_loc_x",
            path="doc/python_api/examples/bpy.types.Operator.6.py",
            function="modal",
        ),
        "set-by-preceding-call",
        id="set-by-preceding-call",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `type` is not defined on `None` in union `Object | None`",
            "return CyclesButtonsPanel.poll(context) and context.object.type != 'LIGHT'",
            path="intern/cycles/blender/addon/ui.py",
            function="poll",
            poll="        return CyclesButtonsPanel.poll(context) and context.object.type != 'LIGHT'",
        ),
        "narrowed-by-poll-helper",
        id="narrowed-by-poll-helper",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `bl_idname` is not defined on `None` in union `Operator | None`",
            'return operator.bl_idname == "IMPORT_ANIM_OT_bvh"',
            path="scripts/addons_core/io_anim_bvh/__init__.py",
            function="poll",
            attributes="bl_parent_id = \"FILE_PT_operator\"\nbl_options = {'HIDE_HEADER'}\n@classmethod\ndef poll(cls, context):\ndef draw(self, context):",
        ),
        "narrowed-by-parent-panel",
        id="narrowed-by-parent-panel",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `data` is not defined on `None` in union `Object | None`",
            "context.object.data.gltf2_variant_default_materials) > 0",
            path="scripts/addons_core/io_scene_gltf2/blender/com/gltf2_blender_ui.py",
            function="poll",
            poll='        return bpy.context.object and bpy.context.object.type == "MESH" and len(\n            context.object.data.gltf2_variant_default_materials) > 0',
        ),
        "narrowed-by-poll-alias",
        id="narrowed-by-poll-alias",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `data` is not defined on `None` in union `Object | None`",
            'col.prop(context.object.data, "active_feature_set")',
            path="scripts/addons_core/rigify/ui.py",
            poll="        return context.mode == 'EDIT_ARMATURE'",
        ),
        "narrowed-by-mode",
        id="narrowed-by-mode",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to bound method `ID.evaluated_get` is incorrect: Expected `Depsgraph`, found `Depsgraph | None`",
            "ob_eval = ob.evaluated_get(depsgraph)",
            path="release/datafiles/blender_icons_geom.py",
        ),
        "rarely-none-member",
        id="rarely-none-member",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `action` is not defined on `None` in union `AnimData | None`",
            "self.selected_action = context.object.animation_data.action.name",
            path="scripts/addons_core/rigify/rot_mode.py",
            cls="POSE_OT_convert_rotation",
            function="invoke",
        ),
        "correlated-condition",
        id="correlated-condition",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `full_library_path` is not defined on `None` in union `AssetRepresentation | None`",
            "asset_lib_path = asset.full_library_path",
            path="scripts/addons_core/pose_library/operators.py",
            cls="PoseAssetUser",
            function="_load_and_use_pose",
        ),
        "narrowed-by-poll-in-caller",
        id="narrowed-by-poll-in-caller",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `objects` is not defined on `None` in union `Collection | None`",
            "context.collection.objects.link(ob)",
            path="scripts/startup/bl_operators/clip.py",
            cls="CLIP_OT_bundles_to_mesh",
            function="execute",
        ),
        "collection-context-member",
        id="collection-context-member",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `areas` is not defined on `None` in union `Screen | None`",
            "if 'PREFERENCES' not in (area.type for area in context.screen.areas):",
            path="scripts/addons_core/bl_pkg/bl_extension_ops.py",
            cls="EXTENSIONS_OT_package_asset_library_show",
            function="execute",
            attributes="bl_options = {'INTERNAL'}\npkg_id: rna_prop_pkg_id\nrepo_index: rna_prop_repo_index\ndef execute(self, context):",
        ),
        "internal-operator",
        id="internal-operator",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `width` is not defined on `None` in union `Region | None`",
            "dimensions = region.width, region.height",
            path="doc/python_api/examples/bpy.types.RenderEngine.1.py",
            function="view_update",
        ),
        "ui-callback-editor-member",
        id="ui-callback-editor-member",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            'Object of type `Literal["TOOL"]` is not assignable to attribute `context` on type `Space | None`',
            "space.context = 'TOOL'",
            path="scripts/startup/bl_app_templates_system/2D_Animation/__init__.py",
            source="            space = area.spaces.active\n            space.context = 'TOOL'",
        ),
        "area-type-active-space",
        id="area-type-active-space",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `tag_redraw` is not defined on `None` in union `Region | None`",
            "bpy.context.region.tag_redraw()",
            path="scripts/addons_core/viewport_vr_preview/operators.py",
            source="        with bpy.context.temp_override(\n                window=window,\n                area=area,\n                region=view3d_region,\n                screen=window.screen\n        ):\n            bpy.context.region.tag_redraw()",
        ),
        "temp-override-member",
        id="temp-override-member",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `vertices` is not defined on `None` in union `Mesh | None`",
            "self.report({'INFO'}, f\"{len(mesh_from_orig.vertices)} in new mesh without modifiers.\")",
            path="doc/python_api/examples/bpy.types.Depsgraph.4.py",
            function="execute",
            source="        mesh_from_orig = obj.to_mesh()\n        self.report({'INFO'}, f\"{len(mesh_from_orig.vertices)} in new mesh without modifiers.\")",
        ),
        "none-excluded-by-arguments",
        id="none-excluded-by-arguments",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `enabled` is not defined on `None` in union `UserAssetLibrary | Unknown | None`",
            "if lib.enabled != enable:",
            path="scripts/addons_core/bl_pkg/bl_extension_ops.py",
            function="extension_asset_library_ensure",
            source="    asset_libraries = bpy.context.preferences.filepaths.asset_libraries\n"
            "    lib = asset_libraries.new(name=name, remote_url=remote_url, extension_id=extension_id)\n"
            "    if lib.enabled != enable:",
        ),
        "none-excluded-by-arguments",
        id="none-excluded-by-arguments-local-collection",
    ),
    # Sorted site by site (docs/reports/spec-95-site-decisions.md), second round.
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `source` is not defined on `None` in union `Image | None`",
            "is_tiled = context.edit_image.source == 'TILED'",
            path="scripts/startup/bl_operators/image.py",
            cls="IMAGE_OT_open_images",
            function="execute",
            source="            bpy.ops.image.open(\n                filepath=filepath,\n                directory=self.directory,\n"
            "                files=files,\n                use_sequence_detection=self.use_sequence_detection,\n"
            "                relative_path=self.relative_path,\n            )\n"
            "            is_tiled = context.edit_image.source == 'TILED'",
        ),
        "set-by-preceding-call",
        id="set-by-preceding-call-multiline-call",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `data` is not defined on `None` in union `Object | None`",
            "mesh = obj.data",
            path="scripts/templates_py/operator_mesh_add.py",
            function="add_box",
            source="    bpy.ops.mesh.primitive_cube_add()\n    obj = bpy.context.active_object\n    mesh = obj.data",
        ),
        "added-object",
        id="c5-added-object-error-falls-through",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `source` is not defined on `None` in union `Image | None`",
            "is_tiled = context.edit_image.source == 'TILED'",
            path="scripts/startup/bl_operators/image.py",
            function="execute",
            source="            bpy.ops.mesh.primitive_plane_add()\n            is_tiled = context.edit_image.source == 'TILED'",
        ),
        "set-by-preceding-call",
        id="c5-added-object-only-for-the-object",
    ),
    *(
        pytest.param(
            diagnostic(rule, "`context.object` is taken as `Object`", "print(context.object.name)"),
            rule.removeprefix("blender-"),
            id=f"c5-{rule.removeprefix('blender-')}",
        )
        for rule in (
            "blender-assumed-internal-operator",
            "blender-assumed-editor-member",
            "blender-assumed-preset-context",
            "blender-assumed-added-object",
        )
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `action` is not defined on `None` in union `AnimData | None`",
            "if not scene.animation_data.action:",
            path="scripts/startup/bl_operators/sequencer.py",
            cls="SequencerFadesAdd",
            function="execute",
            source="        scene = context.sequencer_scene\n        if not scene.animation_data:\n"
            "            scene.animation_data_create()\n        if not scene.animation_data.action:",
        ),
        "set-by-preceding-call",
        id="set-by-preceding-call-ensure-idiom",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `location` is not defined on `None` in union `Object | None`",
            "objects_tmp.sort(key=lambda o: (last_obj.location - o.location).length)",
            path="scripts/startup/bl_operators/rigidbody.py",
            cls="ConnectRigidBodies",
            bases="Operator",
            function="execute",
            has_poll=True,
            poll="        obj = context.object\n        return (obj and obj.rigid_body)",
            source="        obj_act = context.active_object\n        last_obj = obj_act\n"
            "        objects_tmp.sort(key=lambda o: (last_obj.location - o.location).length)",
        ),
        "narrowed-by-poll-alias",
        id="narrowed-by-poll-alias-local-alias",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `nodes` is not defined on `None` in union `NodeTree | None`",
            "nodes = context.space_data.edit_tree.nodes",
            path="scripts/startup/bl_operators/node.py",
            cls="NODE_OT_viewer_shortcut_get",
            bases="Operator",
            function="execute",
            has_poll=True,
            poll="        space = context.space_data\n        return (\n            (space is not None) and\n"
            "            space.node_tree is not None\n        )",
            source="        nodes = context.space_data.edit_tree.nodes",
        ),
        "correlated-condition",
        id="poll-alias-of-another-member",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Method `__getitem__` of type `Overload[(i: SupportsIndex, /) -> int, (s: slice[SupportsIndex | None, "
            "SupportsIndex | None, SupportsIndex | None], /) -> list[int]]` cannot be called with key of type `None` "
            "on object of type `list[int]`",
            "yield prev_file, matches[segment], length",
            path="scripts/startup/bl_operators/image_as_planes.py",
            function="find_image_sequences",
            source="    segment = None\n    for filename in files:\n        yield prev_file, matches[segment], length",
        ),
        "python-optional",
        id="python-optional-index",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Method `__getitem__` of type `Overload[(key: int, /) -> Property, (key: str, /) -> Property, (key: "
            "slice[Any, Any, Any], /) -> list[Property]]` cannot be called with key of type `None` on object of type "
            "`bpy_prop_collection[Property]`",
            "brush_type_items = bpy.types.Brush.bl_rna.properties[cls.brush_type_prop].enum_items",
            path="scripts/startup/bl_ui/properties_paint_common.py",
            cls="BrushAssetShelf",
            function="has_tool_with_brush_type",
        ),
        "general-typing",
        id="general-typing-none-class-attribute-key",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to function `connect_sockets` is incorrect: Expected `NodeSocket`, found `int | NodeSocket | None`",
            "connect_sockets(n2.outputs[connection[0]], connection[1])",
            path="scripts/addons_core/node_wrangler/operators/swap_links.py",
            cls="NODE_OT_swap_links",
            function="execute",
        ),
        "general-typing",
        id="general-typing-list-as-record",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            "Object of type `int` is not assignable to attribute `ui_shortcut` on type "
            "`(Node & ~AlwaysFalsy) | (Unknown & ~AlwaysFalsy)`",
            "viewer_node.ui_shortcut = self.viewer_index",
            path="scripts/startup/bl_operators/node.py",
            cls="NODE_OT_viewer_shortcut_set",
            function="execute",
        ),
        "base-class-subtype",
        id="base-class-subtype-with-unknown",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            "Object of type `AssetRepresentation | None` is not assignable to `AssetRepresentation`",
            "asset: AssetRepresentation = context.asset",
            path="scripts/addons_core/pose_library/operators.py",
            cls="PoseAssetUser",
            function="execute",
            has_poll=True,
        ),
        "narrowed-by-poll-in-caller",
        id="narrowed-by-poll-in-mixin",
    ),
    pytest.param(
        diagnostic(
            "missing-union-attribute",
            "Attribute `animation_data` is not defined on `None` in union `Object | None`",
            "assigned_action = obj.animation_data and obj.animation_data.action",
            path="scripts/addons_core/rigify/rot_mode.py",
            cls="POSE_OT_convert_rotation",
            function="execute",
        ),
        "operator-without-poll",
        id="operator-without-poll",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            'Argument to function `batch_for_shader` is incorrect: Expected `Literal["POINTS", "LINES", "TRIS", "LINE_STRIP", "TRI_STRIP", ... omitted 3 literals]`, found `Literal["TRI_FAN"]`',
            "batch = batch_for_shader(shader, 'TRI_FAN', {\"pos\": vertices})",
            path="scripts/addons_core/node_wrangler/utils/draw.py",
        ),
        "deprecated-enum-value",
        id="deprecated-enum-value",
    ),
    pytest.param(
        diagnostic(
            "missing-attribute",
            "Module `bpy.utils` has no member `script_paths_pref`",
            "*bpy.utils.script_paths_pref(),",
            path="scripts/startup/bl_ui/space_userpref.py",
        ),
        "unexported-function",
        id="unexported-function",
    ),
    # Regrouped from the Blender fixes (spec #123, C1): right code, or code outside Blender's reach.
    pytest.param(
        diagnostic(
            "unresolved-reference",
            "Name `properties_paint_common` used when not defined",
            "properties_paint_common.register()",
            path="scripts/startup/bl_ui/__init__.py",
            function="register",
        ),
        "reload-idiom",
        id="regrouped-dynamic-import-of-submodules",
    ),
    pytest.param(
        diagnostic(
            "unresolved-reference",
            "Name `_icon_cache` used when not defined",
            "    for icon_value in set(_icon_cache.values()):",
            path="scripts/startup/bl_ui/space_toolsystem_common.py",
            source='# Support reloading icons.\nif "_icon_cache" in locals():\n    release = bpy.app.icons.release\n'
            "    for icon_value in set(_icon_cache.values()):",
        ),
        "reload-idiom",
        id="regrouped-locals-guard",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to bound method `Area.header_text_set` is incorrect: Expected `str`, found `None`",
            "context.area.header_text_set(None)",
            path="scripts/startup/bl_operators/wm.py",
            cls="WM_OT_context_modal_mouse",
            function="modal",
        ),
        "stub-none-mismatch",
        id="regrouped-header-text-set-none",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to bound method `GPUVertBuf.attr_fill` is incorrect: Expected `int | str`, found `None`",
            "vbo.attr_fill(id=pos_id, data=verts)",
            path="scripts/modules/gpu_extras/presets.py",
            function="draw_circle_2d",
        ),
        "stub-none-mismatch",
        id="regrouped-attr-fill-id",
    ),
    pytest.param(
        diagnostic(
            "invalid-explicit-return",
            "Return type does not match returned value: expected `IdPropSequence[RigifyName]`, found "
            "`bpy_prop_collection_idprop[RigifyName]`",
            "return id_store.rigify_types  # noqa",
            path="scripts/addons_core/rigify/ui.py",
            function="get_rigify_types",
        ),
        "untyped-python",
        id="regrouped-rigify-typed-return",
    ),
    pytest.param(
        diagnostic(
            "invalid-explicit-return",
            "Return type does not match returned value: expected `TypedObject[Armature]`, found "
            "`_Object_ARMATURE & ~AlwaysFalsy`",
            "return obj  # noqa",
            path="scripts/addons_core/rigify/utils/misc.py",
            function="verify_armature_obj",
        ),
        "untyped-python",
        id="regrouped-rigify-typed-object-return",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to constructor `zip.__new__` is incorrect: Expected `Iterable[Unknown]`, found `None`",
            "for svert, t in zip(stroke, iter_t2d_along_stroke(stroke)):",
            path="scripts/freestyle/modules/parameter_editor.py",
            cls="ColorAlongStrokeShader",
            function="shade",
        ),
        "untyped-python",
        id="regrouped-freestyle-zip-none",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to `Keyframe.__init__` is incorrect: Expected `tuple[FCurve]`, found `None`",
            "key = Keyframe(None, frame, channel)",
            path="scripts/addons_core/io_scene_gltf2/blender/exp/animation/sampled/object/keyframes.py",
            function="gather_object_sampled_keyframes",
        ),
        "untyped-python",
        id="regrouped-gltf-keyframe-none",
    ),
    pytest.param(
        diagnostic(
            "invalid-explicit-return",
            "Return type does not match returned value: expected `HASH`, found `_HashObjectWithOptionalLength`",
            "return hashlib.new(algorithm, usedforsecurity=False)",
            path="scripts/modules/_bpy_internal/disk_file_hash_service/hash_service.py",
            cls="DiskFileHashService",
            function="_get_hasher",
        ),
        "general-typing",
        id="regrouped-typeshed-private-return",
    ),
    pytest.param(
        diagnostic(
            "missing-argument",
            "No argument provided for required parameter `version` of bound method "
            "`PackageInstaller.package_name_version_gen`",
            "for pn in self.package_name_version_gen(package, package_distro_name):",
            path="build_files/linux/install_linux_packages.py",
            cls="PackageInstaller",
            function="package_find",
        ),
        "general-typing",
        id="regrouped-signature-of-every-override",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to function `set_convenience_variable` is incorrect: Expected `Value`, found `None`",
            "gdb.set_convenience_variable(variable_name, None)",
            path="tools/debug/gdb/blender_gdb_extension.py",
            function="eval_var",
        ),
        "general-typing",
        id="regrouped-third-party-stub",
    ),
    pytest.param(
        diagnostic(
            "unresolved-reference",
            "Name `BMO_OP_SLOT_FLT` used when not defined",
            "if tp == BMO_OP_SLOT_FLT:",
            path="doc/python_api/rst_from_bmesh_opdefines.py",
            function="get_args_wash",
        ),
        "runtime-name",
        id="regrouped-globals-update",
    ),
    pytest.param(
        diagnostic(
            "unresolved-reference",
            "Name `gdb` used when not defined",
            "class PrintStructC99(gdb.Command):",
            path="tools/utils/gdb_struct_repr_c99.py",
        ),
        "runtime-name",
        id="regrouped-host-program-module",
    ),
    pytest.param(
        diagnostic(
            "unresolved-reference",
            "Name `me_loops_color_active` used when not defined",
            "me_loops_color = me_loops_color_active.data[:]",
            path="release/datafiles/blender_icons_geom.py",
            function="mesh_data_lists_from_mesh",
        ),
        "undefined-name",
        id="bf1-undefined-name-in-tools",
    ),
    # fake-bpy-module's lossy stubs of Blender's Python modules (`-> None`, a dropped `@staticmethod`).
    pytest.param(
        diagnostic(
            "missing-argument",
            "No argument provided for required parameter `fn` of function `ToolDef.from_fn`",
            "@ToolDef.from_fn",
            path="scripts/startup/bl_ui/space_toolsystem_toolbar.py",
            cls="_defs_view3d_generic",
        ),
        "fake-bpy-python-module",
        id="regrouped-fake-bpy-static-method",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to function `ToolDef.from_fn` is incorrect: Expected `ToolDef`, found `def cursor() -> Unknown`",
            "@ToolDef.from_fn",
            path="scripts/startup/bl_ui/space_toolsystem_toolbar.py",
            cls="_defs_view3d_generic",
        ),
        "fake-bpy-python-module",
        id="regrouped-fake-bpy-static-method-argument",
    ),
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument to bound method `KeyingSetPaths.add` is incorrect: Expected `str`, found `None`",
            "ks.paths.add(id_block, path)",
            path="scripts/startup/keyingsets_builtins.py",
            cls="BUILTIN_KSI_DeltaLocation",
            function="generate",
        ),
        "fake-bpy-python-module",
        id="regrouped-fake-bpy-none-return-argument",
    ),
    pytest.param(
        diagnostic(
            "invalid-explicit-return",
            "Return type does not match returned value: expected `AssetLibraryMeta`, found `None`",
            "return metadata",
            path="scripts/modules/_bpy_internal/assets/remote_library/cli_listing_generator.py",
            function="_toplevel_metadata",
        ),
        "fake-bpy-python-module",
        id="regrouped-fake-bpy-none-return",
    ),
    pytest.param(
        diagnostic(
            "invalid-assignment",
            "Object of type `Literal[0]` is not assignable to attribute `shift_x` on type `Armature | Camera | Curve | "
            "... omitted 11 union elements`",
            "cam.data.shift_x = 0",
            path="scripts/addons_core/viewport_vr_preview/operators.py",
            cls="VIEW3D_OT_vr_location_scouting_active_camera_to_capture",
            function="execute",
        ),
        "object-data-untagged",
        id="regrouped-fake-bpy-object-data-in-a-buggy-class",
    ),
    pytest.param(
        diagnostic(
            "invalid-explicit-return",
            "Return type does not match returned value: expected `tuple[dict[tuple[str, str], InfoStructRNA]]`, found "
            "`tuple[dict[tuple[str, str], InfoStructRNA]] | None`",
            "return ret",
            path="doc/python_api/sphinx_doc_gen.py",
            function="rna_info_BuildRNAInfo_cache",
        ),
        "fake-bpy-python-module",
        id="regrouped-fake-bpy-none-return-cached",
    ),
    # fake-bpy-module's `bpy.types` declares a registered class as an instance, so its method reads as bound.
    pytest.param(
        diagnostic(
            "invalid-argument-type",
            "Argument is incorrect: Expected `Iterable[tuple[str, str, str] | None]`, found `bound method "
            "PREFERENCES_OT_addon_install._target_path_items(context) -> Unknown`",
            "items=bpy.types.PREFERENCES_OT_addon_install._target_path_items,",
            path="scripts/addons_core/bl_pkg/bl_extension_ops.py",
            cls="EXTENSIONS_OT_package_install_files",
        ),
        "fake-bpy-type-alias",
        id="fake-bpy-registered-class-method-bound",
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
]


@pytest.mark.parametrize(("d", "expected"), CASES)
def test_cause(d, expected):
    assert d.cause.name == expected


# Rules ty 0.0.103 split one rule into: which one a diagnostic gets depends on details the causes do not sort by
# (a union receiver, a lost keyword, an implicit return).
SPLITS = [
    {"missing-attribute", "missing-union-attribute"},
    {"incompatible-method-override", "lost-keyword-for-regular-parameter"},
    {"invalid-explicit-return", "invalid-implicit-return", "invalid-generator-return-type"},
]


@pytest.mark.parametrize(
    ("d", "expected", "sibling"),
    [
        pytest.param(case.values[0], case.values[1], sibling, id=f"{case.id}-as-{sibling}")
        for case in CASES
        for split in SPLITS
        if case.values[0].rule in split
        for sibling in sorted(split - {case.values[0].rule})
    ],
)
def test_split_rules_sort_alike(d, expected, sibling):
    assert dataclasses.replace(d, rule=sibling).cause.name == expected


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
        ("assumed-internal-operator", "assumption", "C5"),
        ("narrowed-by-bl-context", "implied-narrowing", "C6"),
        ("bl-context-implies-member", "implied-narrowing", ""),
        ("assumed-added-object", "assumption", "C5"),
        ("preset-context-member", "assumption", ""),
        ("added-object", "assumption", ""),
        ("internal-operator", "assumption", ""),
        ("ui-callback-editor-member", "assumption", ""),
        ("collection-context-member", "assumption", ""),
        ("mixin-self", "typing-debt", ""),
        ("modifiers-new", "typing-debt", ""),
        ("stub-none-mismatch", "typechecker-fix", ""),
        ("runtime-name", "typing-debt", ""),
        ("reload-idiom", "typing-debt", ""),
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
        "scripts/startup/bl_ui/space_x.py:24:1: error[missing-attribute] Unresolved attribute\n"
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
        attributes=first.scope.attributes,
        poll=first.scope.poll,
        source=first.scope.source,
    )
    assert 'bl_label = "X"' in first.scope.attributes
    assert first.scope.poll.strip().endswith("return context.object")
    assert first.scope.source.startswith("    def draw(self, context):")
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
        ("doc\\python_api\\examples\\gpu.4.py", "examples"),
        ("scripts/templates_py/Operator/modal_view3d.py", "templates"),
        ("doc/python_api/sphinx_doc_gen.py", "other"),
    ],
)
def test_area(path, expected):
    assert area(path) == expected


def test_summary_has_every_cause_by_group_group_totals_and_warnings_apart():
    diagnostics = [
        ("narrowed-by-poll", "shipped", "invalid-argument-type", "error"),
        ("narrowed-by-poll", "presets", "blender-narrowed-by-poll", "warning"),
        ("tooldef", "shipped", "missing-attribute", "error"),
        ("unsorted", "other", "invalid-argument-type", "error"),
    ]
    text = summary("# check:blender main, builtin stubs, Blender abc1234567", diagnostics)
    lines = text.splitlines()

    assert lines[0] == "# check:blender main, builtin stubs, Blender abc1234567"
    assert lines[1].split() == [
        "cause",
        "group",
        "slice",
        "shipped",
        "presets",
        "examples",
        "templates",
        "other",
        "total",
    ]
    rows = {line.split()[0]: line.split()[1:] for line in lines[2:] if line.strip()}
    # every cause has a row, also when zero, listed by group
    assert [line.split()[0] for line in lines[2 : 2 + len(CAUSES)]] == [
        c.name for g in GROUPS for c in CAUSES if c.group == g
    ]
    assert rows["narrowed-by-poll"] == ["implied-narrowing", "S5", "1", "1", "0", "0", "0", "2"]
    assert rows["tooldef"] == ["blender-fix", "BF2", "1", "0", "0", "0", "0", "1"]
    assert rows["mixin-self"] == ["typing-debt", "-", "0", "0", "0", "0", "0", "0"]
    # a total per group, every group listed
    group_header = lines.index(next(line for line in lines if line.split()[:1] == ["group"]))
    assert [line.split()[0] for line in lines[group_header + 1 : group_header + 1 + len(GROUPS)]] == GROUPS
    assert rows["implied-narrowing"] == ["1", "1", "0", "0", "0", "2"]
    assert rows["blender-fix"] == ["1", "0", "0", "0", "0", "1"]
    assert rows["assumption"] == ["0", "0", "0", "0", "0", "0"]
    # errors and warnings on separate total lines
    assert rows["errors"] == ["2", "0", "0", "0", "1", "3"]
    assert rows["warnings"] == ["0", "1", "0", "0", "0", "1"]
    # rules sorted by name, with a column per severity
    rule_header = lines.index(next(line for line in lines if line.split()[:1] == ["rule"]))
    assert lines[rule_header].split() == ["rule", "error", "warning"]
    assert lines[rule_header + 1 :] == [
        f"{'blender-narrowed-by-poll':<40}{0:>8}{1:>8}",
        f"{'invalid-argument-type':<40}{2:>8}{0:>8}",
        f"{'missing-attribute':<40}{1:>8}{0:>8}",
    ]
