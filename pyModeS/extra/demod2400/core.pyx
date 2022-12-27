from libc.stdint cimport uint16_t, uint8_t
import numpy as np

from ...c_common cimport crc, df

cdef extern from "demod2400.h":
    int demodulate2400(uint16_t *data, uint8_t *msg, int len_data, int* len_msg)


def demod2400(uint16_t[:] data, float timestamp):
    cdef uint8_t[:] msg_bin
    cdef int i = 0, j, length, crc_msg = 1
    cdef long size = data.shape[0]

    msg_bin = np.zeros(14, dtype=np.uint8)

    while i < size:
        j = demodulate2400(&data[i], &msg_bin[0], size-i, &length)
        if j == 0:
            yield dict(
                # 1 sample data = 2 IQ samples (hence 2*)
                timestamp=timestamp + 2.*i/2400000.,
                payload=None,
                crc=None,
                index=i,
            )
            return
        i += j
        msg_clip = np.asarray(msg_bin)[:length]
        msg = "".join(f"{elt:02X}" for elt in msg_clip)
        crc_msg = crc(msg)
        # if df(msg) != 17 or crc_msg == 0:
        if crc_msg == 0:
            yield dict(
                # 1 sample data = 2 IQ samples (hence 2*)
                timestamp=timestamp + 2.*i/2400000.,
                payload=msg,
                crc=crc_msg,
                index=i,
            )

    yield dict(
        # 1 sample data = 2 IQ samples (hence 2*)
        timestamp=timestamp + 2.*i/2400000.,
        payload=None,
        crc=None,
        index=i,
    )
    return