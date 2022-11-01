# ------------------------------------------
#   BDS 1,7
#   Common usage GICB capability report
# ------------------------------------------

from typing import List

from ... import common


def is17(msg: str) -> bool:
    """Check if a message is likely to be BDS code 1,7

    Args:
        msg (str): 28 hexdigits string

    Returns:
        bool: True or False
    """

    if common.allzeros(msg):
        return False

    d = common.hex2bin(common.data(msg))

    if common.bin2int(d[24:56]) != 0:
        return False

    caps = cap17(msg)

    # basic BDS codes for ADS-B shall be supported
    #   assuming ADS-B out is installed (2017EU/2020US mandate)
    # if not set(['BDS05', 'BDS06', 'BDS08', 'BDS09', 'BDS20']).issubset(caps):
    #     return False

    # at least you can respond who you are
    if "BDS20" not in caps:
        return False

    return True


def cap17(msg: str) -> List[str]:
    """Extract capacities from BDS 1,7 message

    Args:
        msg (str): 28 hexdigits string

    Returns:
        list: list of supported BDS codes
    """
    allbds = [
        "05",
        "06",
        "07",
        "08",
        "09",
        "0A",
        "20",
        "21",
        "40",
        "41",
        "42",
        "43",
        "44",
        "45",
        "48",
        "50",
        "51",
        "52",
        "53",
        "54",
        "55",
        "56",
        "5F",
        "60",
    ]

    d = common.hex2bin(common.data(msg))
    idx = [i for i, v in enumerate(d[:24]) if v == "1"]
    capacity = ["BDS" + allbds[i] for i in idx]

    return capacity
