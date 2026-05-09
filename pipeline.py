"""
Pipeline orchestrator: source files → semantic diff report.

Usage (programmatic):
    pipeline = SemanticDiffPipeline()
    report   = pipeline.run("old.c", "new.c")
    print(report.render())

Usage (pre-compiled IR):
    report = pipeline.run_ir("old.ll", "new.ll")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .classify.control_flow import CFClassifier
from .classify.memory import MemClassifier
from .classify.optimizations import OptClassifier
from .classify.base import FunctionReport
from .compiler.extractor import IRExtractor, CompilationError
from .compiler.normalizer import IRNormalizer
from .diff.engine import DiffEngine, ModuleDiff, FunctionDiff
from .parser.parser import IRParser
from .parser.types import IRModule
from .report.renderer import ReportRenderer


@dataclass
class PipelineConfig:
    opt_level:    str = "O0"
    promote_mem:  bool = True
    clang:        str = "clang"
    opt_tool:     str = "opt"
    output_fmt:   str = "rich"   # 'rich' | 'json'
    extra_cflags: List[str] = field(default_factory=list)
    show_unchanged: bool = False


@dataclass
class DiffReport:
    module_diff: ModuleDiff
    func_reports: List[FunctionReport]
    config: PipelineConfig

    def render(self) -> str:
        renderer = ReportRenderer(show_unchanged=self.config.show_unchanged)
        if self.config.output_fmt == "json":
            return renderer.render_json(self.module_diff, self.func_reports)
        return renderer.render_rich(self.module_diff, self.func_reports)

    @property
    def has_changes(self) -> bool:
        return bool(self.module_diff.changed_functions)


class SemanticDiffPipeline:

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config    = config or PipelineConfig()
        self.normalizer = IRNormalizer()
        self.parser     = IRParser()
        self.engine     = DiffEngine()
        self.classifiers = [OptClassifier(), CFClassifier(), MemClassifier()]
        try:
            self.extractor = IRExtractor(
                clang=self.config.clang,
                opt=self.config.opt_tool,
            )
        except RuntimeError:
            self.extractor = None  # clang not available

    def run(self, old_src: str, new_src: str) -> DiffReport:
        """Compile source files and produce a semantic diff."""
        if self.extractor is None:
            raise CompilationError(
                "clang/opt not found. Install LLVM or use run_ir() to diff pre-compiled IR."
            )
        old_ir = self.extractor.extract(
            old_src, self.config.opt_level,
            self.config.extra_cflags, self.config.promote_mem,
        )
        new_ir = self.extractor.extract(
            new_src, self.config.opt_level,
            self.config.extra_cflags, self.config.promote_mem,
        )
        return self._diff_ir_text(old_ir, new_ir, old_src, new_src)

    def run_ir(self, old_ll: str, new_ll: str) -> DiffReport:
        """Diff pre-compiled LLVM IR files directly."""
        old_ir = Path(old_ll).read_text()
        new_ir = Path(new_ll).read_text()
        return self._diff_ir_text(old_ir, new_ir, old_ll, new_ll)

    def run_ir_text(
        self, old_ir: str, new_ir: str,
        old_label: str = "<old>", new_label: str = "<new>",
    ) -> DiffReport:
        """Diff LLVM IR given as raw strings."""
        return self._diff_ir_text(old_ir, new_ir, old_label, new_label)

    # ── internals ─────────────────────────────────────────────────────────────

    def _diff_ir_text(
        self, old_ir: str, new_ir: str,
        old_label: str, new_label: str,
    ) -> DiffReport:
        old_ir = self.normalizer.normalize(old_ir)
        new_ir = self.normalizer.normalize(new_ir)

        old_mod = self.parser.parse(old_ir, source_file=old_label)
        new_mod = self.parser.parse(new_ir, source_file=new_label)

        module_diff = self.engine.diff(old_mod, new_mod)

        func_reports: List[FunctionReport] = []
        for fd in module_diff.function_diffs:
            merged = FunctionReport(func_name=fd.new_name or fd.old_name)
            for clf in self.classifiers:
                sub = clf.classify(fd)
                merged.changes.extend(sub.changes)
            func_reports.append(merged)

        return DiffReport(
            module_diff=module_diff,
            func_reports=func_reports,
            config=self.config,
        )
