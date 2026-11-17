# Spec #95: the site-by-site sorting of the unsorted diagnostics

After the review fixes (`2170a1c`), `check:blender main` with Blender's own (builtin) stubs still left
1068 diagnostics in shipped scripts, examples and templates under an `unsorted` cause. Each site was
read and given either a fix in Blender or a cause. [spec-95-site-decisions.tsv](spec-95-site-decisions.tsv)
lists every decision by `path:line` at `typecheck-fixes` `42f1ec42783`. Its columns are:

- `decision`: `fix` or `cause`
- `cause_as_sorted`: the name chosen at the site
- `cause`: the merged name `scripts/_buckets.py` uses
- `group`
- `pattern`: what to recognise at the site
- `commit`: the Blender commit that fixes the site, if any

## Fixes in Blender

15 commits on `typecheck-fixes` (`42f1ec42783..9a7af0b8477`), Python only.

Ten fix runtime failures:

- Rigify Convert Rotation Modes, without an assigned action slot.
- Version Bone Hide Property, on a second object without an action.
- Quick Explode with Fade, when the mesh already has the maximum of 8 UV maps.
- Quick Smoke and Quick Liquid:
  - on an object that already has a fluid modifier (a single-instance modifier, so `modifiers.new()` returns `None`)
  - Quick Liquid also fails without a screen
- Remove Add-on, without an area.
- Move to Nodes, on selected objects without the modifier.
- Connect to Output, without an active node. The dead `and not any(...)` clause is dropped and the existing behaviour is kept.
- Fill Range by Selection, without an active object.
- Bake to Keyframes, when nothing is keyed.

Five are cleanups that correct wrong annotations and docstring types:

- the remote listing asset finder
- `KeyframesCo`'s buffer
- the Pose Library menu `draw` (typed as `Menu`, not `UIList`)
- `_path_resolve()`, which can return a struct
- `UI_UL_list.sort_items_helper`

## Causes

The 104 names chosen at the sites were merged into 47 causes, 27 of them new. Rows are decision rows,
so a site with two diagnostics counts twice.

| group | causes | rows | main causes |
|---|---:|---:|---|
| blender-fix | 1 | 6 | wrong-annotation (all fixed above) |
| assumption | 5 | 52 | internal-operator, ui-callback-editor-member, bl-context-implies-member |
| implied-narrowing | 7 | 196 | narrowed-by-poll-helper, narrowed-by-parent-panel, narrowed-by-poll-in-caller, narrowed-by-poll-alias |
| typechecker-fix | 9 | 174 | rna-never-none, stub-signature-gap, mathutils-protocol-stub |
| typing-debt | 25 | 603 | general-typing, none-excluded-by-arguments, untyped-python, modifiers-new, type-enum-sub-pointer, set-by-preceding-call |

`_buckets.py` recognises the causes from the code around each site:

- the class body
- the class's `poll`, including one inherited from a base class in the same file
- the function up to the line
- small site tables, for narrowings made in a caller and for correlated conditions

Offline, the predicates agree with the sorted cause on 952 of the 1031 cause rows. The rest are
accepted:

- **Wrong annotations (6):** fixed in Blender.
- **Same site, different cause:** the three sorters gave different causes to the same pattern. Examples are Node Wrangler's helper poll against the RNA pointer, and the INTERNAL operators of `bl_pkg` against the window context.
- **Tied sites:** sites where two causes both hold, and the first match wins.

## Result

These counts are for `check:blender main` at `9a7af0b8477`, in shipped scripts, examples and templates.

With the builtin stubs:

- Before: 1068 unsorted. After: 21 (20 shipped, 1 example, 0 templates).
- Two of the 21 are `sort_items_helper` calls. They go away once the `main` binary includes `9a7af0b8477`, because the builtin stubs are built from the binary's own `bl_ui`.
- The other 19 are single sites the patterns do not cover:
  - `image.py` and `sequencer.py` read a pointer set by an earlier operator call
  - `image_as_planes.py` uses an `Optional` index
  - aliases in `rigidbody.py`
  - Node Wrangler `swap_links`

With the fake-bpy-module stubs:

- Before: 1666 unsorted. After: 450.
- Most of what remains is gaps in fake-bpy-module's stubs, which these sites were not sorted for.
