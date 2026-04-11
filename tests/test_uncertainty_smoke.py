"""Smoke test for pyModeS._uncertainty lookup tables.

These are data-only tables ported verbatim from v2. The smoke test
confirms a single lookup returns the expected value so that a typo
in the port is caught at import time.
"""

from pyModeS._uncertainty import (
    NA,
    SIL,
    NACp,
    NACv,
    NICv1,
    NICv2,
    NUCp,
    NUCv,
    TC_NICv1_lookup,
    TC_NICv2_lookup,
    TC_NUCp_lookup,
)


def test_tc_nicv1_lookup_sample():
    # TC=5 → NIC=11; TC=11 → dict with subtype keys
    assert TC_NICv1_lookup[5] == 11
    assert TC_NICv1_lookup[11] == {1: 9, 0: 8}


def test_tc_nicv2_lookup_sample():
    # TC=9 → NIC=11; TC=7 → dict with subtype keys
    assert TC_NICv2_lookup[9] == 11
    assert TC_NICv2_lookup[7] == {2: 9, 0: 8}


def test_na_is_none():
    assert NA is None


def test_tc_nucp_lookup_sample():
    # TC=5 → NUCp=9 (high integrity surface position)
    assert TC_NUCp_lookup[5] == 9
    assert TC_NUCp_lookup[11] == 7
    assert TC_NUCp_lookup[18] == 0


def test_nucp_sample():
    # NUCp=9 → HPL=7.5, RCu=3, RCv=4
    entry = NUCp[9]
    assert entry["HPL"] == 7.5
    assert entry["RCu"] == 3
    assert entry["RCv"] == 4


def test_nucv_sample():
    # NUCv=1 → HVE=10, VVE=15.2
    entry = NUCv[1]
    assert entry["HVE"] == 10
    assert entry["VVE"] == 15.2


def test_nicv1_sample():
    # NIC=11, NICs=0 → Rc=7.5
    assert NICv1[11][0]["Rc"] == 7.5


def test_nicv2_sample():
    assert NICv2[11][0]["Rc"] == 7.5


def test_nacp_sample():
    # NACp=11 → EPU=3, VEPU=4
    entry = NACp[11]
    assert entry["EPU"] == 3
    assert entry["VEPU"] == 4


def test_nacv_sample():
    entry = NACv[1]
    assert entry["HFOMr"] == 10
    assert entry["VFOMr"] == 15.2


def test_sil_sample():
    # SIL=3 → PE_RCu=1e-7, PE_VPL=2e-7
    assert SIL[3]["PE_RCu"] == 1e-7
    assert SIL[3]["PE_VPL"] == 2e-7
