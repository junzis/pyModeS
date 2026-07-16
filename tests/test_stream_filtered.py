"""Offline tests for the shareable filtered streaming example."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "stream_filtered.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("stream_filtered", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_prefilter_matches_selected_formats() -> None:
    script = _load_script()

    # DF17 identification and DF20 Comm-B are retained.
    assert script.is_relevant("8D406B902015A678D4D220AA4BDA")
    assert script.is_relevant("A00007318DB436F0A80000A7959E")
    # Short DF11 and ADS-B TC31 operational status are discarded.
    assert not script.is_relevant("5D406B902015A6")
    assert not script.is_relevant("8D485020F8210002004AB8ADA378")


def test_prefilter_is_configurable() -> None:
    script = _load_script()

    assert script.is_relevant(
        "5D406B902015A6",
        frozenset((11,)),
        frozenset(),
    )
    assert script.is_relevant(
        "8D485020F8210002004AB8ADA378",
        frozenset((17,)),
        frozenset(),
    )


def test_emit_json_adds_source_metadata() -> None:
    script = _load_script()
    output = io.StringIO()

    script.emit_json(
        {"df": 17, "icao": "406B90"},
        "8D406B902015A678D4D220AA4BDA",
        1234.5,
        output=output,
    )

    record = json.loads(output.getvalue())
    assert record == {
        "df": 17,
        "icao": "406B90",
        "raw_msg": "8D406B902015A678D4D220AA4BDA",
        "timestamp": 1234.5,
    }


def test_include_meteo_flag_reaches_pipe(tmp_path, capsys) -> None:
    script = _load_script()
    capture = tmp_path / "meteo.csv"
    capture.write_text("1000.0,A0001692185BD5CF400000DFC696\n")

    code = script.main(["--input", str(capture), "--include-meteo"])

    assert code == 0
    record = json.loads(capsys.readouterr().out)
    assert record["bds"] == "4,4"
    assert record["wind_speed"] == 22
