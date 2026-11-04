A repository with several extensions below it (`addons/ws_alpha`, `addons/ws_beta`). Each folder with a
`blender_manifest.toml` is its own extension, although the import root is `features/addon_discovery`:
relative imports resolve inside each extension, and what one registers is not visible in the other.
