# Feature-test progress, builtin stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 17/17 | 8/8 | 3/3 | - | 0 |
| addon_preferences | 11/11 | 6/6 | 10/10 | 3/3 | 0 |
| api_types | 25/25 | 6/6 | 121/121 | 3/3 | 0 |
| assumptions | 5/5 | 25/25 | 3/3 | - | 0 |
| bpy_symbols | 153/153 | 47/47 | 9/9 | 2/2 | 0 |
| context_members | 43/43 | - | 10/10 | - | 0 |
| implied_narrowings | 4/4 | 30/30 | 8/8 | 3/3 | 0 |
| imprecise_annotations | 3/3 | 20/20 | 5/5 | 2/2 | 0 |
| inheritance | 67/67 | 48/48 | 15/15 | 3/3 | 0 |
| operator_calls | 28/28 | 33/33 | 4/4 | 5/5 | 0 |
| operator_properties | 54/54 | 13/13 | 10/11 | 5/5 | 0 |
| properties | 433/433 | 102/102 | 10/10 | 9/9 | 0 |
| property_wrappers | 17/17 | - | 3/3 | 6/6 | 0 |
| registration | 43/43 | 11/11 | 9/9 | 3/3 | 0 |
| registration_checks | 8/8 | 38/38 | 10/10 | - | 0 |
| type_narrowing | 18/18 | - | 2/2 | - | 0 |
| **total** | 929/929 | 387/387 | 232/233 | 44/44 | 0 |
