"""Sort check:blender's diagnostics into causes, each with a group, and into areas of the Blender source.

A **cause** is why a diagnostic is reported; its **group** says where the fix belongs (spec #95), and its **slice**
the spec slice that addresses it. ``S*`` and ``BF*`` are the slices of spec #95, ``C*`` those of spec #123 (the
Blender typechecker spec), so ``S6`` and ``C5`` are both Assumption slices, of the two specs:

- ``blender-fix``: Blender's own Python code is wrong (slices BF1, BF2);
- ``assumption`` / ``implied-narrowing`` / ``imprecise-annotation``: right code the typechecker accepts and reports
  under a dedicated ``blender-*`` rule (S6 and C5, C7; S5 and C6; S4);
- ``typechecker-fix``: RNA flags, the stub generator or ``ty_blender`` (S1, S2, S3);
- ``typing-debt``: out of scope (general typing debt, or a cause the spec leaves as it is);
- ``unsorted``: recognised kinds with no slice, and everything else.

``CAUSES`` is a first-match table over a diagnostic's rule, message, the source line it points at (read from the
worktree ty just checked, so message and line always belong together), its path and its enclosing class and
function (``Scope``). Each cause names the slice that addresses it. The patterns come from the spec's slices and
the research on the ``research/*`` branches (``blender-true-problems``, ``false-positive-fixes``,
``candidate-assumptions``, ``imprecise-patterns``, ``silent-assumptions``, ``stub-gaps``, ``check-blender-setup``).
The causes of the Imprecise annotations, Implied narrowings and Assumptions (S4-S6) are their dedicated rules
(``blender-narrowed-by-poll``, ...): an error of the same shape is code the rule did not accept.
``area(path)`` names the part of the source tree a path is in.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

GROUPS = [
    "blender-fix",
    "assumption",
    "implied-narrowing",
    "imprecise-annotation",
    "typechecker-fix",
    "typing-debt",
    "unsorted",
]

DIAGNOSTIC_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):\d+: (?P<severity>\w+)\[(?P<rule>[\w-]+)\] (?P<msg>.*)$", re.MULTILINE
)

AREAS = [
    (
        "shipped",
        (
            "scripts/startup/",
            "scripts/modules/",
            "scripts/addons_core/",
            "scripts/freestyle/",
            "intern/cycles/blender/addon/",
        ),
    ),
    ("presets", ("scripts/presets/",)),
    ("examples", ("doc/python_api/examples/",)),
    ("templates", ("scripts/templates_py/",)),
]
AREA_NAMES = [name for name, _ in AREAS] + ["other"]


@dataclass(frozen=True)
class Scope:
    """Where a diagnostic sits: the enclosing class (name and bases as written), the enclosing function and its
    parameter names, whether the class defines ``poll`` itself, and the Registered property names its file assigns
    (``bpy.types.X.name = <Property>(...)``); also what the class body and its poll say, and the function's source."""

    cls: str = ""
    bases: str = ""
    function: str = ""
    params: tuple[str, ...] = ()
    has_poll: bool = False
    registers: frozenset[str] = frozenset()
    # The statements directly in the class body (``bl_parent_id = ...``, ``bl_options = {...}``), the source of the
    # ``poll`` the class runs (its own, or that of a base class defined in the same file), and the enclosing
    # function's source up to the diagnostic's line.
    attributes: str = ""
    poll: str = ""
    source: str = ""


@dataclass(frozen=True)
class Diagnostic:
    path: str  # relative to the source root, as ty prints it
    line: int
    rule: str
    msg: str
    text: str  # the source line
    severity: str = "error"
    scope: Scope = field(default_factory=Scope)

    @property
    def cause(self) -> Cause:
        return cause(self)

    @property
    def area(self) -> str:
        return area(self.path)


@dataclass(frozen=True)
class Cause:
    name: str
    group: str
    slice: str  # the spec slice that addresses it, "" when none
    matches: Callable[[Diagnostic], bool]
    rule: str = ""  # the dedicated blender-* rule that reports it once its slice has landed


# --- facts read off a diagnostic -------------------------------------------------------------------------------

MODIFIERS_NEW = r"\.modifiers\.new\("
NULLABLE_MODIFIER = re.compile(r"`(?:\w*Modifier \| None|None \| \w*Modifier)`")
NULLABLE = re.compile(r"\| None`|`None \||in union `[^`]*(?<!~)None|found `[^`]*\| None`")
STRING_LITERAL = re.compile(r"""['"]""")
CONTEXT = r"\b(?:context|ctx|C|_context)\."

OPERATOR_RETURNS = {"execute", "invoke", "modal"}
INTERACTIVE_CALLBACKS = {"invoke", "modal", "exit"}
UI_ROOTS = {"panel", "menu", "header", "uilist"}
UI_DRAW_CALLBACKS = {"draw", "draw_header", "draw_header_preset", "draw_item", "draw_filter"}
# Callback parameters Blender always fills, by position counting ``self``/``cls`` (S1); ``draw_item``'s ``item``
# (position 4) is the list-item Assumption (S6) instead.
NEVER_NONE_PARAMETERS = {
    "draw_item": {3},
    "filter_items": {3},
    "iterator": {2},
    "generate": {2},
    "asset_poll": {1},
    "draw_context_menu": {2, 3},
    "update": {2},
    "render": {1},
    "bake": {1},
    "view_update": {2},
    "view_draw": {2},
    "update_render_passes": {2},
}
CONTEXT_STORE_MEMBERS = {"constraint", "keymap", "animated_id", "freestyle_module", "tool", "asset_shelf"}
FREESTYLE_OVERRIDES = re.compile(
    r"`(?:Unary|Binary)(?:Predicate|Function)\w*\.__call__`|`ChainingIterator\.traverse`|`StrokeShader\.shade`"
)
RENDER_ENGINE_UPDATES = re.compile(r"`RenderEngine\.update(?:_render_passes|_script_node|_custom_camera)?`")
# 2.7x API and functions removed from Python (BF1).
DEAD_API = re.compile(r"no (?:attribute|member) `(?:texture_slots|users_material|formatargspec)`")
# Sub-pointers that exist for one value of a type enum (`fluid_type == 'DOMAIN'`): out of scope.
SETTINGS_POINTER = re.compile(
    r"(?:Domain|Flow|Effector)Settings|RigidBody\w*|FieldSettings|ParticleSettings|Brush\w*Settings|SceneEEVEE"
    r"|DynamicPaint\w*Settings|CollisionSettings|SoftBodySettings"
)
# Sub-pointers that exist for one value of a type or mode enum, or a flag, read without a check: an armature's
# `Object.pose`, a Grease Pencil material's `grease_pencil`, a paint mode's `tool_settings.<mode>`, the `node_tree`
# of a material using nodes or of a group node (research `candidate-assumptions`, "not covered"), the `properties`
# of a geometry-nodes modifier with a node group.
SUB_POINTER = re.compile(
    r"\b(?:Pose|MaterialGPencilStyle|VertexPaint|Sculpt|ImagePaint|UvSculpt|CurvesSculpt|ParticleEdit|Gp\w*Paint"
    r"|NodesModifierProperties)"
    r" \| None`"
)
# Functions and classes of Python code that is untyped as a whole (glTF's dicts and numpy, rigify's
# `IdPropSequence` / `TypedObject`, Freestyle's functors, `_bl_i18n_utils`, `bl_app_override`): typing debt, out of
# scope (research `blender-true-problems`, "Ruled out").
UNTYPED_PACKAGES = (
    "scripts/addons_core/io_scene_gltf2/",
    "scripts/addons_core/rigify/",
    "scripts/freestyle/",
    "scripts/modules/_bl_i18n_utils/",
    "scripts/modules/bl_app_override/",
)
RIGIFY = "scripts/addons_core/rigify/"
NUMPY = re.compile(r"\bndarray\b|\bnumpy\.")
# Optional settings Blender's stubs lack because the Blender that generated them was built without the feature.
BUILD_OPTION_TYPE = re.compile(r"`FFmpegSettings`|`Literal\[\"FFMPEG\"\]` is not assignable")
# Blender's code that reads a pointer its poll() does not check, or that has no poll() (research
# `blender-true-problems`, cause 4): (path, enclosing class or "", enclosing function or "", text on the line).
UNCHECKED_POINTER_BUGS = [
    ("scripts/addons_core/viewport_vr_preview/operators.py",
     "VIEW3D_OT_vr_location_scouting_active_camera_to_capture", "", ""),
    ("scripts/addons_core/viewport_vr_preview/operators.py",
     "VIEW3D_OT_vr_location_scouting_viewfinder_capture", "poll", ""),
    ("scripts/startup/bl_operators/anim.py", "ANIM_OT_keying_set_export", "", ""),
    ("scripts/modules/addon_utils.py", "", "", "ex.name"),
]  # fmt: skip
# The sites whose cause is a fact about their callers or a related check, which no pattern on the line shows
# (docs/reports/spec-95-site-decisions.md): (path, enclosing class or "", enclosing function or "", text on the line).
# A helper or callback reached only after the poll of the operator or panel that runs it checked the pointer, or a
# callback of an operator mixin whose own poll checks it (ty takes a poll as narrowing only on an Operator).
NARROWED_IN_CALLER_SITES = [
    ("scripts/addons_core/pose_library/operators.py", "PoseAssetUser", "", ""),
    ("scripts/addons_core/pose_library/operators.py", "POSELIB_OT_restore_previous_action", "modal", ""),
    ("scripts/addons_core/pose_library/pose_creation.py", "", "create_pose_asset_from_context", ""),
    ("scripts/addons_core/rigify/generate.py", "Generator", "__duplicate_rig", ""),
    ("scripts/startup/bl_operators/copy_global_transform.py", "", "_selected_keyframes", ""),
    ("scripts/startup/bl_operators/copy_global_transform.py", "", "get_matrix", "context.active_object"),
    ("scripts/startup/bl_operators/copy_global_transform.py", "", "set_matrix", "context.active_object"),
    ("scripts/startup/bl_operators/copy_global_transform.py", "OBJECT_OT_fix_to_camera", "_execute", ""),
    ("scripts/startup/bl_operators/uvcalc_lightmap.py", "LightMapPack", "draw", ""),
    ("scripts/startup/bl_ui/space_project.py", "PROJECT_PT_color_management", "draw_centered", ""),
    ("scripts/startup/keyingsets_builtins.py", "BUILTIN_KSI_WholeCharacterSelected", "iterator", ""),
]
# A pointer implied by another check: a sibling enum or flag, the pointer the poll checks (`context.constraint` for
# its owner), a structural invariant, or the same pointer checked through an alias.
CORRELATED_SITES = [
    ("scripts/addons_core/io_scene_fbx/import_fbx.py", "FbxImportHelperNode", "link_hierarchy", "arm.name"),
    (
        "scripts/addons_core/node_wrangler/operators/align_selected.py",
        "NODE_OT_align_selected",
        "execute",
        "active_loc_diff",
    ),
    ("scripts/addons_core/rigify/rot_mode.py", "POSE_OT_convert_rotation", "invoke", ""),
    ("scripts/addons_core/viewport_vr_preview/operators.py", "VIEW3D_OT_cursor_to_vr_landmark", "execute", ""),
    ("scripts/addons_core/viewport_vr_preview/operators.py", "VIEW3D_GGT_vr_landmarks", "draw_prepare", ""),
    ("scripts/startup/bl_operators/constraint.py", "CONSTRAINT_OT_disable_keep_transform", "execute", ""),
    ("scripts/startup/bl_operators/copy_global_transform.py", "", "get_matrix", "arm.matrix_world"),
    ("scripts/startup/bl_operators/copy_global_transform.py", "", "set_matrix", "evaluated_get"),
    ("scripts/startup/bl_operators/geometry_nodes.py", "MoveModifierToNodes", "execute", ""),
    ("scripts/startup/bl_operators/node.py", "NODE_OT_interface_item_remove", "execute", ".parent"),
    ("scripts/startup/bl_operators/node.py", "NODE_OT_viewer_shortcut_get", "execute", ""),
    ("scripts/startup/bl_operators/sequencer.py", "SequencerCrossfadeSounds", "execute", "sequence_editor"),
    ("scripts/startup/bl_operators/sequencer.py", "SequencerSplitMulticam", "execute", ""),
]
# The None test lives in a helper without a TypeGuard, or in the only caller.
HELPER_CHECKS_SITES = [
    ("scripts/addons_core/pose_library/operators.py", "POSELIB_OT_paste_asset", "poll", ""),
    ("scripts/addons_core/pose_library/asset_browser.py", "", "params", "return space_data.params"),
    (
        "scripts/addons_core/viewport_vr_preview/operators.py",
        "VIEW3D_OT_vr_location_scouting_add_marker_from_capture",
        "execute",
        "",
    ),
    ("scripts/startup/bl_operators/image_as_planes.py", "IMAGE_OT_convert_to_mesh_plane", "execute", "img.name"),
    (
        "scripts/modules/_bpy_internal/assets/remote_library/cli_listing_generator_asset_finder.py",
        "",
        "_save_thumbnail",
        "",
    ),
]
# Operators with no poll and no menu entry (deprecated, or run by a button only): a poll would be the clean fix.
OPERATOR_WITHOUT_POLL_SITES = [
    ("scripts/addons_core/rigify/rot_mode.py", "POSE_OT_convert_rotation", "execute", "obj."),
    ("scripts/addons_core/rigify/ui.py", "UpgradeMetarigTypes", "execute", ""),
    ("scripts/addons_core/rigify/ui.py", "UpgradeMetarigLayers", "execute", ""),
]
BASE_CLASS = re.compile(
    r"`\(?(?:NodeSocket|Node|Constraint|Modifier|Strip|ActionStrip|Light|LightProbe|Curve|Texture|TextureSlot|IKParam"
    r"|Gizmo|Space|ID|bpy_struct|AnyType|UserAssetLibrary|Attribute|FEdge|NodeTreeInterfaceItem)(?:\[\w+\])?"
    r"(?: & ~\w+)*\)?`"
)
OTHER_CONTEXT_TYPE = re.compile(r"`(?:Space|Region|Area|Screen|Window|WorkSpace|Context) \| None`")
NEVER_NONE_CONTEXT_TYPE = re.compile(r"`(?:Preferences|WindowManager) \| None`")
CALLBACK_PARAMETER_TYPE = re.compile(
    r"`(?:bpy_struct|AnyType|KeyingSet|AssetRepresentation|Depsgraph|ViewLayer) \| None`"
)
# The rules ty 0.0.103 split one rule into. The causes do not sort by what tells them apart (a union receiver, a
# lost keyword, an implicit return), so a cause that names one names all of its split.
MISSING_ATTRIBUTE_RULES = {"missing-attribute", "missing-union-attribute"}
METHOD_OVERRIDE_RULES = {"incompatible-method-override", "lost-keyword-for-regular-parameter"}
RETURN_RULES = {"invalid-explicit-return", "invalid-implicit-return", "invalid-generator-return-type"}
STUB_GAP_RULES = {
    "not-iterable",
    "unsupported-operator",
    "not-subscriptable",
    "not-callable",
    *METHOD_OVERRIDE_RULES,
    "incompatible-attribute-override",
    "incompatible-property-override",
    "incompatible-mutable-override",
}
GENERAL_TYPING_RULES = {
    "deprecated",
    "invalid-implicit-return-in-function-with-stub-body",
    "unused-type-ignore-comment",
    "unused-ignore-comment",
    "unresolved-global",
}
# Attributes Python code sets on its own functions and modules (`fn._is_first = False`, `mod.__addon_enabled__`).
PYTHON_OBJECT_ATTRIBUTE = re.compile(r"^Function `\w+` has no attribute|on type `(?:def |ModuleType\b)")
MISSING_ATTRIBUTE = re.compile(
    r"has no attribute `(\w+)`|Attribute `(\w+)` is not defined on|Unresolved attribute `(\w+)` on type"
)


# --- facts of the causes sorted site by site (docs/reports/spec-95-site-decisions.md) --------------------------

# A poll that checks its pointers in a form the poll reader does not follow: a helper (Node Wrangler's `nw_check*`,
# rigify's `is_metarig`), a base class or mixin poll (`super().poll(context)`, `PhysicButtonsPanel.poll_force_field`),
# `bool(...)` around the checks, `try`/`except AttributeError`, or `XrSessionState.is_running(context)`.
POLL_HELPER = re.compile(
    r"\bnw_check|\bis_(?:valid_)?metarig\(|return bool\(|super\(\)\.poll\(|\b\w+\.poll(?:_\w+)?\(context\)"
    r"|except AttributeError|\.is_running\("
)
# Mixins whose poll calls such a helper and is defined in another file.
POLL_HELPER_BASES = re.compile(r"\bNWBase\b")
# A poll that checks the pointer through another expression than the one read: `getattr(context, "member", None)`,
# a walrus or local alias, or `bpy.context` for the `context` parameter.
POLL_ALIAS = re.compile(r"\b(?:getattr|hasattr)\(context, |:=|\bbpy\.context\.\w+|^\s+\w+ = context\.\w+", re.MULTILINE)
POLL_MODE = re.compile(r"\bcontext\.mode == 'EDIT_")
# Where Blender's stubs and its C API disagree about None: `Area.header_text_set(None)` clears the header text but the
# parameter is typed `str`, and `GPUVertFormat.attr_add` returns the attribute's id but is typed `-> None` (so the id
# passed to `attr_fill` is None). Fixed in the stubs by the Blender spec.
STUB_NONE_MISMATCH = re.compile(
    r"`(?:Area\.header_text_set|GPUVertBuf\.attr_fill)` is incorrect: Expected `[^`]*`, found `None`"
)
# Modules that import their submodules by name at runtime (`__import__(name=__name__, fromlist=_modules)`) and reload
# them when the module is reloaded.
DYNAMIC_IMPORT_MODULES = ("scripts/startup/bl_ui/__init__.py", "scripts/startup/bl_operators/__init__.py")
# Modules whose names come at runtime: put into `globals()` from a parsed C header, or given by the program that runs
# the script (`gdb` inside GDB).
RUNTIME_NAME_MODULES = ("doc/python_api/rst_from_bmesh_opdefines.py", "tools/utils/gdb_struct_repr_c99.py")
# A return annotation naming a private typeshed type (`hashlib._Hash`), which ty resolves to another private type.
TYPESHED_PRIVATE = re.compile(r"found `_[A-Z]\w*`$")
# Arguments ty checks against a third-party stub that is stricter than the library (`gdb.set_convenience_variable`
# takes None to clear a variable).
THIRD_PARTY_STUB = re.compile(r"`set_convenience_variable` is incorrect")
# A base class method called on `self` whose every override gives the parameter a default.
OVERRIDDEN_SIGNATURE_SITES = [
    ("build_files/linux/install_linux_packages.py", "PackageInstaller", "package_find", "package_name_version_gen("),
]
# RNA pointers Blender always sets that lack PROP_NEVER_NULL (S1): embedded structs (`Bone.color`, a tracking
# object's reconstruction, the XR viewfinder of a session), `wm.keyconfigs.active/user/default`, the active
# tracking object, `SpaceView3D.region_3d`, `AssetRepresentation.metadata`.
NEVER_NULL_TYPE = re.compile(
    r"`(?:XrViewfinderState|BoneColor|MovieTrackingObject|MovieTrackingReconstruction|RegionView3D) \| None"
)
# The ends of a node link and a depsgraph's instances and updates.
LINK_END = re.compile(r"\.(?:from|to)_(?:socket|node)\b|\.links\[")
DEPSGRAPH_MEMBER = re.compile(r"\b(?:dup|inst|instance|object_instance|update)\.(?:object|id)\b|depsgraph\.scene\b")
# Functions that return None only for arguments or states the caller rules out (`bpy.data.<collection>.new()` with
# a valid type, `animation_data_create()`, `load_image()` after an `isfile` check, `begin_result()`, `to_mesh()`).
NONE_ON_FAILURE = re.compile(
    r"\bbpy\.data\.\w+\.new\(|\b(?:uv_layers|asset_libraries)\.new\(|animation_data_create\(\)|\bload_image\("
    r"|\bbegin_result\(|\.to_mesh\(|\bid_properties_ui\("
)
# Calls that make a context member or a pointer exist for the lines after them.
ADDING_CALL = re.compile(r"\b(?:bpy\.)?ops\.\w+\.(?:\w+_)?add\(")
CREATING_CALL = re.compile(r"\bbpy\.ops\.\w+\.(?:open|new|\w+_add)\(")
SETTING_CALL = re.compile(r"\bbpy\.ops\.\w+\.\w+\(|animation_data_create\(\)|\bgenerate_rig\(|nodes\.active = ")
SET_BY_UI_BUTTON_TYPE = re.compile(r"`(?:KeyMap|KeyMapItem|FreestyleModuleSettings) \| None`")
CONTEXT_COLLECTION_TYPE = re.compile(r"`(?:Window|Screen|Collection|LayerCollection|Space|WorkSpace) \| None`")
# Python classes whose Optionals are plain Python typing (`ModuleSpec | None` from `spec_from_file_location`).
PYTHON_OPTIONAL_TYPE = re.compile(r"`(?:ModuleSpec|Loader|BVH_Node) \| None`")
MATHUTILS_TYPE = r"(?:Vector|Matrix|Euler|Color|Quaternion|Buffer)"
MATHUTILS_PROTOCOL = re.compile(
    rf"with key of type `slice\[[^`]*` and value of type `(?:{MATHUTILS_TYPE}|[^`]*` on object of type `"
    rf"(?:{MATHUTILS_TYPE}|bpy_prop_array))"
    rf"|`memoryview\.__new__` is incorrect: Expected `Buffer`, found `{MATHUTILS_TYPE}`"
    rf"|`GPUShader\.uniform_float`|attribute `dimensions` of type `list\[int"
    rf"|found `{MATHUTILS_TYPE}`$|`Vector\.__init__` is incorrect: Expected `Sequence\[float\]`, found `Generator"
    rf"|data descriptor attribute `\w+` on type `{MATHUTILS_TYPE}`"
)
# Stub parameters stricter than the C API (S2): the msgbus key of a class, a `bmesh.ops` sequence, `set[ID]`,
# `foreach_get`/`foreach_set` buffers, `Context.property`, `RenderPass.rect`, collection structs passed as
# `bpy_struct`, `BMLayerItem` keys, the names `libraries.load()` turns into IDs, `rna_type`, `ID.copy()`.
STUB_SIGNATURE = re.compile(
    r"`subscribe_rna` is incorrect|Expected `list\[BM(?:Vert|Edge|Face)[^`]*`, found `(?:BM\w+Seq|list)"
    r"|Expected `set\[ID\]`|`bpy_prop_collection\.foreach_(?:get|set)`|`AnyType & ~AlwaysFalsy` is not iterable"
    r"|attribute `rect` on type `RenderPass`|Expected `bpy_struct`, found `(?:LayerObjects|KeyingSets\w*)`"
    r"|with key of type `BMLayerItem`|attribute `uv` on type `float`|has no attribute `rna_type`"
)
REGISTERED_CLASS = re.compile(r"Module `bpy\.types` has no member `\w+_(?:OT|MT|PT)_\w+`|^Class `\w+_(?:MT|OT|PT)_\w+`")
# Plain Python typing: a record kept in a list or dict, a builtin or stdlib call, a deliberate monkeypatch, an
# attribute set at runtime, a `hasattr` narrowing, a class-body helper call, an override of a Python method.
GENERAL_TYPING = re.compile(
    r"`NodeSocket \| int`|found `bool \| list|No overload of function `join`|`Literal\[[^`]*\] \| list\[str\]`"
    r"|Argument to (?:function `(?:len|pack|module_from_spec)`|bound method `list\.\w+`|constructor `zip\.__new__`"
    r"|`list\.__init__`)|has no attribute `(?:__name__|readline|matches|_\w+)`|^Unresolved attribute `\w+` on type `\w+`"
    r"|on type `ModuleType`|between objects of type `Literal\[[^`]*\]` and `object`|found `object`"
    r"|<Protocol with|on `type` in union|Expected `bool`, found `Literal\[1\]`|is not assignable to `dict\["
    r"|Expected `Literal\[[^`]*\]( \| [^`]*)?`, found `(?:Unknown \| )?str`|Invalid subscript assignment with key of type `(?:Unknown|int|Literal\[\"\w+\"\])`"
    r"|`EllipsisType|`type\.__new__`|`\w+\.__init__` is incorrect: Expected `Sequence\[\(\) ->|`\(\) -> None` has no"
    r"|`int \| NodeSocket|between objects of type `(?:NodeSocket|Literal\[\"#\"\])`|^Invalid subscript assignment"
    r"|cannot be called with key of type `(?:list\[str\]|NodeSocket|None` on object of type `bpy_prop_collection(?:\[\w+\])?)`"
    r"|found `_version_info`|\) \| list\[str\]"
    r"|& ~AlwaysTruthy\)|^Object of type `def |^Object of type `None` is not assignable to `\(|object of type `None`$"
    r"|`float\*`|No overload of function `dirname`|on type `<module '|Argument to function `(?P<cls>\w+)\.\w+` is "
    r"incorrect: Expected `(?P=cls)`"
)
MONKEYPATCH = re.compile(r"^\s*(?:_bpy|pydoc(?:\.Helper)?)\.\w+ = ")


# --- fake-bpy-module's stub shapes (docs/reports/fake-bpy-module-leftovers.md) ----------------------------------

# fake-bpy-module types `Object.data` as the union of every object data type and None. ty prints it cut short;
# it is the `ID | None` of Blender's own stubs (`ID` once a check removed None or some types), so the same causes
# apply.
OBJECT_DATA_UNION = re.compile(
    r"`Armature \| (Camera \| Curve \| \.\.\. omitted 11|[^`]*\.\.\. omitted \d+) union elements`"
)
# fake-bpy-module writes stubs for Blender's own Python modules by inspecting them at runtime, and those come before the
# source on the search path. They lose module constants, dataclass and instance attributes, `__init__`, base
# classes (an exception class, a protocol), return annotations (`-> None`) and the context managers of functions
# and classes.
FAKE_BPY_PYTHON_MODULE = re.compile(
    r"`object\.__init__`"
    r"|^Module `(?:_bpy_internal|addon_utils|bl_ui|rna_prop_ui)\b[\w.]*`"
    r" has no member"
    r"|^Object of type `(?:I18n|AssetV1|FileV1|CatalogV1|AssetLibraryMeta|AssetLibraryIndexPageV1|FileHashInfo"
    r"|BlendFileHeader|URLWithHash)\b[^`]*` has no attribute"
    r"|^Object of type `(?:None|RestrictBlend|ProgressReport)` cannot be used with `with`"
    r"|`<class 'BlendHeaderError'>`|found `ExtraFileMetadataProvider`|found `def asset_listing_main\("
    r"|^Object of type `None` is not assignable to (?:`str \| URLWithHash`|attribute `enabled`)"
    r"|between objects of type `Path` and `None`"
    r"|function `ToolDef\.from_fn`"
)
# The values those lossy stubs return feed a builtin call or a nullable read: (path, enclosing class or "",
# enclosing function or "", text on the line).
FAKE_BPY_PYTHON_MODULE_SITES = [
    ("scripts/addons_core/ui_translate/update_addon.py", "", "", "dict(utils_i18n.get_po_files_from_dir("),
    ("scripts/addons_core/ui_translate/update_repo.py", "", "", "subprocess.run(cmmd"),
    ("scripts/addons_core/ui_translate/update_repo.py", "", "", "languages_menu_lines"),
    ("scripts/modules/_bpy_internal/assets/remote_library/listing_downloader.py", "", "", "path_to_load."),
    ("scripts/modules/_bpy_internal/assets/remote_library/listing_downloader.py", "", "", "urljoin"),
    ("scripts/modules/bl_app_template_utils.py", "", "", "app_template_paths("),
    ("scripts/startup/bl_operators/wm.py", "", "", "path_split"),
    ("doc/python_api/sphinx_doc_gen.py", "", "rna_info_BuildRNAInfo_cache", "return ret"),
]
# A value those lossy stubs type `None` (a function's lost return annotation), passed on or returned: `None` is not
# written on the line. Blender's own stubs resolve these functions to their source.
FAKE_BPY_NONE_VALUE = re.compile(
    r"(?:is incorrect: Expected|does not match returned value: expected) `[^`]*`, found `None`$"
)


def fake_bpy_none_value(d: Diagnostic) -> bool:
    return (
        d.rule in {"invalid-argument-type", *RETURN_RULES}
        and FAKE_BPY_NONE_VALUE.search(d.msg) is not None
        and re.search(r"\bNone\b", d.text) is None
        and STUB_NONE_MISMATCH.search(d.msg) is None
    )


# fake-bpy-module's `_bpy_types` stub declares its own `Context`, `Menu`, ... beside `bpy.types`, and `bpy.types`
# declares the registered Python classes as instances (`X_OT_y: module.X_OT_y`), not as the classes.
FAKE_BPY_TYPE_ALIAS = re.compile(
    r"\b_bpy_types\.Context\b|Expected `type\[Panel \| UIList \| Menu \| \.\.\. omitted \d+ types\]`"
    r"|^Object of type `<class 'UI_UL_list'>[^`]*` has no attribute `is_registered`"
    r"|^Too many positional arguments to bound method `\w+_OT_\w+\.\w+`"
)
# fake-bpy-module types as Optional what RNA never leaves None: `bl_rna`, `RenderViews.active`, and an int property
# (`active_*_index`, read as a collection key or updated in place). Its collections take a key `int | str |
# tuple[str, ...]` (Blender's own stubs: `int`).
FAKE_BPY_NULLABLE = re.compile(r"in union `Struct \| None`|`SceneRenderView \| None`")
FAKE_BPY_NONE_INDEX = re.compile(
    r"\(key: int \| str(?: \| tuple\[str, \.\.\.\])?\) -> \w+, .* cannot be called with key of type `None`"
    r"|between objects of type `None` and `Literal\[1\]`"
)
DYNAMIC_ENUM_PLACEHOLDER = re.compile(r"""Literal\[(['"])(?:DEFAULT|PLACEHOLDER)\1\]`""")
# The per-node socket collections of fake-bpy-module, whose `__getitem__` takes the socket names as literals.
FAKE_BPY_NODE_SOCKETS_KEY = re.compile(
    r"Method `__getitem__` of type `(?:Overload\[\(key: Literal\[0, |bound method _\w+_Node(?:In|Out)puts\.)"
)
# The library key `(name, None)` of a local data-block, which fake-bpy-module's `tuple[str, ...]` rejects.
FAKE_BPY_LIB_KEY = re.compile(r"tuple\[str, \.\.\.\]\) -> .* cannot be called with key of type `tuple\[[^`]*, None\]`")
# fake-bpy-module's C types lack their Python protocols: a `Vector` or `bpy_prop_array` is no `Sequence[float]`,
# `MatrixAccess` has no `__getitem__`, `Vector` no ordering, `Quaternion` no `__neg__`, and the context managers
# of `gpu`, `blf` and `imbuf` (`gpu.matrix.push_pop()`, `GPUOffScreen.bind()`) no `__enter__` / `__exit__`.
FAKE_BPY_PROTOCOL = re.compile(
    r"Expected `Sequence\[float\](?: \| None)?`, found `(?:(?:Any|Unknown) \| Vector|Vector \| Unknown"
    r"|bpy_prop_array\[float\])`"
    r"|found `(?:dict\[str, [^`]*|list\[)list\[Vector\]|`MatrixAccess`|between two objects of type `Vector`"
    r"|^Unary operator `-` is not supported for object of type `Quaternion"
    r"|^Object of type `(?:BLFImBufContext|ImBufBuffer|OffScreenStackContext|MatrixStackContext)` cannot be used"
    r" with `with`"
)


def reload_idiom(d: Diagnostic) -> bool:
    """A name bound only when the module is reloaded: ``importlib.reload(x)``, a ``"x" in locals()`` guard before
    it, or a module that imports its submodules by name at runtime."""
    if d.rule != "unresolved-reference":
        return False
    name = next(iter(re.findall(r"^Name `(\w+)`", d.msg)), "")
    return (
        "reload(" in d.text
        or re.search(rf"[\"']{re.escape(name)}[\"'] in locals\(\)", d.scope.source) is not None
        or d.path.replace("\\", "/") in DYNAMIC_IMPORT_MODULES
    )


def missing_attribute(msg: str) -> str | None:
    match = MISSING_ATTRIBUTE.search(msg)
    return next((g for g in match.groups() if g), None) if match else None


# A type in a union that is no Blender type: a builtin or other lowercase type, a literal, an intersection, or one
# ty could not infer.
PYTHON_TYPE = re.compile(r"(?:[a-z_][\w.]*(?:\[.*\])?|Unknown|Any|Divergent|LiteralString|Literal\[.*\]|\(.*\))$")


# A Blender type as ty prints it: a capitalised class name, without type arguments.
BLENDER_TYPE = re.compile(r"[A-Z][A-Za-z0-9]*$")


# The types a message names, not its attribute, method, function or parameter names.
TYPE_IN_MESSAGE = re.compile(r"(?:type|found|Expected|union|and) `([^`]*)`")
PYTHON_CLASSES = {"None", "EllipsisType", "ModuleType", "~None"}
PYTHON_USE_RULES = {
    "not-subscriptable",
    "not-iterable",
    "not-callable",
    "unsupported-operator",
    *MISSING_ATTRIBUTE_RULES,
}


def union_members(type_: str) -> list[str]:
    """The members of a union type as ty prints it, split at the top level."""
    depth, current, members = 0, "", []
    for char in type_:
        depth += char in "(["
        depth -= char in ")]"
        current += char
        if depth == 0 and current.endswith(" | "):
            members.append(current[:-3])
            current = ""
    return [*members, current]


def base_class_target(type_: str) -> bool:
    """Whether ``type_`` (as ty prints it, in backticks) is a base class, alone or in a union with ``Unknown``
    (``(Node & ~AlwaysFalsy) | (Unknown & ~AlwaysFalsy)``)."""
    if BASE_CLASS.search(type_):
        return True
    members = [m for m in union_members(type_.strip("`")) if not re.match(r"\(?Unknown\b", m)]
    return bool(members) and all(BASE_CLASS.fullmatch(f"`{m}`") for m in members)


def python_optional(d: Diagnostic) -> bool:
    """Whether the nullable types in the message hold no Blender type: a plain Python ``Optional``."""
    unions = [t for t in re.findall(r"`([^`]*)`", d.msg) if "None" in union_members(t)]
    members = [m for t in unions for m in union_members(t) if m != "None"]
    return bool(members) and all(PYTHON_TYPE.match(m) and not m.startswith("bpy_") for m in members)


def unchecked_pointer_bug(d: Diagnostic) -> bool:
    """A nullable read at one of UNCHECKED_POINTER_BUGS; not ``obj.data`` read as a whole ``ID | None`` (fake-bpy-module's
    ``Object.data`` union), which is ``object-data-untagged`` wherever it is."""
    path = d.path.replace("\\", "/")
    if re.search(r"`ID \| None`", d.msg) and ".data" in d.text:
        return False
    return nullable(d) and any(
        path == p and (not c or d.scope.cls == c) and (not f or d.scope.function == f) and t in d.text
        for p, c, f, t in UNCHECKED_POINTER_BUGS
    )


def python_types_only(d: Diagnostic) -> bool:
    """Whether a value is used in a way its type does not allow (subscript, iteration, call, operator, attribute)
    and every type the message names is a Python one (``None``, ``EllipsisType``, a builtin): plain Python typing
    debt, such as an instance attribute initialised to ``None`` or a ``...`` default. A mismatch of an argument or
    return type is left out: it can be a wrong annotation (BF2)."""
    if d.rule not in PYTHON_USE_RULES or NUMPY.search(d.msg):
        return False
    members = [m.removesuffix(" & ~AlwaysFalsy") for t in TYPE_IN_MESSAGE.findall(d.msg) for m in union_members(t)]
    return bool(members) and all(
        m in PYTHON_CLASSES or (PYTHON_TYPE.match(m) and not m.startswith(("bpy_", "Literal["))) for m in members
    )


def correlated_union(d: Diagnostic) -> bool:
    """Whether the message names a union of Blender types, without ``None``, that the code tells apart by a mode, a
    flag or a type field ty does not follow (``PoseBone | EditBone | Object`` picked by ``is_ebone``)."""
    if d.rule not in {*MISSING_ATTRIBUTE_RULES, "invalid-assignment", "invalid-argument-type"}:
        return False
    # ty names the members that lack an attribute when there are many: "not defined on `AddStrip`, `ColorStrip`".
    if re.search(r"is not defined on `\w+`, `\w+`", d.msg):
        return True
    pattern = (
        r"(?:on type|in union|Object of type|found) `([^`]*)`"
        if d.rule != "invalid-argument-type"
        else r"found `([^`]*)`$"
    )
    for type_ in re.findall(pattern, d.msg):
        # ty prints a member narrowed by a truthiness check as `(Node & ~AlwaysFalsy)`.
        members = [re.sub(r"^\((.*) & ~AlwaysFalsy\)$", r"\1", m) for m in union_members(type_)]
        members = [m for m in members if m != "Unknown"]
        if len(members) > 1 and all(
            BLENDER_TYPE.match(m) and m != "None" and not PYTHON_TYPE.match(m) for m in members
        ):
            return True
    return False


def untyped_python(d: Diagnostic) -> bool:
    return (
        d.path.replace("\\", "/").startswith(UNTYPED_PACKAGES)
        or NUMPY.search(d.msg) is not None
        or "`I18nSettings`" in d.msg
    )


def in_scripts(d: Diagnostic) -> bool:
    """Whether the diagnostic is in a doc example or a text-editor template."""
    return d.area in {"examples", "templates"}


def in_presets(d: Diagnostic) -> bool:
    return d.path.replace("\\", "/").startswith("scripts/presets/")


def in_tests(d: Diagnostic) -> bool:
    return d.path.replace("\\", "/").startswith("tests/")


NONE_KEY = "with key of type `None`"


def nullable(d: Diagnostic) -> bool:
    return NULLABLE.search(d.msg) is not None


def root(scope: Scope) -> str:
    """The Blender base of the enclosing class (``panel``, ``menu``, ``header``, ``operator``, ``gizmogroup``,
    ``uilist``), from its idname-style name or its bases as written; ``""`` when neither says."""
    for marker, name in (
        ("_PT_", "panel"),
        ("_MT_", "menu"),
        ("_HT_", "header"),
        ("_OT_", "operator"),
        ("_GGT_", "gizmogroup"),
        ("_UL_", "uilist"),
    ):
        if marker in scope.cls:
            return name
    for base in re.findall(r"\w+", scope.bases):
        if base.lower() in {"panel", "menu", "header", "operator", "gizmogroup", "uilist"}:
            return base.lower()
    return ""


def names_parameter(d: Diagnostic, positions: Iterable[int]) -> bool:
    params = d.scope.params
    return any(i < len(params) and re.search(rf"\b{re.escape(params[i])}\b", d.text) for i in positions)


def callback_never_none(d: Diagnostic) -> bool:
    if "AssetShelf.asset_poll" in d.msg or "AssetShelf.draw_context_menu" in d.msg:
        return True
    positions = NEVER_NONE_PARAMETERS.get(d.scope.function)
    if not positions or not nullable(d) or not CALLBACK_PARAMETER_TYPE.search(d.msg):
        return False
    if d.scope.function == "draw_item":
        return names_parameter(d, positions) and not names_parameter(d, [4])
    return True


def registered_property(d: Diagnostic) -> bool:
    if in_addon(d):
        return False
    if re.search(r"Unresolved attribute `\w+` on type `<class", d.msg):
        return True
    if re.match(r"\s*del\b", d.text) and d.msg.startswith("Class"):
        return True
    if d.rule == "invalid-assignment" and d.msg.startswith("Object of type `_PropertyDeferred` is not assignable"):
        return True
    return missing_attribute(d.msg) in d.scope.registers


def in_addon(d: Diagnostic) -> bool:
    path = d.path.replace("\\", "/")
    return path.startswith(("scripts/addons_core/", "intern/cycles/blender/addon/"))


def ui_draw_pointer(d: Diagnostic) -> bool:
    """A nullable read in the draw callback of a Panel, Menu, Header or UIList: Blender draws it only where its
    pointers exist (its poll, its editor or mode, or the panel's own logic), which ty does not follow (research
    ``blender-true-problems``, "Ruled out": the UI's draw code is guarded by construction)."""
    return nullable(d) and (
        (
            root(d.scope) in UI_ROOTS
            and (d.scope.function in UI_DRAW_CALLBACKS or d.scope.function.startswith("draw_ui"))
        )
        or d.scope.function == "parameters_ui"
    )


def layout_in(roots: set[str]) -> Callable[[Diagnostic], bool]:
    """``self.layout`` read as ``UILayout | None`` in a helper of a class with a root of ``roots``. An operator helper
    may also be a function taking the operator as ``self``, or a method of a mixin (a class with no bases): ty types
    a mixin's ``self.layout`` only when the mixin has users, and as ``UILayout | None`` only when one of them is not
    drawn, such as an Operator."""
    return lambda d: (
        "UILayout | None" in d.msg
        and (
            root(d.scope) in roots
            or ("operator" in roots and not d.scope.cls and d.scope.params[:1] == ("self",))
            or ("operator" in roots and is_mixin(d.scope))
        )
    )


def is_mixin(scope: Scope) -> bool:
    """Whether the enclosing class is a mixin: a class with no bases, whose idname-style name names no Blender
    base."""
    return bool(scope.cls) and not scope.bases and not root(scope)


# A mixin's `super()` (`super().report(...)` in a mixin that redeclares an Operator method for its users), and a set
# literal checked against a mixin method intersected with its users' Blender method: ty types `self` there as the
# mixin and its users' Blender classes, but cannot follow `super()` through that, nor infer the literal's items.
MIXIN_INTERSECTION = re.compile(
    r"Object of type `<super: <class '(\w+)'>, (?:<class ')?\1'?>?>`|a name in the set is not an enum item"
)


def mixin_self(d: Diagnostic) -> bool:
    return "Self@" in d.msg or (is_mixin(d.scope) and MIXIN_INTERSECTION.search(d.msg) is not None)


# An operator idname built at runtime (`"{:s}.hide".format(self._operator_name)`): ty cannot tell the operator, so
# `layout.operator()` keeps the stubs' `OperatorProperties | None`.
RUNTIME_OPERATOR_IDNAME = re.compile(r"""\.operator\((?:f["']|(?:"[^"]*"|'[^']*')\.format\()""")


def rule(*names: str) -> Callable[[Diagnostic], bool]:
    return lambda d: d.rule in names


def any_of(*predicates: Callable[[Diagnostic], bool]) -> Callable[[Diagnostic], bool]:
    return lambda d: any(p(d) for p in predicates)


def outside_tests(predicate: Callable[[Diagnostic], bool]) -> Callable[[Diagnostic], bool]:
    return lambda d: not in_tests(d) and predicate(d)


def read_names(d: Diagnostic) -> set[str]:
    """The names the diagnostic is about: the root of the expression whose attribute is missing or assigned
    (``tree`` in ``tree.nodes.new()``), else every name the line reads."""
    attribute = missing_attribute(d.msg) or next(iter(re.findall(r"to attribute `(\w+)`", d.msg)), None)
    if attribute:
        roots = set(re.findall(rf"(?<![.\w])([A-Za-z_]\w*)(?:[\w.]|\[[^\]]*\])*\.{attribute}\b", d.text))
        if roots:
            return roots
    read = re.sub(r"^\s*[\w, ]+=(?!=)", "", d.text)  # the names a plain assignment binds are not read
    return set(re.findall(r"(?<![.\w])([A-Za-z_]\w*)\b", read))


def assignments(d: Diagnostic, name: str) -> list[str]:
    """The right-hand sides of the assignments to ``name`` before the diagnostic's line, last first."""
    pattern = re.compile(rf"\s*(?:[\w\[\]]+\s*,\s*)*{name}\s*(?:,\s*\w+\s*)*(?::[^=]*)?=(?!=)\s*(.*)")
    return [m[1] for line in reversed(d.scope.source.splitlines()[:-1]) if (m := pattern.match(line))]


def reads_from(d: Diagnostic, pattern: re.Pattern[str] | str, hops: int = 1) -> bool:
    """Whether the diagnostic's line, or the last assignment in its function of a name it is about, matches
    ``pattern`` (``tree = bpy.data.node_groups.new(...)`` for ``tree.nodes``). With ``hops`` above 1 it follows
    that many assignments of a plain name (``last = obj_act``, then ``obj_act = context.active_object``)."""
    if re.search(pattern, d.text):
        return True
    names = read_names(d)
    for _ in range(hops):
        sources = [rhs[0].strip() for name in names if (rhs := assignments(d, name))]
        if any(re.search(pattern, rhs) for rhs in sources):
            return True
        names = {rhs for rhs in sources if re.fullmatch(r"[A-Za-z_]\w*", rhs)}
    return False


def initialised_to_none(d: Diagnostic) -> bool:
    """Whether a name the diagnostic is about is a local first set to ``None`` (``strip1 = None``)."""
    return any(any(re.fullmatch(r"None\s*(?:#.*)?", rhs) for rhs in assignments(d, name)) for name in read_names(d))


def in_sites(sites: list[tuple[str, str, str, str]]) -> Callable[[Diagnostic], bool]:
    """A diagnostic in one of ``sites``: (path, enclosing class or "", enclosing function or "", text on the
    line or "")."""
    return lambda d: any(
        d.path.replace("\\", "/") == p and (not c or d.scope.cls == c) and (not f or d.scope.function == f)
        and t in d.text
        for p, c, f, t in sites
    )  # fmt: skip


def poll_checks_elsewhere(d: Diagnostic) -> bool:
    """A nullable read in a callback of a class whose poll checks it through a helper, a base poll or a wrapper."""
    return (
        (nullable(d) or "with key of type `None`" in d.msg)
        and GENERAL_TYPING.search(d.msg) is None
        and d.scope.function in {"execute", "invoke", "poll"}
        and (POLL_HELPER.search(d.scope.poll) is not None or POLL_HELPER_BASES.search(d.scope.bases) is not None)
    )


def poll_checks_alias(d: Diagnostic) -> bool:
    """A nullable read of a context member the class's poll checks through another expression: ``getattr(context,
    "member", None)``, ``(ob := context.member)``, ``bpy.context.member``, or a local alias (``obj = context.object``, tested in the poll)."""
    if not nullable(d) or d.scope.function not in {"execute", "invoke", "poll"}:
        return False
    members = re.findall(
        r"(?:getattr|hasattr)\(context, [\"'](\w+)|:= (?:bpy\.)?context\.(\w+)|\bbpy\.context\.(\w+)", d.scope.poll
    )
    if d.scope.function == "poll":
        members += re.findall(r"^\s+\w+ = ()context\.(\w+)()", d.scope.poll, re.MULTILINE)
    else:
        # `obj = context.object` then `return obj and ...`: the poll tests the member through its alias. Only a
        # read of the member itself counts (not `context.space_data.edit_tree` after a test of `space_data`).
        tested = {
            member
            for alias, member in re.findall(r"^\s+(\w+) = context\.(\w+)\s*$", d.scope.poll, re.MULTILINE)
            if re.search(rf"\breturn \(?{alias} and\b|\b{alias} is not None\b", d.scope.poll)
        }
        if tested & {"object", "active_object"}:
            tested |= {"object", "active_object"}
        if any(reads_from(d, rf"\bcontext\.{m}\b(?![.\w])", hops=2) for m in tested):
            return True
    names = {m for groups in members for m in groups if m}
    if names & {"object", "active_object"}:
        names |= {"object", "active_object"}
    return any(reads_from(d, rf"\bcontext\.{m}\b") for m in names) or poll_tests_same_path(d)


def poll_tests_same_path(d: Diagnostic) -> bool:
    """``layer = obj.data.layers.active`` read in a callback whose poll tests ``obj.data.layers.active is not
    None``, where ``obj`` is the same context member in both (``(obj := context.active_object)`` in the poll)."""
    for name in read_names(d):
        rhs = next(iter(assignments(d, name)), "").strip()
        if not re.fullmatch(r"\w+(?:\.\w+)+", rhs) or f"{rhs} is not None" not in d.scope.poll:
            continue
        root = rhs.partition(".")[0]
        for member in re.findall(rf"\b{root} = context\.(\w+)\s*$", d.scope.source, re.MULTILINE):
            if re.search(rf"\b{root} :?= context\.{member}\b", d.scope.poll):
                return True
    return False


def parent_panel(d: Diagnostic) -> bool:
    return nullable(d) and d.scope.function == "poll" and "bl_parent_id" in d.scope.attributes


def bl_context_member(d: Diagnostic) -> bool:
    """The active object a top-level Properties tab (``object``, ``physics``) or a mode's tool panels need: the
    ``bl_context`` Implied narrowing where its rule did not accept the read, such as a display-only context
    (``.grease_pencil_paint``), which the tool header also draws as a popover."""
    if "Object | None" not in d.msg or d.scope.function != "poll":
        return False
    if re.search(r"bl_context = [\"']\.", d.scope.attributes):
        return True
    return re.search(r"bl_context = [\"'](?:object|physics)[\"']", d.scope.attributes) is not None and (
        "bl_parent_id" not in d.scope.attributes
    )


def internal_operator(d: Diagnostic) -> bool:
    """An INTERNAL operator (no menu or search entry) reads what the one button or XR action that calls it
    guarantees."""
    if not nullable(d):
        return False
    if "'INTERNAL'" in d.scope.attributes and root(d.scope) == "operator":
        return not d.scope.has_poll or OTHER_CONTEXT_TYPE.search(d.msg) is not None
    return (
        d.path.replace("\\", "/").startswith("scripts/addons_core/viewport_vr_preview/")
        and re.search(r"`(?:Window|XrSessionState|XrEventData) \| None`", d.msg) is not None
    )


def ui_callback_editor_member(d: Diagnostic) -> bool:
    """The region or space read by code that runs inside its editor: the poll of a panel, menu or asset shelf, a
    tool's draw settings, a keymap UI helper, a viewport render engine's ``view_update`` / ``view_draw``."""
    if re.search(r"`(?:Region|Space) \| None`", d.msg) is None:
        return False
    path = d.path.replace("\\", "/")
    return (
        re.search(r"/(?:space_toolsystem_\w+|rna_keymap_ui)\.py$", path) is not None
        or d.scope.function in {"view_update", "view_draw"}
        or (d.scope.function == "poll" and root(d.scope) != "operator" and "KeyingSetInfo" not in d.scope.bases)
    )


def editor_member_outside_execute(d: Diagnostic) -> bool:
    """The editor's members read by an operator's helpers, draw or poll (or a keying set's poll), a draw handler,
    or an exporter's file browser panel: run in their editor."""
    if OTHER_CONTEXT_TYPE.search(d.msg) is None:
        return False
    function = d.scope.function
    if function == "poll" and POLL_HELPER.search(d.scope.poll):
        return False
    return (
        (root(d.scope) == "operator" and function != "execute")
        or (function == "poll" and "KeyingSetInfo" in d.scope.bases)
        or (not d.scope.cls and function.startswith(("draw_", "export_panel_")))
    )


def rna_never_none(d: Diagnostic) -> bool:
    if not nullable(d):
        return False
    return (
        NEVER_NULL_TYPE.search(d.msg) is not None
        or ("`KeyConfig | None`" in d.msg and not reads_from(d, r"\.addon\b"))
        or ("`AssetMetaData | None`" in d.msg and reads_from(d, r"\.metadata\b"))
        or (re.search(r"`(?:Node|NodeSocket|NodeTree) \| None", d.msg) is not None and reads_from(d, LINK_END))
        or (re.search(r"`(?:Object|Scene|ID) \| None`", d.msg) is not None and reads_from(d, DEPSGRAPH_MEMBER))
    )


def set_by_preceding_call(d: Diagnostic) -> bool:
    """A pointer a call earlier in the function made exist (``bpy.ops.object.*_add()``, ``bpy.ops.image.open()``,
    ``animation_data_create()``), or an attribute the callback that always runs first sets (``self._timer`` set
    by ``execute`` and read by ``modal``)."""
    if not nullable(d):
        return False
    if d.scope.function in {"modal", "cancel", "__exit__"} and re.search(r"\bself\.\w+", d.text):
        return True
    earlier = d.scope.source.splitlines()[:-1]
    calls = [i for i, line in enumerate(earlier) if SETTING_CALL.search(line)]
    if not calls:
        return False
    if re.search(r"\bcontext\.\w+", d.text):
        # Counted from the end of a call that creates what the context then points at (`bpy.ops.image.open(...)`
        # over several lines), else from the line the call starts on.
        last = calls[-1]
        if CREATING_CALL.search(earlier[last]):
            last = call_end(earlier, last)
        if len(earlier) - last <= 4:
            return True
    # `if not scene.animation_data: scene.animation_data_create()`, then `scene.animation_data.action`.
    source = "\n".join(earlier)
    if any(
        re.search(rf"\b{name}\.animation_data\b", d.text)
        and re.search(rf"if not {name}\.animation_data:\s*{name}\.animation_data_create\(\)", source)
        for name in read_names(d)
    ):
        return True
    pointer = re.compile(r"\bcontext\.\w+|nodes\.active\b|\bget_rigify_target_rig\(")
    for name in read_names(d):
        for i in range(len(earlier) - 1, calls[0], -1):
            if match := re.match(rf"\s*{name}\s*=(?!=)\s*(.*)", earlier[i]):
                if pointer.search(match[1]) and any(c < i for c in calls):
                    return True
                break
    return False


def added_object(d: Diagnostic) -> bool:
    """``context.object`` / ``active_object`` (or a name set from it) read after a ``bpy.ops.<category>.add()`` or
    ``*_add()`` call earlier in the function, which makes the object it adds active."""
    return (
        "`Object | None`" in d.msg
        and reads_from(d, CONTEXT + r"(?:object|active_object)\b")
        and ADDING_CALL.search("\n".join(d.scope.source.splitlines()[:-1])) is not None
    )


def call_end(lines: list[str], start: int) -> int:
    """The index of the line that closes the call opened on ``lines[start]`` (the call can span several lines)."""
    depth = 0
    for i in range(start, len(lines)):
        depth += lines[i].count("(") - lines[i].count(")")
        if depth <= 0:
            return i
    return start


def rarely_none_member(d: Diagnostic) -> bool:
    """A member None only in states the code cannot run in: the active view layer's depsgraph, the add-on key
    configuration, a property callback's context, the camera during a Freestyle render, an asset's data."""
    if not nullable(d):
        return False
    path = d.path.replace("\\", "/")
    return (
        "`Depsgraph | None`" in d.msg
        or "`Context | None`" in d.msg
        or ("`KeyConfig | None`" in d.msg and reads_from(d, r"\.addon\b"))
        or ("`AssetMetaData | None`" in d.msg and ".asset_data." in d.text)
        or (path.startswith("scripts/freestyle/") and ".camera." in d.text)
        or (not d.scope.cls and d.scope.function.startswith("poll_"))
    )


def window_context(d: Diagnostic) -> bool:
    """The window, screen, space, workspace or collection an operator's ``execute`` (or the importer and exporter
    code it calls, or a script run in a window) reads: present whenever it runs."""
    return CONTEXT_COLLECTION_TYPE.search(d.msg) is not None and (
        d.scope.function == "execute"
        or re.search(r"\bcontext\.(?:window|screen|collection|layer_collection)\b", d.text) is not None
        or d.path.replace("\\", "/").startswith("scripts/modules/_bl_previews_utils/")
    )


# --- the table, first match wins -------------------------------------------------------------------------------

CAUSES = [
    # The Imprecise annotations (S4), Implied narrowings (S5, and C6 of spec #123) and Assumptions (S6, and C5 / C7 of
    # spec #123): the code their dedicated rule accepts and reports, tagged with the slice that added the rule. An
    # error of the same shape is code the rule did not accept, and has another cause.
    *(Cause(name, group, slice_, rule(f"blender-{name}"), f"blender-{name}") for group, slice_, names in (
        ("imprecise-annotation", "S4",
         ("imprecise-operator-return", "imprecise-enum-value", "imprecise-callback-parameter")),
        ("implied-narrowing", "S5", ("narrowed-by-menu-prefix", "narrowed-by-popover", "narrowed-by-poll")),
        ("assumption", "S6", ("assumed-registration", "assumed-complete-registration", "assumed-preferences",
                              "assumed-list-item", "assumed-context-member")),
        ("assumption", "C5", ("assumed-internal-operator", "assumed-editor-member", "assumed-preset-context",
                              "assumed-added-object")),
        ("implied-narrowing", "C6", ("narrowed-by-bl-context",)),
        ("assumption", "C7", ("assumed-subclass-member",)),
    ) for name in names if name != "assumed-preferences"),
    # An add-on's `register()` reads its own preferences, which exist once the add-on is enabled.
    Cause("assumed-preferences", "assumption", "S6", any_of(rule("blender-assumed-preferences"), lambda d: (
        "`AddonPreferences | None`" in d.msg and d.scope.function == "register")), "blender-assumed-preferences"),
    # Stub shapes of fake-bpy-module that Blender's own stubs do not have: a fix in fake-bpy-module.
    Cause("fake-bpy-python-module", "typechecker-fix", "", lambda d: not untyped_python(d) and not in_tests(d)
          and re.search(r"libraries\.load|temp_data", d.text) is None
          and (FAKE_BPY_PYTHON_MODULE.search(d.msg) is not None or in_sites(FAKE_BPY_PYTHON_MODULE_SITES)(d)
               or fake_bpy_none_value(d))),
    Cause("fake-bpy-type-alias", "typechecker-fix", "", lambda d: FAKE_BPY_TYPE_ALIAS.search(d.msg) is not None),
    Cause("fake-bpy-nullable", "typechecker-fix", "", lambda d: FAKE_BPY_NULLABLE.search(d.msg) is not None
          or (FAKE_BPY_NONE_INDEX.search(d.msg) is not None and reads_from(d, r"\.active_\w+"))),
    Cause("fake-bpy-lib-key", "typechecker-fix", "", lambda d: FAKE_BPY_LIB_KEY.search(d.msg) is not None),
    # fake-bpy-module types a node class's own sockets `_<Node>_NodeInputs | None`, indexed by the socket names
    # only, which a node typed by its constructor (`nodes.new('ShaderNodeBsdfPrincipled')`) or a Type tag test
    # exposes at `node.inputs["Color"]` (and at an identifier such as `"Fac"`).
    Cause("fake-bpy-node-sockets", "typechecker-fix", "", lambda d: re.search(r"\.(?:inputs|outputs)\[", d.text)
          is not None and ((d.rule == "not-subscriptable" and "`None`" in d.msg)
                           or FAKE_BPY_NODE_SOCKETS_KEY.search(d.msg) is not None)),
    Cause("fake-bpy-protocol", "typechecker-fix", "", lambda d: FAKE_BPY_PROTOCOL.search(d.msg) is not None),
    # Blender's own code is wrong (BF1 runtime, BF2 annotations).
    Cause("property-on-panel", "blender-fix", "BF1", rule("blender-unsupported-property-host")),
    Cause("dead-api", "blender-fix", "BF1", outside_tests(lambda d: DEAD_API.search(d.msg) is not None)),
    Cause("reload-idiom", "typing-debt", "", reload_idiom),
    Cause("runtime-name", "typing-debt", "", lambda d: d.rule == "unresolved-reference"
          and d.path.replace("\\", "/") in RUNTIME_NAME_MODULES),
    Cause("undefined-name", "blender-fix", "BF1", outside_tests(rule("unresolved-reference"))),
    Cause("missing-argument", "blender-fix", "BF1", outside_tests(lambda d: d.rule == "missing-argument"
          and not in_sites(OVERRIDDEN_SIGNATURE_SITES)(d))),
    Cause("rigify-get-bone", "blender-fix", "BF2", lambda d: d.path.replace("\\", "/").startswith(RIGIFY)
          and re.search(r"EditBone \| PoseBone|PoseBone \| EditBone", d.msg) is not None),
    Cause("correlated-union", "typing-debt", "", correlated_union),
    Cause("tooldef", "blender-fix", "BF2", lambda d: "ToolDef" in d.msg),
    Cause("stub-none-mismatch", "typechecker-fix", "", lambda d: STUB_NONE_MISMATCH.search(d.msg) is not None),
    # Untyped packages (rigify, glTF, Freestyle) keep their typing as it is: `untyped-python` below.
    Cause("none-for-non-optional", "blender-fix", "BF2", lambda d: not in_tests(d) and not untyped_python(d)
          and THIRD_PARTY_STUB.search(d.msg) is None and any_of(
        rule("invalid-parameter-default"),
        lambda d: d.rule == "invalid-argument-type" and d.msg.endswith("found `None`"))(d)),
    Cause("wrong-annotation", "blender-fix", "BF2", outside_tests(any_of(
        lambda d: d.rule == "invalid-type-form" and "bpy.context" in d.text,
        lambda d: d.rule == "invalid-base" and "`Menu`" in d.msg,
        lambda d: "Expected `Menu`, found `<class" in d.msg,
        lambda d: re.search(r"Expected `dict\[[^`]*`, found `tuple\[", d.msg) is not None))),
    # Typechecker fixes (S1 RNA never-None, S2 stub generator, S3 ty_blender).
    Cause("context-never-none", "typechecker-fix", "S1", lambda d: NEVER_NONE_CONTEXT_TYPE.search(d.msg) is not None),
    Cause("callback-never-none", "typechecker-fix", "S1", callback_never_none),
    # ObjectModifiers.new() really returns None when the modifier cannot be added (only a warning report), so an
    # unchecked result is typing debt, not a typechecker fix. Only the modifier itself counts: a nullable receiver
    # on the same line (`self.spline_obj.modifiers.new(...)`) is not the result.
    Cause("modifiers-new", "typing-debt", "", lambda d: NULLABLE_MODIFIER.search(d.msg) is not None
          and reads_from(d, MODIFIERS_NEW)),
    Cause("helper-checks-none", "typing-debt", "", lambda d: "`SpaceAssetInfo.is_asset_browser`" in d.msg
          or (nullable(d) and in_sites(HELPER_CHECKS_SITES)(d))),
    Cause("bmesh-elem-seq", "typechecker-fix", "S2", lambda d: "`BMEdge`" in d.msg and "loop" in d.text),
    Cause("blend-data-lib-key", "typechecker-fix", "S2", lambda d: "`tuple[str, " in d.msg and "[" in d.text),
    Cause("context-store-member", "typechecker-fix", "S2", lambda d: d.msg.startswith("Object of type `Context`")
          and missing_attribute(d.msg) in CONTEXT_STORE_MEMBERS),
    Cause("freestyle-positional", "typechecker-fix", "S2", lambda d: d.rule in METHOD_OVERRIDE_RULES
          and FREESTYLE_OVERRIDES.search(d.msg) is not None),
    Cause("render-engine-positional", "typechecker-fix", "S2", lambda d: d.rule in METHOD_OVERRIDE_RULES
          and RENDER_ENGINE_UPDATES.search(d.msg) is not None),
    # Enums whose items are computed: at runtime (render engines, project sections) or from a tuple expression.
    # The stubs give a computed enum the placeholder item its definition starts with (`DEFAULT`, `PLACEHOLDER`).
    Cause("dynamic-enum", "typechecker-fix", "S2", lambda d: DYNAMIC_ENUM_PLACEHOLDER.search(d.msg) is not None
          or re.search(r"Object of type `str & ~Literal\[|to attribute `(?:engine|active_section)` of type `Literal",
                       d.msg) is not None),
    Cause("stub-context-manager", "typechecker-fix", "S2", lambda d: d.rule == "invalid-context-manager"
          and re.search(r"libraries\.load|temp_data", d.text) is not None),
    Cause("stub-docstring", "typechecker-fix", "S2", lambda d: re.search(
        r"\bkeyconfig_set\b|\btarget_set_value\b|\bunpack_list\(", d.text) is not None),
    Cause("stub-signature-gap", "typechecker-fix", "S2", lambda d: STUB_SIGNATURE.search(d.msg) is not None
          or (d.rule == "invalid-assignment" and "data_to." in d.text)
          or ("`ID | None`" in d.msg and reads_from(d, r"\.copy\(\)"))),
    Cause("mathutils-protocol-stub", "typechecker-fix", "S2", lambda d: MATHUTILS_PROTOCOL.search(d.msg) is not None),
    Cause("callback-positional", "typechecker-fix", "S2", lambda d: d.rule in METHOD_OVERRIDE_RULES
          and "`Gizmo.draw_select`" in d.msg),
    Cause("registered-class-in-bpy-types", "typechecker-fix", "S2", lambda d: "bpy.types." in d.text
          and REGISTERED_CLASS.search(d.msg) is not None),
    # `item_type == 'PANEL'` does not narrow a NodeTreeInterfaceItem, nor `match item.type` a ProjectVariable: the
    # stubs declare no type tag for their subclasses.
    Cause("item-type-tag-narrowing", "typechecker-fix", "S2", lambda d: re.search(
        r"`NodeTreeInterfaceItem(?: & ~AlwaysFalsy)?` has no attribute `(?:interface_items|name)`"
        r"|Expected `NodeTreeInterfacePanel|`ProjectVariable` has no attribute `value`", d.msg) is not None),
    Cause("layout-in-helper", "typechecker-fix", "S3", layout_in({"panel", "menu", "header"})),
    Cause("layout-in-operator-helper", "typing-debt", "", layout_in({"operator"})),
    Cause("cross-file-registered-property", "typing-debt", "", lambda d: re.search(
        r"has no attribute `(?:cycles\w*|selection_sets|hydra_storm)`", d.msg) is not None),
    Cause("file-registered-property", "typechecker-fix", "S3", registered_property),
    Cause("bl-rna-property", "typechecker-fix", "S3", lambda d: d.msg.startswith("Object of type `Property`")),
    Cause("type-call-bases", "typechecker-fix", "S3", rule("blender-invalid-idname")),
    Cause("filter-items-tuple", "typechecker-fix", "S3", lambda d: d.rule in RETURN_RULES
          and d.scope.function == "filter_items"),
    # Returns that contradict the operator API or the function's own annotation.
    Cause("operator-return-misuse", "blender-fix", "BF1", outside_tests(
        lambda d: d.rule in RETURN_RULES and d.scope.function in OPERATOR_RETURNS)),
    Cause("return-annotation", "blender-fix", "BF2", outside_tests(lambda d: d.rule in RETURN_RULES
          and not untyped_python(d) and TYPESHED_PRIVATE.search(d.msg) is None)),
    # Nullable reads, from the most specific source.
    Cause("unchecked-pointer-bug", "blender-fix", "BF1", unchecked_pointer_bug),
    Cause("mixin-self", "typing-debt", "", mixin_self),
    Cause("type-enum-sub-pointer", "typing-debt", "", lambda d: nullable(d) and (
        SETTINGS_POINTER.search(d.msg) is not None or SUB_POINTER.search(d.msg) is not None
        or "`Driver | None`" in d.msg or ("NodeTree | None" in d.msg and reads_from(d, r"\.node_tree\b")))),
    # A plain Python Optional: no Blender type, a stdlib or Python class, or a local initialised to None.
    Cause("python-optional", "typing-debt", "", lambda d: (nullable(d) or (NONE_KEY in d.msg and not poll_checks_elsewhere(d))) and (
        python_optional(d) or PYTHON_OPTIONAL_TYPE.search(d.msg) is not None
        or (initialised_to_none(d) and not untyped_python(d)))),
    # A preset's module-level reads of the context members of the panel that runs it (`bpy.context.cloth`,
    # `edit_movieclip`, `active_strip`, a keymap preset's `preferences`): the preset-context Assumption, where its
    # rule did not accept the read.
    Cause("preset-context-member", "assumption", "", lambda d: nullable(d) and in_presets(d)),
    Cause("ui-draw-pointer", "typing-debt", "", outside_tests(ui_draw_pointer)),
    Cause("object-data-untagged", "typing-debt", "", lambda d: re.search(r"`ID( \| None)?`", d.msg) is not None
          and ("data" in d.text or reads_from(d, r"\.data\b"))),
    # The window, screen, area, region, space and workspace of the editor an operator's `invoke` / `modal` (or a
    # gizmo's `exit`) runs in: those run interactively only, so the members exist (research
    # `blender-true-problems`, "Ruled out": None only in exotic states). Not covered by an Assumption.
    Cause("editor-context-member", "typing-debt", "", any_of(lambda d: OTHER_CONTEXT_TYPE.search(d.msg) is not None
          and d.scope.function in INTERACTIVE_CALLBACKS, editor_member_outside_execute)),
    # A doc example or template reading the context it documents (`bpy.context.object` with an active object),
    # directly or, at module level, through what it read (`obj = bpy.context.object`, then `obj.data`).
    Cause("script-context-member", "typing-debt", "", lambda d: nullable(d) and in_scripts(d)
          and (not d.scope.function or reads_from(d, CONTEXT + r"\w+"))
          and not ui_callback_editor_member(d) and not set_by_preceding_call(d)),
    # The causes sorted site by site (docs/reports/spec-95-site-decisions.md), from the most specific.
    Cause("rna-never-none", "typechecker-fix", "S1", rna_never_none),
    Cause("base-class-subtype", "typing-debt", "", lambda d: (d.rule in MISSING_ATTRIBUTE_RULES
          and BASE_CLASS.search(d.msg) is not None) or (d.rule == "invalid-assignment"
          and base_class_target(d.msg.partition(" on type ")[2]))
          or "Object of type `Node | None` has no attribute" in d.msg
          or re.search(r"found `list\[tuple\[ID(?: \| None)?,", d.msg) is not None),
    # A panel's `bl_context`: the bl-context Implied narrowing, where its rule did not accept the read.
    Cause("bl-context-implies-member", "implied-narrowing", "", bl_context_member),
    Cause("set-by-ui-button", "typing-debt", "", lambda d: "`KeyMapItem | None`" in d.msg
          or (SET_BY_UI_BUTTON_TYPE.search(d.msg) is not None and not poll_checks_alias(d))),
    Cause("window-context-in-execute", "typing-debt", "", lambda d: window_context(d)
          and not ("'INTERNAL'" in d.scope.attributes and root(d.scope) == "operator")
          and not ("`Collection | None`" in d.msg and root(d.scope) == "operator")),
    # The object a `bpy.ops.*.*_add()` call earlier in the function made active: the added-object Assumption,
    # where its rule did not accept the read.
    Cause("added-object", "assumption", "", added_object),
    Cause("set-by-preceding-call", "typing-debt", "", set_by_preceding_call),
    Cause("narrowed-by-poll-helper", "implied-narrowing", "", poll_checks_elsewhere),
    Cause("narrowed-by-parent-panel", "implied-narrowing", "", parent_panel),
    Cause("narrowed-by-poll-alias", "implied-narrowing", "", poll_checks_alias),
    Cause("narrowed-by-mode", "implied-narrowing", "", lambda d: "Object | None" in d.msg
          and POLL_MODE.search(d.scope.poll) is not None),
    Cause("rarely-none-member", "typing-debt", "", rarely_none_member),
    Cause("correlated-condition", "typing-debt", "", lambda d: nullable(d) and in_sites(CORRELATED_SITES)(d)),
    Cause("narrowed-by-poll-in-caller", "implied-narrowing", "", lambda d: nullable(d)
          and in_sites(NARROWED_IN_CALLER_SITES)(d)),
    Cause("collection-context-member", "assumption", "", lambda d: "`Collection | None`" in d.msg
          and root(d.scope) == "operator" and d.scope.function == "execute"),
    Cause("internal-operator", "assumption", "", internal_operator),
    Cause("ui-callback-editor-member", "assumption", "", ui_callback_editor_member),
    Cause("area-type-active-space", "implied-narrowing", "", lambda d: "`Space | None`" in d.msg
          and reads_from(d, r"\.spaces\.active\b")),
    Cause("temp-override-member", "implied-narrowing", "", lambda d: nullable(d) and "temp_override(" in d.scope.source
          and "bpy.context." in d.text),
    Cause("none-excluded-by-arguments", "typing-debt", "", lambda d: nullable(d) and reads_from(d, NONE_ON_FAILURE)),
    Cause("operator-without-poll", "typing-debt", "", lambda d: nullable(d)
          and in_sites(OPERATOR_WITHOUT_POLL_SITES)(d)),
    Cause("context-member-outside-callback", "unsorted", "", lambda d: not untyped_python(d) and (
        OTHER_CONTEXT_TYPE.search(d.msg) is not None
        or (nullable(d) and re.search(CONTEXT + r"\w+", d.text) is not None and not d.scope.function))),
    # Untyped packages (rigify, glTF) keep their internal Optionals: they go to `untyped-python` below.
    # A heterogeneous list read as a record (`[index, socket]`) names None among its items: general typing below.
    Cause("runtime-operator-idname", "typing-debt", "", lambda d: re.search(r"`(?:None \| OperatorProperties|"
          r"OperatorProperties \| None)`", d.msg) is not None and RUNTIME_OPERATOR_IDNAME.search(d.text) is not None),
    Cause("unchecked-pointer", "unsorted", "", lambda d: nullable(d) and not untyped_python(d)
          and GENERAL_TYPING.search(d.msg) is None),
    # The rest, by rule.
    Cause("operator-call", "typing-debt", "", lambda d: "bpy.ops." in d.text or "OperatorProperties" in d.msg
          or "`<module 'bpy.ops'>` is not callable" in d.msg
          or ("`dict[str, Any]`" in d.msg and re.match(r"\s*props\.\w+_OT_", d.text) is not None)
          or (d.rule == "too-many-positional-arguments" and STRING_LITERAL.search(d.text) is not None)),
    Cause("unresolved-import", "typing-debt", "", lambda d: d.rule in {
        "import-not-found", "possibly-missing-submodule"} or "Cannot resolve imported" in d.msg),
    # `batch_for_shader()`'s deprecated primitives, left out of the documented literal.
    Cause("deprecated-enum-value", "typing-debt", "", lambda d: "`batch_for_shader`" in d.msg
          and re.search(r"found `Literal\[\"(?:TRI_FAN|LINE_LOOP)\"\]`", d.msg) is not None),
    # `bpy.utils.script_paths_pref` is missing from `bpy.utils.__all__`, so the stubs leave it out.
    Cause("unexported-function", "typing-debt", "", lambda d: "has no member `script_paths_pref`" in d.msg),
    Cause("untyped-python", "typing-debt", "", untyped_python),
    Cause("private-member", "typing-debt", "", lambda d: re.search(r"has no member `_\w+`", d.msg) is not None),
    Cause("build-option-gap", "typing-debt", "", lambda d: BUILD_OPTION_TYPE.search(d.msg) is not None),
    Cause("general-typing", "typing-debt", "", lambda d: d.rule in GENERAL_TYPING_RULES
          or TYPESHED_PRIVATE.search(d.msg) is not None or THIRD_PARTY_STUB.search(d.msg) is not None
          or in_sites(OVERRIDDEN_SIGNATURE_SITES)(d)
          or PYTHON_OBJECT_ATTRIBUTE.search(d.msg) is not None or python_types_only(d)
          or d.rule in {"redundant-condition", "mismatched-type-name"}
          or (d.rule in METHOD_OVERRIDE_RULES and not in_tests(d))
          or (d.rule == "invalid-context-manager" and "`Iterator[None]`" in d.msg)
          or GENERAL_TYPING.search(d.msg) is not None or MONKEYPATCH.match(d.text) is not None),
    Cause("stub-gap", "unsorted", "", lambda d: d.rule in STUB_GAP_RULES or "object.__init__" in d.msg
          or re.search(r"Module `[\w.]+` has no member", d.msg) is not None),
    Cause("blender-rule", "unsorted", "", lambda d: d.rule.startswith("blender-")),
    Cause("unsorted", "unsorted", "", lambda d: True),
]  # fmt: skip
CAUSE_BY_NAME = {c.name: c for c in CAUSES}
# The dedicated rules of S4-S6 name their cause, ahead of every pattern.
CAUSE_BY_RULE = {c.rule: c for c in CAUSES if c.rule}


def none_last(msg: str) -> str:
    """``msg`` with ``None`` moved to the end of every union it names (fake-bpy-module's stubs spell
    ``None | Scene``), so the facts need to know one spelling."""

    def reorder(match: re.Match[str]) -> str:
        members = union_members(match[1])
        if "None" not in members[:-1]:
            return match[0]
        return "`" + " | ".join([m for m in members if m != "None"] + ["None"]) + "`"

    return re.sub(r"`([^`]*)`", reorder, msg)


def cause(d: Diagnostic) -> Cause:
    """The cause of a diagnostic: the one its dedicated rule reports, else the first entry of CAUSES that
    matches it (with ``None`` last in each union)."""
    if d.rule in CAUSE_BY_RULE:
        return CAUSE_BY_RULE[d.rule]
    d = replace(d, msg=object_data_as_id(none_last(d.msg)))
    return next(c for c in CAUSES if c.matches(d))


def object_data_as_id(msg: str) -> str:
    """``msg`` with fake-bpy-module's ``Object.data`` union, as ty cuts it short, spelled ``ID | None`` (``ID``
    when a check removed None or some of the types), like Blender's own stubs."""
    return OBJECT_DATA_UNION.sub(lambda m: "`ID | None`" if m[1].startswith("Camera") else "`ID`", msg)


# The causes in report order: by group, then in table order.
REPORTED = [c for g in GROUPS for c in CAUSES if c.group == g]


# --- reading ty's output ---------------------------------------------------------------------------------------

DEF = re.compile(r"(?:async\s+)?def\s+(\w+)\s*\(")
CLASS = re.compile(r"class\s+(\w+)\s*(?:\((.*)\))?\s*:")
REGISTERS = re.compile(r"^\s*bpy\.types\.\w+\.(\w+)\s*=\s*(?:bpy\.props\.|props\.)?\w*Property\(", re.MULTILINE)


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip())


def parameters(lines: list[str], index: int) -> tuple[str, ...]:
    """The parameter names of the ``def`` starting at ``lines[index]``, which may span lines."""
    text = ""
    for line in lines[index : index + 20]:
        text += line.split("#")[0] + " "
        if re.search(r"\)\s*(->.*)?:\s*$", line.split("#")[0]):
            break
    start = text.index("(") + 1
    depth, current, parts = 0, "", []
    for char in text[start:]:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        current += char
    parts.append(current)
    names = (re.split(r"[:=]", part)[0].strip().lstrip("*").strip() for part in parts)
    return tuple(n for n in names if n and n != "/")


def class_has_poll(lines: list[str], index: int) -> bool:
    indent = indentation(lines[index])
    for line in lines[index + 1 :]:
        if line.strip() and not line.lstrip().startswith("#") and indentation(line) <= indent:
            return False
        if re.match(r"\s*def\s+poll\s*\(", line):
            return True
    return False


def class_body(lines: list[str], index: int) -> tuple[str, str]:
    """The statements directly in the body of the class at ``lines[index]``, and the source of its own ``poll``."""
    indent = indentation(lines[index])
    body_indent, attributes, poll, in_poll = None, [], [], False
    for line in lines[index + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if indentation(line) <= indent:
            break
        body_indent = body_indent or indentation(line)
        if indentation(line) == body_indent:
            attributes.append(line.strip())
            in_poll = re.match(r"\s*def\s+poll\s*\(", line) is not None
        if in_poll:
            poll.append(line)
    return "\n".join(attributes), "\n".join(poll)


def class_facts(lines: list[str], index: int, bases: str, cache: dict) -> tuple[str, str]:
    """``class_body`` of the class at ``lines[index]``, with the attributes of its base classes defined in the same
    file, and the poll of the first of them that has one when the class has none of its own."""
    if index not in cache:
        cache[index] = class_body(lines, index)
    attributes, poll = cache[index]
    for base in re.findall(r"(\w+)\s*(?:,|$)", bases):
        for i, line in enumerate(lines):
            if re.match(rf"\s*class\s+{base}\b", line):
                if i not in cache:
                    cache[i] = class_body(lines, i)
                attributes += "\n" + cache[i][0]
                poll = poll or cache[i][1]
                break
    return attributes, poll


def enclosing_scope(lines: list[str], line: int, registers: frozenset[str], cache: dict | None = None) -> Scope:
    """The class and function around the 1-based ``line``, found by indentation."""
    index = line - 1
    if not 0 <= index < len(lines):
        return Scope(registers=registers)
    module_source = "\n".join(lines[max(0, index - 40) : index + 1])
    limit = indentation(lines[index]) if lines[index].strip() else 1 << 30
    if limit == 0:
        return Scope(registers=registers, source=module_source)
    function, params, source = "", (), module_source
    for i in range(index - 1, -1, -1):
        text = lines[i]
        stripped = text.strip()
        if not stripped or stripped.startswith(("#", "@", ")", "]", "}")) or indentation(text) >= limit:
            continue
        limit = indentation(text)
        if not function and (match := DEF.match(stripped)):
            function, params, source = match[1], parameters(lines, i), "\n".join(lines[i : index + 1])
        elif match := CLASS.match(stripped):
            attributes, poll = class_facts(lines, i, match[2] or "", {} if cache is None else cache)
            return Scope(match[1], match[2] or "", function, params, class_has_poll(lines, i), registers,
                         attributes, poll, source)  # fmt: skip
        if limit == 0:
            break
    return Scope(function=function, params=params, registers=registers, source=source)


def read_diagnostics(output: str, source: Path) -> list[Diagnostic]:
    """The diagnostics of ty's concise ``output``, run in ``source``, each with the source line it points at and
    its enclosing scope."""
    files: dict[str, tuple[list[str], frozenset[str], dict]] = {}
    diagnostics = []
    for match in DIAGNOSTIC_LINE.finditer(output):
        path, line = match["path"], int(match["line"])
        if path not in files:
            try:
                content = (source / path.replace("\\", "/")).read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""
            files[path] = (content.splitlines(), frozenset(REGISTERS.findall(content)), {})
        lines, registers, cache = files[path]
        text = lines[line - 1] if 0 < line <= len(lines) else ""
        scope = enclosing_scope(lines, line, registers, cache)
        diagnostics.append(Diagnostic(path, line, match["rule"], match["msg"], text, match["severity"], scope))
    return diagnostics


# --- reports ---------------------------------------------------------------------------------------------------


def samples(diagnostics: list[Diagnostic], per_cause: int = 20) -> str:
    """The first ``per_cause`` diagnostics of each cause with their source line and scope, for reading."""
    by_cause: dict[str, list[Diagnostic]] = collections.defaultdict(list)
    for d in diagnostics:
        by_cause[d.cause.name].append(d)
    out = []
    for c in REPORTED:
        out.append(f"## {c.name} ({c.group}{', ' + c.slice if c.slice else ''}): {len(by_cause[c.name])}\n")
        for d in by_cause[c.name][:per_cause]:
            where = ".".join(part for part in (d.scope.cls, d.scope.function) if part)
            out.append(f"{d.path}:{d.line}: {d.severity}[{d.rule}] {d.msg}\n")
            out.append(f"    | {d.text.strip()}{f'    ({where})' if where else ''}\n")
        out.append("\n")
    return "".join(out)


def summary(title: str, diagnostics: Iterable[tuple[str, str, str, str]]) -> str:
    """The cause × area table (with each cause's group and slice), the totals per group, the totals of errors and
    warnings, and the counts per rule and severity (sorted by name) of ``diagnostics``, given as (cause, area, rule,
    severity). Every cause and group gets a row, also when zero, so a diff of two summaries shows what moved where."""
    diagnostics = list(diagnostics)
    cells = collections.Counter((c, a) for c, a, _, _ in diagnostics)
    groups = collections.Counter((CAUSE_BY_NAME[c].group, a) for c, a, _, _ in diagnostics)
    severities = collections.Counter((s, a) for _, a, _, s in diagnostics)
    rules = collections.Counter((r, s) for _, _, r, s in diagnostics)

    def counts(row: str, cell: collections.Counter) -> str:
        values = [cell[row, a] for a in AREA_NAMES]
        return "".join(f"{n:>10}" for n in [*values, sum(values)]) + "\n"

    areas = "".join(f"{a:>10}" for a in [*AREA_NAMES, "total"]) + "\n"
    lines = [title + "\n", f"{'cause':<32}{'group':<22}{'slice':<6}" + areas]
    lines.extend(f"{c.name:<32}{c.group:<22}{c.slice or '-':<6}" + counts(c.name, cells) for c in REPORTED)
    lines.append("\n")
    lines.append(f"{'group':<60}" + areas)
    lines.extend(f"{g:<60}" + counts(g, groups) for g in GROUPS)
    lines.append(f"{'errors':<60}" + counts("error", severities))
    lines.append(f"{'warnings':<60}" + counts("warning", severities))
    lines.append("\n")
    lines.append(f"{'rule':<40}{'error':>8}{'warning':>8}\n")
    lines.extend(f"{r:<40}{rules[r, 'error']:>8}{rules[r, 'warning']:>8}\n" for r in sorted({r for r, _ in rules}))
    return "".join(lines)


def area(path: str) -> str:
    """The area of a path relative to the Blender source root (``/`` or ``\\`` separated)."""
    path = path.replace("\\", "/")
    for name, prefixes in AREAS:
        if path.startswith(prefixes):
            return name
    return "other"
