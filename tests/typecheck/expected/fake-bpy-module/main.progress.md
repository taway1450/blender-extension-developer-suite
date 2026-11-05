# Feature-test progress, fake-bpy-module stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 0/19 | 1/9 | - | - | 34 |
| addon_preferences | 4/17 | 3/8 | - | 0/3 | 31 |
| bpy_symbols | 1/158 | 4/51 | - | - | 213 |
| inheritance | 4/66 | 8/49 | - | 0/3 | 53 |
| operator_calls | 1/22 | 4/29 | - | 0/4 | 103 |
| operator_properties | 1/44 | 6/15 | - | 0/5 | 46 |
| properties | 152/410 | 9/66 | - | 2/9 | 522 |
| property_wrappers | 3/17 | - | - | 1/5 | 19 |
| registration | 0/40 | 3/8 | - | 0/3 | 53 |
| registration_checks | 0/8 | 10/46 | - | - | 27 |
| **total** | 166/801 | 48/281 | - | 3/32 | 1101 |
