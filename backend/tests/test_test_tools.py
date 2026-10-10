"""
Tests for app.tools.test_tools.run_tests.

This genuinely spawns a real `python -m pytest` subprocess against a
throwaway project written to tmp_path — it does not mock subprocess. That
means these tests are a little slower than the others, but they prove the
tool actually works end to end, not just that it builds the right command.
"""

import pytest

from app.tools.security import PathSecurityError
from app.tools.test_tools import run_tests


@pytest.fixture
def toy_project(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_toy.py").write_text(
        "def test_one_plus_one():\n"
        "    assert 1 + 1 == 2\n"
        "\n"
        "def test_deliberately_wrong():\n"
        "    assert 1 + 1 == 3\n"
    )
    return tmp_path


def test_run_tests_reports_correct_pass_and_fail_counts(toy_project):
    result = run_tests(toy_project)

    assert result.passed == 1
    assert result.failed == 1
    assert result.exit_code != 0
    assert not result.all_passed
    assert "test_deliberately_wrong" in result.stdout


def test_run_tests_all_passed_when_everything_passes(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_toy.py").write_text("def test_ok():\n    assert True\n")

    result = run_tests(tmp_path)

    assert result.passed == 1
    assert result.failed == 0
    assert result.exit_code == 0
    assert result.all_passed


def test_run_tests_rejects_path_outside_project_root(toy_project):
    with pytest.raises(PathSecurityError):
        run_tests(toy_project, test_path="../../etc")
