"""Screening evaluation script (AC-SCR-014)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_AC_SCR_014_eval_script_meets_targets() -> None:
    """Given mock data, when the eval script runs, then metrics and matrix are reported."""
    result = subprocess.run(
        [sys.executable, "scripts/eval_screening.py", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)

    assert payload["imported"] == 44
    assert payload["relevant_imported"] == 20
    assert payload["precision"] >= 0.95
    assert payload["recall"] >= 0.85
    assert payload["borderline_accuracy"] >= 0.75
    assert payload["passed"] is True
    assert payload["confusion"]["relevant"]["APPROVED"] == 20
    assert payload["confusion"]["borderline"]["PENDING_REVIEW"] == 8
    assert payload["confusion"]["irrelevant"]["DISCARDED"] == 16
