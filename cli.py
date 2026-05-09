"""
semantic-diff CLI entry point.

Usage examples:
  semantic-diff old.c new.c
  semantic-diff --ir old.ll new.ll
  semantic-diff --format json old.c new.c
  semantic-diff --opt O2 old.c new.c
  semantic-diff --show-unchanged old.c new.c
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from semantic_diff.pipeline import PipelineConfig, SemanticDiffPipeline
else:
    from .pipeline import PipelineConfig, SemanticDiffPipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="semantic-diff",
        description="Semantic diff for compiler IR — compare C/C++ source or LLVM IR files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("old", help="Old source file (.c/.cpp) or IR file (.ll) with --ir")
    p.add_argument("new", help="New source file (.c/.cpp) or IR file (.ll) with --ir")

    p.add_argument(
        "--ir", action="store_true",
        help="Treat inputs as pre-compiled LLVM IR (.ll) instead of source files",
    )
    p.add_argument(
        "--opt", default="O0", metavar="LEVEL",
        help="Optimization level passed to clang (default: O0)",
    )
    p.add_argument(
        "--no-mem2reg", action="store_true",
        help="Skip mem2reg/sroa promotion passes",
    )
    p.add_argument(
        "--format", choices=["rich", "json"], default="rich", dest="fmt",
        help="Output format: rich (default) or json",
    )
    p.add_argument(
        "--show-unchanged", action="store_true",
        help="Include unchanged functions in the report",
    )
    p.add_argument(
        "--clang", default="clang", metavar="PATH",
        help="Path to clang binary (default: clang)",
    )
    p.add_argument(
        "--opt-tool", default="opt", metavar="PATH",
        help="Path to opt binary (default: opt)",
    )
    p.add_argument(
        "-D", action="append", dest="defines", metavar="NAME[=VAL]", default=[],
        help="Pass -DNAME[=VAL] to the compiler (may be repeated)",
    )
    p.add_argument(
        "-I", action="append", dest="includes", metavar="DIR", default=[],
        help="Pass -IDIR to the compiler (may be repeated)",
    )
    p.add_argument(
        "--std", metavar="STANDARD", default=None,
        help="C/C++ language standard passed to clang (e.g. c11, c++17, c++20)",
    )
    p.add_argument(
        "-o", "--output", metavar="FILE", default=None,
        help="Write the report to FILE instead of stdout",
    )
    p.add_argument(
        "--dot", metavar="DIR", default=None,
        help="Write per-function CFG diff as .dot files to DIR (requires graphviz to render)",
    )
    return p


def main(argv=None):
    parser = build_parser()
    args   = parser.parse_args(argv)

    extra_cflags = (
        [f"-D{d}" for d in args.defines] +
        [f"-I{i}" for i in args.includes]
    )
    if args.std:
        extra_cflags.append(f"-std={args.std}")

    config = PipelineConfig(
        opt_level=args.opt,
        promote_mem=not args.no_mem2reg,
        clang=args.clang,
        opt_tool=args.opt_tool,
        output_fmt=args.fmt,
        extra_cflags=extra_cflags,
        show_unchanged=args.show_unchanged,
    )

    try:
        pipeline = SemanticDiffPipeline(config)
        if args.ir:
            report = pipeline.run_ir(args.old, args.new)
        else:
            report = pipeline.run(args.old, args.new)
        rendered = report.render()
        if args.output:
            Path(args.output).write_text(rendered)
        else:
            print(rendered)
        if args.dot:
            if __package__ in (None, ""):
                from semantic_diff.report.dot_renderer import DotRenderer
            else:
                from .report.dot_renderer import DotRenderer
            written = DotRenderer().render(
                report.module_diff, report.func_reports, args.dot
            )
            for path in written:
                print(f"dot: wrote {path}", file=sys.stderr)
        sys.exit(0 if not report.has_changes else 1)

    except FileNotFoundError as e:
        print(f"error: file not found: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
