"""The search path check:blender gives ty for Blender's bundled Python packages."""

import check_blender


def test_blender_site_links_the_listed_packages_and_drops_the_others(tmp_path, monkeypatch):
    install = tmp_path / "blender"
    packages = install / "5.4" / "python" / "lib" / "python3.13" / "site-packages"
    for package in ("numpy", "pxr", "typing_extensions"):
        (packages / package).mkdir(parents=True)
    site_dir = tmp_path / "blender-site"
    (site_dir / "main").mkdir(parents=True)
    (site_dir / "main" / "pxr").symlink_to(packages / "pxr", target_is_directory=True)  # listed by an older run
    monkeypatch.setattr(check_blender, "BLENDER_SITE_DIR", site_dir)
    monkeypatch.setattr(check_blender, "BLENDER_SITE_PACKAGES", ["numpy", "requests"])

    site = check_blender.blender_site("main", install)

    assert site == site_dir / "main"
    assert sorted(p.name for p in site.iterdir()) == ["numpy"]
    assert (site / "numpy").resolve() == (packages / "numpy").resolve()
