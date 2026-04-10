"""Argparse builder for the ``modes`` CLI.

Kept in a separate module so ``test_cli_args.py`` can exercise the
flag surface without importing the heavier ``decode``, ``live``,
``_source``, ``_sink``, ``_tui`` modules.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``modes`` argument parser with both subcommands."""
    parser = argparse.ArgumentParser(
        prog="modes",
        description=(
            "pymodes command-line tool. Use `modes decode MESSAGE` for one-shot "
            "decoding or `modes live --network HOST:PORT` for streaming."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="SUBCOMMAND")

    _add_decode_parser(subparsers)
    _add_live_parser(subparsers)

    return parser


def _add_decode_parser(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    decode_p = subparsers.add_parser(
        "decode",
        help="Decode a single hex message or a file of hex messages.",
        description=(
            "Decode one Mode-S/ADS-B hex message and print the result as JSON, "
            "or decode a file of hex messages (one per line) as JSON lines."
        ),
        epilog=(
            "Examples:\n"
            "  modes decode 8D406B902015A678D4D220AA4BDA\n"
            "  modes decode 8D40058B58C901375147EFD09357 --reference 49.0 6.0\n"
            "  modes decode 8D406B902015A678D4D220AA4BDA --compact | jq .\n"
            "  modes decode --file captures/lfbo.csv --surface-ref LFBO\n"
            "  modes decode --file - --compact < capture.log\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional MESSAGE OR --file PATH (but not both)
    input_group = decode_p.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Single hex message to decode (14 or 28 hex chars).",
    )
    input_group.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="Read hex messages from a file (one per line or 'timestamp,hex' CSV). "
        "Use '-' for stdin.",
    )

    decode_p.add_argument(
        "--compact",
        action="store_true",
        help="Emit one-line JSON instead of pretty-printed (default: pretty).",
    )
    decode_p.add_argument(
        "--full-dict",
        action="store_true",
        help="Populate every key in the canonical schema (missing = null).",
    )
    decode_p.add_argument(
        "--reference",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        default=None,
        help="Airborne CPR reference (lat, lon). Only valid with a single "
        "positional MESSAGE — not with --file.",
    )
    decode_p.add_argument(
        "--surface-ref",
        metavar="REF",
        default=None,
        help="Surface CPR reference: airport ICAO code (e.g. LFBO) or 'lat,lon'.",
    )


def _add_live_parser(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    live_p = subparsers.add_parser(
        "live",
        help="Stream decode from a network TCP source.",
        description=(
            "Connect to a dump1090-style TCP feed, parse Mode-S Beast "
            "binary frames, and emit decoded JSON lines to stdout or a "
            "rich-based live aircraft table."
        ),
        epilog=(
            "Examples:\n"
            "  modes live --network localhost:30005\n"
            "  modes live --network airsquitter.lr.tudelft.nl:10006\n"
            "  modes live --network host:30002 --dump-to flight.jsonl\n"
            "  modes live --network host:30002 --tui  (requires pymodes[tui])\n"
            "  modes live --network host:30002 --quiet --dump-to flight.jsonl\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    live_p.add_argument(
        "--network",
        metavar="HOST:PORT",
        required=True,
        help="TCP endpoint of the Mode-S feed, in host:port form.",
    )
    live_p.add_argument(
        "--surface-ref",
        metavar="REF",
        default=None,
        help="Surface CPR reference: airport ICAO code or 'lat,lon'.",
    )
    live_p.add_argument(
        "--full-dict",
        action="store_true",
        help="Emit every key in the canonical schema (missing = null).",
    )
    live_p.add_argument(
        "--dump-to",
        metavar="FILE",
        default=None,
        help="Tee JSON lines to a file in addition to stdout.",
    )
    live_p.add_argument(
        "--tui",
        action="store_true",
        help="Interactive rich-based aircraft table (requires pymodes[tui]).",
    )
    live_p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout output (use with --dump-to).",
    )


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Post-parse validation for cross-flag constraints.

    argparse's built-in ``add_mutually_exclusive_group`` only handles
    simple "at most one of these" rules. For the cross-flag checks
    below (e.g. ``--reference`` forbidden with ``--file``) we do a
    manual validation pass AFTER parsing succeeds.

    Calls ``parser.error(msg)`` — which prints the message to stderr
    and exits 2 — on the first violation.
    """
    if (
        args.command == "decode"
        and args.file is not None
        and args.reference is not None
    ):
        parser.error(
            "--reference is only valid with a single positional MESSAGE "
            "(use PipeDecoder's CPR pair matching for batch/file mode)."
        )

    if args.command == "live":
        if args.tui and args.dump_to is not None:
            parser.error(
                "--tui and --dump-to are mutually exclusive: the TUI takes "
                "over the terminal and cannot tee to a file."
            )
        if args.tui and args.quiet:
            parser.error(
                "--tui and --quiet are mutually exclusive: the TUI owns "
                "stdout, there is nothing to suppress."
            )
