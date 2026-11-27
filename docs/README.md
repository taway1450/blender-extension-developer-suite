# Documentation

- **[catalog/](catalog/README.md)**: for add-on authors. The Blender-Python features and quirks by what an add-on
  does, each with a checked example and what handles it: the stubs, the add-on typechecker, the linter profile,
  Blender at runtime, or nothing yet, and whether that can change. Generated from
  [examples/catalog/](../examples/catalog/README.md) by `mise run catalog:generate`; do not edit it by hand.
- **[research/](research/)**: for contributors. Notes written while designing a part of the suite: how Blender,
  the stub generators or ty work, and the options weighed for a change.
- **[reports/](reports/)**: for contributors. What a check found at one point in time, such as the causes of the
  diagnostics that remain on Blender's own source (`remaining-causes.md`). They are not kept current.
