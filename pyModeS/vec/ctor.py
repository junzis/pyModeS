import numpy as np
import typing as tp

from .types import InputData

def array(data: tp.Sequence[bytes]) -> InputData:
    """
    Create Numpy array, which is input for parsing functions.

    :param data: Collection of ADS-B messages.
    """
    vec = np.array(data)
    result = vec.view(dtype=np.uint8)
    return result.reshape(-1, 14)

