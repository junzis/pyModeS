import numpy as np
import typing as tp

from .util import create_array
from .types import InputData, DownlinkFormat, TypeCode


def df(data: InputData) -> DownlinkFormat:
    """
    Parse downlink format address from ADS-B messages.

    :param data: ADS-B messages.

    ..seealso:: `Message structure <https://mode-s.org/decode/content/ads-b/1-basics.html>`_
    """
    result = (data[:, 0] & 0xf8) >> 3
    result[result > 24] = 24
    return result

def typecode(data: InputData, df_data: tp.Optional[DownlinkFormat]=None) -> TypeCode:
    """
    Parse type code information from ADS-B messages.

    :param data: ADS-B messages.
    :param df_data: Optional downlink format information for each ADS-B
        message.

    ..seealso:: `ADS-B message types <https://mode-s.org/decode/content/ads-b/1-basics.html>`_
    """
    result = np.zeros(len(data), dtype=np.uint8)
    df_v = df(data) if df_data is None else df_data
    idx = (df_v == 17) | (df_v == 18)
    result[idx] = data[idx, 4] >> 3
    return create_array(result, idx)
