"""Shared parsers for command-line endpoint and position-reference values."""

from __future__ import annotations

from math import isfinite


def parse_network(value: str) -> tuple[str, int]:
    """Parse ``HOST:PORT``, accepting bracketed and unbracketed IPv6 hosts."""
    host, separator, port_text = value.strip().rpartition(":")
    if not separator or not host:
        raise ValueError("--network must be in HOST:PORT form")
    if host.startswith("[") or host.endswith("]"):
        if not (host.startswith("[") and host.endswith("]")):
            raise ValueError("--network has mismatched IPv6 brackets")
        host = host[1:-1]
    if not host:
        raise ValueError("--network host must not be empty")
    try:
        port = int(port_text)
    except ValueError as error:
        raise ValueError("--network port must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("--network port must be between 1 and 65535")
    return host, port


def parse_surface_ref(value: str | None) -> str | tuple[float, float] | None:
    """Parse an airport code or validated ``lat,lon`` surface reference."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("--surface-ref must not be empty")
    if "," not in value:
        return value

    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError("--surface-ref coordinates must be LAT,LON")
    try:
        lat, lon = (float(part.strip()) for part in parts)
    except ValueError as error:
        raise ValueError("--surface-ref coordinates must be numeric") from error
    if not isfinite(lat) or not isfinite(lon):
        raise ValueError("--surface-ref coordinates must be finite")
    if not -90.0 <= lat <= 90.0:
        raise ValueError("--surface-ref latitude must be between -90 and 90")
    if not -180.0 <= lon <= 180.0:
        raise ValueError("--surface-ref longitude must be between -180 and 180")
    return lat, lon
