# imprecise_annotations

**The checker must:** accept code that is less precise than the stubs but right in Blender, type it as the precise
form, and report it under a `blender-imprecise-*` rule (category `blender-imprecise-annotations`, `warn` by
default), while a string literal that is not an enum item stays an error.

## What Blender does

- **Operator results:** `execute`, `invoke` and `modal` return a set of result names, and Blender checks each name
  when the method returns (`bpy_rna.cc`, "incompatible return value"). The names exist as `Literal` types only in the
  stubs, so add-ons write `-> set[str]` (or `typing.Set[str]`), or hold the set in a variable, which makes it a
  `set[str]`. A literal that is not a name (`{"FINSHED"}`, `{'OPERATOR_CANCELLED'}`) raises.
- **Enum values:** an enum property or an enum parameter of a Blender function or operator takes a name, and
  Blender raises for one that is not an item (`py_capi_utils.cc`, `bpy_rna.cc`). A value computed at runtime is a
  `str` (or a `set[str]` for an enum flag set).
- **Callback parameters:** Blender passes `UIList.draw_item` the `data` and `item` the add-on gave
  `template_list`, so annotating them with that subclass is narrower than the parent's type but right. Only Blender
  calls a callback.

## Rules

| Rule | Reports | Typed as |
| --- | --- | --- |
| `blender-imprecise-operator-return` | `-> set[str]` / `Set[str]` on `execute` / `invoke` / `modal` (also in a mixin whose method Blender calls), and a `set[str]` value returned there that is not a set display | the parent's `set[Literal[...]]`, so the returns are checked name by name |
| `blender-imprecise-enum-value` | a `str` (or `set[str]`, no set display) value where a Blender function, operator or property has an enum `Literal` | the enum, as for a literal |
| `blender-imprecise-callback-parameter` | a callback parameter annotated with a subtype of the parent's type without `None` | the annotation |

String literals are precise: one that is not an item is an error under every level, and so is a parameter type that
is no subtype of the parent's (`invalid-method-override`). An add-on's own `Literal` keeps ty's check.

## Configuration

The category's name sets all three rules (`blender-imprecise-annotations = "ignore"` in `[rules]`), a rule's name
one of them; the precedence is `all` < category < rule, in `[[overrides]]` too. `[blender] strictness` (`[tool.ty.blender]`
in `pyproject.toml`) is a preset below all of these: `lenient` ignores the Imprecise annotations, `default` warns,
`strict` makes them errors. An ignored rule still accepts the code.

| Addon | Variant |
| --- | --- |
| `imp_operator_return` | `-> set[str]`, `-> Set[str]`, a set in a variable, a mixin's `execute`, a follow-on `return self.execute(context)`; errors: `{"FINSHED"}`, `{'OPERATOR_CANCELLED'}` |
| `imp_enum_value` | a `str` argument (positional, keyword, operator), a `str` enum property (of a Blender object or of `layout.operator(...)`'s properties), a `set[str]` enum flag set; errors: a literal that is no item, an add-on's own `Literal` |
| `imp_callback_parameter` | `draw_item`'s `data: Armature` and `item: <PropertyGroup>`; error: `icon: str` |
| `imp_config` | an `[[overrides]]` entry in `tests/typecheck/ty.toml`: the category at `error`, `blender-imprecise-enum-value` at `ignore` |
| `imp_strictness` | one use per rule; `check:features` runs it under each `strictness` preset (`_expected/strictness.toml`) |

The `blender-*` markers need the checker; the upstream ones are guards (`bare-ok`). `_expected/strictness.toml`
gives, per preset, the level each rule must be reported at in that add-on: `check:features` runs ty on a copy of the
add-on without its `blender-*` markers, once per preset, and records a `strictness-<preset>` entry for a line where
the reported level differs.

**Named exceptions (5.2):** Blender 5.2's own stubs type `UIList.draw_item`'s `data` and `item` as `AnyType`, a
struct class no add-on type derives from, so `data: Armature` and `item: <PropertyGroup>` stay
`invalid-method-override` there (and `imp_strictness` records `strictness-*` entries for that line).
