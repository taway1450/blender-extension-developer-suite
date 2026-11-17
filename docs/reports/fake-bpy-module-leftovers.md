# The fake-bpy-module leftovers, site by site

`check:blender main` with fake-bpy-module's stubs left 431 diagnostics in the done area (397 shipped, 15
examples, 19 templates) under the `unsorted` cause, against 0 with Blender's own (builtin) stubs. Blender
was built at `typecheck-fixes` `9a7af0b8477` (Blender 5.4), the same build as the baselines, and this run
gave 432: one template diagnostic more than the baseline. Each site was read with `read_diagnostics`, and
joined by `path:line` with the builtin run, to tell what fake-bpy-module's stubs add from what both stub
sets share.

[fake-bpy-module-leftovers.tsv](fake-bpy-module-leftovers.tsv) lists every one of the 432 sites. Its
columns are:

- `site`: `path:line`
- `rule`
- `cause_before`: the cause at `main` before this change (always `unsorted`)
- `cause`: the cause `scripts/_buckets.py` gives now
- `group`
- `message`

## The causes

| cause | group | shipped | examples | templates | total |
|---|---|---:|---:|---:|---:|
| `fake-bpy-python-module` | typechecker-fix | 234 | 0 | 0 | 234 |
| `fake-bpy-protocol` | typechecker-fix | 18 | 13 | 13 | 44 |
| `fake-bpy-nullable` | typechecker-fix | 43 | 0 | 0 | 43 |
| `fake-bpy-lib-key` | typechecker-fix | 23 | 0 | 0 | 23 |
| `fake-bpy-type-alias` | typechecker-fix | 9 | 0 | 1 | 10 |
| `ui-draw-pointer` | typing-debt | 49 | 0 | 0 | 49 |
| `object-data-untagged` | typing-debt | 10 | 2 | 6 | 18 |
| `unchecked-pointer-bug` | blender-fix | 5 | 0 | 0 | 5 |
| `narrowed-by-poll-alias` | implied-narrowing | 4 | 0 | 0 | 4 |
| `helper-checks-none` | typing-debt | 1 | 0 | 0 | 1 |
| `base-class-subtype` | typing-debt | 1 | 0 | 0 | 1 |
| **total** | | 397 | 15 | 20 | 432 |

- **354 are stub-shape differences**, to fix in fake-bpy-module: the five new `fake-bpy-*` causes, all
  in the `typechecker-fix` group, since the stubs are the typechecker's input.
- **78 are existing causes** that fake-bpy-module's spelling hid from their patterns. No new cause was
  needed beyond the five `fake-bpy-*` ones.
  - Most hide behind `Object.data`. fake-bpy-module types it as the union of all object data types and
    None, which ty prints cut short (`` `Armature | Camera | Curve | ... omitted 11 union elements` ``,
    or `omitted 10` once a check removed None). `cause()` now spells that union `ID | None` (or `ID`)
    before matching, as the builtin stubs do, so `object-data-untagged`, `ui-draw-pointer` and the rest
    apply unchanged.
  - The 5 `unchecked-pointer-bug` sites are already-known Blender bugs (the VR camera operators among
    them) that only this normalisation let the pattern see.
  - `narrowed-by-poll-alias` gained `poll_tests_same_path()`: `layer = obj.data.layers.active` in a
    callback whose poll tests `obj.data.layers.active is not None` on the same context member.
  - `base-class-subtype` accepts `list[tuple[ID | None, ...]]`.

### `fake-bpy-python-module` (234)

fake-bpy-module generates the stubs of Blender's Python modules (`_bpy_internal`, `addon_utils`, `bl_ui`,
`bl_operators`, ...) at runtime with `inspect`, in `src/gen_modfile/gen_external_modules_modfile.py`, and
the result loses most of what the source says:

- 112 constructor calls fail, because `__init__` is dropped and `object.__init__` takes no arguments. The
  generator skips every member whose name starts with `_`, dunders included.
- 53 instance or dataclass attributes are missing: only class-level members are recorded.
- 41 module members are missing: module constants are never emitted (`result["constants"]` stays empty),
  and private functions that other modules import are skipped (`listing_common` 17, `addon_utils` 10,
  `bl_ui.node_add_menu` 8, `blender_asset_library_openapi` 3, `json_parsing` 2, `rna_prop_ui` 1).
- 13 context managers cannot be used with `with`: `__enter__` / `__exit__` are dropped, and a
  `@contextmanager` function is stubbed as returning `None`.
- About 15 more lose a return annotation (every return becomes `-> None`, every attribute `typing.Any`)
  or a builtin base (only `dict` is kept, so `Exception` and `NamedTuple` subclasses lose theirs).

The sites sit mostly in `_bpy_internal/assets` (120), `ui_translate` (38), `disk_file_hash_service`
(14) and `addon_utils` (11).

### `fake-bpy-protocol` (44)

The C types of `mathutils`, `gpu`, `blf` and `imbuf` lack protocols the builtin stubs give them:
`Vector` and `bpy_prop_array[float]` are not `Sequence[float]`, `MatrixAccess` has no `__getitem__`,
`Vector` has no ordering and `Quaternion` no `__neg__`, and `MatrixStackContext`,
`OffScreenStackContext`, `BLFImBufContext` and `ImBufBuffer` have no `__enter__` / `__exit__`. Examples
and templates use these most.

### `fake-bpy-nullable` (43)

Properties that are never None come out nullable: `bl_rna` is `Struct | None`, `RenderViews.active` is
`SceneRenderView | None`, and int properties (`active_repo`, `active_texture_index`,
`active_selection_set`, `active_variable_index`, `active_tag`) are `int | None` although the API docs
say `:type: int`. The decision is in `src/fake_bpy_module/transformer/data_type_refiner.py`, where
`is_never_none` is cleared for a type ending in `or None`, a description starting with "Optional", or a
default of `None`. The None-index pattern only counts a read of `.active_*`, so Node Wrangler's
`None` keys, which come from Python locals, stay with their builtin causes.

### `fake-bpy-lib-key` (23)

`bpy_prop_collection.__getitem__` takes `int | str | tuple[str, ...]`, so the library key
`(name, None)` (a local ID) is rejected. The builtin stubs take `tuple[str, str | None]`.

### `fake-bpy-type-alias` (10)

fake-bpy-module still maps `bpy_types` to `bpy.types`, but the module is now `_bpy_types`, so
`_bpy_types.Context`, `_bpy_types.Menu` and others exist as duplicate classes that do not match their
`bpy.types` names. And `bpy.types` declares registered classes as instances
(`PREFERENCES_OT_addon_install: bl_operators.userpref.PREFERENCES_OT_addon_install`), so calling a
method through the class passes one positional argument too many.

## Fixes for fake-bpy-module

On its `stub-generator` branch, for the spec:

1. `gen_external_modules_modfile.py`: keep annotations, `__init__`, `__enter__` / `__exit__` and the
   other dunders, dataclass and instance fields, module constants, private functions that other modules
   use, builtin bases (`Exception`, `NamedTuple`), and `@contextmanager` return types. Generating these
   stubs from the Python source instead of `inspect` would keep all of them at once; the spec decides.
2. Map `_bpy_types` (not `bpy_types`) to `bpy.types`, and declare registered classes in `bpy.types` as
   classes, not instances.
3. `data_type_refiner.py`: `bl_rna` and `RenderViews.active` are never None, and an int property is
   never `int | None`.
4. The collection key is `int | str | tuple[str, str | None]`.
5. The `mathutils`, `gpu`, `blf` and `imbuf` C types get their protocols: `Sequence`, `__getitem__`,
   ordering, `__neg__` and the context-manager methods.

## Moves of already-sorted diagnostics

The new patterns also re-sort some fake-bpy-module diagnostics that already had a cause. Each move was
read and judged correct:

- glTF `Object.data` sites move to `object-data-untagged`.
- `bl_rna` sites move to `fake-bpy-nullable`.
- `addon_utils`' private members move to `fake-bpy-python-module`.
- The `path_split` sites in `wm.py` move to `fake-bpy-python-module`.

With the builtin stubs nothing moves: the summary only gains the five `fake-bpy-*` causes at 0.
Agreement with the builtin cause at the same site rose from 8573 to 8694 sites.

## Environment

The Blender build needs GCC 14 and the EGL/X11/Wayland headers:

```sh
apt-get install gcc-14 g++-14 libegl-dev libgl-dev libx11-dev libxkbcommon-dev libwayland-dev
CC=gcc-14 CXX=g++-14 mise run blender:build main --config headless --ref typecheck-fixes
```
