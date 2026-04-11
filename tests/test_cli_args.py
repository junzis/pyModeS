"""Tests for the `modes` CLI argparse surface."""

from __future__ import annotations

import pytest

from pyModeS.cli._args import build_parser


class TestRootParser:
    def test_no_args_does_not_crash(self):
        parser = build_parser()
        args = parser.parse_args([])
        # With no subcommand, args.command is None; main() prints help
        # and returns 2.
        assert args.command is None

    def test_help_exits_zero(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["--help"])
        assert excinfo.value.code == 0


class TestDecodeSubcommand:
    def test_decode_help_exits_zero(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["decode", "--help"])
        assert excinfo.value.code == 0

    def test_decode_single_message(self):
        parser = build_parser()
        args = parser.parse_args(["decode", "8D406B902015A678D4D220AA4BDA"])
        assert args.command == "decode"
        assert args.message == "8D406B902015A678D4D220AA4BDA"
        assert args.file is None
        assert args.compact is False
        assert args.full_dict is False
        assert args.reference is None
        assert args.surface_ref is None

    def test_decode_with_reference(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "decode",
                "8D40058B58C901375147EFD09357",
                "--reference",
                "49.0",
                "6.0",
            ]
        )
        assert args.reference == [49.0, 6.0]

    def test_decode_compact_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            ["decode", "8D406B902015A678D4D220AA4BDA", "--compact"]
        )
        assert args.compact is True

    def test_decode_full_dict_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            ["decode", "8D406B902015A678D4D220AA4BDA", "--full-dict"]
        )
        assert args.full_dict is True

    def test_decode_with_file(self):
        parser = build_parser()
        args = parser.parse_args(["decode", "--file", "input.log"])
        assert args.file == "input.log"
        assert args.message is None

    def test_decode_file_with_reference_errors(self):
        """--reference is incompatible with --file (many aircraft)."""
        from pyModeS.cli._args import validate_args

        parser = build_parser()
        args = parser.parse_args(
            ["decode", "--file", "input.log", "--reference", "49.0", "6.0"]
        )
        with pytest.raises(SystemExit) as excinfo:
            validate_args(args, parser)
        assert excinfo.value.code == 2

    def test_decode_surface_ref(self):
        parser = build_parser()
        args = parser.parse_args(
            ["decode", "903a23ff426a4e65f7487a775d17", "--surface-ref", "LFBO"]
        )
        assert args.surface_ref == "LFBO"


class TestLiveSubcommand:
    def test_live_help_exits_zero(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["live", "--help"])
        assert excinfo.value.code == 0

    def test_live_requires_network(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["live"])
        assert excinfo.value.code == 2

    def test_live_with_network(self):
        parser = build_parser()
        args = parser.parse_args(["live", "--network", "host.example:10003"])
        assert args.command == "live"
        assert args.network == "host.example:10003"
        assert args.tui is False
        assert args.quiet is False
        assert args.dump_to is None
        assert args.surface_ref is None
        assert args.full_dict is False

    def test_live_all_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "live",
                "--network",
                "host.example:10003",
                "--surface-ref",
                "EHAM",
                "--full-dict",
                "--dump-to",
                "out.jsonl",
            ]
        )
        assert args.network == "host.example:10003"
        assert args.surface_ref == "EHAM"
        assert args.full_dict is True
        assert args.dump_to == "out.jsonl"

    def test_live_tui_with_dump_to_errors(self):
        """--tui is incompatible with --dump-to (TUI owns terminal)."""
        from pyModeS.cli._args import validate_args

        parser = build_parser()
        args = parser.parse_args(
            ["live", "--network", "host:1234", "--tui", "--dump-to", "out.log"]
        )
        with pytest.raises(SystemExit) as excinfo:
            validate_args(args, parser)
        assert excinfo.value.code == 2

    def test_live_tui_with_quiet_errors(self):
        """--tui is incompatible with --quiet (nothing to suppress)."""
        from pyModeS.cli._args import validate_args

        parser = build_parser()
        args = parser.parse_args(["live", "--network", "host:1234", "--tui", "--quiet"])
        with pytest.raises(SystemExit) as excinfo:
            validate_args(args, parser)
        assert excinfo.value.code == 2
