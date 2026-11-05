# Feature-test progress, builtin stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 8/19 | 7/8 | 1/1 | - | 22 |
| addon_preferences | 1/13 | 0/5 | 7/7 | 1/3 | 16 |
| bpy_symbols | 0/157 | 0/48 | 3/3 | - | 144 |
| inheritance | 0/62 | 0/41 | 12/12 | 0/3 | 26 |
| operator_calls | 0/21 | 0/25 | 4/4 | 0/4 | 58 |
| operator_properties | 0/43 | 1/9 | 7/7 | 0/5 | 25 |
| properties | 0/417 | 0/65 | 4/4 | 0/9 | 312 |
| property_wrappers | 0/15 | - | 2/2 | 0/5 | 18 |
| registration | 0/40 | 0/5 | 3/3 | 0/3 | 12 |
| registration_checks | 0/8 | 0/36 | 10/10 | - | 15 |
| **total** | 9/795 | 8/242 | 53/53 | 1/32 | 648 |
