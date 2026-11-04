# IDE results, builtin stubs, Blender main

Written by `mise run check:ide main --update`; the task fails when this file would change.
Each section is one marker: the queried code line, then what ty's language server returned for it.

## features/props_annotations/ide_props_annotations.py:9:7 ^hover

`s.count`

````text
```python
Unknown
```
````

## features/props_annotations/ide_props_annotations.py:9:7 ^hover-contains "int"

`s.count`

````text
FAIL: does not contain "int"
````

## features/props_annotations/ide_props_annotations.py:12:7 ^hover-contains "Object"

`s.target`

````text
FAIL: does not contain "Object"
````

## ide/completion_docs/ide_completion_docs.py:14:14 ^completion location

`obj.locat`

````text
- location: detail: Vector
  documentation: (none)
````

## ide/completion_docs/ide_completion_docs.py:16:17 ^completion select_set

`obj.select_s`

````text
- select_set: detail: bound method Object.select_set(state: bool, *, view_layer: ViewLayer | None = None) -> None
  documentation: (none)
````

## ide/completion_docs/ide_completion_docs.py:21:34 ^completion primitive_cube_add

`bpy.ops.mesh.primitive_cube_a`

````text
- primitive_cube_add: detail: def primitive_cube_add(*, size: float = ..., calc_uvs: bool = True, enter_editmode: bool = False, align: Literal["WORLD", "VIEW", "CURSOR"] = "WORLD", location: Sequence[float] = ..., rotation: Sequence[float] = ..., scale: Sequence[float] = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]
  documentation: (none)
````

## ide/deprecation/ide_deprecation.py:12:11 ^deprecated

`brush.falloff_angle`

````text
FAIL: no deprecated diagnostic at the caret
````

## ide/deprecation/ide_deprecation.py:12:11 ^hover

`brush.falloff_angle`

````text
```python
float
```
````

## ide/deprecation/ide_deprecation.py:12:11 ^hover-contains "Deprecated"

`brush.falloff_angle`

````text
FAIL: does not contain "Deprecated"
````

## ide/enum_docs/ide_enum_docs.py:9:9 ^hover

`obj.type`

````text
```python
Literal["MESH", "CURVE", "SURFACE", "META", "FONT", ... omitted 11 literals]
```
````

## ide/enum_docs/ide_enum_docs.py:11:18 ^hover-contains "Mesh"

`obj.type == "MESH"`

````text
FAIL: no hover
````

## ide/enum_docs/ide_enum_docs.py:16:17 ^hover-contains "Warning"

`op.report({"WARNING"}, "x")`

````text
FAIL: no hover
````

## ide/enum_docs/ide_enum_docs.py:18:14 ^hover-contains "Finished"

`return {"FINISHED"}`

````text
FAIL: no hover
````

## ide/hover_rna_props/ide_hover_rna_props.py:9:9 ^hover

`obj.location`

````text
```python
Vector
```
````

## ide/hover_rna_props/ide_hover_rna_props.py:9:9 ^hover-contains "Location of the object"

`obj.location`

````text
FAIL: does not contain "Location of the object"
````

## ide/hover_rna_props/ide_hover_rna_props.py:12:9 ^hover-contains "Parent object"

`obj.parent`

````text
FAIL: does not contain "Parent object"
````

## ide/hover_rna_props/ide_hover_rna_props.py:14:9 ^hover-contains "Object data"

`obj.data`

````text
FAIL: does not contain "Object data"
````

## ide/hover_rna_props/ide_hover_rna_props.py:19:11 ^hover

`scene.frame_current`

````text
```python
int
```
````

## ide/hover_rna_props/ide_hover_rna_props.py:19:11 ^hover-contains "Current frame"

`scene.frame_current`

````text
FAIL: does not contain "Current frame"
````

## ide/hover_rna_props/ide_hover_rna_props.py:25:13 ^hover

`context.active_object`

````text
```python
Object
```
````

## ide/hover_rna_props/ide_hover_rna_props.py:27:13 ^hover

`context.scene`

````text
```python
Scene | None
```
````

## ide/hover_rna_props/ide_hover_rna_props.py:32:7 ^hover-contains "Object data-block defining an object in a scene"

`Object`

````text
FAIL: does not contain "Object data-block defining an object in a scene"
````

## ide/signature_docs/ide_signature_docs.py:11:20 ^signature

`obj.select_set(True)`

````text
label: (state: bool, *, view_layer: ViewLayer | None = None) -> None
active parameter: 0
parameters:
- state: bool: (no documentation)
- view_layer: ViewLayer | None = None: (no documentation)
documentation:
(none)
````

## ide/signature_docs/ide_signature_docs.py:11:20 ^signature-param "Selection state to define"

`obj.select_set(True)`

````text
FAIL: does not contain "Selection state to define"
````

## ide/signature_docs/ide_signature_docs.py:14:26 ^hover-contains "Use this instead of the active view layer"

`obj.select_set(True, view_layer=None)`

````text
FAIL: does not contain "Use this instead of the active view layer"
````

## ide/signature_docs/ide_signature_docs.py:21:19 ^signature

`obj.ray_cast((0, 0, 0), (0, 0, 1))`

````text
label: (origin: Sequence[float], direction: Sequence[float], *, distance: float = ..., depsgraph: Depsgraph | None = None) -> tuple[bool, Vector, Vector, int]
active parameter: 0
parameters:
- origin: Sequence[float]: (no documentation)
- direction: Sequence[float]: (no documentation)
- distance: float = ...: (no documentation)
- depsgraph: Depsgraph | None = None: (no documentation)
documentation:
(none)
````

## ide/signature_docs/ide_signature_docs.py:23:40 ^hover-contains "Maximum distance"

`obj.ray_cast((0, 0, 0), (0, 0, 1), distance=1.0)`

````text
FAIL: does not contain "Maximum distance"
````

## ide/signature_docs/ide_signature_docs.py:28:41 ^hover-contains "tooltip"

`bpy.props.IntProperty(name="Count", description="Number of items")`

````text
FAIL: does not contain "tooltip"
````

## ide/signature_docs/ide_signature_docs.py:33:37 ^signature

`bpy.ops.mesh.primitive_cube_add(size=2.0)`

````text
label: (*, size: float = ..., calc_uvs: bool = True, enter_editmode: bool = False, align: Literal["WORLD", "VIEW", "CURSOR"] = "WORLD", location: Sequence[float] = ..., rotation: Sequence[float] = ..., scale: Sequence[float] = ...) -> set[Literal["RUNNING_MODAL", "CANCELLED", "FINISHED", "PASS_THROUGH", "INTERFACE"]]
active parameter: 0
parameters:
- size: float = ...: (no documentation)
- calc_uvs: bool = True: (no documentation)
- enter_editmode: bool = False: (no documentation)
- align: Literal["WORLD", "VIEW", "CURSOR"] = "WORLD": (no documentation)
- location: Sequence[float] = ...: (no documentation)
- rotation: Sequence[float] = ...: (no documentation)
- scale: Sequence[float] = ...: (no documentation)
documentation:
(none)
````

## ide/signature_docs/ide_signature_docs.py:33:37 ^signature-param "Size"

`bpy.ops.mesh.primitive_cube_add(size=2.0)`

````text
FAIL: does not contain "Size"
````
