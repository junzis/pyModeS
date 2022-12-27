from cpython cimport array

from .core cimport make_key as c_make_key, btea as c_btea

import array
import math
from ctypes import c_byte
from textwrap import wrap

AIRCRAFT_TYPES = [
    "Unknown",  # 0
    "Glider",  # 1
    "Tow-Plane",  # 2
    "Helicopter",  # 3
    "Parachute",  # 4
    "Parachute Drop-Plane",  # 5
    "Hangglider",  # 6
    "Paraglider",  # 7
    "Aircraft",  # 8
    "Jet",  # 9
    "UFO",  # 10
    "Balloon",  # 11
    "Airship",  # 12
    "UAV",  # 13
    "Reserved",  # 14
    "Static Obstacle",  # 15
]

cdef long bytearray2int(str icao24):
    return (
        (int(icao24[4:6], 16) & 0xFF)
        | ((int(icao24[2:4], 16) & 0xFF) << 8)
        | ((int(icao24[:2], 16) & 0xFF) << 16)
    )

cpdef array.array make_key(long timestamp, str icao24):
    cdef long addr = bytearray2int(icao24)
    cdef array.array a = array.array('i', [0, 0, 0, 0])
    c_make_key(a.data.as_ints, timestamp, (addr << 8) & 0xffffff)
    return a

cpdef array.array btea(long timestamp, str msg):
    cdef int p
    cdef str icao24 = msg[4:6] + msg[2:4] + msg[:2]
    cdef array.array key = make_key(timestamp, icao24)

    pieces = wrap(msg[8:], 8)
    cdef array.array toDecode = array.array('i', len(pieces) * [0])
    for i, piece in enumerate(pieces):
        p = 0
        for elt in wrap(piece, 2)[::-1]:
            p = (p << 8) + int(elt, 16)
        toDecode[i] = p

    c_btea(toDecode.data.as_ints, -5, key.data.as_ints)
    return toDecode

cdef float velocity(int ns, int ew):
    return math.hypot(ew / 4, ns / 4)

def heading(ns, ew, velocity):
    if velocity < 1e-6:
        velocity = 1
    return (math.atan2(ew / velocity / 4, ns / velocity / 4) / 0.01745) % 360

def turningRate(a1, a2):
    return ((((a2 - a1)) + 540) % 360) - 180

def flarm(long timestamp, str msg, float refLat, float refLon, **kwargs):
    """Decode a FLARM message.

    Args:
        timestamp (int)
        msg (str)
        refLat (float): the receiver's location
        refLon (float): the receiver's location

    Returns:
        a dictionary with all decoded fields. Any extra keyword argument passed
        is included in the output dictionary.
    """
    cdef str icao24 = msg[4:6] + msg[2:4] + msg[:2]
    cdef int magic = int(msg[6:8], 16)

    if magic != 0x10 and magic != 0x20:
        return None

    cdef array.array decoded = btea(timestamp, msg)

    cdef int aircraft_type = (decoded[0] >> 28) & 0xF
    cdef int gps = (decoded[0] >> 16) & 0xFFF
    cdef int raw_vs = c_byte(decoded[0] & 0x3FF).value

    noTrack = ((decoded[0] >> 14) & 0x1) == 1
    stealth = ((decoded[0] >> 13) & 0x1) == 1

    cdef int altitude =  (decoded[1] >> 19) & 0x1FFF

    cdef int lat = decoded[1] & 0x7FFFF

    cdef int mult_factor = 1 << ((decoded[2] >> 30) & 0x3)
    cdef int lon = decoded[2] & 0xFFFFF

    ns = list(
        c_byte((decoded[3] >> (i * 8)) & 0xFF).value * mult_factor
        for i in range(4)
    )
    ew = list(
        c_byte((decoded[4] >> (i * 8)) & 0xFF).value * mult_factor
        for i in range(4)
    )

    cdef int roundLat = int(refLat * 1e7) >> 7
    lat = (lat - roundLat) % 0x080000
    if lat >= 0x040000:
        lat -= 0x080000
    lat = (((lat + roundLat) << 7) + 0x40) 

    roundLon = int(refLon * 1e7) >> 7
    lon = (lon - roundLon) % 0x100000
    if lon >= 0x080000:
        lon -= 0x100000
    lon = (((lon + roundLon) << 7) + 0x40)

    speed = sum(velocity(n, e) for n, e in zip(ns, ew)) / 4

    heading4 = heading(ns[0], ew[0], speed)
    heading8 = heading(ns[1], ew[1], speed)

    return dict(
        timestamp=timestamp,
        icao24=icao24,
        latitude=round(lat * 1e-7, 6),
        longitude=round(lon * 1e-7, 6),
        geoaltitude=altitude,
        vertical_speed=raw_vs * mult_factor / 10,
        groundspeed=round(speed),
        track=round(heading4 - 4 * turningRate(heading4, heading8) / 4),
        type=AIRCRAFT_TYPES[aircraft_type],
        sensorLatitude=refLat,
        sensorLongitude=refLon,
        isIcao24=magic==0x10,
        noTrack=noTrack,
        stealth=stealth,
        **kwargs
    )