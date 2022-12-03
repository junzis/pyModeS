from typing import Any

from . import DecodedMessage

AIRCRAFT_TYPES: list[str]


def flarm(
    timestamp: int,
    msg: str,
    refLat: float,
    refLon: float,
    **kwargs: Any,
) -> DecodedMessage: ...
