from __future__ import annotations

import argparse

from .config import load_config
from .screen import run_screen


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="edgar-chip-screener",
        description="Screen semiconductor companies from SEC submissions.zip and companyfacts.zip.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    screen_parser = subparsers.add_parser("screen", help="Run the SEC-only chip screener")
    screen_parser.add_argument("--submissions", required=True, help="Path to SEC submissions.zip")
    screen_parser.add_argument("--companyfacts", required=True, help="Path to SEC companyfacts.zip")
    screen_parser.add_argument("--config", help="Path to JSON config")
    screen_parser.add_argument("--output", default="outputs/chip_screen.csv", help="Output CSV path")

    args = parser.parse_args()
    if args.command == "screen":
        config = load_config(args.config)
        results = run_screen(args.submissions, args.companyfacts, config, args.output)
        passed = sum(1 for result in results if result.passed)
        print(f"Screened {len(results)} chip-related filers. Passed: {passed}. Output: {args.output}")


if __name__ == "__main__":
    main()

