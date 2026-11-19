"""The search path check:blender gives ty for Blender's bundled Python packages."""

import check_blender


def test_blender_site_links_the_listed_packages_and_drops_the_others(tmp_path, monkeypatch):
    install = tmp_path / "blender"
    packages = install / "5.4" / "python" / "lib" / "python3.13" / "site-packages"
    for package in ("numpy", "pxr", "typing_extensions"):
        (packages / package).mkdir(parents=True)
    site_dir = tmp_path / "blender-site"
    (site_dir / "main").mkdir(parents=True)
    check_blender.link_directory(site_dir / "main" / "pxr", packages / "pxr")  # listed by an older run
    monkeypatch.setattr(check_blender, "BLENDER_SITE_DIR", site_dir)
    monkeypatch.setattr(check_blender, "BLENDER_SITE_PACKAGES", ["numpy", "requests"])

    site = check_blender.blender_site("main", install)

    assert site == site_dir / "main"
    assert sorted(p.name for p in site.iterdir()) == ["numpy"]
    assert (site / "numpy").resolve() == (packages / "numpy").resolve()


def test_blender_site_links_the_default_addons_from_the_source(tmp_path, monkeypatch):
    install = tmp_path / "blender"
    (install / "5.4" / "python" / "lib" / "python3.13" / "site-packages" / "numpy").mkdir(parents=True)
    source = tmp_path / "source"
    (source / "intern" / "cycles" / "blender" / "addon").mkdir(parents=True)
    monkeypatch.setattr(check_blender, "BLENDER_SITE_DIR", tmp_path / "blender-site")
    monkeypatch.setattr(check_blender, "BLENDER_SITE_PACKAGES", ["numpy"])

    site = check_blender.blender_site("main", install, source)

    assert site is not None
    assert sorted(p.name for p in site.iterdir()) == ["cycles", "numpy"]
    assert (site / "cycles").resolve() == (source / "intern" / "cycles" / "blender" / "addon").resolve()


def test_rendered_runtime_stubs_leave_out_the_copied_sources(tmp_path, monkeypatch):
    stubs = tmp_path / "stubs"
    for path in ("bpy/types/__init__.pyi", "bl_ui/__init__.py", "bpy_extras/wm_utils/progress_report.py"):
        (stubs / path).parent.mkdir(parents=True, exist_ok=True)
        (stubs / path).write_text("", encoding="utf-8")
    (stubs / check_blender.COMPLETE_MARKER).write_text("build 1", encoding="utf-8")
    monkeypatch.setattr(check_blender, "RUNTIME_RENDERED_DIR", tmp_path / "rendered")

    rendered = check_blender.rendered_runtime_stubs("main", stubs)

    files = sorted(p.relative_to(rendered).as_posix() for p in rendered.rglob("*") if p.is_file())
    assert files == [check_blender.COMPLETE_MARKER, "bpy/types/__init__.pyi"]
    assert not (rendered / "bpy_extras").exists()  # a folder of copies alone would be a namespace package


def test_rendered_runtime_stubs_follow_new_stubs(tmp_path, monkeypatch):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "old.pyi").write_text("", encoding="utf-8")
    (stubs / check_blender.COMPLETE_MARKER).write_text("build 1", encoding="utf-8")
    monkeypatch.setattr(check_blender, "RUNTIME_RENDERED_DIR", tmp_path / "rendered")
    check_blender.rendered_runtime_stubs("main", stubs)
    (stubs / "old.pyi").unlink()
    (stubs / "new.pyi").write_text("", encoding="utf-8")

    unchanged = check_blender.rendered_runtime_stubs("main", stubs)
    assert (unchanged / "old.pyi").exists()  # the same marker: the mirror is reused
    (stubs / check_blender.COMPLETE_MARKER).write_text("build 2", encoding="utf-8")
    refreshed = check_blender.rendered_runtime_stubs("main", stubs)
    assert sorted(p.name for p in refreshed.glob("*.pyi")) == ["new.pyi"]
