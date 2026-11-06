# What do the stray leftovers on `main` need? (#53, map #49)

Sources: `tests/typecheck/expected/{builtin,fake-bpy-module}/main.txt` (non-inheritance lines), diagnostic messages
from a narrowed `mise run check:features main registration registration_checks operator_properties addon_preferences`
(results matched the recorded baselines), `mise run check:load main` on the five add-ons (all `ok`), the generated stubs in
`.cache/bpy-stubs{,-builtin}/main`, Blender source in `.cache/blender-src/main` (fork checkout, upstream ancestry), the
`blender` submodule (branch `stub-generator`) and `fake-bpy-module` submodule (branch `stub-generator`).

## Table

| Line (add-on) | Generator | Cause | Recommended fix, and where |
| --- | --- | --- | --- |
| `bpy.types.VIEW3D_MT_object.append(draw_menu)`, `.append(draw_leaked_menu)  # ty: ignore[blender-unregister-mismatch]`, `.remove(draw_menu)` (`regchk_unregister_leak`) | builtin | `Module bpy.types has no member VIEW3D_MT_object`. `Menu.append/prepend/remove` **are** in the builtin stubs, with the right type `Callable[[Self, Context], None]`. What is missing is the class: `_rna_info.rna_id_ignore` drops every struct id containing `_MT_`, `_PT_`, `_HT_` (also `_OT_`, `_KSI_`), so no bundled menu, panel or header reaches the RST or the stubs (`_UL_` lists are not filtered, so 34 of them are there). | **Stub fix, Blender fork (`blender` submodule, `stub-generator`, main only).** In the stub pipeline, keep the `_MT_` / `_PT_` / `_HT_` structs that Blender's bundled UI registers (≈491 menus, 1049 panels, 27 headers per fake's list) and emit each as a bare subclass (`class VIEW3D_MT_object(Menu): ...`). Not a checker change: that `bpy.types.VIEW3D_MT_object` exists is a stub fact. |
| same three lines | fake-bpy-module | `Expected (Context, /) -> None, found def draw_menu(self, context)`. Blender's docstring (`_bpy_types.py:1255-1256`, upstream commit `ca3b23ae350`) says `Callable[[Self, :class:Context], None]`. fake's `parse_callable_elements` refines the parameter list with `parse_multiple_data_type_elements`, which drops any element it can't refine (`data_type_refiner.py:798-803`). `Self` is unknown, so `[Self, Context]` becomes `[Context]`. Both `_bpy_types._GenericUI.append` and `bpy.types.Menu.append` are affected. | **Stub fix, fake-bpy-module (`stub-generator`).** Refine a bare `Self` to `typing_extensions.Self`, as `SelfRewriter` already writes it. Also make `parse_callable_elements` put `typing.Any` in a parameter slot it can't refine, so the arity is kept, rather than dropping the slot. |
| (the failing `registration_checks` marker, 36/37) | both | The marker on line 65 (`# ty: ignore[blender-unregister-mismatch]`) fails only because the line has another diagnostic (`summary.md`: "FAIL … Module `bpy.types` has no member `VIEW3D_MT_object`"). The rule itself fires. | Fixed by the two stub fixes above. No checker work. |
| `keyconfig = bpy.context.window_manager.keyconfigs.addon` (`opprops_sinks`) | both | `Attribute keyconfigs is not defined on None in union WindowManager \| None`. `Context.window_manager` has no `PROP_NEVER_NULL` (`rna_context.cc:263-266`), so both generators add `\| None`, like every other `Context` pointer (`preferences`, `scene`, `blend_data`, …). `keyconfigs.addon` (`KeyConfig \| None`) is really None in background mode, and the add-on already checks that. | **Test-add-on change.** Guard it the way `prefs_ext/ui/panel.py:22` already guards `context.preferences`: `wm = bpy.context.window_manager` / `if wm is not None and (keyconfig := wm.keyconfigs.addon) is not None:` (or two plain `if`s). ty's behaviour is correct for the documented API, and the line is add-on code, not a marker. A Blender-source change (adding `PROP_NEVER_NULL` to `Context.window_manager`) would be an RNA change, not a stub-generator fix, and it would single out one of ~20 nullable `Context` pointers. Not recommended. |
| `if cls.is_registered:` (`reg_conditional`) | builtin only | `has no attribute is_registered` on the union of the `Operator` subclasses. At runtime `is_registered` is a **metaclass property** (`_bpy_types.py:977-981`, `_RNAMeta`) of Operator, PropertyGroup, KeyingSetInfo, USDHook, AddonPreferences, Panel, UIList, Header, Menu, AssetShelf, FileHandler, NodeTree, Node, NodeSocket, NodeTreeInterfaceSocket and RenderEngine. Neither generator models metaclasses (`sphinx_doc_gen.py` documents only the class's own members). fake passes only because a hand-written mod adds `is_registered: bool` to `Operator` and `Panel` (`src/mods/common/analyzer/append/bpy.types.mod.rst:19-29`). | **Stub fix, Blender fork builtin generator (main only).** Emit `class _RNAMeta(type)` with `@property def is_registered(cls) -> bool` (plus a `_RNAMetaPropGroup` for the PropertyGroup/Node family), and `metaclass=_RNAMeta` on each class whose `type(py_class)` is one of them. That is the runtime model: class-only, not visible on instances. Side effect, for #51/#52: `check_inh_bases.py`'s `WithAbc(AbcMixin, Operator)  # ty: ignore[conflicting-metaclass …]  # oracle-skip: the stubs do not declare Blender's metaclass` then gets its `conflicting-metaclass`, which matches the runtime `TypeError`. Optional: give fake the same model instead of its two-class mod. |
| `importlib.reload(reloaded)` under `if "bpy" in locals():` (`reg_imports`) | both | `Name reloaded used when not defined`. ty can't know that the true branch only runs when Blender re-executes the module in its old `__dict__` (`addon_utils.py:435-438`, `647-652`: `importlib.reload(mod)`), where the earlier `from . import reloaded` binding still exists. It is Blender's standard idiom (10 bundled add-ons use `if "bpy" in locals():`). The same diagnostic shows in Blender's own `io_mesh_uv_layout` / `bl_pkg` in `.cache/ty-results/main.txt`. | **Checker change.** A predicate in `ty_blender` recognises the reload guard: a module-level `if "<name>" in locals():` in an add-on module. A file under `dedicated/blender/` gives a name that is unbound in that branch the module's public (global) type of that symbol, when the module binds it elsewhere. That needs one one-line hook where `infer_name_load` reports `unresolved-reference`. Not a test-add-on change: the markers test this idiom on purpose. Fallback if the hook proves invasive: a named exception (stock ty limitation, the code is correct at runtime). |
| `LIST_CLASSES += [REG_LOOP_OT_extended]` (`reg_loop`) | both | `+= is not supported between list[<class REG_LOOP_OT_appended> \| <class REG_LOOP_OT_list>] and list[<class REG_LOOP_OT_extended>]`. ty infers the unannotated list's element type from the literal and the later `.append` (but not from `+=`), and `list` is invariant. This is plain Python typing: pyright and mypy reject it too (they would already reject the `.append`). Nothing about it is Blender. | **Test-add-on change.** `LIST_CLASSES: list[type[Operator]] = [REG_LOOP_OT_list]`. The walk reads the value of an `AnnAssign` exactly as it does an `Assign` (`walk.rs:587-597`) and handles a module-level `+=` (`walk.rs:598-604`), so the registration markers keep testing the same variants. Rerun `check:features main registration` to confirm. |
| `self.layout.…` in `opprops_idnames`, `reg_autoload/panels.py`, `prefs_ext/ui/panel.py`; `layout.operator(…)` ×5 via `layout = self.layout` in `opprops_sinks` | both | `UILayout \| None`. All are inside `def draw(self, context)` overrides of `Panel`. | **#50** (narrowing in draw callbacks). Constraint for #50: narrow the *type of the `self.layout` expression*, not a syntactic `self.layout.<x>` pattern, so that the alias `layout = self.layout` in `opprops_sinks` is covered. No line is left over. |

No other non-inheritance line is in either `main.txt`. `main.ide.md` has no non-inheritance failure (`main.progress.md`: every IDE column outside inheritance is full).

Order: the test-add-on changes (`reg_loop`, `opprops_sinks`) first, then the fake refiner fix and the Blender-fork generator fixes (UI classes, metaclass), then the reload-guard checker hook. None of these needs a named exception on `main`. On **5.2** the same lines stay as follows: the test-add-on changes and the reload hook also clear them there. The stub-blocked ones (`VIEW3D_MT_object` ×3 on both, `is_registered` on builtin) stay 5.2 named exceptions, per the map.

## Evidence

### `regchk_unregister_leak`: builtin

- Diagnostic: `__init__.py:64:5: error[unresolved-attribute] Module bpy.types has no member VIEW3D_MT_object` (lines 64, 65, 69).
- `.cache/bpy-stubs-builtin/main/bpy/types/__init__.pyi:15096` `class Menu(bpy_struct)` has `append(cls, draw_func: Callable[[Self, Context], None])`, `prepend` and `remove`. No `_MT_`, `_PT_` or `_HT_` class is in the file (0 matches). There are 34 `_UL_` classes. There is no module `__getattr__`.
- `blender/scripts/modules/_rna_info.py:51-65` `rna_id_ignore` returns True for ids containing `_OT_`, `_MT_`, `_PT_`, `_HT_`, `_KSI_`, and `BuildRNAInfo` (`:863-866`) skips them. `module_name` (`:156-162`) is `"bpy.types"` for these classes (`hasattr(bpy.types, id)`), so the later `USE_ONLY_BUILTIN_RNA_TYPES` filter (`sphinx_doc_gen.py:2478-2498`) would keep them. `rna_id_ignore` is the only thing in the way.
- Runtime: `check:load main registration_checks/regchk_unregister_leak` → `ok`. `bpy.types.VIEW3D_MT_object.append(two_arg_func)` works.

### `regchk_unregister_leak`: fake-bpy-module

- Diagnostic: `Argument to bound method _GenericUI.append is incorrect: Expected (Context, /) -> None, found def draw_menu(self, context) -> Unknown`.
- `.cache/bpy-stubs/main/_bpy_types-stubs/__init__.pyi:247-249`: `class _GenericUI: @classmethod def append(cls, draw_func: collections.abc.Callable[[Context], None])`. `bpy-stubs/types/__init__.pyi:69571` `Menu.append(cls, draw_func: Callable[[Context], None] | None)`.
- Source docstring: `.cache/blender-src/main/scripts/modules/_bpy_types.py:1247-1257` `:type draw_func: Callable[[Self, :class:`Context`], None]`, from upstream commit `ca3b23ae350` "Fix: doc-string for `_bpy_types.py:_GenericUI.append/prepend/remove`" (Ref !165002). Runtime call: `func(self, context)` (`:1212`).
- `fake-bpy-module/src/fake_bpy_module/transformer/data_type_refiner.py:794-803`: `parse_multiple_data_type_elements` appends only elements whose refinement is non-empty. `:820-842` `parse_callable_elements` uses it for the parameter list.
- Side notes (no diagnostic here): fake declares `bpy.types.VIEW3D_MT_object: bl_ui.space_view3d.VIEW3D_MT_object` (an *instance*, `types/__init__.pyi:152107`), but at runtime it is the class. The `| None` on `Menu.append`'s `draw_func` is wrong too.
- Failing marker: `.cache/typecheck-results/main/builtin/summary.md:50` "FAIL `…regchk_unregister_leak/__init__.py:65` … Module `bpy.types` has no member `VIEW3D_MT_object` [unresolved-attribute]". README: "On a marker's line it also fails the marker".

### `opprops_sinks`: `keyconfigs.addon`

- Diagnostic (both): `Attribute keyconfigs is not defined on None in union WindowManager | None` (column 17 = `.keyconfigs`).
- `.cache/blender-src/main/source/blender/makesrna/intern/rna_context.cc:263-266` defines `window_manager` with `PROP_NONE` and no never-null flag. Every other `Context` pointer is the same (`blend_data`, `preferences`, `scene`, …: all `X | None` in the builtin stub). `rna_wm.cc:2927` `addon` `KeyConfig` is None in background mode, so the add-on's `if keyconfig is not None` is right.
- Precedent in the suite: `addon_preferences/prefs_ext/ui/panel.py:22` `if context.preferences is not None:`. Blender's own docs example `bpy.types.KeyMaps.1.py:38` gets the same diagnostic (`.cache/ty-results/main.txt`).
- Runtime: `check:load main operator_properties/opprops_sinks` → `ok`. So `window_manager` is not None at register time. That does not make the stub fact `never None`.

### `reg_conditional`: `cls.is_registered`

- Diagnostic (builtin): `Object of type <class REG_CONDITIONAL_OT_environment> | … has no attribute is_registered`.
- `.cache/blender-src/main/scripts/modules/_bpy_types.py:977-985`: `class _RNAMeta(type): @property def is_registered(cls): return "bl_rna" in cls.__dict__`. Metaclass users: `:1100, 1160, 1164, 1168, 1172, 1293, 1297, 1301, 1305, 1495, 1499, 1503, 1507, 1529, 1558, 1619`.
- The builtin stub has `is_registered` only on `Property` (an RNA field, `:3631`). Neither generator emits `metaclass=` (no match in `sphinx_stub_gen.py` / `sphinx_doc_gen.py`).
- fake: `bpy-stubs/types/__init__.pyi:85957` `Operator.is_registered: bool` and `:86850` on `Panel`, both from the mod `append/bpy.types.mod.rst`. `_bpy_types-stubs` `class _RNAMeta: is_registered: Any` (not a metaclass).
- Runtime: `check:load main registration/reg_conditional` → `ok` (`unregister()` evaluates `cls.is_registered`).

### `reg_imports`: reload idiom

- Diagnostic (both): `Name reloaded used when not defined`.
- Blender reloads add-on modules in place: `scripts/modules/addon_utils.py:435-438` (module changed on disk) and `:647-652` (`reset_all(reload_scripts=True)`, F8). `"bpy" in locals()` is True only then. Bundled users: `addons_core/{bl_pkg,io_anim_bvh,io_curve_svg,io_mesh_uv_layout,io_scene_fbx,io_scene_gltf2,pose_library}/…`.
- `.cache/ty-results/main.txt` shows the same class of diagnostic on Blender's own add-ons (`io_mesh_uv_layout/__init__.py:26` `export_uv_eps used when not defined`).
- Marker dependency: `check_reg_imports.py` asserts `bpy.ops.reg_imports.reloaded()`, and README row "the `importlib.reload` pattern". So the idiom is what's being tested.

### `reg_loop`: `+=`

- Diagnostic (both): `Operator += is not supported between objects of type list[<class REG_LOOP_OT_appended> | <class REG_LOOP_OT_list>] and list[<class REG_LOOP_OT_extended>]`.
- The walk does not depend on ty's inferred element type (the marker for `REG_LOOP_OT_extended` passes, 40/40, although ty's type omits it). `walk.rs:587-597` treats `AnnAssign` with a value like `Assign`, so an annotation doesn't change the walk.
- Runtime: `check:load main registration/reg_loop` → `ok`.

### `self.layout` lines (handed to #50)

- Messages: `Attribute operator/prop/operator_menu_enum/operator_enum is not defined on None in union UILayout | None` at `prefs_ext/ui/panel.py:23`, `opprops_idnames/__init__.py:40-41`, `opprops_sinks/__init__.py:52-56` (receiver is the local `layout = self.layout`, `:51`), `reg_autoload/panels.py:12`. Each is in a `Panel.draw(self, context)` override.
