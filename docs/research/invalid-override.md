# How `blender-invalid-override` replaces `invalid-method-override`

Research note, 2026-11-06, for [#51](https://github.com/taway1450/blender-extension-developer-suite/issues/51)
(map #49). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

Sources: Blender `main` (`.cache/blender-src/main`, 5.4 alpha), cross-checked against `4.2` and `5.2`; the fork at
`ty-blender/ruff-blender` (branch `blender`, `b4135144e1`). Blender line numbers below are at that `main`.

## Design

Two parts. One reports Blender's own verdict. The other stops ty's verdict from contradicting it.

1. **Reporting.** `blender-invalid-override` is a lint reported from the per-file diagnostics query for first-party
   files, the way #27 and #29 report their rules, so `# ty: ignore` works the same. For each callback `def` in a
   Blender-derived class it reads two things:
   - **kind:** from ty's function decorators (`classmethod`, `staticmethod`). A `def` with an unknown decorator is
     skipped, and so are non-`def` bindings (`poll = f`).
   - **positional count:** `len(posonlyargs) + len(args)` from the AST, which is CPython's `co_argcount`. Defaults
     count; `*args`, keyword-only parameters and `**kwargs` do not.

   It reports on the `def` name, so the marker on the `def` line matches, also when the `def` is decorated. The
   level is Error, because Blender raises at `register_class`.
2. **Suppression.** A hook in upstream's override checks (the member check and the inherited-conflict check)
   replaces the parent's contract before the assignability test:
   - unchanged when the name is not a Blender callback of the class's root, so all non-Blender code is untouched;
   - nothing (no ty report) when `blender-invalid-override` reports this definition, so the two rules never fire
     on the same line;
   - otherwise a relaxed contract: the parent's callable with every parameter made **positional-only** (Blender
     passes arguments by position, `bpy_rna.cc:10111-10130`). For `UIList.draw_item` it is also **cut to the
     override's count** (7–10). The parent's parameter and return types are kept, so ty's
     `invalid-method-override` still reports type incompatibilities.

**Rejected alternatives.**
- A blanket "skip Blender callbacks" would be simpler, but it would silence the type-incompatibility guards
  (`inh_override_types`) that the relaxed contract keeps.
- Reporting from inside upstream's `overrides.rs`: its `check_class` returns early when ty's override rules are
  disabled and when the class has no members of its own, and #27 settled on one reporting site.

### Scope of the rule

The rule covers **every class that derives from a registrable Blender class** and checks the `def`s in its own
body. Whether the add-on registers the class does not matter. This is the same scope as upstream's
`invalid-method-override`, which it replaces, and it needs no `register()` walk, so it cannot go silent when the
walk is incomplete. A Blender-derived base that is never registered is still checked, because a registered
subclass inherits its `def` and Blender validates that one (`getattr` on the class, `bpy_rna.cc:9751`). The
diagnostic then sits once, on the base's `def`.

**A plain mixin's methods are not checked by this rule.** The mixin has no Blender parent and can be combined with
different roots. Where a mixin method conflicts with the Blender stub method in a Blender-derived class, the
inherited-conflict hook still applies the relaxed contract. So renamed parameters are accepted, but a real mismatch
(wrong count, wrong decorator) keeps upstream's class-line `invalid-method-override`, which is useful there because
Blender would reject it. Checking mixin callbacks through registered classes (a presence rule over the registration
findings) is a possible later extension. No marker asks for it.

`AddonPreferences.draw` is not an RNA callback: `space_userpref.py:2486-2496` calls it from Python, so it is not
in the table.

### The table (Blender `main`; confirmed against `bl_rna` sources and `bpy_class_validate_recursive`)

Counts include `self`/`cls` (what Blender compares with `co_argcount`). Kind: **cm** = must be a `classmethod`
(Blender demands a bound method: `FUNC_NO_SELF` without `FUNC_USE_SELF_TYPE`, `bpy_rna.cc:9782-9799`); **fn** =
must be a plain function, where a `staticmethod` also passes because class access unwraps it, and a `classmethod`
fails ("to be a function, not a method", `:9801-9812`). **Req** = `FUNC_REGISTER` without `_OPTIONAL` (#52's
`blender-missing-callback`). **bool** = a single boolean output, converted with `PyObject_IsTrue`
(`bpy_rna.cc:1711-1717`), so any value is accepted.

| Root | Callback | Kind | Positional | Req | bool | RNA source (main) |
| --- | --- | --- | --- | --- | --- | --- |
| Operator | `poll(cls, context)` | cm | 2 | | yes | rna_wm_api.cc:1350 |
| Operator | `execute(self, context)` | fn | 2 | | | rna_wm_api.cc:1358 |
| Operator | `check(self, context)` | fn | 2 | | yes | rna_wm_api.cc:1370 |
| Operator | `invoke(self, context, event)` | fn | 3 | | | rna_wm_api.cc:1381 |
| Operator | `modal(self, context, event)` | fn | 3 | | | rna_wm_api.cc:1394 |
| Operator | `draw(self, context)` | fn | 2 | | | rna_wm_api.cc:1408 |
| Operator | `cancel(self, context)` | fn | 2 | | | rna_wm_api.cc:1415 |
| Operator | `description(cls, context, properties)` | cm | 3 | | | rna_wm_api.cc:1422 |
| Macro | `poll(cls, context)` | cm | 2 | | yes | rna_wm_api.cc:1450 |
| Macro | `draw(self, context)` | fn | 2 | | | rna_wm_api.cc:1458 |
| Panel | `poll(cls, context)` | cm | 2 | | yes | rna_ui.cc:1884 |
| Panel | `draw(self, context)` | fn | 2 | **req** | | rna_ui.cc:1893 |
| Panel | `draw_header(self, context)` | fn | 2 | | | rna_ui.cc:1899 |
| Panel | `draw_header_preset(self, context)` | fn | 2 | | | rna_ui.cc:1905 |
| UIList | `draw_item(self, context, layout, data, item, icon, active_data[, active_property, index, flt_flag])` | fn | **7–10** | | | rna_ui.cc:2125 (`PARM_PYFUNC_REGISTER_OPTIONAL` on `active_property`) |
| UIList | `draw_filter(self, context, layout)` | fn | 3 | | | rna_ui.cc:2166 |
| UIList | `filter_items(self, context, data, property)` | fn | 4 | | | rna_ui.cc:2175 (2 outputs: flags, neworder) |
| Header | `draw(self, context)` | fn | 2 | **req** | | rna_ui.cc:2240 |
| Menu | `poll(cls, context)` | cm | 2 | | yes | rna_ui.cc:2309 |
| Menu | `draw(self, context)` | fn | 2 | **req** | | rna_ui.cc:2318 |
| AssetShelf | `poll(cls, context)` | cm | 2 | | yes | rna_ui.cc:2483 |
| AssetShelf | `asset_poll(cls, asset)` | cm | 2 | | yes | rna_ui.cc:2491 |
| AssetShelf | `get_active_asset(cls)` | cm | 1 | | | rna_ui.cc:2502 |
| AssetShelf | `draw_context_menu(cls, context, asset, layout)` | cm | 4 | | | rna_ui.cc:2515 |
| FileHandler | `poll_drop(cls, context)` | cm | 2 | | yes | rna_ui.cc:2623 |
| KeyingSetInfo | `poll(self, context)` | **fn** | 2 | **req** | yes | rna_animation.cc:1247 |
| KeyingSetInfo | `iterator(self, context, ks)` | fn | 3 | **req** | | rna_animation.cc:1255 |
| KeyingSetInfo | `generate(self, context, ks, data)` | fn | 4 | **req** | | rna_animation.cc:1265 |
| Node | `poll(cls, node_tree)` | cm | 2 | **req** (met by `_bpy_types.Node.poll`) | yes | rna_nodetree.cc:4413 |
| Node | `poll_instance(self, node_tree)` | fn | 2 | | yes | rna_nodetree.cc:4421 |
| Node | `update(self)` | fn | 1 | | | rna_nodetree.cc:4430 |
| Node | `insert_link(self, link)` | fn | 2 | | | rna_nodetree.cc:4436 |
| Node | `init(self, context)` | fn | 2 | | | rna_nodetree.cc:4443 |
| Node | `copy(self, node)` | fn | 2 | | | rna_nodetree.cc:4450 |
| Node | `free(self)` | fn | 1 | | | rna_nodetree.cc:4458 |
| Node | `draw_buttons(self, context, layout)` | fn | 3 | | | rna_nodetree.cc:4463 |
| Node | `draw_buttons_ext(self, context, layout)` | fn | 3 | | | rna_nodetree.cc:4474 |
| Node | `draw_label(self)` | fn | 1 | | | rna_nodetree.cc:4485 |
| NodeTree | `poll(cls, context)` | cm | 2 | | yes | rna_nodetree.cc:4872 |
| NodeTree | `update(self)` | fn | 1 | | | rna_nodetree.cc:4880 |
| NodeTree | `get_from_context(cls, context)` | cm | 2 | | | rna_nodetree.cc:4885 (3 outputs) |
| NodeTree | `valid_socket_type(cls, idname)` | cm | 2 | | yes | rna_nodetree.cc:4901 |
| NodeSocket | `draw(self, context, layout, node, text)` | fn | 5 | **req** | | rna_node_socket.cc:985 |
| NodeSocket | `draw_color(self, context, node)` | fn | 3 | | | rna_node_socket.cc:1003 |
| NodeSocket | `draw_color_simple(cls)` | cm | 1 | | | rna_node_socket.cc:1016 |
| NodeTreeInterfaceSocket | `draw(self, context, layout)` | fn | 3 | | | rna_node_tree_interface.cc:1448 |
| NodeTreeInterfaceSocket | `init_socket(self, node, socket, data_path)` | fn | 4 | | | rna_node_tree_interface.cc:1458 |
| NodeTreeInterfaceSocket | `from_socket(self, node, socket)` | fn | 3 | | | rna_node_tree_interface.cc:1469 |
| Gizmo | `draw(self, context)` | fn | 2 | **req** | | rna_wm_gizmo.cc:1051 |
| Gizmo | `draw_select(self, context, select_id)` | fn | 3 | | | rna_wm_gizmo.cc:1058 |
| Gizmo | `test_select(self, context, location)` | fn | 3 | | | rna_wm_gizmo.cc:1066 |
| Gizmo | `modal(self, context, event, tweak)` | fn | 4 | | | rna_wm_gizmo.cc:1092 |
| Gizmo | `setup(self)` | fn | 1 | | | rna_wm_gizmo.cc:1109 |
| Gizmo | `invoke(self, context, event)` | fn | 3 | | | rna_wm_gizmo.cc:1114 |
| Gizmo | `exit(self, context, cancel)` | fn | 3 | | | rna_wm_gizmo.cc:1126 |
| Gizmo | `select_refresh(self)` | fn | 1 | | | rna_wm_gizmo.cc:1138 |
| GizmoGroup | `poll(cls, context)` | cm | 2 | | yes | rna_wm_gizmo.cc:1460 |
| GizmoGroup | `setup_keymap(cls, keyconfig)` | cm | 2 | | | rna_wm_gizmo.cc:1468 |
| GizmoGroup | `setup(self, context)` | fn | 2 | **req** | | rna_wm_gizmo.cc:1480 |
| GizmoGroup | `refresh(self, context)` | fn | 2 | | | rna_wm_gizmo.cc:1487 |
| GizmoGroup | `draw_prepare(self, context)` | fn | 2 | | | rna_wm_gizmo.cc:1494 |
| GizmoGroup | `invoke_prepare(self, context, gizmo)` | fn | 3 | | | rna_wm_gizmo.cc:1500 |
| RenderEngine | `update(self, data, depsgraph)` | fn | 3 | | | rna_render.cc:584 |
| RenderEngine | `render(self, depsgraph)` | fn | 2 | | | rna_render.cc:590 |
| RenderEngine | `render_frame_finish(self)` | fn | 1 | | | rna_render.cc:596 |
| RenderEngine | `draw(self, context, depsgraph)` | fn | 3 | | | rna_render.cc:601 |
| RenderEngine | `bake(self, depsgraph, object, pass_type, pass_filter, width, height)` | fn | 7 | | | rna_render.cc:609 |
| RenderEngine | `view_update(self, context, depsgraph)` | fn | 3 | | | rna_render.cc:634 |
| RenderEngine | `view_draw(self, context, depsgraph)` | fn | 3 | | | rna_render.cc:642 |
| RenderEngine | `view_pause(self, context)` | fn | 2 | | | rna_render.cc:650 (main only) |
| RenderEngine | `view_resume(self, context)` | fn | 2 | | | rna_render.cc:656 (main only) |
| RenderEngine | `update_script_node(self, node)` | fn | 2 | | | rna_render.cc:663 |
| RenderEngine | `update_render_passes(self, scene, renderlayer)` | fn | 3 | | | rna_render.cc:669 |
| RenderEngine | `update_custom_camera(self, cam)` | fn | 2 | | | rna_render.cc:675 (5.2+) |

The registrable roots without callbacks are `PropertyGroup`, `AddonPreferences`, `KeyConfigPreferences` and
`USDHook`.

**Corrections to the ticket and the README.**
- `KeyingSetInfo.poll` is an **instance method**, unlike every other `poll`. Its flags are `FUNC_REGISTER`
  without `FUNC_NO_SELF` (`rna_animation.cc:1249`), and both stubs declare `def poll(self, context)`.
- `Panel.poll`, `Menu.poll`, `Macro.poll`, `AssetShelf.*`, `FileHandler.poll_drop` and `Node.poll` are
  classmethods too. The README's list (`poll`, `description`, `draw_color_simple`, `NodeTree`, `GizmoGroup`) covers
  them only through "`poll`".
- `NodeSocketStandard.draw_color_simple` has `FUNC_NO_SELF | FUNC_USE_SELF_TYPE` (`rna_node_socket.cc:1081`), which
  validation would treat as a plain function. It has a C implementation and `NodeSocketStandard` has no register
  functions, so add-ons never meet it. The table keeps `NodeSocket`'s `cm`, and Blender's own template
  (`templates_py/custom_nodes.py:42`) agrees.

**Version notes.**
- `draw_item` accepts 7–10 in 4.2 as well. 4.2 sets the optional flag through a stale `parm`, after an unassigned
  `RNA_def_int` (`4.2/.../rna_ui.cc:2067-2071`), which makes `active_property` optional, as in main.
- Apart from the three `RenderEngine` callbacks noted in the table, the table is identical across 4.2, 5.2 and
  main. Diffs of the extracted tables are in the evidence section.

### Bool-converted callbacks

A boolean output passes through `PyObject_IsTrue` when it is a function result (`bpy_rna.cc:1711-1717`, comment:
"so many poll functions return None or a valid Object"). So these callbacks accept any value:

`Operator.poll`, `Operator.check`, `Macro.poll`, `Panel.poll`, `Menu.poll`, `AssetShelf.poll`,
`AssetShelf.asset_poll`, `FileHandler.poll_drop`, `KeyingSetInfo.poll`, `Node.poll`, `Node.poll_instance`,
`NodeTree.poll`, `NodeTree.valid_socket_type`, `GizmoGroup.poll`.

### Names Blender's Python bases define (for #52's `blender-mixin-order`)

From `scripts/modules/_bpy_types.py` (main and 5.2; `bpy_types.py` in 4.2), restricted to registrable roots and
their Python intermediates:

| Python base | Names it defines |
| --- | --- |
| `Operator` (1100) | `as_keywords`, `__getattribute__`, `__setattr__`, `__delattr__` |
| `Macro` (1139) | `define` (classmethod) |
| `_GenericUI` (1176), a base of `Panel`, `UIList`, `Header` and `Menu` | `is_extended`, `append`, `prepend`, `remove` (classmethods), `_dyn_ui_initialize`, `_dyn_owner_apply` |
| `Menu` (1305) | `path_menu`, `draw_preset`, `draw_collapsible` |
| `Node` (1507) | `poll(cls, ntree)` (classmethod, returns `True`; also an RNA callback) |
| `CompositorNode` / `ShaderNode` / `TextureNode` / `GeometryNode` (1563–1609) | `poll` (4.2: `CompositorNode.update` too) |
| `NodeSocket` (1529) | `links` (property) |
| `Gizmo` (990) | `draw_custom_shape`, `new_custom_shape` (staticmethod), `__getattribute__`, `__setattr__`, `__delattr__` |
| `HydraRenderEngine` (1623) | `__init__`, `__del__`, `get_render_settings`, `update`, `render`, `view_update`, `view_draw`, `bl_use_shading_nodes_custom`, `bl_delegate_id` |
| metaclass `_RNAMeta` (977; `RNAMeta` in 4.2) | `is_registered` (class property) |
| `PropertyGroup`, `KeyingSetInfo`, `USDHook`, `AddonPreferences`, `Panel`, `UIList`, `Header`, `AssetShelf`, `FileHandler`, `NodeTree`, `GizmoGroup`, `RenderEngine` | nothing beyond `__slots__` |

`Node.poll` is the one name that is both an RNA callback and a Python-base method: it names its parameter `ntree`,
where the stubs say `node_tree`. Without the positional-only contract, ty reports that rename on every `Node.poll`
override.

## Evidence

### Blender's verdict at registration (`source/blender/python/intern/bpy_rna.cc`, main)

- `pyrna_register_class` (`:10546`) passes `bpy_class_validate` to the struct's register callback (`:10669`).
  `bpy_class_validate_recursive` (`:9712`) first validates the RNA base struct (`srna_base`), then walks
  `RNA_struct_type_functions(srna)` and keeps those with `FUNC_REGISTER` (`:9740-9746`).
- **Lookup:** `PyObject_GetOptionalAttrString(py_class, identifier)` (`:9751`), an ordinary attribute lookup on the
  class, so it finds a `def` anywhere in the MRO: mixins, unregistered bases, Blender's Python bases (which is how
  `_bpy_types.Node.poll` meets the required `Node.poll`). A missing non-optional callback raises
  `expected %s, %s class to have an "%s" attribute` (`:9756-9763`).
- **Kind:** `is_staticmethod = (flag & FUNC_NO_SELF) && !(flag & FUNC_USE_SELF_TYPE)` (`:9782`).
  - When it is set, the attribute must be a `PyMethod`, which is what a `classmethod` gives on class access.
    Otherwise Blender raises `attribute to be a static/class method, not a %s` (`:9787-9799`). A `staticmethod`
    or a plain `def` gives a function, so both fail.
  - When it is not set, the attribute must be a `PyFunction`, else `to be a function, not a %s` (`:9801-9812`).
    A `staticmethod` gives the raw function on class access and passes. A `classmethod` gives a bound method and
    fails.
- **Count:** `rna_function_register_arg_count` (`:9676`) counts the non-output parameters, plus 1 for `self`
  unless the function is "static". It sets `min_count` at the first `PARM_PYFUNC_REGISTER_OPTIONAL` parameter. The
  validation then compares `co_argcount` (`:9818`), adding 1 for `cls` in the static case (`:9823-9826`). Out of
  range it raises `function to have %d args, found %d`, or `between %d and %d args` with max and min swapped
  (`:9828-9851`). `co_argcount` counts positional-only and positional-or-keyword parameters, defaults included,
  and leaves out `*args`, keyword-only parameters and `**kwargs`. That is exactly the README's rule.
- **Call:** `bpy_class_call` (`:9952`) builds a positional tuple of `co_argcount` items (`:10101-10130`), so names
  never matter and `draw_item` receives only as many arguments as it has parameters. It passes the instance first
  for functions and the class for classmethods (`:10111-10125`).
- **Return:** a single output goes through `pyrna_py_to_prop` (`:10209-10210`). For `PROP_BOOLEAN` with
  `PARM_OUTPUT` that is `PyObject_IsTrue` (`:1711-1717`).

### The RNA definitions

[`invalid-override/rna_callbacks.py`](invalid-override/rna_callbacks.py) parses every `RNA_def_function(srna, ...)`
in `makesrna/intern/*.cc`, keeps the `FUNC_REGISTER` ones, and applies the two formulas above. Run it with the
Blender source root as its argument (`python rna_callbacks.py .cache/blender-src/main`); it prints one line per
callback with its kind, whether it is required, and its positional count. The table above is that output, with
each row read by hand at its source line. To re-derive the table for a new Blender version, run it on that
version's source and diff the output against the previous one.

The `diff` between versions:
- main vs 5.2: only `view_pause` and `view_resume`.
- main vs 4.2: those two, plus `update_custom_camera`, plus `draw_item`. The `draw_item` difference is a parser
  artefact of 4.2's stale `parm`; read by hand, 4.2 is 7–10 too.

A first version of the parser missed `filter_items`' outputs (defined through a `prop` variable). Scanning
Blender's own scripts with the table flagged every `filter_items(self, context, data, propname)` and exposed that
bug. With it fixed, the table flags nothing in Blender's scripts (startup UI, `addons_core`, templates).

`RNA_def_struct_register_funcs` sites (`rna_ID.cc`, `rna_wm.cc`, `rna_userdef.cc`, `rna_usd.cc`, ...) cover the
roots without callbacks.

### What upstream ty reports without the hook, and why

- `invalid-method-override` on a member fires when the bound override is not assignable to the bound parent
  callable. That covers fewer parameters, an extra required one, `*args` in place of a positional-or-keyword
  `context`, and a renamed parameter (keyword calls). It does not compare decorators, so a classmethod `execute`,
  an instance or static `poll` and an instance `description` all bind to compatible callables and go unreported.
  A trailing default (`extra=None`) is compatible as well. So ty misses part of what Blender rejects, and reports
  renames that Blender accepts.
- A mixin's `poll(cls, ntree)` combined with `Node` gets a class-line report from upstream's inherited-conflict
  check, against the stubs' `Node.poll(cls, node_tree)`.
- The stubs have the right kinds and names (both generators). For example, builtin main declares
  `Operator.poll`/`description` as classmethods, `Node.poll(cls, node_tree: NodeTree | None)`, `UIList.draw_item`
  with 9 parameters after `self`, and `KeyingSetInfo.poll(self, context)`. So the relaxed contract can be built
  from the stub's own signature.
