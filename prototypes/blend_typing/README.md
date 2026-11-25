# PROTOTYPE: typing code from a .blend file (throwaway)

Throwaway code that answers one question from `docs/research/blend-file-typing.md`: what types can a checker get from
a `.blend`, and how would they reach a script? The answers are in §8 of that note. Nothing here is production code,
and nothing else in the repo depends on it. The letters are the approaches of §4 of the note.

| File | Approach | What it shows |
|---|---|---|
| `blendread.py` | shared | a dependency-free reader: header, blocks, SDNA, zstd (system libzstd) and gzip |
| `extract_manifest.py` | B | `.blend` → TOML manifest (IDs, object and data types, modifiers, material and node group nodes with their sockets), without Blender |
| `blender_extract.py` | G | the same manifest, written by Blender after it opened the file (the loaded state, after versioning) |
| `gen_stubs.py` | C | manifest → overlay `.pyi` with `Literal` keys, against the builtin stubs |
| `reader_check.py` | A | reads the bound files itself, no manifest, and types an add-on's `reveal_type` calls the way a reader inside ty would |
| `make_examples.py` | — | builds the generated example files in Blender |
| `examples/` | D | three add-ons whose `blender_manifest.toml` binds their files (`[tool.blender] blend-files`) |
| `measure_reader.py`, `measure_reader.out` | A | the SDNA fields a reader needs, time per stage, and how many test keys the files hold |

The example add-ons:

- `asset_pack/`: appends a material (`Rust`, with a noise texture), a geometry node group (`Scatter Points`) and an
  object (`Rock`, with a Bevel modifier) from the `assets.blend` it ships;
- `scene_template/`: runs against the camera, area light and cube of its `startup.blend`;
- `sculpt_template/`: a copy of Blender's own Sculpting template `startup.blend`, saved by Blender 5.2, so B and G
  differ when a newer Blender (`main`, 5.4) loads it.

Each add-on reads the same names twice: `check_bare` through `bpy.data`, as scripts do today, and `check_overlay`
through the overlay in `_blend/`, which it binds under `TYPE_CHECKING`.

Run all four on the examples (`--make` rebuilds `assets.blend` and the scene template's `startup.blend` first). The
outputs go to `.cache/blend-typing/<version>/`, and `summary.md` lists where B and G disagree:

```bash
mise run probe:blend-typing main --make --update-overlays
```

The overlays from both manifests go to the cache; `--update-overlays` writes B's into `examples/*/_blend/`, and the
summary says when a committed one is stale. To see what the checker makes of them, check copies of the
add-ons against the builtin stubs (the overlays are generated against them):

```bash
for ex in asset_pack scene_template sculpt_template; do cp -r prototypes/blend_typing/examples/$ex examples/addons/prototype_$ex; done
```

```bash
mise run check:addons main --generator builtin prototype_asset_pack prototype_scene_template prototype_sculpt_template
```

The task compares with the results recorded for the example add-ons, so it lists every diagnostic of the copies
as new (`+`) and fails; do not pass `--update`. The full output is in
`.cache/typecheck-results/main/builtin/examples-ty.txt`.

```bash
rm -rf examples/addons/prototype_*
```

`measure_reader.py` reads Blender's test files, so it needs their Git LFS content:

```bash
python3 -I prototypes/blend_typing/measure_reader.py .cache/blender-src/main
```
