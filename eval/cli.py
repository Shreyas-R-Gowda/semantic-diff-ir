from __future__ import annotations

import argparse
import json

from .benchmark import benchmark_to_dict, render_benchmark_text, run_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semantic-diff-eval",
        description="Run the built-in semantic-diff benchmark suite.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: text (default) or json",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark()
    if args.format == "json":
        print(json.dumps(benchmark_to_dict(result), indent=2))
    else:
        print(render_benchmark_text(result))
    return 0 if result.passed == result.total else 1


if __name__ == "__main__":
    raise SystemExit(main())
