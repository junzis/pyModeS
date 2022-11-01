# Copyright (C) 2015 Junzi Sun (TU Delft)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
Common functions for Mode-S decoding
"""

from typing import Optional

import numpy as np

from ... import common
from ...extra import aero
from . import (  # noqa: F401
    bds10,
    bds17,
    bds20,
    bds30,
    bds40,
    bds44,
    bds45,
    bds50,
    bds60,
    bds61,
    bds62,
)


def is50or60(
    msg: str, spd_ref: float, trk_ref: float, alt_ref: float
) -> Optional[str]:
    """Use reference ground speed and trk to determine BDS50 and DBS60.

    Args:
        msg (str): 28 hexdigits string
        spd_ref (float): reference speed (ADS-B ground speed), kts
        trk_ref (float): reference track (ADS-B track angle), deg
        alt_ref (float): reference altitude (ADS-B altitude), ft

    Returns:
        String or None: BDS version, or possible versions,
          or None if nothing matches.

    """

    def vxy(v, angle):
        vx = v * np.sin(np.radians(angle))
        vy = v * np.cos(np.radians(angle))
        return vx, vy

    # message must be both BDS 50 and 60 before processing
    if not (bds50.is50(msg) and bds60.is60(msg)):
        return None

    # --- assuming BDS60 ---
    h60 = bds60.hdg60(msg)
    m60 = bds60.mach60(msg)
    i60 = bds60.ias60(msg)

    # additional check now knowing the altitude
    if (m60 is not None) and (i60 is not None):
        ias_ = aero.mach2cas(m60, alt_ref * aero.ft) / aero.kts
        if abs(i60 - ias_) > 20:
            return "BDS50"

    if h60 is None or (m60 is None and i60 is None):
        return "BDS50,BDS60"

    m60 = np.nan if m60 is None else m60
    i60 = np.nan if i60 is None else i60

    # --- assuming BDS50 ---
    h50 = bds50.trk50(msg)
    v50 = bds50.gs50(msg)

    if h50 is None or v50 is None:
        return "BDS50,BDS60"

    XY5 = vxy(v50 * aero.kts, h50)
    XY6m = vxy(aero.mach2tas(m60, alt_ref * aero.ft), h60)
    XY6i = vxy(aero.cas2tas(i60 * aero.kts, alt_ref * aero.ft), h60)

    allbds = ["BDS50", "BDS60", "BDS60"]

    X = np.array([XY5, XY6m, XY6i])
    Mu = np.array(vxy(spd_ref * aero.kts, trk_ref))

    # compute Mahalanobis distance matrix
    # Cov = [[20**2, 0], [0, 20**2]]
    # mmatrix = np.sqrt(np.dot(np.dot(X-Mu, np.linalg.inv(Cov)), (X-Mu).T))
    # dist = np.diag(mmatrix)

    # since the covariance matrix is identity matrix,
    #     M-dist is same as eculidian distance
    try:
        dist = np.linalg.norm(X - Mu, axis=1)
        BDS = allbds[np.nanargmin(dist)]
    except ValueError:
        return "BDS50,BDS60"

    return BDS


def infer(msg: str, mrar: bool = False) -> Optional[str]:
    """Estimate the most likely BDS code of an message.

    Args:
        msg (str): 28 hexdigits string
        mrar (bool): Also infer MRAR (BDS 44) and MHR (BDS 45).
          Defaults to False.

    Returns:
        String or None: BDS version, or possible versions,
          or None if nothing matches.

    """
    df = common.df(msg)

    if common.allzeros(msg):
        return "EMPTY"

    # For ADS-B / Mode-S extended squitter
    if df == 17:
        tc = common.typecode(msg)
        if tc is None:
            return None

        if 1 <= tc <= 4:
            return "BDS08"  # identification and category
        if 5 <= tc <= 8:
            return "BDS06"  # surface movement
        if 9 <= tc <= 18:
            return "BDS05"  # airborne position, baro-alt
        if tc == 19:
            return "BDS09"  # airborne velocity
        if 20 <= tc <= 22:
            return "BDS05"  # airborne position, gnss-alt
        if tc == 28:
            return "BDS61"  # aircraft status
        if tc == 29:
            return "BDS62"  # target state and status
        if tc == 31:
            return "BDS65"  # operational status

    # For Comm-B replies
    IS10 = bds10.is10(msg)
    IS17 = bds17.is17(msg)
    IS20 = bds20.is20(msg)
    IS30 = bds30.is30(msg)
    IS40 = bds40.is40(msg)
    IS50 = bds50.is50(msg)
    IS60 = bds60.is60(msg)
    IS44 = bds44.is44(msg)
    IS45 = bds45.is45(msg)

    if mrar:
        allbds = np.array(
            [
                "BDS10",
                "BDS17",
                "BDS20",
                "BDS30",
                "BDS40",
                "BDS44",
                "BDS45",
                "BDS50",
                "BDS60",
            ]
        )
        mask = [IS10, IS17, IS20, IS30, IS40, IS44, IS45, IS50, IS60]
    else:
        allbds = np.array(
            ["BDS10", "BDS17", "BDS20", "BDS30", "BDS40", "BDS50", "BDS60"]
        )
        mask = [IS10, IS17, IS20, IS30, IS40, IS50, IS60]

    bds = ",".join(sorted(allbds[mask]))

    if len(bds) == 0:
        return None
    else:
        return bds
