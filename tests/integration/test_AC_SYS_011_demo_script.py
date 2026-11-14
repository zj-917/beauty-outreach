"""End-to-end demo script (AC-SYS-011)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_AC_SYS_011_demo_script_runs_the_full_flow() -> None:
    """Given seeded mock data, when demo.py --fast runs, then it asserts and exits 0."""
    result = subprocess.run(
        [sys.executable, "scripts/demo.py", "--fast"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output

    assert "DEMO OK" in result.stdout
    assert "success=4" in result.stdout
    assert "failed=3" in result.stdout
    assert "skipped=13" in result.stdout
    assert "BLACKLISTED 2" in result.stdout
