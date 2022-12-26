#ifndef __CORE_H__
#define __CORE_H__

#include <stdint.h>

#define DELTA 0x9e3779b9
#define MX (((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ ((sum ^ y) + (key[(p & 3) ^ e] ^ z)))

void make_key(int *key, long time, long address);
long obscure(long key, unsigned long seed);
void btea(uint32_t *v, int n, uint32_t const key[4]);

#endif
