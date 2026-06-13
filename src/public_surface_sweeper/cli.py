from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .sweeper import SEVERITY_ORDER, Finding, format_summary, format_text, scan, summarize_findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check a repository for public release hygiene issues."
    )
    parser.add_argument("root", nargs="?", default=".", help="Repository root to scan.")
    parser.add_argument("--json", action="store_true", help="Print JSON findings.")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a release-readiness summary instead of individual findings.",
    )
    parser.add_argument(
        "--fail-on",
        choices=["none", "warning", "error"],
        default="error",
        help="Minimum severity that returns a failing exit code.",
    )
    return parser


def _should_fail(findings: list[Finding], fail_on: str) -> bool:
    if fail_on == "none":
        return False
    threshold = SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER[item.severity] >= threshold for item in findings)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    findings = scan(Path(args.root))
    if args.summary:
        summary = summarize_findings(findings)
        if args.json:
            print(json.dumps(asdict(summary), indent=2))
        else:
            print(format_summary(summary))
    elif args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2))
    else:
        print(format_text(findings))
    return 1 if _should_fail(findings, args.fail_on) else 0
