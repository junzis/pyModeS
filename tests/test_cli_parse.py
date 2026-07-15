"""Tests for shared CLI value parsing."""

import pytest

from pyModeS.cli._parse import parse_network, parse_surface_ref


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("host.example:10006", ("host.example", 10006)),
        ("[::1]:30005", ("::1", 30005)),
        ("::1:30005", ("::1", 30005)),
    ],
)
def test_parse_network(value, expected) -> None:
    assert parse_network(value) == expected


def test_parse_surface_reference() -> None:
    assert parse_surface_ref("LFBO") == "LFBO"
    assert parse_surface_ref(" 43.63, 1.37 ") == (43.63, 1.37)
    assert parse_surface_ref(None) is None
