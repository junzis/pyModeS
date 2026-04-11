"""Tests for `modes decode` subcommand."""

from __future__ import annotations

import io
import json

import pytest


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """Invoke cli.main with argv; return (exit_code, stdout, stderr)."""
    from pymodes.cli import main

    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


class TestDecodeSingleMessage:
    def test_basic_pretty(self, capsys):
        code, out, _err = _run(["decode", "8D406B902015A678D4D220AA4BDA"], capsys)
        assert code == 0
        # Pretty JSON is multi-line
        assert "\n  " in out
        data = json.loads(out)
        assert data["df"] == 17
        assert data["icao"] == "406B90"
        assert data["callsign"] == "EZY85MH"

    def test_compact(self, capsys):
        code, out, _err = _run(
            ["decode", "8D406B902015A678D4D220AA4BDA", "--compact"], capsys
        )
        assert code == 0
        # Compact JSON has no indentation
        assert "\n  " not in out
        # Still parses
        data = json.loads(out)
        assert data["icao"] == "406B90"

    def test_full_dict(self, capsys):
        from pymodes._schema import _FULL_SCHEMA

        code, out, _err = _run(
            ["decode", "8D406B902015A678D4D220AA4BDA", "--full-dict"], capsys
        )
        assert code == 0
        data = json.loads(out)
        for key in _FULL_SCHEMA:
            assert key in data

    def test_reference(self, capsys):
        code, out, _err = _run(
            [
                "decode",
                "8D40058B58C901375147EFD09357",
                "--reference",
                "49.0",
                "6.0",
            ],
            capsys,
        )
        assert code == 0
        data = json.loads(out)
        assert "latitude" in data
        assert abs(data["latitude"] - 49.82410) < 0.001

    def test_surface_ref_airport(self, capsys):
        code, out, _err = _run(
            [
                "decode",
                "903a23ff426a4e65f7487a775d17",
                "--surface-ref",
                "LFBO",
            ],
            capsys,
        )
        assert code == 0
        data = json.loads(out)
        assert abs(data["latitude"] - 43.62646) < 0.001
        assert abs(data["longitude"] - 1.37476) < 0.001

    def test_invalid_hex_exits_one(self, capsys):
        code, out, err = _run(["decode", "not-hex-at-all"], capsys)
        assert code == 1
        assert "error" in err.lower()
        assert out == ""


class TestDecodeInlineBatch:
    def test_comma_separated_emits_json_lines(self, capsys):
        code, out, _err = _run(
            [
                "decode",
                "8D406B902015A678D4D220AA4BDA,8D485020994409940838175B284F",
            ],
            capsys,
        )
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["icao"] == "406B90"
        assert json.loads(lines[1])["icao"] == "485020"
        # Batch output is always compact JSON lines (not pretty), so
        # no leading indentation whitespace on the JSON objects.
        assert all(not line.startswith("  ") for line in lines)

    def test_comma_separated_tolerates_spaces(self, capsys):
        code, out, _err = _run(
            [
                "decode",
                "8D406B902015A678D4D220AA4BDA, 8D485020994409940838175B284F ",
            ],
            capsys,
        )
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 2
        assert json.loads(lines[1])["icao"] == "485020"

    def test_comma_separated_cpr_pair_resolves(self, capsys):
        # Two airborne CPR frames from the same aircraft — the
        # transient PipeDecoder should resolve them into lat/lon.
        code, out, _err = _run(
            [
                "decode",
                "8D40058B58C901375147EFD09357,8D40058B58C904A87F402D3B8C59",
            ],
            capsys,
        )
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 2
        second = json.loads(lines[1])
        assert "latitude" in second

    def test_comma_separated_with_malformed_message(self, capsys):
        # Mixed valid/invalid — invalid ones become error-dicts in
        # the output stream; exit code stays 0.
        code, out, _err = _run(
            [
                "decode",
                "8D406B902015A678D4D220AA4BDA,NOTHEX,8D485020994409940838175B284F",
            ],
            capsys,
        )
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 3
        assert json.loads(lines[0])["icao"] == "406B90"
        assert "error" in json.loads(lines[1])
        assert json.loads(lines[2])["icao"] == "485020"

    def test_comma_separated_with_reference_errors(self, capsys):
        # --reference is a single-aircraft hint; it cannot apply to
        # multiple comma-separated messages at different positions.
        # argparse.parser.error() raises SystemExit(2), so we catch
        # it and inspect stderr for the explanation.
        with pytest.raises(SystemExit) as excinfo:
            _run(
                [
                    "decode",
                    "8D40058B58C901375147EFD09357,8D40058B58C904A87F402D3B8C59",
                    "--reference",
                    "49.0",
                    "6.0",
                ],
                capsys,
            )
        assert excinfo.value.code == 2
        captured = capsys.readouterr()
        assert "--reference" in captured.err

    def test_comma_separated_with_surface_ref(self, capsys):
        # Surface CPR reference does apply uniformly (all aircraft on
        # the same airport taxiway), so it's legal in batch mode.
        code, out, _err = _run(
            [
                "decode",
                "903a23ff426a4e65f7487a775d17,903a23ff426a38565950432ebf95",
                "--surface-ref",
                "LFBO",
            ],
            capsys,
        )
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert abs(data["latitude"] - 43.62646) < 0.01


class TestDecodeFile:
    def test_file_hex_per_line(self, tmp_path, capsys):
        p = tmp_path / "input.log"
        p.write_text("8D406B902015A678D4D220AA4BDA\n8D485020994409940838175B284F\n")
        code, out, _err = _run(["decode", "--file", str(p)], capsys)
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["icao"] == "406B90"
        assert json.loads(lines[1])["icao"] == "485020"

    def test_file_csv_with_timestamps(self, tmp_path, capsys):
        p = tmp_path / "input.csv"
        p.write_text(
            "1446332400.0,8D40058B58C901375147EFD09357\n"
            "1446332405.0,8D40058B58C904A87F402D3B8C59\n"
        )
        code, out, _err = _run(["decode", "--file", str(p)], capsys)
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 2
        # Second message should have resolved lat/lon via CPR pair matching
        data2 = json.loads(lines[1])
        assert "latitude" in data2

    def test_file_stdin(self, capsys, monkeypatch):
        monkeypatch.setattr(
            "sys.stdin",
            io.StringIO("8D406B902015A678D4D220AA4BDA\n"),
        )
        code, out, _err = _run(["decode", "--file", "-"], capsys)
        assert code == 0
        assert '"icao": "406B90"' in out or '"icao":"406B90"' in out

    def test_file_with_malformed_line(self, tmp_path, capsys):
        p = tmp_path / "mixed.log"
        p.write_text(
            "8D406B902015A678D4D220AA4BDA\nNOT HEX\n8D485020994409940838175B284F\n"
        )
        code, out, _err = _run(["decode", "--file", str(p)], capsys)
        # Exit code is 0 because --file mode never aborts on individual errors
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 3
        assert json.loads(lines[0])["icao"] == "406B90"
        assert "error" in json.loads(lines[1])
        assert json.loads(lines[2])["icao"] == "485020"

    def test_file_surface_ref(self, tmp_path, capsys):
        p = tmp_path / "surface.log"
        p.write_text("903a23ff426a4e65f7487a775d17\n")
        code, out, _err = _run(
            ["decode", "--file", str(p), "--surface-ref", "LFBO"], capsys
        )
        assert code == 0
        data = json.loads(out.strip())
        assert abs(data["latitude"] - 43.62646) < 0.001

    def test_file_does_not_exist_exits_one(self, capsys):
        code, _out, err = _run(["decode", "--file", "/nonexistent/file.log"], capsys)
        assert code == 1
        assert "error" in err.lower() or "no such file" in err.lower()
