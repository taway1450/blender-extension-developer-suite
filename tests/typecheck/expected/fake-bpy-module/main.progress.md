# Feature-test progress, fake-bpy-module stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 17/17 | 8/8 | 3/3 | - | 0 |
| addon_preferences | 11/11 | 6/6 | 10/10 | 3/3 | 0 |
| api_types | 25/25 | 6/6 | 85/121 | 3/3 | 23 |
| assumptions | 10/10 | 58/58 | 14/14 | - | 0 |
| bpy_symbols | 153/153 | 47/47 | 9/9 | 2/2 | 0 |
| context_members | 43/43 | - | 10/10 | - | 0 |
| implied_narrowings | 8/8 | 51/60 | 23/23 | 3/3 | 0 |
| imprecise_annotations | 3/3 | 20/20 | 5/5 | 2/2 | 0 |
| inheritance | 73/73 | 50/50 | 15/15 | 5/5 | 0 |
| operator_calls | 28/28 | 33/33 | 4/4 | 5/5 | 0 |
| operator_properties | 54/54 | 13/13 | 10/11 | 5/5 | 0 |
| pointer_aliases | 17/17 | 5/5 | 9/9 | 1/1 | 0 |
| properties | 423/433 | 102/102 | 8/10 | 9/9 | 0 |
| property_wrappers | 17/17 | - | 3/3 | 6/6 | 0 |
| registration | 43/43 | 11/11 | 9/9 | 3/3 | 0 |
| registration_checks | 8/8 | 38/38 | 10/10 | - | 0 |
| type_narrowing | 14/26 | 1/1 | 5/5 | - | 8 |
| **total** | 947/969 | 449/458 | 232/271 | 47/47 | 31 |
