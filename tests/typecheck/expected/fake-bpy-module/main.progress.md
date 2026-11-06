# Feature-test progress, fake-bpy-module stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 17/17 | 8/8 | 3/3 | - | 0 |
| addon_preferences | 9/10 | 5/5 | 10/10 | 3/3 | 1 |
| bpy_symbols | 153/153 | 47/47 | 9/9 | 2/2 | 0 |
| inheritance | 16/62 | 3/42 | 12/12 | 0/3 | 9 |
| operator_calls | 22/22 | 29/29 | 4/4 | 4/4 | 0 |
| operator_properties | 43/43 | 9/9 | 7/7 | 5/5 | 8 |
| properties | 421/421 | 101/101 | 5/5 | 9/9 | 0 |
| property_wrappers | 17/17 | - | 3/3 | 6/6 | 0 |
| registration | 40/40 | 4/4 | 3/3 | 2/3 | 3 |
| registration_checks | 9/9 | 35/36 | 10/10 | - | 2 |
| **total** | 747/794 | 241/281 | 66/66 | 31/35 | 23 |
