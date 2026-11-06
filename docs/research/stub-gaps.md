# What does each stub gap need?

Research for [#71](https://github.com/taway1450/blender-extension-developer-suite/issues/71) (map [#67](https://github.com/taway1450/blender-extension-developer-suite/issues/67)). Evidence: `check:blender main` with Blender's own stubs (Blender main `dc491af090`, 14,077 diagnostics, `.cache/analysis/main-builtin.txt`), re-classified per gap with the bucket classifier `bucket.py`. Counts are the diagnostics a fix removes on that run. "Shipped" is `scripts/` plus the Cycles add-on; "tests+doc" is `tests/` and `doc/`.

## Where the stubs come from

Blender's own stubs are made in two steps, both in the Blender fork (`blender` branch, `doc/python_api/`):

1. **`sphinx_doc_gen.py`** runs inside Blender and writes RST from runtime introspection. Classes go through `pyclass2sphinx` (line 1977), module members through `pymodule2sphinx` (line 1326), protocol slots through `write_dunder_methods` with the tables `DUNDER_METHODS` (line 1603) and `CLASS_OVERRIDES` (lines 1670–1917).
2. **`sphinx_stub_gen.py`** turns the RST into `.pyi`. Its hand-kept tables are `CLASS_BASES` (line 1182), `SEQUENCE_ELEM_TYPES` (line 1194) and the empty `CLASS_EXTRA_MEMBERS` (line 1206). Attributes are written as `name: type = ...` by `write_attribute` (line 1672). `bpy_prop_array` / `bpy_prop_collection` get their generic overloads in `write_class` (lines 1429–1547).

Most gaps are facts the RST never carries, so the fix usually belongs in step 1 (the docs gain them too), and step 2 only when the fact is typing-only.

## Summary

| # | Gap | Fix | Location | Size | Removed (shipped / tests+doc) |
|---|-----|-----|----------|------|------|
| 1 | Classes without bases or `__init__` (freestyle, dataclasses) | Emit `__bases__` and the Python `__init__` signature | `sphinx_doc_gen.py` `pyclass2sphinx` | ~25 lines | 382 (370 / 12) |
| 2a | `BMVertSeq` / `BMEdgeSeq` / `BMFaceSeq` not iterable | `__iter__` returns `Iterator[BMxxx]` | `sphinx_doc_gen.py` `CLASS_OVERRIDES` | 3–6 lines | 42 (8 / 34) |
| 2b | `ImBufBuffer` not subscriptable | `__enter__` returns `memoryview` | `sphinx_doc_gen.py` `CLASS_OVERRIDES` | 3 lines | 52 (0 / 52) |
| 2c | `MatrixAccess` (`mat.col[i]`) yields `float` | `__getitem__` → `Vector`, `__iter__` → `Iterator[Vector]` | `sphinx_doc_gen.py` `CLASS_OVERRIDES` | 5 lines | 27 (17 / 10) |
| 3 | `bpy_prop_array` comparisons (`version <= (2, 78, 1)`) | Thick-wrapped `version` arrays are tuples: type them `tuple[int, int, int]` | `sphinx_doc_gen.py` RNA property typing | ~10 lines | 29 (29 / 0) |
| 4 | Math properties reject sequences on write | Property with a `Sequence` setter for `Vector`/`Color`/`Euler`/`Quaternion`/`Matrix` | `sphinx_stub_gen.py` `write_attribute` | ~30 lines | 163 (57 / 106) |
| 4b | Plain array properties reject sequences on write; slice assignment | Same setter for `bpy_prop_array[T]` attributes; `__setitem__` slice overload | `sphinx_stub_gen.py` | ~10 lines | 21 (12 / 9) |
| 4c | `bpy_prop_array` passed where `Sequence[float]` is wanted | `Sequence[_T]` base | `sphinx_stub_gen.py` `write_class` | 2 lines | 7 (7 / 0) |
| 5 | `bl_rna` missing | `bl_rna: Struct` on `bpy_struct` | `sphinx_doc_gen.py` (bpy_struct RST) | ~8 lines | 80 (59 / 21) |
| 6 | Module members missing | Document non-`__all__` public functions and `frozenset` / mappingproxy data | `sphinx_doc_gen.py` `pymodule2sphinx` | ~25 lines | ~30 of 42; 12 stay (private) |
| 7 | C modules without stubs | Partial stubs (`__getattr__`), `_freestyle` re-exports | new hand-written stubs copied by `sphinx_stub_gen.py` | 4 small files | 64 (60 / 4) |

Total ~900, matching the ~900 the map counts as stub gaps. All fixes go to Blender's own generator on `main`; none needs fake-bpy-module, and none needs a change to ty (gap 4 relies on behaviour ty already has, see below).

---

## 1. Classes without bases or `__init__`

**Evidence.** 151 `object.__init__` errors (124 in `scripts/freestyle`, 24 `unknown-argument` on `bpy_extras.anim_utils.BakeOptions(...)` in `bl_operators/anim.py` and `tests/python/bl_animation_bake.py`, 3 on `UILayout_Fake(layout)` in `bl_app_override`), plus 231 further freestyle diagnostics that come from the same missing bases: `Operators.select(QuantitativeInvisibilityUP1D(0))` rejected because `QuantitativeInvisibilityUP1D` is not a `UnaryPredicate1D` (`argtype-other` 135), `pyChainSilhouetteGenericIterator` has no `is_begin` / `increment` / `current_edge` (it is a `ChainingIterator`), `ViewEdge` has no `length_2d` / `time_stamp` (it is an `Interface1D`).

**Cause.** `pyclass2sphinx` (`sphinx_doc_gen.py:1977–1993`) writes `.. class:: Name` with no bases, for every class not using a `.. class::` docstring. The only trace of the hierarchy is prose ("Class hierarchy: `UnaryFunction1D` > `UnaryFunction1DDouble`", `freestyle.types.rst:2893`), which the stub generator cannot read. It also skips every `_`-prefixed key (line 1999), so a pure-Python class's `__init__` (including a dataclass's generated one) is never documented. So:

- `freestyle/types/__init__.pyi`: `class UnaryFunction1DDouble:` / `class ViewEdge:` with no base.
- `freestyle/functions/__init__.pyi:224`: `class pyDensityAnisotropyF1D: ...` (empty; the source is `class pyDensityAnisotropyF1D(UnaryFunction1DDouble)` with `__init__(self, level, integrationType=..., sampling=2.0)`, `scripts/freestyle/modules/freestyle/functions.py:286`).
- `bpy_extras/anim_utils/__init__.pyi:34`: `class BakeOptions:` with only `__eq__` / `__repr__` (source: `@dataclass class BakeOptions` with 13 fields).

`sphinx_stub_gen.py` already turns `.. class:: Name(Base)` into bases (`extract_class`, lines 434–453), so only the RST is missing them.

**Fix** in `pyclass2sphinx`:
- write `.. class:: Name(Base1, Base2)` from `value.__bases__`, leaving out `object` and bases that are not documented classes (the stub generator's type-reference check, `find_type_ref_errors`, catches a base it cannot resolve);
- for a `FunctionType` `__init__` in `value.__dict__`, write `.. method:: __init__(...)` from `inspect.signature`, the way `pyfunc2sphinx` already does for public methods. C classes keep their docstring `__init__(*args)`.

Freestyle C classes then get their real bases (`tp_base`), which is what fixes the predicate and iterator errors.

`UILayout_Fake(layout)` (3) is `bpy_struct.__new__(cls, struct)`: add `__new__(cls, struct: bpy_struct, /)` to `bpy_struct` in the same pass (a `CLASS_OVERRIDES` dunder or one RST method).

**Size:** ~25 lines in one function. **Removes:** 382 (16 of them are `Self@` attributes in freestyle iterator subclasses, currently bucketed `dynamic:self-in-mixin`, that resolve once the base is known).

## 2. Protocol gaps

### 2a. `BMFaceSeq` / `BMVertSeq` / `BMEdgeSeq` are not iterable

`bmesh/types/__init__.pyi:217`: `def __iter__(self) -> BMFaceSeq: ...` with no `__next__` on `BMFaceSeq`, so ty finds the iterator invalid. The `__iter__` return type comes from `DUNDER_METHODS["__iter__"]` (`"self"`), and the BMesh entries in `CLASS_OVERRIDES` (`sphinx_doc_gen.py:1897–1916`) override only `__getitem__`. At runtime `tp_iter` returns a `BMIter` yielding elements.

**Fix:** in each of the `BMVertSeq` / `BMEdgeSeq` / `BMFaceSeq` overrides, add `"__iter__": DunderInfo(return_type="typing.Iterator[:class:`BMVert`]")` (as `bpy_prop_collection` does, line 1824). `BMElemSeq`, `BMEditSelSeq` and `BMLayerCollection` should get the same treatment in that commit. **Size:** 3–6 lines. **Removes:** 42.

### 2b. `ImBufBuffer` cannot be subscripted

`with ibuf.buffer() as buf: buf[0, 0, 0]`, `buf.shape`, `buf.cast('B')`: the stub says `__enter__(self) -> ImBufBuffer` (`imbuf/types/__init__.pyi:26`), from `DUNDER_METHODS["__enter__"]` returning `"self"` (`sphinx_doc_gen.py:1653`). At runtime `py_imbuf_buffer_enter` returns `PyMemoryView_FromBuffer(...)` (`source/blender/python/generic/imbuf_py_api.cc:962–1024`); `ImBufBuffer` has no item access itself.

**Fix:** `("imbuf.types", "ImBufBuffer"): ClassOverrides(dunders={"__enter__": DunderInfo(return_type="memoryview")})`. **Size:** 3 lines. **Removes:** 52 (all `tests/python/bl_imbuf_py_api.py` and one doc example: subscript 12, subscript assignment 11, `shape` / `ndim` / `cast` 28, one argument).

### 2c. `MatrixAccess` (further gap)

`mathutils/__init__.pyi:175`: `MatrixAccess.__getitem__(...) -> float` and `__iter__ -> MatrixAccess`, so `matrix.col[3][1]`, `matrix.col[1].xyz = ...` and `for v in mat.row` fail. A row/column is a `Vector`.

**Fix:** `CLASS_OVERRIDES[("mathutils", "MatrixAccess")]` with `__getitem__` → `:class:`Vector``, `__iter__` → `typing.Iterator[:class:`Vector`]`, `__setitem__` value `Sequence[float]`. **Size:** ~5 lines. **Removes:** 27.

## 3. `bpy_prop_array` comparisons are a wrong type, not missing operators

All 29 diagnostics compare a `version` property: `bpy.context.preferences.version <= (2, 78, 1)` and `library.version` in the Cycles add-on's `version_update.py`. Adding `__lt__` etc. to `bpy_prop_array` would be wrong: `pyrna_prop_richcmp` returns `NotImplemented` for ordering (`bpy_rna.cc:1042–1065`), so comparing a real `bpy_prop_array` with a tuple raises `TypeError`.

These properties are not `bpy_prop_array` at runtime. `Preferences.version`, `Library.version` and `BlendData.version` are `PROP_THICK_WRAP` int arrays (`rna_userdef.cc:8313`, `rna_ID.cc:2843`, `rna_main.cc:691`), and `pyrna_math_object_from_array` returns a thick-wrapped int array as a tuple slice (`bpy_rna.cc:848–851`, `968–974`). `version_update.py:101` confirms it, using `library.version` as a dict key. These three are the only thick-wrapped int arrays (`grep PROP_THICK_WRAP makesrna/intern/*.cc`; the two float ones are `PROP_MATRIX`, so already `Matrix`).

**Fix:** type them `tuple[int, int, int]`. RNA does not expose `PROP_THICK_WRAP` to Python, so `sphinx_doc_gen.py` needs either a three-entry table keyed `(struct, property)` or a runtime probe (`type(bpy.context.preferences.version) is tuple`) applied to every non-dynamic int array of `bpy.data` / `context.preferences` / a `Library`. The table, guarded by an assertion that the probe agrees, is the smaller, reviewable option. **Size:** ~10 lines. **Removes:** 29, all shipped.

## 4. Math properties reject sequences on write

### Does ty honour a property whose setter type differs from its getter?

Yes. ty's mdtests pin both forms:

- `@property` with a wider setter: `crates/ty_python_semantic/resources/mdtest/properties.md:52–76` (getter `int`, setter `str`: `C().value = "new"` is accepted, `C().value = 1` is an `invalid-assignment`, and `C().value` reads as `int`); `mdtest/assignment/augmented.md:286–304` ("Properties with different getter and setter types": `/=` is checked against the setter, later reads use the getter).
- A data descriptor's `__set__` decides what may be assigned: `mdtest/assignment/augmented.md:306–325`.

So the map's condition ("if ty honours asymmetric property types") holds, and no ty change is needed.

### How the stubs should declare it

`write_attribute` (`sphinx_stub_gen.py:1672–1701`) writes `location: Vector = ...`. For an attribute whose converted type is one of the math types, it should write instead:

```python
@property
def location(self) -> Vector: ...
@location.setter
def location(self, value: Vector | Sequence[float]) -> None: ...
```

with setter types matching what `pyrna_py_to_array` / mathutils accept:

| Getter | Setter value |
|---|---|
| `Vector` | `Sequence[float]` |
| `Color` | `Sequence[float]` |
| `Euler` | `Sequence[float]` (an `Euler` is one) |
| `Quaternion` | `Sequence[float]` |
| `Matrix` | `Sequence[Sequence[float]]` |

(`Vector`, `Color`, `Euler`, `Quaternion` already subclass `Sequence[float]` and `Matrix` subclasses `Sequence[Sequence[float]]` through `CLASS_BASES`, so the plain `Sequence` covers them; the operator stubs already spell parameters this way, e.g. `location: Vector | Sequence[float]` in `bpy/ops/object`.) An attribute the RST marks read-only keeps the plain annotation. Rendering a property for the `bpy.props` `Annotated[...]` declarations is not needed: those are add-on classes, not RNA attributes.

Things the build ticket must check: hover / go-to-definition on such an attribute in `check:ide` (it becomes a property), and that no `ty_blender` rule reads RNA attribute declarations by annotation (the Type tag work in #67 reads `ob.data`, which is not a math type).

**Size:** ~30 lines in `write_attribute` plus a setter-type table. **Removes:** 163 `invalid-assignment` (`location` 44, `tail` / `head` 26, `color` / `color_highlight` 22, `rotation_euler` 12, `scale` 9, `rotation_quaternion`, `co`, safe-area presets, ...).

### 4b. Plain array properties (further gap)

The same asymmetry hits `bpy_prop_array[T]` attributes: `image.pixels = [...]`, `pb.lock_location = (True, True, True)`, `mat.diffuse_color = (...)`, `rotation_axis_angle = tuple(...)` (15), and slice assignment `image.pixels[:] = buffer`, `obj.color[0:3] = ...` (6): `bpy_prop_array.__setitem__` is declared for `int` only (`bpy/types/__init__.pyi:3951`). **Fix:** in the same `write_attribute` branch, a setter taking `Sequence[T]` for `bpy_prop_array[T]` attributes; in `write_class`'s `bpy_prop_array` block add `__setitem__` overloads for `int` → `_T` and `slice` → `Iterable[_T]`. **Size:** ~10 lines. **Removes:** 21. (6 more, `constraint_axis[0] = True` on `layout.operator(...)` results typed `Sequence[bool]`, belong to `operator_properties`.)

### 4c. `bpy_prop_array` is not a `Sequence` (further gap)

`Vector(self.offset)` with `offset` a `FloatVectorProperty` value: `bpy_prop_array[float]` is not assignable to `Sequence[float]` (7). **Fix:** add `bpy_prop_array` to `CLASS_BASES` with `Sequence[_T]` (it implements `__len__` / `__getitem__` / `__iter__` / `__contains__`; mathutils types get the same treatment). **Size:** 2 lines. **Removes:** 7.

## 5. `bl_rna` missing on classes

`bpy.types.Operator.bl_rna`, `ob.bl_rna.properties[...]`: no `bl_rna` anywhere in `bpy/types/__init__.pyi` (only `bl_rna_get_subclass*`). `bl_rna` is set on every RNA type at runtime (and readable from instances), but it is not in `bpy_struct.__dict__`, so `pyclass2sphinx` never sees it.

**Fix:** document it on `bpy_struct` in `sphinx_doc_gen.py`, next to the existing `bpy_struct` `CLASS_OVERRIDES` entry (line 1804): `.. attribute:: bl_rna` with `:type: :class:`Struct``, marked class attribute. `write_attribute` then writes `bl_rna: Struct = ...`, which ty reads on both the class and instances. `CLASS_EXTRA_MEMBERS[("bpy.types", "bpy_struct")]` would also work, but the docs should say it too. **Size:** ~8 lines. **Removes:** 80 (10 more are on `X | None` receivers and wait on the nullability work).

## 6. Missing module members

Of the 114 `stub-gap:module-member` diagnostics, 42 are Blender modules; the rest are user-defined `bpy.ops.*` in examples and tests (operator registration is runtime), non-Windows stdlib (`os.getuid`, `fcntl`, `termios`: a check-setup platform question), `gdb`, and genuine Blender bugs (`bpy.app.handlers.scene_update_post`, `bpy.utils.register_module`, `bpy.types.AssetData`, `bpy.ops.mesh.primitive_box_add`).

| Member | Diags | Why missing | Fix |
|---|---|---|---|
| `bpy.utils.system_resource`, `script_paths_pref`, `is_path_builtin` | 10 | Not in `bpy.utils.__all__` (`scripts/modules/bpy/utils/__init__.py:10–66`), and `pymodule2sphinx` documents only `__all__` when there is one (line 1340) | A per-module "also document" table in `sphinx_doc_gen.py`, next to `PRIVATE_ATTR_INCLUDE` (line 584), since patching `__all__` is out of scope |
| `bpy.path.extensions_image` / `_movie` / `_audio` | 9 | In `__all__`, but `frozenset` values are skipped: only `bool, int, float, str, tuple` become `.. data::` (line 1511), the rest is logged "not documenting" (1519) | Document `frozenset` and mappingproxy values, with `:type: frozenset[str]` / `types.MappingProxyType[str, ...]` from the element types |
| `imbuf.file_types` | 6 | A mappingproxy (`imbuf_py_api.cc:1802–1816`), skipped as above | Same change |
| `bpy.utils._sys_path_ensure_append`, `bpy.utils.units` (via `_bpy`) | 2 | Private | None |
| `bpy.app.handlers._extension_repos_*` | 10 | Deliberately private: "should not be considered part of the public Python API" (`bpy_app_handlers.cc:173–177`) | Leave; the 10 diagnostics in `bl_pkg` stay (or an entry in `PRIVATE_ATTR_INCLUDE` if the reviewer wants them in the stubs anyway) |

**Size:** ~25 lines. **Removes:** ~30 (incl. the `imports` of `is_path_builtin`); the 12 private ones stay by decision.

## 7. C modules without stubs

| Module | Imports failing | Runtime | Fix |
|---|---|---|---|
| `_cycles` | 33 | Cycles' C module, undocumented | Partial stub: `def __getattr__(name: str) -> Incomplete: ...` |
| `_bpy` | 19 (most in `doc/python_api/sphinx_doc_gen.py`, `scripts/modules`) | Private C module behind `bpy.utils`, `bpy.ops`, `bpy.props` | Partial stub with `__getattr__` |
| `_freestyle` | 7 | Its classes are re-exported as `freestyle.types` / `.predicates` / `.chainingiterators` / ... (`from _freestyle import ...`) | Stub re-exporting the documented classes from those modules, so names keep their types |
| `_bpy_hydra` | 5 | Hydra C module | Partial stub with `__getattr__` |

None of these has RST, so `sphinx_stub_gen.py` gains a small directory of hand-written stubs it copies into the output (or a `HANDWRITTEN_STUBS` dict of module → text). `__getattr__` stubs only remove the import errors: the names stay untyped, which is no worse than today. **Size:** 4 short files plus ~10 lines. **Removes:** 64 (60 shipped, mostly the Cycles add-on).

## Further gaps checked and left out

- **`bpy.ops.x.y.poll()` / `.idname()`** (15, `Function mode_set has no attribute poll`): operators are stubbed as plain functions. Belongs to `operator_calls` (operator objects carry `poll`, `idname`, `get_rna_type`), not to this ticket.
- **`driver_add` / `keyframe_insert` returning `FCurve | list[FCurve]`** (12): the runtime returns a list when `index == -1` *and* the property is an array, which no overload on `int` can express. Leave the union.
- **Context members not in the stubs** (`context.constraint`, `context.keymap`, set through `context_pointer_set`; `context.depsgraph`, `scene_collection` in old tests): context_members research.
- **`numpy` missing** (63 imports, plus 50 `None.__getitem__` on `pixels.shape` in doc examples): check setup (bundled site-packages), already settled in #67.
- **`attr-other` / `argtype-other` / `assign-other`** otherwise hold no further stub gaps of size: the largest groups are removed APIs in old tests (`ViewLayer.collections` 92, `BlendData.groups` 12), custom properties registered at runtime (`Object.selection_sets` 18, rigify / glTF properties), Type tag narrowing (`ID.matrix_world`, `Space.clip`), add-on internals (`VExportNode.uuid`), and `OperatorProperties.data_path` (operator_properties).
