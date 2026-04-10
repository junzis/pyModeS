"""Airport lookup: ICAO code → (lat, lon) or tuple passthrough."""

from pymodes.data.airports import AIRPORTS


def resolve_airport(airport: str | tuple[float, float]) -> tuple[float, float]:
    """Resolve an airport argument to a (lat, lon) tuple.

    Args:
        airport: Either an ICAO code like "EHAM" looked up in the
            shipped database, or an explicit (lat, lon) tuple which
            is returned verbatim.

    Returns:
        (lat, lon) tuple in decimal degrees.

    Raises:
        ValueError: If a string code is passed that is not in the
            shipped database.
    """
    if isinstance(airport, tuple):
        return airport
    try:
        return AIRPORTS[airport]
    except KeyError:
        raise ValueError(f"unknown airport code: {airport}") from None
