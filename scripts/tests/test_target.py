import argparse

import pytest

from _common import StepError
from _target import add_target_arguments
from build_ty import binary_from_args, stock_command


def parse(binary, *argv):
    parser = argparse.ArgumentParser()
    add_target_arguments(parser, binary=binary)
    return parser.parse_args(["main", *argv])


def test_profile_defaults_to_dev():
    assert parse("ty").profile == "dev"
    assert parse("ty", "--profile", "profiling").profile == "profiling"


def test_no_binary_arguments_without_a_binary():
    args = parse(None)
    assert args.target_binary is None
    with pytest.raises(SystemExit):
        parse(None, "--profile", "dev")


def test_given_binary_is_used_without_building(tmp_path):
    ty = tmp_path / "ty.exe"
    ty.write_text("")
    assert binary_from_args(parse("ty", "--ty", str(ty)), "ty") == ty.resolve()
    with pytest.raises(StepError):
        binary_from_args(parse("ty", "--ty", str(tmp_path / "missing")), "ty")


def test_stock_commands_pin_the_fork_base():
    assert stock_command("ty")[1].startswith("ty@0.")
    assert stock_command("ruff")[1].startswith("ruff@0.")
