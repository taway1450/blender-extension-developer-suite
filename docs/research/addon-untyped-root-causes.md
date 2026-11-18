# Root causes of untyped-python errors in Blender's add-ons: the lasting findings

Research note, 2026-11-17, for [#115](https://github.com/taway1450/blender-extension-developer-suite/issues/115)
(map [#107](https://github.com/taway1450/blender-extension-developer-suite/issues/107)). Trimmed on 2026-11-18 to
the rationale and the Blender/ty facts; the build plan and counts were dropped; the issue keeps a summary of the findings.

The question was what causes the top shapes of the `untyped-python` cause in Rigify, glTF and Freestyle, and where
each one is fixed: in ty, in the stubs, or in the add-on. The add-on fixes have landed, and the nested-class
override false positive (Rigify) was fixed upstream in ty 0.0.103, which the fork is on. What stays here are the
findings about ty, numpy and Blender's stub generator.

Conventions: `src/` is `.cache/blender-src/main/`, `stubs/` is `.cache/bpy-stubs-builtin/main/`, `ruff/` is
`ty-blender/ruff-blender/`, and `numpy/` is Blender's bundled numpy 2.3.4 (`.cache/blender-site/main/numpy`).
*Verified locally* means stock `uvx ty@0.0.98` (the fork's base version at the time) on a small file.

---

## 1. numpy: `np.dtype(...)` is always `dtype[float64]`

**Shape.** glTF builds structured arrays (`np.empty(n, dtype=np.dtype(dot_fields))`,
`src/scripts/addons_core/io_scene_gltf2/blender/exp/primitive_extract.py`, `imp/mesh.py`) and reads and writes
fields by name. ty types the array as `ndarray[tuple[int], dtype[float64]]` and rejects every string key.

**Root cause.** The cause is not ndarray's overloads. ty evaluates every `np.dtype(...)` call to `dtype[float64]`:

- *Verified locally:* `np.dtype([("vertex_index", np.uint32)])`, `np.dtype("u4")` and even `np.dtype(np.uint32)` all
  reveal `dtype[float64]`. `np.empty(3, dtype=np.uint32)` is correct.
- numpy's first `dtype.__new__` overload is `dtype: type[float64] | None` (`numpy/__init__.pyi:1171-1177`). The class
  body later defines `def type(self) -> type[_ScalarT_co]` as a property (`numpy/__init__.pyi:1586`).
- ty resolves the name `type` in that annotation to the class's own `type` property, not to `builtins.type`.
  `reveal_type(np.dtype.__new__)` shows the first overload as `dtype: Unknown | None`. So that overload accepts
  anything and always wins.
- Copying the same overloads into a class without a `type` member gives the right answer (`D[void]`).

ty resolves annotation names this way on purpose. [astral-sh/ty#1747](https://github.com/astral-sh/ty/issues/1747)
asked ty to stop resolving annotations to class members that shadow a global, such as a method named `set`. It was
closed as *not planned*. numpy has since fixed its side:

- On numpy `main`, `__init__.pyi` imports `type` as `py_type` and annotates `py_type[float64 | ct.c_double] | ...`,
  with a comment that the aliases keep annotations from resolving to class members.
- numpy 2.4.0 still has the bare `type[...]` ([v2.4.0 `__init__.pyi`](https://github.com/numpy/numpy/blob/v2.4.0/numpy/__init__.pyi)).
- Blender bundles 2.3.4.

So this is a stub bug (numpy's), exposed by a deliberate ty choice. It is neither a ty bug nor a glTF bug. With
numpy up to 2.4.0, passing the field list straight to `dtype=` avoids it: the `DTypeLike` overload types the result
as `ndarray[..., dtype[Any]]`, which accepts field names (*verified locally*). Annotating the array as
`NDArray[np.void]` does not help, because the right-hand side is still `dtype[float64]`. It clears without any edit
once Blender bundles a numpy release with the `py_type` aliases.

---

## 2. Freestyle: `Operators.create(pred, list[StrokeShader])`

### 2.1 `Sequence` is the wrong stub fix

Each style module builds a list literal of shaders and passes it to `Operators.create`:

```python
shaders_list = [ConstantThicknessShader(4), SamplingShader(2), pyDiffusion2Shader(offset, nbIter), ...]
Operators.create(TrueUP1D(), shaders_list)   # styles/anisotropic_diffusion.py:33-39
```

The stub is `def create(pred: UnaryPredicate1D, shaders: list[StrokeShader]) -> None`, from the C docstring
`:type shaders: list[:class:\`StrokeShader\`]` (`src/source/blender/freestyle/intern/python/BPy_Operators.cpp:571`).

- ty infers the unannotated literal as `list[ConstantThicknessShader | SamplingShader | ...]`.
- `list` is invariant: typeshed's `class list(MutableSequence[_T])` uses a plain `_T = TypeVar("_T")`.
- The spec says old-style TypeVars are invariant by default, "which means that e.g. `list[Manager]` is neither a
  supertype nor a subtype of `list[Employee]`" ([generics.rst](https://github.com/python/typing/blob/main/docs/spec/generics.rst)).

ty is right. But **`Sequence` is the wrong stub fix**. The C function parses `shaders` with `"O!"` and `&PyList_Type`
(`BPy_Operators.cpp:578-587`), and its error message is "2nd argument must be a list of StrokeShader objects"
(`:603`). A tuple raises `TypeError` at runtime, so `Sequence[StrokeShader]` would accept calls that fail.

The sound fix is a parameter generic over the element type:

```python
_StrokeShaderT = TypeVar("_StrokeShaderT", bound=StrokeShader)
def create(pred: UnaryPredicate1D, shaders: list[_StrokeShaderT]) -> None: ...
```

`list[A | B]` then solves `_StrokeShaderT = A | B`, which satisfies the bound. It stays sound because `create` only
reads the list, and a non-list is still rejected (*verified locally*). The generator already supports documented
TypeVars (`TYPE_VARS` in `src/doc/python_api/sphinx_stub_gen.py`); one with a bound outside the standard library
also needs `track_type_var` to import the bound.

### 2.2 The generator's default `-> None`

**Shape.** `for prev, svert in pairwise(stroke):` and `for svert, t in iter_distance_from_camera(...)` (and the
other `iter_*` helpers of `freestyle.utils`) report that `None` is not iterable.

**Root cause.**

- The stub says `def pairwise(...) -> None` and `def iter_distance_from_camera(...) -> None`
  (`stubs/freestyle/utils/__init__.pyi`).
- The generator falls back to `"None"` whenever a callable has no `:rtype:`: `ret_type = "None"`
  (`src/doc/python_api/sphinx_stub_gen.py:1929-1931` for functions, `:1808-1810` for methods).
- The sources are generators or return `zip(...)` (`src/scripts/freestyle/modules/freestyle/utils.py:445-464, 479-607`),
  and their docstrings have `:type` fields but no `:rtype:`.

Other functions in the same stub are wrong the same way but cause no error: `get_strokes`, `get_test_stroke`,
`tripplewise`, `stroke_curvature` and `stroke_normal`.

**Recommendation (still open).** Make the generator stop writing `-> None` for an undocumented return of a
Python-defined function. It could emit `-> Any`, or fail the stub check for a function that has `:type` fields but
no `:rtype:`. `-> None` silently turns a missing doc into a wrong type.
