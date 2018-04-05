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

from __future__ import absolute_import, print_function, division
import numpy as np

from pyModeS.extra import aero
from pyModeS.decoder.common import allzeros
from pyModeS.decoder.bds.bds10 import is10
from pyModeS.decoder.bds.bds17 import is17
from pyModeS.decoder.bds.bds20 import is20
from pyModeS.decoder.bds.bds30 import is30
from pyModeS.decoder.bds.bds40 import is40
from pyModeS.decoder.bds.bds50 import is50, trk50, gs50
from pyModeS.decoder.bds.bds60 import is60, hdg60, mach60, ias60


def is50or60(msg, spd_ref, trk_ref, alt_ref):
    """Use reference ground speed and trk to determine BDS50 and DBS60

    Args:
        msg (String): 28 bytes hexadecimal message string
        spd_ref (float): reference speed (ADS-B ground speed), kts
        trk_ref (float): reference track (ADS-B track angle), deg
        alt_ref (float): reference altitude (ADS-B altitude), ft

    Returns:
        String or None: BDS version, or possible versions, or None if nothing matches.
    """
    def vxy(v, angle):
        vx = v * np.sin(np.radians(angle))
        vy = v * np.cos(np.radians(angle))
        return vx, vy

    if not (is50(msg) and is60(msg)):
        return None

    h50 = trk50(msg)
    v50 = gs50(msg)
    h50 = np.nan if h50 is None else h50
    v50 = np.nan if v50 is None else v50

    h60 = hdg60(msg)
    m60 = mach60(msg)
    i60 = ias60(msg)
    h60 = np.nan if h60 is None else h60
    m60 = np.nan if m60 is None else m60
    i60 = np.nan if i60 is None else i60

    XY5 = vxy(v50*aero.kts, h50)
    XY6m = vxy(aero.mach2tas(m60, alt_ref*aero.ft), h60)
    XY6i = vxy(aero.cas2tas(i60*aero.kts, alt_ref*aero.ft), h60)

    allbds = ['BDS50', 'BDS60', 'BDS60']

    X = np.array([XY5, XY6m, XY6i])
    Mu = np.array(vxy(spd_ref*aero.kts, trk_ref))

    # compute Mahalanobis distance matrix
    # Cov = [[20**2, 0], [0, 20**2]]
    # mmatrix = np.sqrt(np.dot(np.dot(X-Mu, np.linalg.inv(Cov)), (X-Mu).T))
    # dist = np.diag(mmatrix)

    # since the covariance matrix is identity matrix,
    #     M-dist is same as eculidian distance
    try:
        dist = np.linalg.norm(X-Mu, axis=1)
        BDS = allbds[np.nanargmin(dist)]
    except ValueError:
        return None

    return BDS


def infer(msg):
    """Estimate the most likely BDS code of an message

    Args:
        msg (String): 28 bytes hexadecimal message string

    Returns:
        String or None: BDS version, or possible versions, or None if nothing matches.
    """

    if allzeros(msg):
        return None

    IS10 = is10(msg)
    IS17 = is17(msg)
    IS20 = is20(msg)
    IS30 = is30(msg)
    IS40 = is40(msg)
    IS50 = is50(msg)
    IS60 = is60(msg)

    allbds = np.array([
        "BDS10", "BDS17", "BDS20", "BDS30", "BDS40", "BDS50", "BDS60"
    ])

    mask = [IS10, IS17, IS20, IS30, IS40, IS50, IS60]

    bds = ','.join(sorted(allbds[mask]))

    if len(bds) == 0:
        return None
    else:
        return bds
