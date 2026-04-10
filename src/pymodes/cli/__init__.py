"""pymodes command-line interface.

Two subcommands:

- ``modes decode`` — one-shot or file-based hex → JSON decoder
- ``modes live`` — streaming TCP → PipeDecoder → JSON-lines or rich TUI

The entry point is registered in ``pyproject.toml`` as ``modes``. The
full implementation lives in the sibling modules in this package:
``_args``, ``decode``, ``live``, ``_source``, ``_sink``, ``_tui``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

__all__ = ["main"]


def _load_runner(submodule: str) -> Callable[[argparse.Namespace], int]:
    """Lazily import ``pymodes.cli.<submodule>.run``.

    Uses :func:`importlib.import_module` so mypy does not try to
    resolve the submodule statically — the ``decode`` and ``live``
    modules land in later Plan 6 tasks.
    """
    module = importlib.import_module(f"pymodes.cli.{submodule}")
    runner: Callable[[argparse.Namespace], int] = module.run
    return runner


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
        return _load_runner("decode")(args)
    if args.command == "live":
        return _load_runner("live")(args)

    parser.print_help()
    return 2
