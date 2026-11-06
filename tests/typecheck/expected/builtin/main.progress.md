# Feature-test progress, builtin stubs, Blender main

Markers that pass, per feature, and the diagnostics on lines without a marker. Written by `--update` of
`check:features` and `check:ide` from the recorded results next to this file; do not edit. Guards are markers
that hold without ty-blender (`# bare-ok`) and are not counted in the assert_type and expected-error columns.

| Feature | assert_type | expected errors | guards | IDE | other diagnostics |
| --- | --- | --- | --- | --- | --- |
| addon_discovery | 17/17 | 8/8 | 3/3 | - | 0 |
| addon_preferences | 11/11 | 5/5 | 10/10 | 3/3 | 1 |
| bpy_symbols | 153/153 | 47/47 | 9/9 | 2/2 | 0 |
| inheritance | 16/62 | 3/42 | 12/12 | 0/3 | 9 |
| operator_calls | 22/22 | 29/29 | 4/4 | 4/4 | 0 |
| operator_properties | 45/45 | 9/9 | 7/7 | 5/5 | 7 |
| properties | 421/421 | 101/101 | 5/5 | 9/9 | 0 |
| property_wrappers | 17/17 | - | 3/3 | 6/6 | 0 |
| registration | 40/40 | 4/4 | 3/3 | 3/3 | 3 |
| registration_checks | 9/9 | 37/37 | 10/10 | - | 0 |
| **total** | 751/797 | 243/282 | 66/66 | 32/35 | 20 |
