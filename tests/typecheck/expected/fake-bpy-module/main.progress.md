# Feature-test progress, fake-bpy-module stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 0/19 | 0/8 | 1/1 | - | 22 |
| addon_preferences | 0/13 | 0/5 | 7/7 | 0/3 | 21 |
| bpy_symbols | 0/157 | 1/48 | 3/3 | - | 146 |
| inheritance | 0/62 | 0/41 | 12/12 | 0/3 | 25 |
| operator_calls | 0/21 | 0/25 | 4/4 | 0/4 | 58 |
| operator_properties | 0/43 | 0/9 | 7/7 | 0/5 | 23 |
| properties | 0/409 | 0/64 | 2/2 | 0/9 | 303 |
| property_wrappers | 0/15 | - | 2/2 | 0/5 | 18 |
| registration | 0/40 | 0/5 | 3/3 | 0/3 | 12 |
| registration_checks | 0/8 | 0/36 | 10/10 | - | 16 |
| **total** | 0/787 | 1/241 | 51/51 | 0/32 | 644 |
