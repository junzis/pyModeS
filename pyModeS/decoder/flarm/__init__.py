from typing import TypedDict

from .decode import flarm as flarm_decode

__all__ = ["DecodedMessage", "flarm"]


class DecodedMessage(TypedDict):
    timestamp: int
    icao24: str
    latitude: float
    longitude: float
    altitude: int
    vertical_speed: float
    groundspeed: int
    track: int
    type: str
    sensorLatitude: float
    sensorLongitude: float
    isIcao24: bool
    noTrack: bool
    stealth: bool


flarm = flarm_decode
