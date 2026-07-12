from __future__ import annotations

import argparse

from .config import load_config
from .download import download_sec_bulk_files
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
    screen_parser.add_argument("--limit", type=int, help="Stop after this many matching submission candidates")
    screen_parser.add_argument(
        "--only-cik",
        action="append",
        help="Screen one CIK. Can be repeated. Useful for small test runs.",
    )

    download_parser = subparsers.add_parser("download", help="Download SEC bulk ZIP files")
    download_parser.add_argument("--output-dir", default="data/raw", help="Directory for SEC ZIP files")
    download_parser.add_argument(
        "--contact-email",
        required=True,
        help="Email included in the SEC User-Agent declaration",
    )
    download_parser.add_argument("--overwrite", action="store_true", help="Replace existing ZIP files")

    args = parser.parse_args()
    if args.command == "screen":
        config = load_config(args.config)
        results = run_screen(
            args.submissions,
            args.companyfacts,
            config,
            args.output,
            limit=args.limit,
            only_ciks=args.only_cik,
        )
        passed = sum(1 for result in results if result.passed)
        print(f"Screened {len(results)} chip-related filers. Passed: {passed}. Output: {args.output}")
    elif args.command == "download":
        paths = download_sec_bulk_files(args.output_dir, args.contact_email, args.overwrite)
        print("Downloaded SEC data:")
        for path in paths:
            print(f"- {path}")


if __name__ == "__main__":
    main()
