# How are the class-level inheritance rules detected? (#52)

Research for map #49. Fork paths are relative to `ty-blender/ruff-blender/crates/` (branch `blender`, at
`b4135144e1`); Blender paths are relative to `.cache/blender-src/main/`. Recorded results are from
`tests/typecheck/expected/<generator>/main.txt`, with full messages from `.cache/typecheck-results/main/*/summary.md`.

## Short answer

All 26 class-level lines are **the same on both generators, and the same again on 5.2**. None of these rules
depends on the stubs (see the evidence section).

| Rule / line | Kind | Recommended design | Seam |
| --- | --- | --- | --- |
| `blender-registered-base` | registration, **presence** | New `Rule::RegisteredBase` in `registration_findings`. For each pair of `Event::RegisterClass` events of the `register()` walk where one class is in the other's MRO (`mro_classes(..).skip(1)`), report the subclass, unless it derives from `PropertyGroup` or the two events are on exclusive branches (`path.is_exclusive_with`). Order and `exact` are not needed ("whatever the order"). The walk does not need to be complete: unseen registrations could only add pairs. The report goes on the subclass's class name (the `Site` held by `AddonClasses.classes`), so a subclass defined outside the add-on is dropped like every other finding. | `ty_python_semantic/src/types/dedicated/blender/registration_checks.rs:38-46` (enum), `:75-79` (add `checks.registered_bases(register, &classes)`), `:524` (`registered_classes`); `lints.rs:37-170` (declare), `:172` (register), `:238-246` (map the rule) |
| `blender-missing-callback` | registration, **presence** (same policy as `blender-invalid-idname`) | New `Rule::MissingCallback`, checked on the classes that `idnames` checks: the registered ones, and when the walk gave up, every class that may be registered minus the bases (`registration_checks.rs:349-350`; move that predicate into a shared `AddonClasses` method). For each required callback of the class's root (from the #51 table: `Panel`/`Menu`/`Header`/`NodeSocket` → `draw`), it is **present** when any class in `mro_classes(class)` that is **not** a `bpy.types` class binds the name (`own_binding`). The stubs declare `draw` on the roots themselves, so they must not count. Mixins later in the MRO and `bl_ui` stub classes such as `VIEW3D_MT_object` do count, because Blender looks the name up with `PyObject_GetOptionalAttrString(py_class, …)` along the whole MRO. | same as above, plus `classes.rs:63` (`mro_classes`), `:112` (`own_binding`), `symbols.rs:83` (`is_bpy_types_class`) |
| `blender-mixin-order` | class shape, per file | For each class in a first-party file: walk its MRO. For each `bpy.types` class `R` in it, take the names the #51 table says Blender's **Python** class for `R` defines. A name is lost when the first class in the MRO that binds it is `R` (or a stand-in for it), while a later non-`bpy.types` class (a mixin) binds it too. Report once on the class name, naming the mixin and the name. Use the table, not the stubs: they declare RNA callbacks (`Operator.poll`, `Menu.draw`) next to the Python names, and `INH_MIXINS_OT_poll_last(Operator, PollMixin)` must stay silent. No registration condition. | New `dedicated/blender/class_rules.rs`, called from the `ClassDef` arm of the existing per-file visitor (`rules.rs:427-433`, next to `check_operator_mixins` at `:431`), which already visits every class of a first-party file through `file_diagnostics` (`lints.rs:220`). No upstream edit. |
| `blender-invalid-base` | class shape, per file | Take the `bpy.types` classes in the MRO. The first one is the most derived; if any other `bpy.types` class in the MRO is not in that first class's MRO, the class has two Blender bases. The check uses only `bpy.types`, so mixins from `bpy_extras` / `bl_ui` (`ImportHelper`, `AssetBrowserPanel`) never count, and the extra bases fake-bpy-module adds (`Object(ID, bpy_struct)`) form one chain. Report on the class name. | same `class_rules.rs` |
| `inh_bases/__init__.py:10` `invalid-attribute-override` | ty's own, a consequence of the two bases | `blender-invalid-base` **replaces** ty's inherited-conflict checks on that class, as `blender-invalid-override` replaces `invalid-method-override` (one rule per line). This needs a one-line hook: `&& !crate::types::blender::has_invalid_bases(db, class)` added to the condition at `ty_python_semantic/src/types/overrides.rs:92`, which guards `check_inherited_conflicts`. The predicate is the one `class_rules.rs` reports. The alternative, re-marking the line `# ty: ignore[blender-invalid-base, invalid-attribute-override]`, is allowed by the map, but a user would then get several diagnostics for one mistake (`Operator`+`Menu` conflicts on more names). | `overrides.rs:92` (hook), `mod.rs:48-64` (re-export) |
| `check_inh_bases.py:41` `WithAbc` (unused `conflicting-metaclass`) | Blender fact the stubs lack | In `class_rules.rs`, emit ty's **own** `CONFLICTING_METACLASS` (`types/diagnostic.rs:262`, `pub(crate)`) when a class has a `bpy.types` base, and a non-Blender base whose metaclass (`ClassLiteral::metaclass`, `types/class.rs:729`) is not `type`. In Blender every registrable root has `_RNAMeta` or `_RNAMetaPropGroup`. Only emit it while ty's metaclass for the Blender base is still `type`, so a stub that declares the metaclass later takes over without a duplicate. No upstream edit. | `class_rules.rs` |
| `check_inh_bases.py:49` `WithSlots` (unused `instance-layout-conflict`) | Blender fact the stubs lack | Likewise, emit `INSTANCE_LAYOUT_CONFLICT` (`diagnostic.rs:352`) when a non-Blender base has a disjoint base (`nearest_disjoint_base`, `types/class.rs:1644`, visible inside `crate::types`) and the Blender base has none in ty's eyes. In Blender, `bpy_struct` is a C type with its own layout. | `class_rules.rs` |
| `inh_chains` ×2, `inh_registered_base` ×2 `unresolved-attribute` | **not** inherited properties | All four are `self.layout.<x>(…)` in a `draw` override: "Attribute `operator` is not defined on `None` in union `UILayout \| None`". The settled `self.layout` narrowing (#50) fixes them. **Constraint for #50:** in `inh_chains` the `draw` belongs to **unregistered** bases (`INH_CHAINS_PT_base(Panel)`, `INH_CHAINS_MT_base(Menu)`), so the narrowing must key on "overrides `Panel`/`Menu` `draw`", not on registration. The inherited properties along the chain already pass (`check_inh_chains.py` 5/5). | #50 |
| `inh_mixins` `assert_type(context, Context)` / `(event, Event)` | override typing | `invoke` of the unregistered `INH_MIXINS_OT_base(Operator)` is unannotated, so the parameters are `Unknown`. This is #50's typing of an unannotated override. | #50 |
| `inh_mixins` `NodeFirst` / `NodeLast` `invalid-method-override` | ty's inherited **method** conflict | "Base classes for class … define method `poll` incompatibly". `TreePollMixin.poll(cls, ntree)` vs `Node.poll(cls, node_tree: …)`: a renamed positional parameter, which the spec says is no error. **Note for #51:** these come from `check_inherited_method_conflict` (`overrides.rs:348`, called at `:270-283`), **not** from `check_override`. #51's renamed-parameter exemption has to reach that path too. It then clears both lines, so `blender-mixin-order` needs no suppression of its own on `NodeLast`. | #51 |

### What each class-level rule needs from #51's table

- **`blender-missing-callback`:** the "required callbacks" rows, per registrable root (`Panel`, `Menu`, `Header`,
  `NodeSocket` → `draw`). These are the RNA functions that are `is_registered` and not `is_registered_optional`.
- **`blender-mixin-order`:** per `bpy.types` class name, the names its Python class in `scripts/modules/_bpy_types.py`
  defines, **including what it inherits from Python-only mixins** (`_GenericUI` gives `Panel`, `Menu`, `Header` and
  `UIList` the names `is_extended`, `append`, `prepend`, `remove`, `_dyn_ui_initialize`), and **dunders**
  (`Operator.__getattribute__`, `__setattr__`, `__delattr__`, and the same on `Gizmo`). The table is keyed by the
  `bpy.types` name found in the MRO, so `ShaderNode` / `CompositorNode` / `TextureNode` / `GeometryNode` each carry
  their own `poll`, and the rule takes the union along the MRO. Left open for #51: whether `bpy_struct`'s C methods
  (`get`, `keys`, `as_pointer`, …) belong in the table. They also win over a later mixin, but the spec says
  "Python base classes".
- `blender-invalid-base` and `blender-registered-base` need no table: `bpy.types` membership (`symbols.rs:83`) and
  `derives_from(.., &["PropertyGroup"])` (`classes.rs:24`) are enough.

### Markers that move (builtin = fake-bpy-module = 5.2, line refs into `expected/*/main.txt`)

| Slice | Lines cleared | Count |
| --- | --- | --- |
| `blender-missing-callback` | 18, 22, 25, 30 (`generated/inh_invalid_{header,menu,panel,socket}_no_draw`) | 4 |
| `blender-registered-base` | 101, 102, 104, 106, 107, 108 (`inh_registered_base`), 37 (`inh_inherited_idname`: `blender-duplicate-registration` already fires there) | 7 |
| `blender-invalid-base` + `overrides.rs:92` hook | 31, 32 (`inh_bases/__init__.py:10`) | 2 |
| metaclass / layout in `class_rules.rs` | 33, 34 (`check_inh_bases.py:41,49`) | 2 |
| `blender-mixin-order` | 40, 41 (`keywords_last`, `append_last`); 43 only together with #51 (44 is the same line) | 2 + 1 |
| #50 (`self.layout`) | 35, 36, 103, 105 | 4 |
| #50 (override typing) | 38, 39 | 2 |
| #51 (renamed-parameter exemption on the inherited-conflict path) | 42, 44 | 2 |

That is 26 of 26. The bare run is unaffected: every new marker that passes needs the checker. The oracle is
unaffected too: `blender-*` markers and the two `oracle-skip` lines are not judged by it, and their `oracle-skip`
reasons stay true because the stubs still declare neither the metaclass nor the layout. The first build should
check the `check:features` diff of the **other** features for new `blender-registered-base` /
`blender-mixin-order` hits. This research did not run them.

### Interactions to settle in #54 (small)

- On a class with two Blender bases, `blender-mixin-order` stays silent (one rule per line).
- A registered `Panel` that is both missing `draw` and a registered base gets both rules: they are different causes,
  but they share a line.
- `WithAbc` / `WithSlots` also carry `blender-unregistered-class`, which already fires (the
  `unused-ignore-comment` names only the stock rule).

## Evidence

### What fails today (`.cache/typecheck-results/main/builtin/summary.md:191-205`, fake identical)

- `inh_bases/__init__.py:10`: "Incompatible inherited attribute `bl_options`: `Operator.bl_options` is incompatible
  with `Panel.bl_options` [invalid-attribute-override]", plus the unknown `blender-invalid-base`. Emitted by
  `attributes::check_inherited_conflict` (`ty_python_semantic/src/types/overrides/attributes.rs:942`, message at
  `:1013`), called from `check_inherited_conflicts` (`overrides.rs:170`), which `check_class` (`overrides.rs:78`) runs
  under the `:92` condition. Upstream calls `check_class` at `types/infer/builder/post_inference/static_class.rs:1130`.
- `check_inh_bases.py:41`: "Unused `ty: ignore` directive: 'conflicting-metaclass'". `check_inh_bases.py:49`: the same
  for 'instance-layout-conflict'. Neither stub set declares a metaclass, `__slots__` or `@disjoint_base` on `bpy_struct`
  or the roots (`.cache/bpy-stubs-builtin/main/bpy/types/__init__.pyi:16`, `class bpy_struct:`;
  `.cache/bpy-stubs/main/bpy-stubs/types/__init__.pyi:3363`, `class bpy_struct[_GenericType1]:`). ty derives disjoint
  bases only from `@disjoint_base` or non-empty `__slots__` (`types/class/static_literal.rs:740-755`), and the
  metaclass from the bases (`static_literal.rs:1238`).
- `inh_chains/__init__.py:59,73` and `inh_registered_base/__init__.py:53,64`: "Attribute `operator`/`label` is not
  defined on `None` in union `UILayout | None`". The same error appears in `opprops_*` and `reg_autoload`, which is
  #50's settled narrowing.
- `inh_mixins/__init__.py:34,35`: `Unknown` for `context` / `event` in the unannotated `invoke` (#50).
- `inh_mixins/__init__.py:131,136`: "Base classes for class … define method `poll` incompatibly" (message at
  `types/diagnostic.rs:5307`, from `check_inherited_method_conflict`, `overrides.rs:348`). Builtin stub:
  `def poll(cls, node_tree: NodeTree | None) -> bool` (`bpy-stubs-builtin/main/bpy/types/__init__.pyi:4484`). Mixin:
  `def poll(cls, ntree)`.
- Every other line: `ignore-comment-unknown-rule` for the four `blender-*` rules, which do not exist yet
  (`lints.rs:37-170` declares 15 lints, none of them).

### Blender facts (primary source)

- Required callbacks: `bpy_class_validate_recursive` (`source/blender/python/intern/bpy_rna.cc:9712`) looks each
  `FUNC_REGISTER` function up with `PyObject_GetOptionalAttrString(py_class, …)`, an MRO-wide `getattr`, and raises
  "expected %s, %s class to have an \"%s\" attribute" (`:9758`) unless it is `FUNC_REGISTER_OPTIONAL`.
- Registered base: `pyrna_register_class` (`bpy_rna.cc:10546`) detaches the old Python class ("Old srna still
  references us", `:10695`). Its `--debug-python` warning checks both base and subclass ("references and already
  registered base-class", `:10600`, and "sub-class", `:10609`), so the order does not matter. That supports reporting
  the subclass whatever the order. `PropertyGroup` is excluded on the runtime evidence in
  `features/inheritance/README.md` (A → B → C keeps working).
- Python bases (`scripts/modules/_bpy_types.py`): `_StructRNA = _types.bpy_struct` (`:10`), `_StructMetaPropGroup =
  _types.bpy_struct_meta_idprop` (`:11`); `class _RNAMeta(type)` (`:977`); `Operator(_StructRNA, metaclass=_RNAMeta)`
  (`:1100`) with `as_keywords` (`:1124`) and the three attribute dunders; `_GenericUI` (`:1176`) with `is_extended`
  (`:1232`), `append` (`:1247`), `prepend`, `remove`; `Panel`/`UIList`/`Header`/`Menu(_StructRNA, _GenericUI,
  metaclass=_RNAMeta)` (`:1293-1305`); `Menu.draw_preset` (`:1445`), `path_menu`, `draw_collapsible`;
  `Node(_StructRNA, metaclass=_RNAMetaPropGroup)` (`:1507`) with `poll(cls, ntree)` (`:1511`), and the `poll` of each
  `NodeInternal` subtype (`:1567-1609`). Every root has a non-`type` metaclass and a C base with its own layout,
  which explains the `ABC` (metaclass conflict) and `__slots__` (lay-out conflict) failures.
- `Operator` defines no `poll` in Python, so `INH_MIXINS_OT_poll_last(Operator, PollMixin)` is fine at runtime and
  the stubs' `Operator.poll` must not drive `blender-mixin-order`.

### Why these seams (the map's settled decisions)

- #29 (`gh issue view 29`, comment): one add-on-level `registration_findings`, reported per file. "An incomplete walk
  proves presence, never absence." Registered-base and missing-callback are both presence findings: they report what
  the walk saw and need no completeness. Missing-callback copies `blender-invalid-idname`'s rule: when the walk gave
  up, it checks every class that may be registered except the bases (`registration_checks.rs:345-351`). Exclusive
  branches come from `BranchPath` (`walk.rs:141-150`).
- `file_diagnostics` (`lints.rs:194-228`, hooked at `types.rs:263`) already runs the per-file, first-party property
  rules (`check_properties`, `rules.rs:59`), whose visitor reaches every `ClassDef` (`rules.rs:427`). The class-shape
  rules ride on it with **no new upstream hook**. The only upstream edit is the one-line `overrides.rs:92` condition.
  This follows the existing pattern of `exempts_attribute_override` (`overrides/attributes.rs:618` →
  `member.rs:377`).
- Emitting ty's stock `conflicting-metaclass` / `instance-layout-conflict` from Blender code is better than the two
  alternatives:
  - **Stub fixes** (`metaclass=` on the roots, `@disjoint_base` on `bpy_struct` in both stub forks) would make
    stock ty pass the markers on the bare stubs. They would then have to become `# bare-ok` guards, and 5.2 would
    stay a named exception, because the map does not backport stub fixes.
  - **Hooks in `as_disjoint_base` / `try_metaclass`** (upstream `static_literal.rs:740` and `:1238`) would change
    the types of every Blender class (metaclass attribute lookups, `type(cls)`), a far larger blast radius than two
    diagnostics.
