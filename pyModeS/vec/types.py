import numpy as np

# define aliases for basic types to support static type analysis; these for
# convenience
# NOTE: more specific types can be defined when numpy 1.20 is released,
# i.e. use of np.ndarray[dtype, shape] shall be possible
InputData = np.ndarray
DownlinkFormat = np.ndarray
TypeCode = np.ndarray
