# Feature-test progress, fake-bpy-module stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 18/19 | 7/8 | 1/1 | - | 0 |
| addon_preferences | 1/10 | 0/5 | 10/10 | 1/3 | 5 |
| bpy_symbols | 138/153 | 32/48 | 8/8 | 2/2 | 1 |
| inheritance | 3/62 | 0/42 | 12/12 | 0/3 | 9 |
| operator_calls | 0/22 | 0/29 | 4/4 | 0/4 | 33 |
| operator_properties | 0/43 | 0/9 | 7/7 | 0/5 | 16 |
| properties | 420/421 | 93/95 | 5/5 | 9/9 | 0 |
| property_wrappers | 17/17 | - | 3/3 | 6/6 | 0 |
| registration | 3/40 | 0/4 | 3/3 | 0/3 | 4 |
| registration_checks | 2/9 | 0/36 | 10/10 | - | 3 |
| **total** | 602/796 | 132/276 | 63/63 | 18/35 | 71 |
