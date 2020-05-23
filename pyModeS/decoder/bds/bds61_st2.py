# ------------------------------------------
#   BDS 6,1
#   ADS-B TC=28
#   Aircraft Airborne status
#   (Subtype 1)
# ------------------------------------------

from typing import Tuple
from pyModeS import common

from pyModeS.decoder import acas


def threat_type(msg: str) -> int:
    """Determine the threat type indicator.

    Value    Meaning
    -----    ---------------------------------------
    0        No identity data in TID
    1        TID has Mode S address (ICAO)
    2        TID has altitude, range, and bearing
    3        Not assigned

    :param msg: 28 hexdigits string
    :return: indicator of threat type
    """
    mb = common.hex2bin(common.data(msg))
    tti = common.bin2int(mb[28:30])
    return tti


def threat_identity(msg: str) -> str:
    mb = common.hex2bin(common.data(msg))
    tti = threat_type(msg)

    # The ICAO of the threat is announced
    if tti == 1:
        return common.icao(mb[30:55])
    else:
        raise RuntimeError("%s: Missing threat identity (ICAO)")


def threat_location(msg: str) -> Tuple:
    """Get the altitude, range, and bearing of the threat.

    Altitude is the Mode C altitude

    :param msg: 28 hexdigits string
    :return: tuple of the Mode C altitude, range, and bearing
    """
    mb = common.hex2bin(common.data(msg))
    tti = threat_type(msg)

    # Altitude, range, and bearing of threat
    if tti == 2:
        altitude = common.altitude(mb[31:44])
        distance = common.bin2int(mb[44:51])
        bearing = common.bin2int(mb[51:57])
        return altitude, distance, bearing


def has_multiple_threats(msg: str) -> bool:
    """ Indicate if the ACAS is processing multiple threats simultaneously.

    :param msg: 28 hexdigits string
    :return: if there are multiple threats
    """
    return acas.mte(msg) == 1


def active_resolution_advisories(msg: str) -> str:
    """Decode active resolution advisory.

    Uses ARA decoding function from ACAS module.

    :param msg: 28 bytes hexadecimal message string
    :return: RA charactristics
    """
    return acars.ara(msg)


def is_ra_terminated(msg: str) -> bool:
    """Indicate if the threat is still being generated.

    Mode S transponder is still required to report RA 18 seconds after
    it is terminated by ACAS. Hence, the RAT filed is used.

    :param msg: 28 hexdigits string
    :return: if the threat is terminated
    """
    return acas.rat(msg) == 1


def ra_complement(msg: str) -> str:
    """Resolution Advisory Complement.

    :param msg: 28 hexdigits string
    :return: RACs
    """
    return acas.rac(msg)
