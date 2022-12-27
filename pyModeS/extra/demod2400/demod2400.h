#ifndef __DEMOD_2400_H__
#define __DEMOD_2400_H__

#define MODES_LONG_MSG_BYTES     14
#define MODES_SHORT_MSG_BYTES    7

#include <stdint.h>

int demodulate2400(uint16_t *mag, uint8_t *msg, int len_mag, int* len_msg);

#endif