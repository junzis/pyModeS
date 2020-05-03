from .bds.bds08 import me08
from .bds.bds09 import me09
from pyModeS import common


def encode_adsb(**kwargs):
    """Encode ADS-B message.

    Args:
        icao (string): Transponder ICAO address (6 hexdigits)
        capability (int): Transponder capability, between 0 and 7
        typecode (int): Typecode, less than 32

        callsign (string): Callsign (6 hexdigits)
        category (int): Aircraft category, between 0 and 7, Default to 0.

        speed (int): Speed in knots.
        angle (float): Track angle or heading angle in degrees.
        vertical_rate (int): vertical rate in feet/minute
        intent_change (int): Intent change flag, 0 or 1. Default to 0.
        ifr_capability (int): IFR capability flag, 0 or 1. Default to 1.
        navigation_quality (int): NUC (ver 0) or NACv (ver 1, 2), between 0 and 7.
            Default to 0.
        supersonic (bool): Is this a supersonic flight? Default to False.
        speed_type (str): Speed type: GS, IAS, or TAS. Default to GS.
        vertical_rate_source (str): GNSS or BARO. Default to BARO.
        gnss_baro_alt_diff (int): Different between GNSS and barometric altitude in feet.
            Negative value indicates GNSS altitude below barometric altitude. Default to 0

    Returns:
        string: 28 hexdigits raw message

    """
    tc = kwargs.get("typecode")

    if 1 <= tc <= 4:
        me = me08(**kwargs)
    elif tc == 19:
        me = me09(**kwargs)

    msg = _constuct(**dict(kwargs, me=me))
    return msg


def _constuct(**kwargs):
    icao = kwargs.get("icao")
    me = kwargs.get("me")
    capability = kwargs.get("capability", 6)

    if icao is None or len(icao) != 6:
        raise Exception("Transponder address must be 6 hexadecimal characters.")

    if me is None or len(me) != 14:
        raise Exception("Message be 14 hexadecimal characters.")

    if capability > 6:
        raise Exception("Transponder capability must be smaller than 7.")

    header_bin = "10001" + "{0:03b}".format(capability)
    header_hex = "{0:02X}".format(int(header_bin, 2))

    msg = header_hex + icao + me + "000000"

    pi = common.crc(msg, encode=True)
    pi_hex = "{0:06X}".format(pi)

    msg = msg[:-6] + pi_hex
    return msg
