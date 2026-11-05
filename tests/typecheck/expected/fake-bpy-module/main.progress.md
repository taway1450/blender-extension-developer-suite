# Feature-test progress, fake-bpy-module stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 16/19 | 7/8 | 1/1 | - | 0 |
| addon_preferences | 1/13 | 0/5 | 7/7 | 1/3 | 2 |
| bpy_symbols | 114/157 | 29/48 | 3/3 | - | 11 |
| inheritance | 3/62 | 0/41 | 12/12 | 0/3 | 9 |
| operator_calls | 0/21 | 0/25 | 4/4 | 0/4 | 33 |
| operator_properties | 0/43 | 0/9 | 7/7 | 0/5 | 18 |
| properties | 163/417 | 38/65 | 4/4 | 9/9 | 3 |
| property_wrappers | 2/15 | - | 2/2 | 1/5 | 15 |
| registration | 3/40 | 0/5 | 3/3 | 0/3 | 4 |
| registration_checks | 2/8 | 0/36 | 10/10 | - | 3 |
| **total** | 304/795 | 74/242 | 53/53 | 11/32 | 98 |
