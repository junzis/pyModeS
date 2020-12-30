import typing as tp
from functools import singledispatch

from .vec import common as common_vec
from .vec.types import InputData
try:
    from . import c_common as common_str
except:
    from . import py_common as common_str

@singledispatch
def df(msg: tp.Any) -> int:
    raise NotImplementedError('Only string and NumPy arrays supported')

@df.register
def _df_str(msg: str) -> int:
    return common_str.df(msg)

@df.register
def _df_vec(msg: InputData) -> int:
    return common_vec.df(msg)

@singledispatch
def typecode(msg: tp.Any) -> int:
    raise NotImplementedError('Only string and NumPy arrays supported')

@typecode.register
def _tc_str(msg: str) -> int:
    return common_str.typecode(msg)

@typecode.register
def _tc_vec(msg: InputData) -> int:
    return common_vec.typecode(msg)

icao = common_str.icao
altitude = common_str.altitude
altcode = common_str.altcode
allzeros = common_str.allzeros
data = common_str.data
wrongstatus = common_str.wrongstatus
idcode = common_str.idcode
floor = common_str.floor
cprNL = common_str.cprNL
crc = common_str.crc
squawk = common_str.squawk
hex2bin = common_str.hex2bin
hex2bin = common_str.hex2bin
bin2int = common_str.bin2int
