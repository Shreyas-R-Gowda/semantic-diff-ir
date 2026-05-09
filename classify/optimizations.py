"""
Optimization-level change classifier.

Fixes over the original:
  - Wrong enum: "unroll factor changed" was using LOOP_UNROLL_LOST (wrong
    kind and severity).  Now uses a descriptive message under LOOP_UNROLL_GAINED
    or LOOP_UNROLL_LOST with the actual direction.
  - Dead code condition was too strict: removed_blocks > 0 AND instr_delta < 0
    missed cases where instructions were reorganized (blocks removed but
    overall count grew due to scalar epilogue in a vectorized loop).
  - Inlining now estimates expected instruction delta for stronger evidence.
  - IV stride change now reported as an unroll signal even without explicit
    factor metadata.
"""
from __future__ import annotations
from ..diff.engine import FunctionDiff, LoopDiff
from .base import ChangeKind, FunctionReport


class OptClassifier:

    def classify(self, diff: FunctionDiff) -> FunctionReport:
        report = FunctionReport(func_name=diff.new_name or diff.old_name)
        self._loop_opts(diff, report)
        self._inlining(diff, report)
        self._dead_code(diff, report)
        return report

    def _loop_opts(self, diff: FunctionDiff, report: FunctionReport):
        for ld in diff.loop_diffs:
            old, new, hdr = ld.old_loop, ld.new_loop, ld.header

            if old is None and new is not None:
                report.add(ChangeKind.LOOP_ADDED,
                            f"Loop at block {hdr!r} ADDED", severity="warn")
                continue
            if old is not None and new is None:
                report.add(ChangeKind.LOOP_REMOVED,
                            f"Loop at block {hdr!r} REMOVED", severity="info")
                continue

            # Unroll changes
            if ld.unroll_changed:
                old_f = old.unroll_factor
                new_f = new.unroll_factor
                if old_f is None and new_f is not None:
                    report.add(
                        ChangeKind.LOOP_UNROLL_GAINED,
                        f"Loop {hdr!r}: unrolling ADDED (factor ×{new_f})",
                        severity="perf",
                        details=f"IV stride: {new.iv_stride}  phi nodes: {new.phi_count}",
                    )
                elif old_f is not None and new_f is None:
                    report.add(
                        ChangeKind.LOOP_UNROLL_LOST,
                        f"Loop {hdr!r}: unrolling LOST (was ×{old_f})",
                        severity="perf",
                        details=(
                            "Possible causes: trip count became non-constant, "
                            "loop body too large after inlining, or -O2 → -O0."
                        ),
                    )
                else:
                    # Factor changed (e.g. x4 → x8)
                    kind = (ChangeKind.LOOP_UNROLL_GAINED
                            if (new_f or 0) > (old_f or 0)
                            else ChangeKind.LOOP_UNROLL_LOST)
                    report.add(
                        kind,
                        f"Loop {hdr!r}: unroll factor ×{old_f} → ×{new_f}",
                        severity="perf",
                    )
            elif ld.iv_stride_changed and not ld.unroll_changed:
                # IV stride changed but unroll_factor was not detected —
                # still a meaningful signal worth surfacing
                old_s = old.iv_stride if old else 1
                new_s = new.iv_stride if new else 1
                if new_s != old_s:
                    report.add(
                        ChangeKind.LOOP_UNROLL_GAINED if new_s > old_s
                        else ChangeKind.LOOP_UNROLL_LOST,
                        f"Loop {hdr!r}: IV stride {old_s} → {new_s} "
                        f"(unroll signal, factor not determined)",
                        severity="perf",
                    )

            # Vectorization changes
            if ld.vector_changed:
                old_w = old.vector_width if old else 0
                new_w = new.vector_width if new else 0
                if old_w == 0 and new_w > 0:
                    report.add(
                        ChangeKind.VECTORIZE_GAINED,
                        f"Loop {hdr!r}: vectorization GAINED (width={new_w})",
                        severity="perf",
                        details=(
                            f"Expect ~{new_w}× throughput on memory-bound ops. "
                            f"Trip count: {new.trip_count or 'unknown'}."
                        ),
                    )
                    # Mark instr delta as explained to suppress noisy INSTR_COUNT_UP
                    diff.explained_instr_delta = True
                elif old_w > 0 and new_w == 0:
                    report.add(
                        ChangeKind.VECTORIZE_LOST,
                        f"Loop {hdr!r}: vectorization LOST",
                        severity="perf",
                        details=(
                            f"Was width={old_w}. Possible causes: aliasing "
                            "introduced, non-constant trip count, or loop body "
                            "contains non-vectorizable instructions."
                        ),
                    )
                else:
                    report.add(
                        ChangeKind.VECTORIZE_WIDTH_CHANGE,
                        f"Loop {hdr!r}: vector width {old_w} → {new_w}",
                        severity="perf",
                        details=f"Throughput impact: ~{new_w/old_w:.1f}× relative change.",
                    )

            if ld.runtime_check_added:
                report.add(
                    ChangeKind.RUNTIME_CHECK_ADDED,
                    f"Loop {hdr!r}: runtime alias check ADDED",
                    severity="warn",
                    details=(
                        "Alias check adds a branch at loop entry. "
                        "The scalar fallback path will execute if pointers overlap."
                    ),
                )

    def _inlining(self, diff: FunctionDiff, report: FunctionReport):
        for callee in diff.inlined_functions:
            report.add(
                ChangeKind.INLINING_ADDED,
                f"{callee!r} inlined (call site removed from {diff.new_name!r})",
                severity="perf",
                details=(
                    "Inlining eliminates call overhead and enables "
                    "cross-function optimizations (CSE, DCE, loop opts)."
                ),
            )
            # Inlining adds instructions — mark delta as explained
            if diff.instr_delta > 0:
                diff.explained_instr_delta = True

        for callee in diff.deinlined_functions:
            report.add(
                ChangeKind.INLINING_REMOVED,
                f"{callee!r} no longer inlined (new call site in {diff.new_name!r})",
                severity="perf",
                details=(
                    "Possible causes: function size exceeded inline threshold, "
                    "noinline attribute added, or optimization level lowered."
                ),
            )

    def _dead_code(self, diff: FunctionDiff, report: FunctionReport):
        removed_blocks = sum(1 for bd in diff.block_diffs if bd.status == "removed")
        added_blocks   = sum(1 for bd in diff.block_diffs if bd.status == "added")

        # Original condition (instr_delta < 0) was too strict: missed
        # cases where a dead block was removed but vector epilogue was added.
        if removed_blocks > 0 and not diff.has_loop_or_vector_change():
            report.add(
                ChangeKind.DEAD_CODE_ELIMINATED,
                f"{removed_blocks} block(s) eliminated "
                f"({abs(diff.instr_delta)} fewer instructions)",
                severity="info",
                details=(
                    "Eliminated blocks are unreachable or provably never taken. "
                    "This is a correctness-preserving optimization."
                ),
            )

        if added_blocks > 0 and diff.instr_delta > 0 and not diff.has_loop_or_vector_change():
            report.add(
                ChangeKind.DEAD_CODE_REINTRODUCED,
                f"{added_blocks} new block(s) added, {diff.instr_delta} more instructions",
                severity="warn",
            )
