"""Uncertainty parameters.

"""

from __future__ import annotations

import sys

if sys.version_info < (3, 8):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

NA = None

TC_NUCp_lookup = {
    0: 0,
    5: 9,
    6: 8,
    7: 7,
    8: 6,
    9: 9,
    10: 8,
    11: 7,
    12: 6,
    13: 5,
    14: 4,
    15: 3,
    16: 2,
    17: 1,
    18: 0,
    20: 9,
    21: 8,
    22: 0,
}

TC_NICv1_lookup: dict[int, int | dict[int, int]] = {
    5: 11,
    6: 10,
    7: 9,
    8: 0,
    9: 11,
    10: 10,
    11: {1: 9, 0: 8},
    12: 7,
    13: 6,
    14: 5,
    15: 4,
    16: {1: 3, 0: 2},
    17: 1,
    18: 0,
    20: 11,
    21: 10,
    22: 0,
}

TC_NICv2_lookup: dict[int, int | dict[int, int]] = {
    5: 11,
    6: 10,
    7: {2: 9, 0: 8},
    8: {3: 7, 2: 6, 1: 6, 0: 0},
    9: 11,
    10: 10,
    11: {3: 9, 0: 8},
    12: 7,
    13: 6,
    14: 5,
    15: 4,
    16: {3: 3, 0: 2},
    17: 1,
    18: 0,
    20: 11,
    21: 10,
    22: 0,
}


class NUCpEntry(TypedDict):
    HPL: None | float
    RCu: None | int
    RCv: None | int


NUCp: dict[int, NUCpEntry] = {
    9: {"HPL": 7.5, "RCu": 3, "RCv": 4},
    8: {"HPL": 25, "RCu": 10, "RCv": 15},
    7: {"HPL": 185, "RCu": 93, "RCv": NA},
    6: {"HPL": 370, "RCu": 185, "RCv": NA},
    5: {"HPL": 926, "RCu": 463, "RCv": NA},
    4: {"HPL": 1852, "RCu": 926, "RCv": NA},
    3: {"HPL": 3704, "RCu": 1852, "RCv": NA},
    2: {"HPL": 18520, "RCu": 9260, "RCv": NA},
    1: {"HPL": 37040, "RCu": 18520, "RCv": NA},
    0: {"HPL": NA, "RCu": NA, "RCv": NA},
}


class NUCvEntry(TypedDict):
    HVE: None | float
    VVE: None | float


NUCv: dict[int, NUCvEntry] = {
    0: {"HVE": NA, "VVE": NA},
    1: {"HVE": 10, "VVE": 15.2},
    2: {"HVE": 3, "VVE": 4.5},
    3: {"HVE": 1, "VVE": 1.5},
    4: {"HVE": 0.3, "VVE": 0.46},
}


class NACpEntry(TypedDict):
    EPU: None | int
    VEPU: None | int


NACp: dict[int, NACpEntry] = {
    11: {"EPU": 3, "VEPU": 4},
    10: {"EPU": 10, "VEPU": 15},
    9: {"EPU": 30, "VEPU": 45},
    8: {"EPU": 93, "VEPU": NA},
    7: {"EPU": 185, "VEPU": NA},
    6: {"EPU": 556, "VEPU": NA},
    5: {"EPU": 926, "VEPU": NA},
    4: {"EPU": 1852, "VEPU": NA},
    3: {"EPU": 3704, "VEPU": NA},
    2: {"EPU": 7408, "VEPU": NA},
    1: {"EPU": 18520, "VEPU": NA},
    0: {"EPU": NA, "VEPU": NA},
}


class NACvEntry(TypedDict):
    HFOMr: None | float
    VFOMr: None | float


NACv: dict[int, NACvEntry] = {
    0: {"HFOMr": NA, "VFOMr": NA},
    1: {"HFOMr": 10, "VFOMr": 15.2},
    2: {"HFOMr": 3, "VFOMr": 4.5},
    3: {"HFOMr": 1, "VFOMr": 1.5},
    4: {"HFOMr": 0.3, "VFOMr": 0.46},
}


class SILEntry(TypedDict):
    PE_RCu: None | float
    PE_VPL: None | float


SIL: dict[int, SILEntry] = {
    3: {"PE_RCu": 1e-7, "PE_VPL": 2e-7},
    2: {"PE_RCu": 1e-5, "PE_VPL": 1e-5},
    1: {"PE_RCu": 1e-3, "PE_VPL": 1e-3},
    0: {"PE_RCu": NA, "PE_VPL": NA},
}


class NICv1Entry(TypedDict):
    Rc: None | float
    VPL: None | float


NICv1: dict[int, dict[int, NICv1Entry]] = {
    # NIC is used as the index at second Level
    11: {0: {"Rc": 7.5, "VPL": 11}},
    10: {0: {"Rc": 25, "VPL": 37.5}},
    9: {1: {"Rc": 75, "VPL": 112}},
    8: {0: {"Rc": 185, "VPL": NA}},
    7: {0: {"Rc": 370, "VPL": NA}},
    6: {0: {"Rc": 926, "VPL": NA}, 1: {"Rc": 1111, "VPL": NA}},
    5: {0: {"Rc": 1852, "VPL": NA}},
    4: {0: {"Rc": 3702, "VPL": NA}},
    3: {1: {"Rc": 7408, "VPL": NA}},
    2: {0: {"Rc": 14008, "VPL": NA}},
    1: {0: {"Rc": 37000, "VPL": NA}},
    0: {0: {"Rc": NA, "VPL": NA}},
}


class NICv2Entry(TypedDict):
    Rc: None | float


NICv2: dict[int, dict[int, NICv2Entry]] = {
    # Decimal value of [NICa NICb/NICc] is used as the index at second Level
    11: {0: {"Rc": 7.5}},
    10: {0: {"Rc": 25}},
    9: {2: {"Rc": 75}, 3: {"Rc": 75}},
    8: {0: {"Rc": 185}},
    7: {0: {"Rc": 370}, 3: {"Rc": 370}},
    6: {0: {"Rc": 926}, 1: {"Rc": 556}, 2: {"Rc": 556}, 3: {"Rc": 1111}},
    5: {0: {"Rc": 1852}},
    4: {0: {"Rc": 3702}},
    3: {3: {"Rc": 7408}},
    2: {0: {"Rc": 14008}},
    1: {0: {"Rc": 37000}},
    0: {0: {"Rc": NA}},
}
