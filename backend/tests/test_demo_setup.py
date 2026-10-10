"""Tests for the demo script's project-setup helper (no Gemini involved)."""

import importlib.util
from pathlib import Path

import pytest

from app.tools.test_tools import run_tests

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "investigate_demo.py"


@pytest.fixture(scope="module")
def demo():
    spec = importlib.util.spec_from_file_location("investigate_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("incident, expected_failed_test", [
    ("login", "test_login_with_valid_credentials_returns_a_token"),
    ("orders-total", "test_get_order_total_includes_sales_tax"),
    ("orders-404", "test_get_nonexistent_order_returns_404"),
])
def test_prepared_demo_project_has_exactly_one_bug_left(demo, incident, expected_failed_test):
    project = demo.prepare_demo_project(incident)

    result = run_tests(project)

    assert result.failed == 1
    assert f"FAILED tests/" in result.stdout and expected_failed_test in result.stdout.split("short test summary")[-1]


def test_preparing_the_demo_does_not_touch_the_shipped_project(demo):
    shipped = Path(__file__).resolve().parents[2] / "sample_project" / "app" / "auth.py"
    before = shipped.read_text()
    demo.prepare_demo_project("orders-total")
    assert shipped.read_text() == before
