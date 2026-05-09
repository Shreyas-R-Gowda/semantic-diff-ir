"""
Evaluation harness for semantic diff quality.

Compares tool output against ground-truth annotations to measure:
  - Precision / recall of change detection
  - False-positive rate
  - Matching accuracy (did we pair the right functions?)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..classify.base import ChangeKind
from ..diff.engine import FunctionDiff, ModuleDiff


@dataclass
class EvalResult:
    total_functions:    int = 0
    correctly_matched:  int = 0
    false_positives:    int = 0   # reported changed but shouldn't be
    false_negatives:    int = 0   # not reported but should have been
    true_positives:     int = 0

    change_kind_hits:   Dict[str, int] = field(default_factory=dict)
    change_kind_misses: Dict[str, int] = field(default_factory=dict)

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def summary(self) -> str:
        return (
            f"Precision={self.precision:.2%}  "
            f"Recall={self.recall:.2%}  "
            f"F1={self.f1:.2%}  "
            f"TP={self.true_positives}  "
            f"FP={self.false_positives}  "
            f"FN={self.false_negatives}"
        )


@dataclass
class GroundTruth:
    """Expected changes for one function pair."""
    func_name:       str
    expected_status: str   # 'modified' | 'added' | 'removed' | 'unchanged'
    expected_kinds:  List[ChangeKind] = field(default_factory=list)


class Evaluator:
    """
    Compare a ModuleDiff + reported changes against ground-truth annotations.

    Typical usage in a test suite:
        gt = [
            GroundTruth("sum", "modified",
                        [ChangeKind.LOOP_UNROLL_GAINED, ChangeKind.VECTORIZE_GAINED]),
            GroundTruth("helper", "unchanged"),
        ]
        result = Evaluator().evaluate(module_diff, func_reports, gt)
        assert result.precision > 0.8
    """

    def evaluate(
        self,
        module_diff: ModuleDiff,
        func_reports,    # List[FunctionReport]
        ground_truth: List[GroundTruth],
    ) -> EvalResult:
        result = EvalResult()
        result.total_functions = len(ground_truth)

        diff_map   = {(fd.new_name or fd.old_name): fd for fd in module_diff.function_diffs}
        report_map = {r.func_name: r for r in func_reports}

        for gt in ground_truth:
            fd = diff_map.get(gt.func_name)
            if fd is None:
                result.false_negatives += 1
                continue

            status_correct = fd.status == gt.expected_status
            if status_correct:
                result.correctly_matched += 1

            if gt.expected_status in ("modified", "added", "removed"):
                if fd.status == gt.expected_status:
                    result.true_positives += 1
                elif fd.status == "unchanged":
                    result.false_negatives += 1
                else:
                    result.false_positives += 1
            else:
                if fd.status != "unchanged":
                    result.false_positives += 1

            report = report_map.get(gt.func_name)
            if report and gt.expected_kinds:
                found_kinds = {c.kind for c in report.changes}
                for k in gt.expected_kinds:
                    if k in found_kinds:
                        result.change_kind_hits[k.name] = (
                            result.change_kind_hits.get(k.name, 0) + 1
                        )
                    else:
                        result.change_kind_misses[k.name] = (
                            result.change_kind_misses.get(k.name, 0) + 1
                        )

        return result
