# ------------------------------------------
#   BDS 0,8
#   ADS-B TC=1-4
#   Aircraft identitification and category
# ------------------------------------------

from pyModeS import common

charmap = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ##### ###############0123456789######"


def me08(callsign, **kwargs):
    cs = callsign
    tc = kwargs.get("typecode")
    cat = kwargs.get("category", 0)

    if len(cs) > 8:
        raise Exception("callsign must contain less than 9 characters")

    if tc > 4:
        raise Exception("typecode must be less 5")

    if cat > 7:
        raise Exception("category must be less 8")

    if not cs.isalnum():
        raise Exception("callsign must only contain alphanumeric characters")

    cs = "{:<8}".format(cs.upper())

    idx = [charmap.index(c) for c in cs]
    me_bin = (
        "{0:05b}".format(tc)
        + "{0:03b}".format(cat)
        + "".join("{0:06b}".format(i) for i in idx)
    )

    me_hex = "{0:04X}".format(int(me_bin, 2))

    return me_hex
