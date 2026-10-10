"""
Safe test-running tool.

This is the one tool in the layer that executes something rather than
just reading data, so it gets the strictest guardrail: it can ONLY run
`python -m pytest <path>` inside a given project root — never an arbitrary
shell command, and never a command a caller gets to construct freely. This
matches the project's safety requirement of an allowlist approach for
dangerous operations ("running predefined test commands" is allowed;
"arbitrary shell execution" is not).

No LLM involvement here either — running tests and reading their exit
code/output is deterministic.
"""

import re
import subprocess
import sys
from pathlib import Path

from app.tools.models import TestRunResult
from app.tools.security import resolve_within_root

_TIMEOUT_SECONDS = 60


def run_tests(project_root: Path, test_path: str = "tests") -> TestRunResult:
    """
    Run pytest against `test_path` (relative to `project_root`, defaults
    to the project's tests/ directory) and return a structured result.

    Raises PathSecurityError (via resolve_within_root) if test_path would
    resolve outside project_root — so this can't be pointed at some other
    part of the filesystem.
    """
    project_root = project_root.resolve()
    target = resolve_within_root(project_root, test_path)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(target), "-v", "--tb=short"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
    )

    return TestRunResult(
        passed=_count(result.stdout, "passed"),
        failed=_count(result.stdout, "failed"),
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _count(pytest_output: str, word: str) -> int:
    """Pull a count like '3 passed' or '2 failed' out of pytest's summary line."""
    match = re.search(rf"(\d+) {word}", pytest_output)
    return int(match.group(1)) if match else 0
