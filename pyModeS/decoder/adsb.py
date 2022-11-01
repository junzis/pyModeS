"""ADS-B module.

The ADS-B module also imports functions from the following modules:

- bds05: ``airborne_position()``, ``airborne_position_with_ref()``,
  ``altitude()``
- bds06: ``surface_position()``, ``surface_position_with_ref()``,
  ``surface_velocity()``
- bds08: ``category()``, ``callsign()``
- bds09: ``airborne_velocity()``, ``altitude_diff()``

"""

from __future__ import annotations
from datetime import datetime

from .. import common
from . import uncertainty
from .bds.bds05 import airborne_position, airborne_position_with_ref
from .bds.bds05 import altitude as altitude05
from .bds.bds06 import (
    surface_position,
    surface_position_with_ref,
    surface_velocity,
)
from .bds.bds08 import callsign, category
from .bds.bds09 import airborne_velocity, altitude_diff
from .bds.bds61 import emergency_squawk, emergency_state, is_emergency
from .bds.bds62 import (
    altitude_hold_mode,
    approach_mode,
    autopilot,
    baro_pressure_setting,
    emergency_status,
    horizontal_mode,
    lnav_mode,
    selected_altitude,
    selected_heading,
    target_altitude,
    target_angle,
    tcas_operational,
    tcas_ra,
    vertical_mode,
    vnav_mode,
)

__all__ = [
    "airborne_position",
    "airborne_position_with_ref",
    "altitude05",
    "surface_position",
    "surface_position_with_ref",
    "surface_velocity",
    "callsign",
    "category",
    "airborne_velocity",
    "altitude_diff",
    "emergency_squawk",
    "emergency_state",
    "is_emergency",
    "df",
    "icao",
    "typecode",
    "position",
    "position_with_ref",
    "altitude",
    "velocity",
    "speed_heading",
    "oe_flag",
    "version",
    "nuc_p",
    "nuc_v",
    "nic_v1",
    "nic_v2",
    "nic_s",
    "nic_a_c",
    "nic_b",
    "nac_p",
    "nac_v",
    "sil",
    "selected_altitude",
    "target_altitude",
    "vertical_mode",
    "horizontal_mode",
    "selected_heading",
    "target_angle",
    "baro_pressure_setting",
    "autopilot",
    "vnav_mode",
    "altitude_hold_mode",
    "approach_mode",
    "lnav_mode",
    "tcas_operational",
    "tcas_ra",
    "emergency_status",
]


def df(msg: str) -> int:
    return common.df(msg)


def icao(msg: str) -> None | str:
    return common.icao(msg)


def typecode(msg: str) -> None | int:
    return common.typecode(msg)


def position(
    msg0: str,
    msg1: str,
    t0: int | datetime,
    t1: int | datetime,
    lat_ref: None | float = None,
    lon_ref: None | float = None,
) -> None | tuple[float, float]:
    """Decode surface or airborne position from a pair of even and odd
    position messages.

    Note, that to decode surface position using the position message pair,
    the reference position has to be provided.

    Args:
        msg0 (string): even message (28 hexdigits)
        msg1 (string): odd message (28 hexdigits)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message
        lat_ref (float): latitude of reference position
        lon_ref (float): longitude of reference position

    Returns:
        (float, float): (latitude, longitude) of the aircraft

    """
    tc0 = typecode(msg0)
    tc1 = typecode(msg1)

    if tc0 is None or tc1 is None:
        raise RuntimeError("Incorrect or inconsistent message types")

    if 5 <= tc0 <= 8 and 5 <= tc1 <= 8:
        if lat_ref is None or lon_ref is None:
            raise RuntimeError(
                "Surface position encountered, a reference position"
                " lat/lon required. Location of receiver can be used."
            )
        else:
            return surface_position(msg0, msg1, t0, t1, lat_ref, lon_ref)

    elif 9 <= tc0 <= 18 and 9 <= tc1 <= 18:
        # Airborne position with barometric height
        return airborne_position(msg0, msg1, t0, t1)

    elif 20 <= tc0 <= 22 and 20 <= tc1 <= 22:
        # Airborne position with GNSS height
        return airborne_position(msg0, msg1, t0, t1)

    else:
        raise RuntimeError("Incorrect or inconsistent message types")


def position_with_ref(
    msg: str, lat_ref: float, lon_ref: float
) -> tuple[float, float]:
    """Decode position with only one message.

    A reference position is required, which can be previously
    calculated location, ground station, or airport location.
    The function works with both airborne and surface position messages.
    The reference position shall be within 180NM (airborne) or 45NM (surface)
    of the true position.

    Args:
        msg (str): even message (28 hexdigits)
        lat_ref: previous known latitude
        lon_ref: previous known longitude

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    tc = typecode(msg)

    if tc is None:
        raise RuntimeError("incorrect or inconsistent message types")

    if 5 <= tc <= 8:
        return surface_position_with_ref(msg, lat_ref, lon_ref)

    elif 9 <= tc <= 18 or 20 <= tc <= 22:
        return airborne_position_with_ref(msg, lat_ref, lon_ref)

    else:
        raise RuntimeError("incorrect or inconsistent message types")


def altitude(msg: str) -> None | float:
    """Decode aircraft altitude.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: altitude in feet

    """
    tc = typecode(msg)

    if tc is None or tc < 5 or tc == 19 or tc > 22:
        raise RuntimeError("%s: Not a position message" % msg)

    elif tc >= 5 and tc <= 8:
        # surface position, altitude 0
        return 0

    else:
        # airborn position
        return altitude05(msg)


def velocity(
    msg: str, source: bool = False
) -> None | tuple[None | float, None | float, None | int, str]:
    """Calculate the speed, heading, and vertical rate
       (handles both airborne or surface message).

    Args:
        msg (str): 28 hexdigits string
        source (boolean): Include direction and vertical rate sources in return.
            Default to False.
            If set to True, the function will return six value instead of four.

    Returns:
        int, float, int, string, [string], [string]:
            - Speed (kt)
            - Angle (degree), either ground track or heading
            - Vertical rate (ft/min)
            - Speed type ('GS' for ground speed, 'AS' for airspeed)
            - [Optional] Direction source ('TRUE_NORTH' or 'MAGNETIC_NORTH')
            - [Optional] Vertical rate source ('BARO' or 'GNSS')

        For surface messages, vertical rate and its respective sources are set
        to None.

    """
    tc = typecode(msg)
    error = "incorrect or inconsistent message types, expecting 4<TC<9 or TC=19"
    if tc is None:
        raise RuntimeError(error)

    if 5 <= tc <= 8:
        return surface_velocity(msg, source)

    elif tc == 19:
        return airborne_velocity(msg, source)

    else:
        raise RuntimeError(error)


def speed_heading(msg: str) -> None | tuple[None | float, None | float]:
    """Get speed and ground track (or heading) from the velocity message
    (handles both airborne or surface message)

    Args:
        msg (str): 28 hexdigits string

    Returns:
        (int, float): speed (kt), ground track or heading (degree)
    """
    decoded = velocity(msg)
    if decoded is None:
        return None
    spd, trk_or_hdg, rocd, tag = decoded
    return spd, trk_or_hdg


def oe_flag(msg: str) -> int:
    """Check the odd/even flag. Bit 54, 0 for even, 1 for odd.
    Args:
        msg (str): 28 hexdigits string
    Returns:
        int: 0 or 1, for even or odd frame
    """
    msgbin = common.hex2bin(msg)
    return int(msgbin[53])


def version(msg: str) -> int:
    """ADS-B Version

    Args:
        msg (str): 28 hexdigits string, TC = 31

    Returns:
        int: version number
    """
    tc = typecode(msg)

    if tc != 31:
        raise RuntimeError(
            "%s: Not a status operation message, expecting TC = 31" % msg
        )

    msgbin = common.hex2bin(msg)
    version = common.bin2int(msgbin[72:75])

    return version


def nuc_p(msg: str) -> tuple[int, None | float, None | int, None | int]:
    """Calculate NUCp, Navigation Uncertainty Category - Position
    (ADS-B version 1)

    Args:
        msg (str): 28 hexdigits string,

    Returns:
        int: NUCp, Navigation Uncertainty Category (position)
        int: Horizontal Protection Limit
        int: 95% Containment Radius - Horizontal (meters)
        int: 95% Containment Radius - Vertical (meters)

    """
    tc = typecode(msg)

    if tc is None or tc < 5 or tc is None or tc > 22:
        raise RuntimeError(
            "%s: Not a surface position message (5<TC<8), \
            airborne position message (8<TC<19), \
            or airborne position with GNSS height (20<TC<22)"
            % msg
        )

    NUCp = uncertainty.TC_NUCp_lookup[tc]
    index = uncertainty.NUCp.get(NUCp, None)

    if index is not None:
        HPL = index["HPL"]
        RCu = index["RCu"]
        RCv = index["RCv"]
    else:
        HPL, RCu, RCv = uncertainty.NA, uncertainty.NA, uncertainty.NA

    RCv = uncertainty.NA

    # RCv only available for GNSS height
    if tc == 20:
        RCv = 4
    elif tc == 21:
        RCv = 15

    return NUCp, HPL, RCu, RCv


def nuc_v(msg: str) -> tuple[int, None | float, None | float]:
    """Calculate NUCv, Navigation Uncertainty Category - Velocity
    (ADS-B version 1)

    Args:
        msg (str): 28 hexdigits string,

    Returns:
        int: NUCv, Navigation Uncertainty Category (velocity)
        int or string: 95% Horizontal Velocity Error
        int or string: 95% Vertical Velocity Error
    """
    tc = typecode(msg)

    if tc != 19:
        raise RuntimeError(
            "%s: Not an airborne velocity message, expecting TC = 19" % msg
        )

    msgbin = common.hex2bin(msg)
    NUCv = common.bin2int(msgbin[42:45])
    index = uncertainty.NUCv.get(NUCv, None)

    if index is not None:
        HVE = index["HVE"]
        VVE = index["VVE"]
    else:
        HVE, VVE = uncertainty.NA, uncertainty.NA

    return NUCv, HVE, VVE


def nic_v1(msg: str, NICs: int) -> tuple[int, None | float, None | float]:
    """Calculate NIC, navigation integrity category, for ADS-B version 1

    Args:
        msg (str): 28 hexdigits string
        NICs (int or string): NIC supplement

    Returns:
        int: NIC, Navigation Integrity Category
        int or string: Horizontal Radius of Containment
        int or string: Vertical Protection Limit
    """
    tc = typecode(msg)
    if tc is None or tc < 5 or tc > 22:
        raise RuntimeError(
            "%s: Not a surface position message (5<TC<8), \
            airborne position message (8<TC<19), \
            or airborne position with GNSS height (20<TC<22)"
            % msg
        )

    NIC = uncertainty.TC_NICv1_lookup[tc]

    if isinstance(NIC, dict):
        NIC = NIC[NICs]

    d_index = uncertainty.NICv1.get(NIC, None)
    Rc, VPL = uncertainty.NA, uncertainty.NA

    if d_index is not None:
        index = d_index.get(NICs, None)
        if index is not None:
            Rc = index["Rc"]
            VPL = index["VPL"]

    return NIC, Rc, VPL


def nic_v2(msg: str, NICa: int, NICbc: int) -> tuple[int, int]:
    """Calculate NIC, navigation integrity category, for ADS-B version 2

    Args:
        msg (str): 28 hexdigits string
        NICa (int or string): NIC supplement - A
        NICbc (int or string): NIC supplement - B or C

    Returns:
        int: NIC, Navigation Integrity Category
        int or string: Horizontal Radius of Containment
    """
    tc = typecode(msg)
    if tc is None or tc < 5 or tc > 22:
        raise RuntimeError(
            "%s: Not a surface position message (5<TC<8), \
            airborne position message (8<TC<19), \
            or airborne position with GNSS height (20<TC<22)"
            % msg
        )

    NIC = uncertainty.TC_NICv2_lookup[tc]

    if 20 <= tc <= 22:
        NICs = 0
    else:
        NICs = NICa * 2 + NICbc

    try:
        if isinstance(NIC, dict):
            NIC = NIC[NICs]

        Rc = uncertainty.NICv2[NIC][NICs]["Rc"]
    except KeyError:
        Rc = uncertainty.NA

    return NIC, Rc  # type: ignore


def nic_s(msg: str) -> int:
    """Obtain NIC supplement bit, TC=31 message

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: NICs number (0 or 1)
    """
    tc = typecode(msg)

    if tc != 31:
        raise RuntimeError(
            "%s: Not a status operation message, expecting TC = 31" % msg
        )

    msgbin = common.hex2bin(msg)
    nic_s = int(msgbin[75])

    return nic_s


def nic_a_c(msg: str) -> tuple[int, int]:
    """Obtain NICa/c, navigation integrity category supplements a and c

    Args:
        msg (str): 28 hexdigits string

    Returns:
        (int, int): NICa and NICc number (0 or 1)
    """
    tc = typecode(msg)

    if tc != 31:
        raise RuntimeError(
            "%s: Not a status operation message, expecting TC = 31" % msg
        )

    msgbin = common.hex2bin(msg)
    nic_a = int(msgbin[75])
    nic_c = int(msgbin[51])

    return nic_a, nic_c


def nic_b(msg: str) -> int:
    """Obtain NICb, navigation integrity category supplement-b

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: NICb number (0 or 1)
    """
    tc = typecode(msg)

    if tc is None or tc < 9 or tc > 18:
        raise RuntimeError(
            "%s: Not a airborne position message, expecting 8<TC<19" % msg
        )

    msgbin = common.hex2bin(msg)
    nic_b = int(msgbin[39])

    return nic_b


def nac_p(msg: str) -> tuple[int, int | None, int | None]:
    """Calculate NACp, Navigation Accuracy Category - Position

    Args:
        msg (str): 28 hexdigits string, TC = 29 or 31

    Returns:
        int: NACp, Navigation Accuracy Category (position)
        int or string: 95% horizontal accuracy bounds,
            Estimated Position Uncertainty
        int or string: 95% vertical accuracy bounds,
            Vertical Estimated Position Uncertainty
    """
    tc = typecode(msg)

    if tc not in [29, 31]:
        raise RuntimeError(
            "%s: Not a target state and status message, \
                           or operation status message, expecting TC = 29 or 31"
            % msg
        )

    msgbin = common.hex2bin(msg)

    if tc == 29:
        NACp = common.bin2int(msgbin[71:75])
    elif tc == 31:
        NACp = common.bin2int(msgbin[76:80])

    try:
        EPU = uncertainty.NACp[NACp]["EPU"]
        VEPU = uncertainty.NACp[NACp]["VEPU"]
    except KeyError:
        EPU, VEPU = uncertainty.NA, uncertainty.NA

    return NACp, EPU, VEPU


def nac_v(msg: str) -> tuple[int, float | None, float | None]:
    """Calculate NACv, Navigation Accuracy Category - Velocity

    Args:
        msg (str): 28 hexdigits string, TC = 19

    Returns:
        int: NACv, Navigation Accuracy Category (velocity)
        int or string: 95% horizontal accuracy bounds for velocity,
            Horizontal Figure of Merit
        int or string: 95% vertical accuracy bounds for velocity,
            Vertical Figure of Merit
    """
    tc = typecode(msg)

    if tc != 19:
        raise RuntimeError(
            "%s: Not an airborne velocity message, expecting TC = 19" % msg
        )

    msgbin = common.hex2bin(msg)
    NACv = common.bin2int(msgbin[42:45])

    try:
        HFOMr = uncertainty.NACv[NACv]["HFOMr"]
        VFOMr = uncertainty.NACv[NACv]["VFOMr"]
    except KeyError:
        HFOMr, VFOMr = uncertainty.NA, uncertainty.NA

    return NACv, HFOMr, VFOMr


def sil(
    msg: str,
    version: None | int,
) -> tuple[float | None, float | None, str]:
    """Calculate SIL, Surveillance Integrity Level

    Args:
        msg (str): 28 hexdigits string with TC = 29, 31

    Returns:
        int or string:
            Probability of exceeding Horizontal Radius of Containment RCu
        int or string:
            Probability of exceeding Vertical Integrity Containment Region VPL
        string: SIL supplement based on per "hour" or "sample", or 'unknown'
    """
    tc = typecode(msg)

    if tc not in [29, 31]:
        raise RuntimeError(
            "%s: Not a target state and status message, \
                           or operation status message, expecting TC = 29 or 31"
            % msg
        )

    msgbin = common.hex2bin(msg)

    if tc == 29:
        SIL = common.bin2int(msgbin[76:78])
    elif tc == 31:
        SIL = common.bin2int(msgbin[82:84])

    try:
        PE_RCu = uncertainty.SIL[SIL]["PE_RCu"]
        PE_VPL = uncertainty.SIL[SIL]["PE_VPL"]
    except KeyError:
        PE_RCu, PE_VPL = uncertainty.NA, uncertainty.NA

    base = "unknown"

    if version == 2:
        if tc == 29:
            SIL_SUP = common.bin2int(msgbin[39])
        elif tc == 31:
            SIL_SUP = common.bin2int(msgbin[86])

        if SIL_SUP == 0:
            base = "hour"
        elif SIL_SUP == 1:
            base = "sample"

    return PE_RCu, PE_VPL, base
