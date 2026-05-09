"""
Built-in semantic-diff benchmark cases.

The cases are small LLVM IR pairs with commit-style descriptions and expected
semantic consequences. They let the evaluator exercise the full normalization,
parse, diff, classify, and report pipeline without requiring network access,
large repository checkouts, or a local LLVM `opt` binary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from ..classify.base import ChangeKind
from ..pipeline import PipelineConfig, SemanticDiffPipeline
from .evaluator import Evaluator, GroundTruth


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    project: str
    commit_description: str
    old_ir: str
    new_ir: str
    ground_truth: List[GroundTruth]


@dataclass
class BenchmarkCaseResult:
    case: BenchmarkCase
    precision: float
    recall: float
    f1: float
    expected_kinds: List[str]
    found_kinds: List[str]
    missing_kinds: List[str]
    unexpected_kinds: List[str]

    @property
    def passed(self) -> bool:
        return not self.missing_kinds and self.recall == 1.0


@dataclass
class BenchmarkSuiteResult:
    case_results: List[BenchmarkCaseResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.case_results if r.passed)

    @property
    def total(self) -> int:
        return len(self.case_results)

    @property
    def average_f1(self) -> float:
        if not self.case_results:
            return 0.0
        return sum(r.f1 for r in self.case_results) / len(self.case_results)

    def summary(self) -> str:
        return (
            f"Benchmark cases passed={self.passed}/{self.total}  "
            f"average F1={self.average_f1:.2%}"
        )


def builtin_benchmark_cases() -> List[BenchmarkCase]:
    return [
        BenchmarkCase(
            id="llvm-loop-vectorize-gained",
            project="LLVM LoopVectorize",
            commit_description=(
                "Recognize a fixed-stride loop and emit vector IR for the hot path."
            ),
            old_ir=_SCALAR_LOOP,
            new_ir=_VECTORIZED_LOOP,
            ground_truth=[
                GroundTruth(
                    "kernel",
                    "modified",
                    [ChangeKind.LOOP_UNROLL_GAINED, ChangeKind.VECTORIZE_GAINED],
                )
            ],
        ),
        BenchmarkCase(
            id="llvm-loop-vectorize-lost",
            project="LLVM LoopVectorize",
            commit_description=(
                "A bound/aliasing change prevents the loop from using the vector path."
            ),
            old_ir=_VECTORIZED_LOOP,
            new_ir=_SCALAR_LOOP,
            ground_truth=[
                GroundTruth(
                    "kernel",
                    "modified",
                    [ChangeKind.LOOP_UNROLL_LOST, ChangeKind.VECTORIZE_LOST],
                )
            ],
        ),
        BenchmarkCase(
            id="llvm-inline-added",
            project="LLVM Inliner",
            commit_description=(
                "A small helper becomes profitable to inline into the caller."
            ),
            old_ir=_CALL_HELPER,
            new_ir=_HELPER_INLINED,
            ground_truth=[
                GroundTruth("compute", "modified", [ChangeKind.INLINING_ADDED])
            ],
        ),
        BenchmarkCase(
            id="llvm-inline-removed",
            project="LLVM Inliner",
            commit_description=(
                "A helper grows past the inline threshold and remains a call."
            ),
            old_ir=_HELPER_INLINED,
            new_ir=_CALL_HELPER,
            ground_truth=[
                GroundTruth("compute", "modified", [ChangeKind.INLINING_REMOVED])
            ],
        ),
        BenchmarkCase(
            id="llvm-branch-added",
            project="LLVM InstCombine",
            commit_description=(
                "A fast-path guard introduces an extra conditional branch."
            ),
            old_ir=_RETURN_INPUT,
            new_ir=_ABS_WITH_BRANCH,
            ground_truth=[
                GroundTruth(
                    "compute",
                    "modified",
                    [
                        ChangeKind.BRANCH_ADDED,
                        ChangeKind.CFG_COMPLEXITY_UP,
                        ChangeKind.DEAD_CODE_REINTRODUCED,
                        ChangeKind.INSTR_COUNT_UP,
                    ],
                )
            ],
        ),
        BenchmarkCase(
            id="llvm-branch-removed",
            project="LLVM SimplifyCFG",
            commit_description=(
                "A conditional branch is folded into straight-line select code."
            ),
            old_ir=_ABS_WITH_BRANCH,
            new_ir=_ABS_WITH_SELECT,
            ground_truth=[
                GroundTruth(
                    "compute",
                    "modified",
                    [
                        ChangeKind.BRANCH_REMOVED,
                        ChangeKind.CFG_COMPLEXITY_DOWN,
                        ChangeKind.DEAD_CODE_ELIMINATED,
                        ChangeKind.INSTR_COUNT_DOWN,
                    ],
                )
            ],
        ),
        BenchmarkCase(
            id="sqlite-loads-added",
            project="SQLite",
            commit_description=(
                "A new predicate reads an additional field from the row header."
            ),
            old_ir=_ONE_LOAD,
            new_ir=_TWO_LOADS,
            ground_truth=[
                GroundTruth(
                    "compute",
                    "modified",
                    [ChangeKind.LOAD_COUNT_CHANGED, ChangeKind.INSTR_COUNT_UP],
                )
            ],
        ),
        BenchmarkCase(
            id="postgres-stores-removed",
            project="PostgreSQL",
            commit_description=(
                "Remove a redundant state write after proving the value unchanged."
            ),
            old_ir=_TWO_STORES,
            new_ir=_ONE_STORE,
            ground_truth=[
                GroundTruth(
                    "compute",
                    "modified",
                    [ChangeKind.STORE_COUNT_CHANGED, ChangeKind.INSTR_COUNT_DOWN],
                )
            ],
        ),
        BenchmarkCase(
            id="redis-memdeps-added",
            project="Redis",
            commit_description=(
                "An update path adds store-load reuse on the same pointer."
            ),
            old_ir=_LOW_MEM_DEPS,
            new_ir=_HIGH_MEM_DEPS,
            ground_truth=[
                GroundTruth(
                    "compute",
                    "modified",
                    [
                        ChangeKind.LOAD_COUNT_CHANGED,
                        ChangeKind.STORE_COUNT_CHANGED,
                        ChangeKind.MEM_DEP_CHANGED,
                        ChangeKind.INSTR_COUNT_UP,
                    ],
                )
            ],
        ),
        BenchmarkCase(
            id="openssl-critical-path-longer",
            project="OpenSSL",
            commit_description=(
                "A hardened arithmetic sequence adds serial data dependencies."
            ),
            old_ir=_SHORT_DEP_CHAIN,
            new_ir=_LONG_DEP_CHAIN,
            ground_truth=[
                GroundTruth(
                    "compute",
                    "modified",
                    [ChangeKind.CRITICAL_PATH_LONGER, ChangeKind.INSTR_COUNT_UP],
                )
            ],
        ),
    ]


def run_benchmark(
    cases: Iterable[BenchmarkCase] | None = None,
    config: PipelineConfig | None = None,
) -> BenchmarkSuiteResult:
    pipeline = SemanticDiffPipeline(config or PipelineConfig(output_fmt="json"))
    evaluator = Evaluator()
    results: List[BenchmarkCaseResult] = []

    for case in cases or builtin_benchmark_cases():
        report = pipeline.run_ir_text(case.old_ir, case.new_ir, case.id + ":old", case.id + ":new")
        eval_result = evaluator.evaluate(
            report.module_diff, report.func_reports, case.ground_truth
        )
        expected = _expected_kind_names(case.ground_truth)
        found = _found_kind_names(report.func_reports)
        results.append(
            BenchmarkCaseResult(
                case=case,
                precision=eval_result.precision,
                recall=eval_result.recall,
                f1=eval_result.f1,
                expected_kinds=expected,
                found_kinds=found,
                missing_kinds=sorted(set(expected) - set(found)),
                unexpected_kinds=sorted(set(found) - set(expected)),
            )
        )

    return BenchmarkSuiteResult(results)


def render_benchmark_text(result: BenchmarkSuiteResult) -> str:
    lines = [result.summary(), ""]
    for item in result.case_results:
        marker = "PASS" if item.passed else "FAIL"
        lines.append(f"{marker} {item.case.id} [{item.case.project}]")
        lines.append(f"  description: {item.case.commit_description}")
        lines.append(f"  expected: {', '.join(item.expected_kinds) or '-'}")
        lines.append(f"  found:    {', '.join(item.found_kinds) or '-'}")
        if item.missing_kinds:
            lines.append(f"  missing:  {', '.join(item.missing_kinds)}")
        if item.unexpected_kinds:
            lines.append(f"  extra:    {', '.join(item.unexpected_kinds)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def benchmark_to_dict(result: BenchmarkSuiteResult) -> Dict[str, object]:
    return {
        "summary": {
            "passed": result.passed,
            "total": result.total,
            "average_f1": result.average_f1,
        },
        "cases": [
            {
                "id": item.case.id,
                "project": item.case.project,
                "commit_description": item.case.commit_description,
                "passed": item.passed,
                "precision": item.precision,
                "recall": item.recall,
                "f1": item.f1,
                "expected_kinds": item.expected_kinds,
                "found_kinds": item.found_kinds,
                "missing_kinds": item.missing_kinds,
                "unexpected_kinds": item.unexpected_kinds,
            }
            for item in result.case_results
        ],
    }


def _expected_kind_names(ground_truth: List[GroundTruth]) -> List[str]:
    return sorted({kind.name for gt in ground_truth for kind in gt.expected_kinds})


def _found_kind_names(func_reports) -> List[str]:
    return sorted({change.kind.name for report in func_reports for change in report.changes})


_SCALAR_LOOP = """\
define i32 @kernel(ptr %p, i32 %n) {
entry:
  br label %loop
loop:
  %i = phi i32 [ 0, %entry ], [ %i2, %loop ]
  %ptr = getelementptr i32, ptr %p, i32 %i
  %v = load i32, ptr %ptr
  %i2 = add i32 %i, 1
  %c = icmp slt i32 %i2, %n
  br i1 %c, label %loop, label %exit
exit:
  ret i32 %v
}
"""

_VECTORIZED_LOOP = """\
define i32 @kernel(ptr %p, i32 %n) {
entry:
  br label %loop
loop:
  %i = phi i32 [ 0, %entry ], [ %i2, %loop ]
  %ptr = getelementptr <4 x i32>, ptr %p, i32 %i
  %v = load <4 x i32>, ptr %ptr
  %i2 = add i32 %i, 4
  %c = icmp slt i32 %i2, %n
  br i1 %c, label %loop, label %exit
exit:
  %e = extractelement <4 x i32> %v, i32 0
  ret i32 %e
}
"""

_CALL_HELPER = """\
define i32 @compute(i32 %x) {
entry:
  %r = call i32 @helper(i32 %x)
  ret i32 %r
}
"""

_HELPER_INLINED = """\
define i32 @compute(i32 %x) {
entry:
  %r = mul i32 %x, %x
  ret i32 %r
}
"""

_RETURN_INPUT = """\
define i32 @compute(i32 %x) {
entry:
  ret i32 %x
}
"""

_ABS_WITH_BRANCH = """\
define i32 @compute(i32 %x) {
entry:
  %c = icmp sgt i32 %x, 0
  br i1 %c, label %pos, label %neg
pos:
  ret i32 %x
neg:
  %n = sub i32 0, %x
  ret i32 %n
}
"""

_ABS_WITH_SELECT = """\
define i32 @compute(i32 %x) {
entry:
  %c = icmp sgt i32 %x, 0
  %n = sub i32 0, %x
  %r = select i1 %c, i32 %x, i32 %n
  ret i32 %r
}
"""

_ONE_LOAD = """\
define i32 @compute(ptr %p) {
entry:
  %a = load i32, ptr %p
  ret i32 %a
}
"""

_TWO_LOADS = """\
define i32 @compute(ptr %p, ptr %q) {
entry:
  %a = load i32, ptr %p
  %b = load i32, ptr %q
  %s = add i32 %a, %b
  ret i32 %s
}
"""

_TWO_STORES = """\
define void @compute(ptr %p, i32 %x) {
entry:
  store i32 %x, ptr %p
  store i32 %x, ptr %p
  ret void
}
"""

_ONE_STORE = """\
define void @compute(ptr %p, i32 %x) {
entry:
  store i32 %x, ptr %p
  ret void
}
"""

_LOW_MEM_DEPS = """\
define i32 @compute(ptr %p, i32 %x) {
entry:
  store i32 %x, ptr %p
  %a = load i32, ptr %p
  ret i32 %a
}
"""

_HIGH_MEM_DEPS = """\
define i32 @compute(ptr %p, i32 %x) {
entry:
  store i32 %x, ptr %p
  %a = load i32, ptr %p
  store i32 %a, ptr %p
  %b = load i32, ptr %p
  ret i32 %b
}
"""

_SHORT_DEP_CHAIN = """\
define i32 @compute(i32 %x) {
entry:
  %a = add i32 %x, 1
  %b = add i32 %x, 2
  %c = add i32 %a, %b
  ret i32 %c
}
"""

_LONG_DEP_CHAIN = """\
define i32 @compute(i32 %x) {
entry:
  %a = add i32 %x, 1
  %b = mul i32 %a, 3
  %c = sub i32 %b, 4
  %d = xor i32 %c, %a
  %e = add i32 %d, %b
  %f = mul i32 %e, %c
  %g = add i32 %f, %d
  ret i32 %g
}
"""
