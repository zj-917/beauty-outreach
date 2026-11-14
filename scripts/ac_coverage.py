"""Build the AC → test coverage report (06-test-plan §2, T-20).

A test counts for an AC when its function name follows
``test_AC_<MODULE>_<NNN>_…`` or its docstring carries a ``Covers:`` line.
Exits non-zero when any P0 AC has no test.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPECS = ROOT / "specs" / "modules"
DEFAULT_TESTS = ROOT / "tests"
DEFAULT_OUTPUT = ROOT / "docs" / "ac-coverage.md"

AC_ROW_RE = re.compile(r"^\|\s*(AC-[A-Z]+-\d{3})\s*\|\s*(P\d)(★?)\s*\|")
NAME_RE = re.compile(r"^test_AC_([A-Z]+)_(\d{3}(?:_\d{3})*)_")
AC_ID_RE = re.compile(r"AC-[A-Z]+-\d{3}")


@dataclass(frozen=True)
class Ac:
    """One acceptance criterion parsed from a module spec."""

    id: str
    priority: str


@dataclass(frozen=True)
class Hit:
    """One test function that exercises an AC."""

    path: str
    function: str


def parse_acs(specs: Path) -> list[Ac]:
    """Return every AC row across the module specs, in spec order."""
    acs: list[Ac] = []
    seen: set[str] = set()
    for path in sorted(specs.glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = AC_ROW_RE.match(line)
            if match and match.group(1) not in seen:
                seen.add(match.group(1))
                acs.append(Ac(match.group(1), match.group(2) + match.group(3)))
    return acs


def ac_ids_from_name(name: str) -> set[str]:
    """Map ``test_AC_STAT_001_004_x`` to ``{AC-STAT-001, AC-STAT-004}``."""
    match = NAME_RE.match(name)
    if match is None:
        return set()
    module = match.group(1)
    return {f"AC-{module}-{number}" for number in match.group(2).split("_")}


def scan_tests(tests: Path) -> dict[str, list[Hit]]:
    """Map AC ids to the test functions that reference them."""
    coverage: dict[str, list[Hit]] = {}
    for path in sorted(tests.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        relative = path.relative_to(tests.parent).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            ids = ac_ids_from_name(node.name)
            docstring = ast.get_docstring(node) or ""
            if "Covers:" in docstring:
                ids |= set(AC_ID_RE.findall(docstring))
            for ac_id in sorted(ids):
                coverage.setdefault(ac_id, []).append(Hit(relative, node.name))
    return coverage


def render_report(acs: list[Ac], coverage: dict[str, list[Hit]]) -> str:
    """Render the Markdown coverage table plus a summary."""
    lines = [
        "# AC → 测试覆盖表",
        "",
        "> 由 `python scripts/ac_coverage.py` 生成，请勿手工编辑。",
        "> 判定方式：测试函数名 `test_AC_<模块>_<编号>_…`，或 docstring 中的 `Covers:` 行。",
        "",
        "| AC | 优先级 | 测试 | 状态 |",
        "|---|---|---|---|",
    ]
    uncovered: list[Ac] = []
    for ac in acs:
        hits = coverage.get(ac.id, [])
        if hits:
            tests = "<br>".join(f"`{hit.path}::{hit.function}`" for hit in hits)
            status = "✅ 已覆盖"
        else:
            tests = "—"
            status = "⬜ 未覆盖"
            uncovered.append(ac)
        lines.append(f"| {ac.id} | {ac.priority} | {tests} | {status} |")

    covered = len(acs) - len(uncovered)
    by_priority = {"P0": [], "P1": [], "P2": []}
    for ac in uncovered:
        by_priority.setdefault(ac.priority[:2], []).append(ac)
    lines += [
        "",
        "## 汇总",
        "",
        f"- AC 总数：{len(acs)}",
        f"- 已覆盖：{covered}",
        f"- 未覆盖 P0：{len(by_priority['P0'])}",
        f"- 未覆盖 P1：{len(by_priority['P1'])}（不阻断）",
        f"- 未覆盖 P2：{len(by_priority['P2'])}（不排期）",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Parse options, write the report and report the blocking gap count."""
    parser = argparse.ArgumentParser(description="Generate the AC coverage report")
    parser.add_argument("--specs", type=Path, default=DEFAULT_SPECS)
    parser.add_argument("--tests", type=Path, default=DEFAULT_TESTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    acs = parse_acs(args.specs)
    if not acs:
        print(f"no AC tables found under {args.specs}", file=sys.stderr)
        return 2
    coverage = scan_tests(args.tests)
    report = render_report(acs, coverage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")

    uncovered = [ac for ac in acs if ac.id not in coverage]
    uncovered_p0 = [ac.id for ac in uncovered if ac.priority.startswith("P0")]
    print(f"AC coverage written to {args.output}")
    print(
        f"total={len(acs)} covered={len(acs) - len(uncovered)} "
        f"uncovered_p0={len(uncovered_p0)}"
    )
    if uncovered_p0:
        print("uncovered P0: " + ", ".join(uncovered_p0), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
