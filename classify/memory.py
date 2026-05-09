"""
Memory-access change classifier.

Threshold fix over v1:
  The original used an absolute delta threshold of 2, which meant going
  from 2→4 loads (100% increase, delta=2) didn't fire because the check
  was `abs(delta) >= 2` — 2 is not >= 2 is False.  More fundamentally,
  an absolute delta is wrong for all function sizes: a delta of 1 on a
  2-load function (50% change) is more significant than a delta of 5 on
  a 200-load function (2.5% change).

  New policy: fire when EITHER the absolute delta >= MIN_ABS_DELTA (catches
  tiny functions where even 1 extra load matters) OR the relative change
  >= MIN_REL_CHANGE (catches large functions where percentages matter more).
"""
from __future__ import annotations

from ..diff.engine import FunctionDiff
from ..parser.types import Opcode
from .base import ChangeKind, FunctionReport

_MIN_ABS_DELTA  = 1      # fire on any single-instruction change
_MIN_REL_CHANGE = 0.25   # or any ≥25% relative change (whichever triggers first)


def _should_report(old_cnt: int, new_cnt: int) -> bool:
    delta = abs(new_cnt - old_cnt)
    if delta == 0:
        return False
    if delta >= _MIN_ABS_DELTA:
        return True
    baseline = old_cnt or 1
    return (delta / baseline) >= _MIN_REL_CHANGE


class MemClassifier:

    def classify(self, diff: FunctionDiff) -> FunctionReport:
        report = FunctionReport(func_name=diff.new_name or diff.old_name)
        self._load_store(diff, report)
        self._alloca(diff, report)
        self._mem_deps(diff, report)
        return report

    def _load_store(self, diff: FunctionDiff, report: FunctionReport):
        for op, kind, label in [
            (Opcode.LOAD,  ChangeKind.LOAD_COUNT_CHANGED,  "load"),
            (Opcode.STORE, ChangeKind.STORE_COUNT_CHANGED, "store"),
        ]:
            old_cnt = diff.old_histogram.get(op.value, 0)
            new_cnt = diff.new_histogram.get(op.value, 0)
            delta   = new_cnt - old_cnt

            if not _should_report(old_cnt, new_cnt):
                continue

            direction = "UP" if delta > 0 else "DOWN"
            sev       = "warn" if delta > 0 else "info"
            baseline  = old_cnt or 1
            pct       = abs(delta) / baseline * 100
            report.add(
                kind,
                f"{label.upper()} count {direction}: {old_cnt} → {new_cnt} "
                f"({delta:+d}, {pct:.0f}%)",
                severity=sev,
                details=(
                    "More loads increase memory bandwidth pressure."
                    if delta > 0 and label == "load" else
                    "More stores increase write bandwidth and may stall pipelines."
                    if delta > 0 else
                    f"Fewer {label}s — likely due to CSE, DCE, or vectorization."
                ),
            )

    def _alloca(self, diff: FunctionDiff, report: FunctionReport):
        old_alloca = diff.old_histogram.get(Opcode.ALLOCA.value, 0)
        new_alloca = diff.new_histogram.get(Opcode.ALLOCA.value, 0)
        delta = new_alloca - old_alloca

        if delta == 0:
            return

        direction = "UP" if delta > 0 else "DOWN"
        sev       = "warn" if delta > 0 else "info"
        report.add(
            ChangeKind.ALLOCA_CHANGED,
            f"Stack allocations {direction}: {old_alloca} → {new_alloca} ({delta:+d})",
            severity=sev,
            details=(
                "More allocas may indicate register spills, new local variables, "
                "or that mem2reg was not applied."
                if delta > 0 else
                "Fewer allocas: variables promoted to registers (mem2reg) or eliminated."
            ),
        )

    def _mem_deps(self, diff: FunctionDiff, report: FunctionReport):
        if diff.status in ("added", "removed"):
            return

        old_deps = diff.old_mem_deps
        new_deps = diff.new_mem_deps
        delta    = new_deps - old_deps

        if not _should_report(old_deps, new_deps):
            return

        direction = "UP" if delta > 0 else "DOWN"
        sev       = "warn" if delta > 0 else "info"
        baseline  = old_deps or 1
        pct       = abs(delta) / baseline * 100
        report.add(
            ChangeKind.MEM_DEP_CHANGED,
            f"Memory dependencies {direction}: {old_deps} → {new_deps} "
            f"({delta:+d}, {pct:.0f}%)",
            severity=sev,
            details=(
                "More store→load pairs on same pointer. May block vectorization "
                "and cause pipeline stalls. Consider __restrict or loop restructuring."
                if delta > 0 else
                "Fewer store→load dependencies — better alias analysis or restructuring. "
                "May unlock vectorization."
            ),
        )
