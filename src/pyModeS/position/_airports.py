"""Surface-position reference lookup: ICAO airport code or (lat, lon) tuple."""

from pyModeS.data.airports import AIRPORTS


def resolve_surface_ref(
    surface_ref: str | tuple[float, float],
) -> tuple[float, float]:
    """Resolve a surface-position reference to a (lat, lon) tuple.

    Surface BDS 0,6 messages need a nearby reference (within 45 NM)
    to disambiguate the four-quadrant CPR encoding. Callers can pass
    either an ICAO airport code looked up in the shipped database, or
    a raw (lat, lon) tuple of the receiver location.

    Args:
        surface_ref: Either an ICAO code like "EHAM" looked up in the
            shipped airport database, or an explicit (lat, lon) tuple
            (typically the receiver position) which is returned verbatim.

    Returns:
        (lat, lon) tuple in decimal degrees.

    Raises:
        ValueError: If a string code is passed that is not in the
            shipped database.
    """
    if isinstance(surface_ref, tuple):
        return surface_ref
    try:
        return AIRPORTS[surface_ref]
    except KeyError:
        raise ValueError(f"unknown airport code: {surface_ref}") from None
