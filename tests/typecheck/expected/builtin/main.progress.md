# Feature-test progress, builtin stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 8/19 | 7/8 | 1/1 | - | 21 |
| addon_preferences | 1/13 | 0/5 | 7/7 | 1/3 | 4 |
| bpy_symbols | 85/157 | 28/48 | 3/3 | - | 39 |
| inheritance | 0/62 | 0/41 | 12/12 | 0/3 | 12 |
| operator_calls | 0/21 | 0/25 | 4/4 | 0/4 | 33 |
| operator_properties | 0/43 | 1/9 | 7/7 | 0/5 | 20 |
| properties | 121/417 | 33/65 | 4/4 | 5/9 | 39 |
| property_wrappers | 2/15 | - | 2/2 | 1/5 | 15 |
| registration | 0/40 | 0/5 | 3/3 | 0/3 | 11 |
| registration_checks | 0/8 | 0/36 | 10/10 | - | 10 |
| **total** | 217/795 | 69/242 | 53/53 | 7/32 | 204 |
