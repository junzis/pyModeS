# ------------------------------------------
#   BDS 0,9
#   ADS-B TC=19
#   Aircraft Airborne velocity
# ------------------------------------------

from __future__ import annotations

import math

from ... import common


def airborne_velocity(
    msg: str, source: bool = False
) -> None | tuple[None | int, None | float, None | int, str]:
    """Decode airborne velocity.

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

    """
    if common.typecode(msg) != 19:
        raise RuntimeError(
            "%s: Not a airborne velocity message, expecting TC=19" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:8])

    if common.bin2int(mb[14:24]) == 0 or common.bin2int(mb[25:35]) == 0:
        return None

    trk_or_hdg: None | float
    spd: None | float

    if subtype in (1, 2):

        v_ew = common.bin2int(mb[14:24])
        v_ns = common.bin2int(mb[25:35])

        if v_ew == 0 or v_ns == 0:
            spd = None
            trk_or_hdg = None
            vs = None
        else:
            v_ew_sign = -1 if mb[13] == "1" else 1
            v_ew = v_ew - 1  # east-west velocity
            if subtype == 2:  # Supersonic
                v_ew *= 4

            v_ns_sign = -1 if mb[24] == "1" else 1
            v_ns = v_ns - 1  # north-south velocity
            if subtype == 2:  # Supersonic
                v_ns *= 4

            v_we = v_ew_sign * v_ew
            v_sn = v_ns_sign * v_ns

            spd = math.sqrt(v_sn * v_sn + v_we * v_we)  # unit in kts
            spd = int(spd)

            trk = math.atan2(v_we, v_sn)
            trk = math.degrees(trk)  # convert to degrees
            trk = trk if trk >= 0 else trk + 360  # no negative val

            trk_or_hdg = round(trk, 2)

        spd_type = "GS"
        dir_type = "TRUE_NORTH"

    else:
        if mb[13] == "0":
            hdg = None
        else:
            hdg = common.bin2int(mb[14:24]) / 1024 * 360.0
            hdg = round(hdg, 2)

        trk_or_hdg = hdg

        spd = common.bin2int(mb[25:35])
        spd = None if spd == 0 else spd - 1
        if subtype == 4 and spd is not None:  # Supersonic
            spd *= 4

        if mb[24] == "0":
            spd_type = "IAS"
        else:
            spd_type = "TAS"

        dir_type = "MAGNETIC_NORTH"

    vr_source = "GNSS" if mb[35] == "0" else "BARO"
    vr_sign = -1 if mb[36] == "1" else 1
    vr = common.bin2int(mb[37:46])
    vs = None if vr == 0 else int(vr_sign * (vr - 1) * 64)

    if source:
        return (  # type: ignore
            spd,
            trk_or_hdg,
            vs,
            spd_type,
            dir_type,
            vr_source,
        )
    else:
        return spd, trk_or_hdg, vs, spd_type


def altitude_diff(msg: str) -> None | float:
    """Decode the differece between GNSS and barometric altitude.

    Args:
        msg (str): 28 hexdigits string, TC=19

    Returns:
        int: Altitude difference in feet. Negative value indicates GNSS altitude
        below barometric altitude.

    """
    tc = common.typecode(msg)

    if tc is None or tc != 19:
        raise RuntimeError(
            "%s: Not a airborne velocity message, expecting TC=19" % msg
        )

    msgbin = common.hex2bin(msg)
    sign = -1 if int(msgbin[80]) else 1
    value = common.bin2int(msgbin[81:88])

    if value == 0 or value == 127:
        return None
    else:
        return sign * (value - 1) * 25  # in ft.
