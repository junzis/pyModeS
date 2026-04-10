"""pymodes command-line interface.

Two subcommands:

- ``modes decode`` — one-shot or file-based hex → JSON decoder
- ``modes live`` — streaming TCP → PipeDecoder → JSON-lines or rich TUI

The entry point is registered in ``pyproject.toml`` as ``modes``. The
full implementation lives in the sibling modules in this package:
``_args``, ``decode``, ``live``, ``_source``, ``_sink``, ``_tui``.
"""

from __future__ import annotations

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the exit code.

    Delegates to :mod:`pymodes.cli._args` for argument parsing and
    dispatches to ``decode.run`` or ``live.run`` based on the chosen
    subcommand. Returns 0 on normal exit, non-zero on error.
    """
    from pymodes.cli._args import build_parser, validate_args

    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)

    if args.command == "decode":
        from pymodes.cli.decode import run as run_decode

        return run_decode(args)
    if args.command == "live":
        from pymodes.cli.live import run as run_live

        return run_live(args)

    parser.print_help()
    return 2
