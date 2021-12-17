import numpy as np

def create_array(data, idx):
    """
    Create NumPy masked array.

    Note, that this function differes from NumPy constructor semantics. The
    index indicates the valid values (not the invalid as in the default
    masked array in NumPy).

    :param data: Input data.
    :param idx: Index of valid values.
    """
    return np.ma.array(data, mask=~idx)

# vim: sw=4:et:ai
