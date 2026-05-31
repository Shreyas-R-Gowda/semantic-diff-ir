"""
Evaluate semantic-diff against source files from exact local git commits.

The evaluator checks out each configured revision, compiles the selected source
file with clang, restores the repository checkout, and compares the detected
ChangeKind values with the expected set.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import yaml

from ..classify.base import ChangeKind
from ..pipeline import PipelineConfig, SemanticDiffPipeline


@dataclass(frozen=True)
class RealCommitCase:
    id: str
    repo: Path
    file: str
    old_commit: str
    new_commit: str
    expected_changes: List[ChangeKind]


@dataclass
class RealCommitCaseResult:
    case: RealCommitCase
    precision: float
    recall: float
    f1: float
    expected_kinds: List[str]
    found_kinds: List[str]
    missing_kinds: List[str]
    unexpected_kinds: List[str]

    @property
    def passed(self) -> bool:
        return not self.missing_kinds and not self.unexpected_kinds


@dataclass
class RealCommitSuiteResult:
    case_results: List[RealCommitCaseResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for result in self.case_results if result.passed)

    @property
    def total(self) -> int:
        return len(self.case_results)

    @property
    def average_f1(self) -> float:
        if not self.case_results:
            return 0.0
        return sum(result.f1 for result in self.case_results) / self.total

    def summary(self) -> str:
        return (
            f"Real commit cases passed={self.passed}/{self.total}  "
            f"average F1={self.average_f1:.2%}"
        )


def load_cases(config_path: str) -> List[RealCommitCase]:
    path = Path(config_path).expanduser().resolve()
    data = yaml.safe_load(path.read_text()) or {}
    entries = data.get("entries", data) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise ValueError("config must contain a YAML list or an 'entries' list")

    return [_parse_case(entry, index) for index, entry in enumerate(entries, 1)]


def run_real_commit_eval(
    cases: Iterable[RealCommitCase],
    clang: str = "clang",
) -> RealCommitSuiteResult:
    pipeline = SemanticDiffPipeline(PipelineConfig(output_fmt="json"))
    results: List[RealCommitCaseResult] = []

    for case in cases:
        _ensure_clean_repo(case.repo)
        original_ref = _current_ref(case.repo)
        try:
            old_ir = _compile_at_commit(case, case.old_commit, clang)
            new_ir = _compile_at_commit(case, case.new_commit, clang)
        finally:
            _git_checkout(case.repo, original_ref)

        report = pipeline.run_ir_text(
            old_ir,
            new_ir,
            f"{case.id}:old",
            f"{case.id}:new",
        )
        expected = sorted(kind.name for kind in case.expected_changes)
        found = sorted(
            {
                change.kind.name
                for func_report in report.func_reports
                for change in func_report.changes
            }
        )
        results.append(_build_result(case, expected, found))

    return RealCommitSuiteResult(results)


def render_real_commit_text(result: RealCommitSuiteResult) -> str:
    lines = [result.summary(), ""]
    for item in result.case_results:
        marker = "PASS" if item.passed else "FAIL"
        lines.append(f"{marker} {item.case.id} [{item.case.repo.name}]")
        lines.append(f"  file:        {item.case.file}")
        lines.append(
            f"  commits:     {item.case.old_commit} -> {item.case.new_commit}"
        )
        lines.append(f"  precision:   {item.precision:.2%}")
        lines.append(f"  recall:      {item.recall:.2%}")
        lines.append(f"  F1:          {item.f1:.2%}")
        lines.append(f"  expected:    {', '.join(item.expected_kinds) or '-'}")
        lines.append(f"  found:       {', '.join(item.found_kinds) or '-'}")
        if item.missing_kinds:
            lines.append(f"  missing:     {', '.join(item.missing_kinds)}")
        if item.unexpected_kinds:
            lines.append(f"  extra:       {', '.join(item.unexpected_kinds)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m semantic_diff.eval.real_commit_eval",
        description="Evaluate semantic-diff against exact commits in local git repos.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to YAML config containing real-commit evaluation entries",
    )
    parser.add_argument(
        "--clang",
        default="clang",
        help="Path to clang binary (default: clang)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_real_commit_eval(load_cases(args.config), clang=args.clang)
    print(render_real_commit_text(result))
    return 0 if result.passed == result.total else 1


def _parse_case(entry: Any, index: int) -> RealCommitCase:
    if not isinstance(entry, dict):
        raise ValueError(f"entry {index} must be a YAML mapping")

    required = ("repo", "file", "old_commit", "new_commit", "expected_changes")
    missing = [key for key in required if key not in entry]
    if missing:
        raise ValueError(f"entry {index} is missing: {', '.join(missing)}")

    repo = Path(str(entry["repo"])).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f"entry {index} repo does not exist: {repo}")

    expected = _parse_expected_changes(entry["expected_changes"], index)
    case_id = str(entry.get("id") or f"{repo.name}:{entry['file']}:{index}")
    return RealCommitCase(
        id=case_id,
        repo=repo,
        file=str(entry["file"]),
        old_commit=str(entry["old_commit"]),
        new_commit=str(entry["new_commit"]),
        expected_changes=expected,
    )


def _parse_expected_changes(values: Any, index: int) -> List[ChangeKind]:
    if not isinstance(values, list):
        raise ValueError(f"entry {index} expected_changes must be a list")

    expected: List[ChangeKind] = []
    for value in values:
        try:
            expected.append(ChangeKind[str(value)])
        except KeyError as exc:
            raise ValueError(
                f"entry {index} has unknown ChangeKind: {value}"
            ) from exc
    return expected


def _build_result(
    case: RealCommitCase,
    expected: List[str],
    found: List[str],
) -> RealCommitCaseResult:
    expected_set = set(expected)
    found_set = set(found)
    true_positives = len(expected_set & found_set)
    false_positives = len(found_set - expected_set)
    false_negatives = len(expected_set - found_set)
    precision = _ratio(true_positives, true_positives + false_positives)
    recall = _ratio(true_positives, true_positives + false_negatives)
    f1 = _ratio(2 * precision * recall, precision + recall)
    return RealCommitCaseResult(
        case=case,
        precision=precision,
        recall=recall,
        f1=f1,
        expected_kinds=expected,
        found_kinds=found,
        missing_kinds=sorted(expected_set - found_set),
        unexpected_kinds=sorted(found_set - expected_set),
    )


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _ensure_clean_repo(repo: Path) -> None:
    status = _run(["git", "status", "--porcelain"], cwd=repo).stdout.strip()
    if status:
        raise RuntimeError(
            f"refusing to checkout commits in dirty repository: {repo}"
        )


def _current_ref(repo: Path) -> str:
    branch = _run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=repo,
        check=False,
    )
    if branch.returncode == 0:
        return branch.stdout.strip()
    return _run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()


def _compile_at_commit(case: RealCommitCase, commit: str, clang: str) -> str:
    _git_checkout(case.repo, commit)
    source = case.repo / case.file
    if not source.is_file():
        raise FileNotFoundError(f"{case.file} does not exist at commit {commit}")

    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "output.ll"
        _run(
            [
                clang,
                "-O2",
                "-S",
                "-emit-llvm",
                "-fno-discard-value-names",
                str(source),
                "-o",
                str(output),
            ],
            cwd=case.repo,
        )
        return output.read_text()


def _git_checkout(repo: Path, ref: str) -> None:
    _run(["git", "checkout", "--quiet", ref], cwd=repo)


def _run(
    command: List[str],
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        timeout=120,
    )


if __name__ == "__main__":
    raise SystemExit(main())
