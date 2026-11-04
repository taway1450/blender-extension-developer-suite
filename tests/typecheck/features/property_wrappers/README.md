# property_wrappers

**The checker must:** evaluate an annotation as a value and, when the value is a property made by a `bpy.props`
function, give the field that property's type, whatever the expression looks like: a module constant, an alias of
the function, `functools.partial`, an item of a dict or tuple, the return of a small wrapper function. When the
options that decide the type (subtype, size, items) are known, the type is exact.

When it cannot tell:

| Case | Expected type |
| --- | --- |
| a wrapper that returns one of several properties | the union of their types |
| a FloatVector whose subtype or size is not known | `Any` |
| an Int / Float / Bool / String with unknown options | the scalar type (no option changes it) |
| a value the checker cannot evaluate at all | `Any`, and no error |

| Addon | Variant |
| --- | --- |
| `wrap_values` | all of the above on one PropertyGroup |
