from __future__ import absolute_import, print_function, division

import numpy as np
from pyModeS.extra import aero
from pyModeS.decoder.modes import allzeros
from pyModeS.decoder.bds.bds10 import isBDS10
from pyModeS.decoder.bds.bds17 import isBDS17
from pyModeS.decoder.bds.bds20 import isBDS20
from pyModeS.decoder.bds.bds30 import isBDS30
from pyModeS.decoder.bds.bds40 import isBDS40
from pyModeS.decoder.bds.bds50 import isBDS50, trk50, gs50
from pyModeS.decoder.bds.bds60 import isBDS60, hdg60, mach60, ias60


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
        vx = v * np.sin(np.deg2rad(angle))
        vy = v * np.cos(np.deg2rad(angle))
        return vx, vy

    if not (isBDS50(msg) and isBDS60(msg)):
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
    Mu = np.array(vxy(spd_ref*aero.kts, trk_ref*aero.kts))

    # compute Mahalanobis distance matrix
    # Cov = [[20**2, 0], [0, 20**2]]
    # mmatrix = np.sqrt(np.dot(np.dot(X-Mu, np.linalg.inv(Cov)), (X-Mu).T))
    # dist = np.diag(mmatrix)

    # since the covariance matrix is identity matrix,
    #     M-dist is same as eculidian distance
    dist = np.linalg.norm(X-Mu, axis=1)
    BDS = allbds[np.nanargmin(dist)]

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

    is10 = isBDS10(msg)
    is17 = isBDS17(msg)
    is20 = isBDS20(msg)
    is30 = isBDS30(msg)
    is40 = isBDS40(msg)
    is50 = isBDS50(msg)
    is60 = isBDS60(msg)

    allbds = np.array([
        "BDS10", "BDS17", "BDS20", "BDS30", "BDS40", "BDS50", "BDS60"
    ])

    isBDS = [is10, is17, is20, is30, is40, is50, is60]

    bds = ','.join(sorted(allbds[isBDS]))

    if len(bds) == 0:
        return None
    else:
        return bds
