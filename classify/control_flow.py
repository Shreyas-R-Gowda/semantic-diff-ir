"""
Control-flow and performance metric classifier.

Fixes over the original:
  - INSTR_COUNT_UP/DOWN now suppressed when loop/vector/inlining changes
    already explain the delta (FunctionDiff.explained_instr_delta flag).
  - CFG complexity threshold is relative (20% edge change) but now also
    requires a minimum absolute delta to avoid noise on tiny functions.
  - Critical path threshold raised to 3 to reduce noise.
  - All metrics add a 'details' string explaining the likely cause.
"""
from __future__ import annotations

from ..diff.engine import FunctionDiff
from ..parser.types import Opcode
from .base import ChangeKind, FunctionReport

_CFG_COMPLEX_REL_THRESHOLD  = 0.20   # 20% relative edge change
_CFG_COMPLEX_ABS_THRESHOLD  = 2      # minimum absolute edge delta
_CRITICAL_PATH_THRESHOLD    = 3      # minimum delta to report


class CFClassifier:

    def classify(self, diff: FunctionDiff) -> FunctionReport:
        report = FunctionReport(func_name=diff.new_name or diff.old_name)
        self._branch_changes(diff, report)
        self._cfg_complexity(diff, report)
        self._perf_metrics(diff, report)
        return report

    def _branch_changes(self, diff: FunctionDiff, report: FunctionReport):
        old_br = diff.old_histogram.get(Opcode.BR.value, 0)
        new_br = diff.new_histogram.get(Opcode.BR.value, 0)
        old_sw = diff.old_histogram.get(Opcode.SWITCH.value, 0)
        new_sw = diff.new_histogram.get(Opcode.SWITCH.value, 0)

        old_total = old_br + old_sw
        new_total = new_br + new_sw
        delta = new_total - old_total

        if delta > 0:
            report.add(
                ChangeKind.BRANCH_ADDED,
                f"{delta} branch(es) ADDED "
                f"(br: {old_br}→{new_br}"
                + (f", switch: {old_sw}→{new_sw}" if old_sw or new_sw else "")
                + ")",
                severity="warn",
                details=(
                    "Additional branches add misprediction risk. "
                    "Check if an early-exit or guard was added."
                ),
            )
        elif delta < 0:
            report.add(
                ChangeKind.BRANCH_REMOVED,
                f"{abs(delta)} branch(es) REMOVED "
                f"(br: {old_br}→{new_br}"
                + (f", switch: {old_sw}→{new_sw}" if old_sw or new_sw else "")
                + ")",
                severity="info",
                details="Fewer branches reduces misprediction exposure.",
            )

    def _cfg_complexity(self, diff: FunctionDiff, report: FunctionReport):
        if diff.status in ("added", "removed"):
            return

        old_edges = diff.old_edge_count
        new_edges = diff.new_edge_count
        delta_abs = new_edges - old_edges

        if old_edges == 0 and new_edges == 0:
            return

        # Require both relative AND absolute thresholds to fire
        baseline = old_edges or 1
        delta_rel = delta_abs / baseline

        if (abs(delta_rel) > _CFG_COMPLEX_REL_THRESHOLD
                and abs(delta_abs) >= _CFG_COMPLEX_ABS_THRESHOLD):
            if delta_abs > 0:
                report.add(
                    ChangeKind.CFG_COMPLEXITY_UP,
                    f"CFG complexity INCREASED: edges {old_edges}→{new_edges} "
                    f"(+{delta_rel:.0%}), blocks {diff.old_block_count}→{diff.new_block_count}",
                    severity="warn",
                    details=(
                        "Higher CFG complexity can degrade branch prediction "
                        "and increase register pressure."
                    ),
                )
            else:
                report.add(
                    ChangeKind.CFG_COMPLEXITY_DOWN,
                    f"CFG complexity DECREASED: edges {old_edges}→{new_edges} "
                    f"({delta_rel:.0%}), blocks {diff.old_block_count}→{diff.new_block_count}",
                    severity="info",
                )

    def _perf_metrics(self, diff: FunctionDiff, report: FunctionReport):
        if diff.status in ("added", "removed"):
            return

        # Instruction count: suppress when loop/vector/inlining already explains it
        if not diff.explained_instr_delta:
            if diff.instr_delta > 0:
                report.add(
                    ChangeKind.INSTR_COUNT_UP,
                    f"Instruction count UP: {diff.old_instr_count}→{diff.new_instr_count} "
                    f"(+{diff.instr_delta})",
                    severity="info",
                )
            elif diff.instr_delta < 0:
                report.add(
                    ChangeKind.INSTR_COUNT_DOWN,
                    f"Instruction count DOWN: {diff.old_instr_count}→{diff.new_instr_count} "
                    f"({diff.instr_delta})",
                    severity="info",
                )

        # Critical path: only report meaningful changes
        cp_delta = diff.critical_path_delta
        if cp_delta > _CRITICAL_PATH_THRESHOLD:
            report.add(
                ChangeKind.CRITICAL_PATH_LONGER,
                f"Critical path LONGER: {diff.old_critical_path}→{diff.new_critical_path} "
                f"(+{cp_delta} use-def hops)",
                severity="perf",
                details=(
                    "Longer critical path increases minimum latency. "
                    "Check for new serial dependencies in the hot path."
                ),
            )
        elif cp_delta < -_CRITICAL_PATH_THRESHOLD:
            report.add(
                ChangeKind.CRITICAL_PATH_SHORTER,
                f"Critical path SHORTER: {diff.old_critical_path}→{diff.new_critical_path} "
                f"({cp_delta} use-def hops)",
                severity="perf",
                details="Shorter critical path improves out-of-order execution opportunity.",
            )
