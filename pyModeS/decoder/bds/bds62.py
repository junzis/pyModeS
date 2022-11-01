# ------------------------------------------
#   BDS 6,2
#   ADS-B TC=29
#   Target State and Status
# ------------------------------------------

from __future__ import annotations

from ... import common


def selected_altitude(msg: str) -> tuple[None | float, str]:
    """Decode selected altitude.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Selected altitude (ft)
        string: Source ('MCP/FCU' or 'FMS')

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        raise RuntimeError(
            "%s: ADS-B version 1 target state and status message does not"
            " contain selected altitude, use target altitude instead" % msg
        )

    alt = common.bin2int(mb[9:20])
    if alt == 0:
        return None, "N/A"
    alt = (alt - 1) * 32
    alt_source = "MCP/FCU" if int(mb[8]) == 0 else "FMS"

    return alt, alt_source


def target_altitude(msg: str) -> tuple[None | int, str, str]:
    """Decode target altitude.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Target altitude (ft)
        string: Source ('MCP/FCU', 'Holding mode' or 'FMS/RNAV')
        string: Altitude reference, either pressure altitude or barometric
           corrected altitude ('FL' or 'MSL')

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 1:
        raise RuntimeError(
            "%s: ADS-B version 2 target state and status message does not"
            " contain target altitude, use selected altitude instead" % msg
        )

    alt_avail = common.bin2int(mb[7:9])
    if alt_avail == 0:
        return None, "N/A", ""
    elif alt_avail == 1:
        alt_source = "MCP/FCU"
    elif alt_avail == 2:
        alt_source = "Holding mode"
    else:
        alt_source = "FMS/RNAV"

    alt_ref = "FL" if int(mb[9]) == 0 else "MSL"

    alt = -1000 + common.bin2int(mb[15:25]) * 100

    return alt, alt_source, alt_ref


def vertical_mode(msg: str) -> None | int:
    """Decode vertical mode.

    Value   Meaning
    -----   -----------------------
    1       "Acquiring" mode
    2       "Capturing" or "Maintaining" mode
    3       Reserved

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Vertical mode

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 1:
        raise RuntimeError(
            "%s: ADS-B version 2 target state and status message does not"
            " contain vertical mode, use vnav mode instead" % msg
        )

    vertical_mode = common.bin2int(mb[13:15])
    if vertical_mode == 0:
        return None

    return vertical_mode


def horizontal_mode(msg: str) -> None | int:
    """Decode horizontal mode.

    Value   Meaning
    -----   -----------------------
    1       "Acquiring" mode
    2       "Capturing" or "Maintaining" mode
    3       Reserved

    Args:
        msg (str): 28 hexdigits string

    Returns:
        int: Horizontal mode

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 1:
        raise RuntimeError(
            "%s: ADS-B version 2 target state and status message does not "
            "contain horizontal mode, use lnav mode instead" % msg
        )

    horizontal_mode = common.bin2int(mb[25:27])
    if horizontal_mode == 0:
        return None

    return horizontal_mode


def selected_heading(msg: str) -> None | float:
    """Decode selected heading.

    Args:
        msg (str): 28 bytes hexadecimal message string

    Returns:
        float: Selected heading (degree)

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        raise RuntimeError(
            "%s: ADS-B version 1 target state and status message does not "
            "contain selected heading, use target angle instead" % msg
        )

    if int(mb[29]) == 0:
        return None
    else:
        hdg_sign = int(mb[30])
        hdg = (hdg_sign + 1) * common.bin2int(mb[31:39]) * (180 / 256)
        hdg = round(hdg, 2)

    return hdg


def target_angle(msg: str) -> tuple[None | int, str, str]:
    """Decode target heading/track angle.

    Args:
        msg (str): 28 bytes hexadecimal message string

    Returns:
        int: Target angle (degree)
        string: Angle type ('Heading' or 'Track')
        string: Source ('MCP/FCU', 'Autopilot Mode' or 'FMS/RNAV')

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 1:
        raise RuntimeError(
            "%s: ADS-B version 2 target state and status message does not "
            "contain target angle, use selected heading instead" % msg
        )

    angle_avail = common.bin2int(mb[25:27])
    if angle_avail == 0:
        return None, "", "N/A"
    else:
        angle = common.bin2int(mb[27:36])

        if angle_avail == 1:
            angle_source = "MCP/FCU"
        elif angle_avail == 2:
            angle_source = "Autopilot mode"
        else:
            angle_source = "FMS/RNAV"

        angle_type = "Heading" if int(mb[36]) else "Track"

    return angle, angle_type, angle_source


def baro_pressure_setting(msg: str) -> None | float:
    """Decode barometric pressure setting.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        float: Barometric pressure setting (millibars)

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        raise RuntimeError(
            "%s: ADS-B version 1 target state and status message does not "
            "contain barometric pressure setting" % msg
        )

    baro = common.bin2int(mb[20:29])
    if baro == 0:
        return None

    return 800 + (baro - 1) * 0.8


def autopilot(msg) -> None | bool:
    """Decode autopilot engagement.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: Autopilot engaged

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        raise RuntimeError(
            "%s: ADS-B version 1 target state and status message does not "
            "contain autopilot engagement" % msg
        )

    if int(mb[46]) == 0:
        return None

    autopilot = True if int(mb[47]) == 1 else False

    return autopilot


def vnav_mode(msg) -> None | bool:
    """Decode VNAV mode.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: VNAV mode engaged

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        raise RuntimeError(
            "%s: ADS-B version 1 target state and status message does not "
            "contain vnav mode, use vertical mode instead" % msg
        )

    if int(mb[46]) == 0:
        return None

    vnav_mode = True if int(mb[48]) == 1 else False

    return vnav_mode


def altitude_hold_mode(msg) -> None | bool:
    """Decode altitude hold mode.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: Altitude hold mode engaged

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        raise RuntimeError(
            "%s: ADS-B version 1 target state and status message does not "
            "contain altitude hold mode" % msg
        )

    if int(mb[46]) == 0:
        return None

    alt_hold_mode = True if int(mb[49]) == 1 else False

    return alt_hold_mode


def approach_mode(msg) -> None | bool:
    """Decode approach mode.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: Approach mode engaged

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        raise RuntimeError(
            "%s: ADS-B version 1 target state and status message does not "
            "contain approach mode" % msg
        )

    if int(mb[46]) == 0:
        return None

    app_mode = True if int(mb[51]) == 1 else False

    return app_mode


def lnav_mode(msg) -> None | bool:
    """Decode LNAV mode.

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: LNAV mode engaged

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        raise RuntimeError(
            "%s: ADS-B version 1 target state and status message does not "
            "contain lnav mode, use horizontal mode instead" % msg
        )

    if int(mb[46]) == 0:
        return None

    lnav_mode = True if int(mb[53]) == 1 else False

    return lnav_mode


def tcas_operational(msg) -> None | bool:
    """Decode TCAS/ACAS operational.

    Args:
        msg (str): 28 bytes hexadecimal message string

    Returns:
        bool: TCAS/ACAS operational

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 0:
        tcas = True if int(mb[51]) == 0 else False
    else:
        tcas = True if int(mb[52]) == 1 else False

    return tcas


def tcas_ra(msg) -> bool:
    """Decode TCAS/ACAS Resolution advisory.

    Args:
        msg (str): 28 bytes hexadecimal message string

    Returns:
        bool: TCAS/ACAS Resolution advisory active

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 1:
        raise RuntimeError(
            "%s: ADS-B version 2 target state and status message does not "
            "contain TCAS/ACAS RA" % msg
        )

    tcas_ra = True if int(mb[52]) == 1 else False

    return tcas_ra


def emergency_status(msg) -> int:
    """Decode aircraft emergency status.

    Value   Meaning
    -----   -----------------------
    0       No emergency
    1       General emergency
    2       Lifeguard/medical emergency
    3       Minimum fuel
    4       No communications
    5       Unlawful interference
    6       Downed aircraft
    7       Reserved

    Args:
        msg (str): 28 bytes hexadecimal message string

    Returns:
        int: Emergency status

    """

    if common.typecode(msg) != 29:
        raise RuntimeError(
            "%s: Not a target state and status message, expecting TC=29" % msg
        )

    mb = common.hex2bin(msg)[32:]

    subtype = common.bin2int(mb[5:7])

    if subtype == 1:
        raise RuntimeError(
            "%s: ADS-B version 2 target state and status message does not "
            "contain emergency status" % msg
        )

    return common.bin2int(mb[53:56])
