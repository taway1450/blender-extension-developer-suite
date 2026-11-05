import argparse

import pytest

from _common import StepError
from _target import add_target_arguments
from build_ty import binary_from_args, binary_path


def parse(binary, *argv):
    parser = argparse.ArgumentParser()
    add_target_arguments(parser, binary=binary)
    return parser.parse_args(["main", *argv])


def test_profile_defaults_to_release_and_debug_is_dev():
    assert parse("ty").profile == "release"
    assert parse("ty", "--debug").profile == "dev"
    assert parse("ty", "--profile", "profiling").profile == "profiling"
    assert binary_path("ty", "dev").parent.name == "debug"


def test_no_binary_arguments_without_a_binary():
    args = parse(None)
    assert args.target_binary is None
    with pytest.raises(SystemExit):
        parse(None, "--profile", "dev")


def test_given_binary_is_used_without_building(tmp_path):
    ruff = tmp_path / "ruff.exe"
    ruff.write_text("")
    assert binary_from_args(parse("ruff", "--ruff", str(ruff)), "ruff") == ruff.resolve()
    with pytest.raises(StepError):
        binary_from_args(parse("ruff", "--ruff", str(tmp_path / "missing")), "ruff")
