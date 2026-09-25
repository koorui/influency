from __future__ import annotations

import argparse
import json

from .attribution import run_attribution
from .purification import run_purification


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="数据提纯与AI贡献归因集成工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    purify = subparsers.add_parser("purify", help="运行数据提纯和可选的高区分度选样")
    purify.add_argument("--records", required=True)
    purify.add_argument("--config", required=True)
    purify.add_argument("--output", required=True)
    purify.add_argument("--references")
    purify.add_argument("--responses")
    purify.add_argument("--split")

    attribute = subparsers.add_parser("attribute", help="基于结构化证据和Search发现运行贡献归因")
    attribute.add_argument("--input", required=True)
    attribute.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "purify":
        result = run_purification(
            args.records,
            args.config,
            args.output,
            references_path=args.references,
            responses_path=args.responses,
            split_path=args.split,
        )
    else:
        result = run_attribution(args.input, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

