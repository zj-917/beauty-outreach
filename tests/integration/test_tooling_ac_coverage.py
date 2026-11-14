"""The AC → test coverage tool from 06-test-plan §2."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ac_coverage.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_ac_coverage_report_lists_every_ac_and_passes(tmp_path: Path) -> None:
    """Given the real specs and tests, when the tool runs, then every P0 is covered."""
    output = tmp_path / "coverage.md"
    result = _run("--output", str(output))
    assert result.returncode == 0, result.stdout + result.stderr

    report = output.read_text(encoding="utf-8")
    assert report.count("\n| AC-") == 145
    assert "| AC-SYS-007 | P0 |" in report
    assert "test_AC_SYS_007_fresh_startup_smoke_test_runs_lifespan" in report
    assert "| AC-SYS-010 | P1 |" in report
    assert "test_AC_SYS_010_shutdown_stops_the_worker_within_five_seconds" in report
    assert "未覆盖 P0：0" in report


def test_ac_coverage_exits_nonzero_when_a_p0_has_no_test(tmp_path: Path) -> None:
    """Given a P0 AC without any test, when the tool runs, then it reports and exits 1."""
    specs = tmp_path / "specs" / "modules"
    specs.mkdir(parents=True)
    (specs / "demo.md").write_text(
        "| AC | P | 描述 |\n|---|---|---|\n"
        "| AC-DEMO-001 | P0 | 未覆盖的 P0 |\n"
        "| AC-DEMO-002 | P2 | 未排期 |\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    output = tmp_path / "coverage.md"

    result = _run(
        "--specs", str(specs), "--tests", str(tests), "--output", str(output)
    )

    assert result.returncode == 1
    assert "AC-DEMO-001" in result.stderr
    report = output.read_text(encoding="utf-8")
    assert "| AC-DEMO-001 | P0 | — | ⬜ 未覆盖 |" in report
    assert "| AC-DEMO-002 | P2 | — | ⬜ 未覆盖 |" in report
    assert "未覆盖 P0：1" in report


def test_ac_coverage_reads_covers_docstrings(tmp_path: Path) -> None:
    """Given a scenario test with a Covers line, when the tool runs, then the AC is covered."""
    specs = tmp_path / "specs" / "modules"
    specs.mkdir(parents=True)
    (specs / "demo.md").write_text(
        "| AC | P | 描述 |\n|---|---|---|\n| AC-DEMO-001 | P0 | 场景 |\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_scenario.py").write_text(
        'def test_e2e_99_scenario():\n'
        '    """Covers: AC-DEMO-001.\n\n'
        "    Given x, when y, then z.\n"
        '    """\n',
        encoding="utf-8",
    )
    output = tmp_path / "coverage.md"

    result = _run(
        "--specs", str(specs), "--tests", str(tests), "--output", str(output)
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = output.read_text(encoding="utf-8")
    expected_row = (
        "| AC-DEMO-001 | P0 | `tests/test_scenario.py::test_e2e_99_scenario` "
        "| ✅ 已覆盖 |"
    )
    assert expected_row in report
