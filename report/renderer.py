"""
Report renderer: ModuleDiff + FunctionReport list → human-readable output.

Improvements over original:
  - Changes grouped by severity tier (perf → warn → info) for scannability
  - Confidence indicator on function matches (exact/signature/histogram/body)
  - 'details' lines shown for every change that has one
  - Before/after summary table for modified functions
  - JSON output includes match_reason for traceability
"""
from __future__ import annotations

import json
from typing import List

from ..classify.base import ChangeKind, FunctionReport, SemanticChange
from ..diff.engine import BlockDiff, FunctionDiff, ModuleDiff

# ── ANSI helpers ─────────────────────────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_DIM    = "\033[2m"
_MAGENTA= "\033[35m"

_SEV_COLOR = {
    "perf":  _CYAN,
    "warn":  _YELLOW,
    "info":  _GREEN,
    "error": _RED,
}
_SEV_ORDER = {"perf": 0, "warn": 1, "info": 2, "error": 0}

_STATUS_ICON = {
    "added":     f"{_GREEN}+{_RESET}",
    "removed":   f"{_RED}-{_RESET}",
    "modified":  f"{_YELLOW}~{_RESET}",
    "unchanged": f"{_DIM}={_RESET}",
}

_CONFIDENCE_BADGE = {
    "exact":     "",
    "signature": f" {_DIM}[sig-match]{_RESET}",
    "histogram": f" {_DIM}[hist-match]{_RESET}",
    "body":      f" {_DIM}[body-match]{_RESET}",
}


def _c(text: str, color: str) -> str:
    return f"{color}{text}{_RESET}"


def _bold(text: str) -> str:
    return f"{_BOLD}{text}{_RESET}"


class ReportRenderer:

    def __init__(self, show_unchanged: bool = False, color: bool = True):
        self.show_unchanged = show_unchanged
        self.color = color

    # ── rich terminal ─────────────────────────────────────────────────────────

    def render_rich(
        self, diff: ModuleDiff, reports: List[FunctionReport]
    ) -> str:
        lines: List[str] = []
        report_map = {r.func_name: r for r in reports}

        lines.append(_bold("=" * 72))
        lines.append(
            _bold(f"Semantic Diff: {diff.old_source!r}  →  {diff.new_source!r}")
        )
        lines.append(_bold("=" * 72))

        total_changed = len(diff.changed_functions)
        lines.append(
            f"  Functions changed: {_bold(str(total_changed))} / "
            f"{len(diff.function_diffs)}"
        )
        lines.append("")

        # Sort: modified first, then added/removed, then unchanged
        ordered = sorted(
            diff.function_diffs,
            key=lambda fd: (
                0 if fd.status == "modified" else
                1 if fd.status in ("added", "removed") else 2
            ),
        )

        for fd in ordered:
            if fd.status == "unchanged" and not self.show_unchanged:
                continue
            self._render_function(fd, report_map, lines)

        if not diff.changed_functions:
            lines.append(_c("  No semantic changes detected.", _GREEN))

        lines.append("")
        return "\n".join(lines)

    def _render_function(
        self,
        fd: FunctionDiff,
        report_map: dict,
        lines: List[str],
    ):
        icon   = _STATUS_ICON.get(fd.status, "?")
        name   = fd.new_name or fd.old_name
        header = f"{icon} {_bold(name)}"

        # Confidence badge (only for non-exact matches)
        badge = _CONFIDENCE_BADGE.get(fd.match_reason, "")

        if fd.status == "added":
            header += f"  [{_c('ADDED', _GREEN)}, {fd.new_instr_count} instrs]{badge}"
        elif fd.status == "removed":
            header += f"  [{_c('REMOVED', _RED)}, {fd.old_instr_count} instrs]{badge}"
        elif fd.status == "modified":
            delta_str = (
                f"{fd.instr_delta:+d} instrs" if fd.instr_delta else "structural only"
            )
            header += f"  [{_c('MODIFIED', _YELLOW)}, {delta_str}]{badge}"
        else:
            header += f"  [{_c('unchanged', _DIM)}]{badge}"

        lines.append(header)

        if fd.status == "modified":
            self._render_summary_table(fd, lines)

        report = report_map.get(name)
        if report and report.has_changes:
            # Group by severity: perf → warn → info
            grouped: dict = {"perf": [], "warn": [], "info": [], "error": []}
            for change in report.changes:
                grouped.setdefault(change.severity, []).append(change)

            for sev in ("perf", "warn", "error", "info"):
                for change in grouped.get(sev, []):
                    self._render_change(change, lines)

        self._render_block_diffs(fd.block_diffs, lines)
        lines.append("")

    def _render_summary_table(self, fd: FunctionDiff, lines: List[str]):
        rows = [
            ("instrs",        fd.old_instr_count,   fd.new_instr_count),
            ("blocks",        fd.old_block_count,   fd.new_block_count),
            ("CFG edges",     fd.old_edge_count,    fd.new_edge_count),
            ("critical path", fd.old_critical_path, fd.new_critical_path),
            ("mem deps",      fd.old_mem_deps,       fd.new_mem_deps),
        ]
        for label, old_val, new_val in rows:
            delta = new_val - old_val
            if delta == 0:
                continue
            color = _RED if delta > 0 else _GREEN
            sign  = "+" if delta > 0 else ""
            lines.append(
                f"    {label:<14} {old_val} → {_c(str(new_val), color)} "
                f"({_c(f'{sign}{delta}', color)})"
            )

    def _render_change(self, change: SemanticChange, lines: List[str]):
        color = _SEV_COLOR.get(change.severity, "")
        tag   = f"[{change.severity.upper()}]"
        lines.append(f"    {_c(tag, color)} {change.description}")
        if change.details:
            lines.append(f"           {_c(change.details, _DIM)}")

    def _render_block_diffs(
        self, block_diffs: List[BlockDiff], lines: List[str]
    ):
        changed = [bd for bd in block_diffs if bd.changed]
        if not changed:
            return

        lines.append(f"    {_bold('Block-level changes:')}")
        for bd in changed:
            if bd.status == "added":
                lbl = bd.new_label or "?"
                lines.append(f"      {_c('+', _GREEN)} block {lbl!r} ADDED")
            elif bd.status == "removed":
                lbl = bd.old_label or "?"
                lines.append(f"      {_c('-', _RED)} block {lbl!r} REMOVED")
            else:
                old_lbl = bd.old_label or "?"
                new_lbl = bd.new_label or "?"
                lbl_str = old_lbl if old_lbl == new_lbl else f"{old_lbl!r}→{new_lbl!r}"
                pct = f"{bd.similarity:.0%}"
                lines.append(
                    f"      {_c('~', _YELLOW)} block {lbl_str} modified "
                    f"(similarity {pct})"
                )
                if bd.removed_instrs:
                    lines.append(
                        f"        removed: {', '.join(bd.removed_instrs[:8])}"
                        + (" …" if len(bd.removed_instrs) > 8 else "")
                    )
                if bd.added_instrs:
                    lines.append(
                        f"        added:   {', '.join(bd.added_instrs[:8])}"
                        + (" …" if len(bd.added_instrs) > 8 else "")
                    )

    # ── JSON output ───────────────────────────────────────────────────────────

    def render_json(
        self, diff: ModuleDiff, reports: List[FunctionReport]
    ) -> str:
        report_map = {r.func_name: r for r in reports}
        out = {
            "old_source": diff.old_source,
            "new_source": diff.new_source,
            "summary": {
                "total_functions": len(diff.function_diffs),
                "changed": len(diff.changed_functions),
                "added": sum(1 for fd in diff.function_diffs if fd.status == "added"),
                "removed": sum(1 for fd in diff.function_diffs if fd.status == "removed"),
                "modified": sum(1 for fd in diff.function_diffs if fd.status == "modified"),
            },
            "functions": [
                self._fd_to_dict(fd, report_map)
                for fd in diff.function_diffs
                if fd.status != "unchanged" or self.show_unchanged
            ],
        }
        return json.dumps(out, indent=2)

    def _fd_to_dict(self, fd: FunctionDiff, report_map: dict) -> dict:
        name   = fd.new_name or fd.old_name
        report = report_map.get(name)
        changes = []
        if report:
            changes = [
                {
                    "kind":        c.kind.name,
                    "description": c.description,
                    "severity":    c.severity,
                    "details":     c.details,
                }
                for c in report.changes
            ]

        return {
            "old_name":         fd.old_name,
            "new_name":         fd.new_name,
            "status":           fd.status,
            "match_confidence": round(fd.match_confidence, 3),
            "match_reason":     fd.match_reason,
            "metrics": {
                "old_instr_count":   fd.old_instr_count,
                "new_instr_count":   fd.new_instr_count,
                "instr_delta":       fd.instr_delta,
                "old_block_count":   fd.old_block_count,
                "new_block_count":   fd.new_block_count,
                "old_critical_path": fd.old_critical_path,
                "new_critical_path": fd.new_critical_path,
                "critical_path_delta": fd.critical_path_delta,
                "old_mem_deps":      fd.old_mem_deps,
                "new_mem_deps":      fd.new_mem_deps,
            },
            "block_diffs": [
                {
                    "old_label":      bd.old_label,
                    "new_label":      bd.new_label,
                    "status":         bd.status,
                    "similarity":     round(bd.similarity, 3),
                    "added_instrs":   bd.added_instrs,
                    "removed_instrs": bd.removed_instrs,
                }
                for bd in fd.block_diffs
                if bd.changed
            ],
            "changes": changes,
        }
