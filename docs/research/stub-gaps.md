# What does each stub gap need?

Research note, 2026-11-06, for [#71](https://github.com/taway1450/blender-extension-developer-suite/issues/71) (map [#67](https://github.com/taway1450/blender-extension-developer-suite/issues/67)). Trimmed on 2026-11-18 to the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

Blender citations are at main `dc491af090`. Every gap below has landed in Blender's own generator on the fork; none needed fake-bpy-module, and none needed a change to ty (gap 4 relies on behaviour ty already has).

## Where the stubs come from

Blender's own stubs are made in two steps, both in the Blender fork (`blender` branch, `doc/python_api/`):

1. **`sphinx_doc_gen.py`** runs inside Blender and writes RST from runtime introspection. Classes go through `pyclass2sphinx`, module members through `pymodule2sphinx`, protocol slots through `write_dunder_methods` with the tables `DUNDER_METHODS` and `CLASS_OVERRIDES`.
2. **`sphinx_stub_gen.py`** turns the RST into `.pyi`. Its hand-kept tables are `CLASS_BASES`, `SEQUENCE_ELEM_TYPES` and `CLASS_EXTRA_MEMBERS`. Attributes are written as `name: type = ...` by `write_attribute`. `bpy_prop_array` / `bpy_prop_collection` get their generic overloads in `write_class`.

Most gaps are facts the RST never carries, so the fix usually belongs in step 1 (the docs gain them too), and step 2 only when the fact is typing-only.

## 1. Classes without bases or `__init__`

**Cause.** `pyclass2sphinx` writes `.. class:: Name` with no bases, for every class not using a `.. class::` docstring. The only trace of the hierarchy is prose ("Class hierarchy: `UnaryFunction1D` > `UnaryFunction1DDouble`" in `freestyle.types.rst`), which the stub generator cannot read. It also skips every `_`-prefixed key, so a pure-Python class's `__init__` (including a dataclass's generated one) is never documented. So freestyle classes lost their bases (`QuantitativeInvisibilityUP1D` is not a `UnaryPredicate1D`, `ViewEdge` not an `Interface1D`), Python subclasses such as `pyDensityAnisotropyF1D` came out empty, and the dataclass `bpy_extras.anim_utils.BakeOptions` had no fields.

`sphinx_stub_gen.py` already turns `.. class:: Name(Base)` into bases (`extract_class`), so only the RST is missing them.

**Fix** in `pyclass2sphinx` (step 1): write `.. class:: Name(Base1, Base2)` from `value.__bases__`, leaving out `object` and bases that are not documented classes; for a `FunctionType` `__init__` in `value.__dict__`, write `.. method:: __init__(...)` from `inspect.signature`. C classes keep their docstring `__init__(*args)`. Freestyle C classes then get their real bases (`tp_base`). `UILayout_Fake(layout)` is `bpy_struct.__new__(cls, struct)`, so `bpy_struct` gets `__new__(cls, struct: bpy_struct, /)` in the same pass.

## 2. Protocol gaps

### 2a. `BMFaceSeq` / `BMVertSeq` / `BMEdgeSeq` are not iterable

The stub said `def __iter__(self) -> BMFaceSeq: ...` with no `__next__` on `BMFaceSeq`, so ty finds the iterator invalid. The `__iter__` return type comes from `DUNDER_METHODS["__iter__"]` (`"self"`), and the BMesh entries in `CLASS_OVERRIDES` override only `__getitem__`. At runtime `tp_iter` returns a `BMIter` yielding elements. **Fix:** an `__iter__` override returning `Iterator[BMVert]` etc., as `bpy_prop_collection` has; `BMElemSeq`, `BMEditSelSeq` and `BMLayerCollection` get the same.

### 2b. `ImBufBuffer` cannot be subscripted

`with ibuf.buffer() as buf: buf[0, 0, 0]`, `buf.shape`, `buf.cast('B')`: the stub said `__enter__(self) -> ImBufBuffer`, from `DUNDER_METHODS["__enter__"]` returning `"self"`. At runtime `py_imbuf_buffer_enter` returns `PyMemoryView_FromBuffer(...)` (`source/blender/python/generic/imbuf_py_api.cc:962–1024`); `ImBufBuffer` has no item access itself. **Fix:** a `CLASS_OVERRIDES` entry with `__enter__` returning `memoryview`.

### 2c. `MatrixAccess`

`MatrixAccess.__getitem__(...) -> float` and `__iter__ -> MatrixAccess`, so `matrix.col[3][1]`, `matrix.col[1].xyz = ...` and `for v in mat.row` failed. A row/column is a `Vector`. **Fix:** `__getitem__` → `Vector`, `__iter__` → `Iterator[Vector]`, `__setitem__` value `Sequence[float]`.

## 3. `bpy_prop_array` comparisons are a wrong type, not missing operators

The comparisons all compare a `version` property: `bpy.context.preferences.version <= (2, 78, 1)` and `library.version` in the Cycles add-on's `version_update.py`. Adding `__lt__` etc. to `bpy_prop_array` would be wrong: `pyrna_prop_richcmp` returns `NotImplemented` for ordering (`bpy_rna.cc:1042–1065`), so comparing a real `bpy_prop_array` with a tuple raises `TypeError`.

These properties are not `bpy_prop_array` at runtime. `Preferences.version`, `Library.version` and `BlendData.version` are `PROP_THICK_WRAP` int arrays (`rna_userdef.cc:8313`, `rna_ID.cc:2843`, `rna_main.cc:691`), and `pyrna_math_object_from_array` returns a thick-wrapped int array as a tuple slice (`bpy_rna.cc:848–851`, `968–974`). `version_update.py:101` confirms it, using `library.version` as a dict key. These three are the only thick-wrapped int arrays (`grep PROP_THICK_WRAP makesrna/intern/*.cc`; the two float ones are `PROP_MATRIX`, so already `Matrix`).

**Fix:** type them `tuple[int, int, int]`. RNA does not expose `PROP_THICK_WRAP` to Python, so `sphinx_doc_gen.py` needs either a table keyed `(struct, property)` or a runtime probe (`type(bpy.context.preferences.version) is tuple`). The table, guarded by an assertion that the probe agrees, is the smaller, reviewable option.

## 4. Math properties reject sequences on write

### Does ty honour a property whose setter type differs from its getter?

Yes. ty's mdtests pin both forms:

- `@property` with a wider setter: `crates/ty_python_semantic/resources/mdtest/properties.md:52–76` (getter `int`, setter `str`: `C().value = "new"` is accepted, `C().value = 1` is an `invalid-assignment`, and `C().value` reads as `int`); `mdtest/assignment/augmented.md:286–304` ("Properties with different getter and setter types": `/=` is checked against the setter, later reads use the getter).
- A data descriptor's `__set__` decides what may be assigned: `mdtest/assignment/augmented.md:306–325`.

So no ty change is needed.

### How the stubs declare it

`write_attribute` (step 2) writes a math-typed attribute as a property with a wider setter instead of `location: Vector = ...`:

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

### 4b. Plain array properties

The same asymmetry hits `bpy_prop_array[T]` attributes: `image.pixels = [...]`, `pb.lock_location = (True, True, True)`, `mat.diffuse_color = (...)`, and slice assignment `image.pixels[:] = buffer`, `obj.color[0:3] = ...`: `bpy_prop_array.__setitem__` was declared for `int` only. **Fix:** a setter taking `Sequence[T]` for `bpy_prop_array[T]` attributes, and `__setitem__` overloads for `int` → `_T` and `slice` → `Iterable[_T]`.

### 4c. `bpy_prop_array` is not a `Sequence`

`Vector(self.offset)` with `offset` a `FloatVectorProperty` value: `bpy_prop_array[float]` was not assignable to `Sequence[float]`. **Fix:** `bpy_prop_array` gets `Sequence[_T]` in `CLASS_BASES` (it implements `__len__` / `__getitem__` / `__iter__` / `__contains__`).

## 5. `bl_rna` missing on classes

`bpy.types.Operator.bl_rna`, `ob.bl_rna.properties[...]`: no `bl_rna` anywhere in the stubs (only `bl_rna_get_subclass*`). `bl_rna` is set on every RNA type at runtime (and readable from instances), but it is not in `bpy_struct.__dict__`, so `pyclass2sphinx` never sees it.

**Fix:** document it on `bpy_struct` in `sphinx_doc_gen.py` (step 1, so the docs say it too): `.. attribute:: bl_rna` with `:type: :class:`Struct``, marked class attribute. ty reads the resulting `bl_rna: Struct = ...` on both the class and instances.

## 6. Missing module members

| Member | Why missing | Fix |
|---|---|---|
| `bpy.utils.system_resource`, `script_paths_pref`, `is_path_builtin` | Not in `bpy.utils.__all__` (`scripts/modules/bpy/utils/__init__.py:10–66`), and `pymodule2sphinx` documents only `__all__` when there is one | A per-module "also document" table in `sphinx_doc_gen.py`, next to `PRIVATE_ATTR_INCLUDE`, since patching `__all__` is out of scope |
| `bpy.path.extensions_image` / `_movie` / `_audio` | In `__all__`, but `frozenset` values are skipped: only `bool, int, float, str, tuple` become `.. data::`, the rest is logged "not documenting" | Document `frozenset` and mappingproxy values, with `:type: frozenset[str]` / `types.MappingProxyType[str, ...]` from the element types |
| `imbuf.file_types` | A mappingproxy (`imbuf_py_api.cc:1802–1816`), skipped as above | Same change |
| `bpy.utils._sys_path_ensure_append`, `bpy.utils.units` (via `_bpy`) | Private | None |
| `bpy.app.handlers._extension_repos_*` | Deliberately private: "should not be considered part of the public Python API" (`bpy_app_handlers.cc:173–177`) | Leave |

Other module-member misses are not stub gaps: user-defined `bpy.ops.*` in examples and tests (operator registration is runtime), non-Windows stdlib (`os.getuid`, `fcntl`, `termios`), `gdb`, and genuine Blender bugs (`bpy.app.handlers.scene_update_post`, `bpy.utils.register_module`, `bpy.types.AssetData`, `bpy.ops.mesh.primitive_box_add`).

## 7. C modules without stubs

| Module | Runtime | Fix |
|---|---|---|
| `_cycles` | Cycles' C module, undocumented | Partial stub: `def __getattr__(name: str) -> Incomplete: ...` |
| `_bpy` | Private C module behind `bpy.utils`, `bpy.ops`, `bpy.props` | Partial stub with `__getattr__` |
| `_freestyle` | Its classes are re-exported as `freestyle.types` / `.predicates` / `.chainingiterators` / ... (`from _freestyle import ...`) | Stub re-exporting the documented classes from those modules, so names keep their types |
| `_bpy_hydra` | Hydra C module | Partial stub with `__getattr__` |

None of these has RST, so `sphinx_stub_gen.py` copies hand-written stubs into the output. `__getattr__` stubs only remove the import errors: the names stay untyped.

## Further gaps checked and left out

- **`bpy.ops.x.y.poll()` / `.idname()`** (`Function mode_set has no attribute poll`): operators are stubbed as plain functions. Belongs to `operator_calls` (operator objects carry `poll`, `idname`, `get_rna_type`).
- **`driver_add` / `keyframe_insert` returning `FCurve | list[FCurve]`**: the runtime returns a list when `index == -1` *and* the property is an array, which no overload on `int` can express. Leave the union.
- **Context members not in the stubs** (`context.constraint`, `context.keymap`, set through `context_pointer_set`; `context.depsgraph`, `scene_collection` in old tests): see [context-members.md](context-members.md).
- **`numpy` missing**: check setup (bundled site-packages), settled in #67.
- **The rest** holds no further stub gaps: removed APIs in old tests (`ViewLayer.collections`, `BlendData.groups`), custom properties registered at runtime (`Object.selection_sets`, rigify / glTF properties), Type tag narrowing (`ID.matrix_world`, `Space.clip`), add-on internals, and `OperatorProperties.data_path` (operator_properties).
