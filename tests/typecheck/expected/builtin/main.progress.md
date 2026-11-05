# Feature-test progress, builtin stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 2/19 | 1/9 | - | - | 34 |
| addon_preferences | 4/17 | 3/8 | - | 0/3 | 34 |
| bpy_symbols | 1/158 | 3/51 | - | - | 205 |
| inheritance | 4/66 | 8/49 | - | 0/3 | 54 |
| operator_calls | 1/22 | 4/29 | - | 0/4 | 103 |
| operator_properties | 1/44 | 7/15 | - | 0/5 | 68 |
| properties | 4/410 | 10/66 | - | 2/9 | 384 |
| property_wrappers | 2/17 | - | - | 1/5 | 18 |
| registration | 0/40 | 3/8 | - | 0/3 | 54 |
| registration_checks | 0/8 | 10/46 | - | - | 27 |
| **total** | 19/801 | 49/281 | - | 3/32 | 981 |
