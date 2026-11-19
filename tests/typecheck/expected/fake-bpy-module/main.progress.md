# Feature-test progress, fake-bpy-module stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 17/17 | 8/8 | 3/3 | - | 0 |
| addon_preferences | 24/24 | 7/7 | 11/11 | 3/3 | 0 |
| api_types | 30/30 | 6/7 | 259/277 | 3/3 | 17 |
| assumptions | 15/15 | 67/67 | 15/15 | - | 0 |
| bpy_symbols | 153/153 | 47/47 | 9/9 | 2/2 | 0 |
| context_members | 56/56 | - | 16/16 | - | 0 |
| implied_narrowings | 8/8 | 69/69 | 23/23 | 3/3 | 0 |
| imprecise_annotations | 3/3 | 20/20 | 5/5 | 2/2 | 0 |
| inheritance | 78/78 | 48/48 | 18/18 | 5/5 | 0 |
| operator_calls | 31/31 | 34/34 | 4/4 | 5/5 | 0 |
| operator_properties | 54/54 | 13/13 | 11/11 | 5/5 | 0 |
| pointer_aliases | 9/9 | 6/6 | 5/5 | 1/1 | 0 |
| properties | 449/449 | 102/102 | 15/15 | 9/9 | 0 |
| property_wrappers | 17/17 | - | 3/3 | 6/6 | 0 |
| registration | 46/46 | 11/11 | 11/11 | 3/3 | 0 |
| registration_checks | 13/13 | 39/39 | 11/11 | - | 0 |
| type_narrowing | 60/65 | 1/1 | 21/21 | - | 3 |
| **total** | 1063/1068 | 478/479 | 440/458 | 47/47 | 20 |
