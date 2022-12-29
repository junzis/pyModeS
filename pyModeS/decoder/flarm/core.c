#include "core.h"

/*
 *
 * https://pastebin.com/YK2f8bfm
 *
 * NEW ENCRYPTION
 *
 * Swiss glider anti-colission system moved to a new encryption scheme: XXTEA
 * The algorithm encrypts all the packet after the header: total 20 bytes or 5 long int words of data
 *
 * XXTEA description and code are found here: http://en.wikipedia.org/wiki/XXTEA
 * The system uses 6 iterations of the main loop.
 *
 * The system version 6 sends two type of packets: position and ... some unknown data
 * The difference is made by bit 0 of byte 3 of the packet: for position data this bit is zero.
 *
 * For position data the key used depends on the time and transmitting device address.
 * The key is as well obscured by a weird algorithm.
 * The code to generate the key is:
 *
 * */

void make_key(int *key, long time, long address)
{
  const long key1[4] = {0xe43276df, 0xdca83759, 0x9802b8ac, 0x4675a56b};
  const long key1b[4] = {0xfc78ea65, 0x804b90ea, 0xb76542cd, 0x329dfa32};
  const long *table = ((((time >> 23) & 255) & 0x01) != 0) ? key1b : key1;

  for (int i = 0; i < 4; i++)
  {
    key[i] = obscure(table[i] ^ ((time >> 6) ^ address), 0x045D9F3B) ^ 0x87B562F4;
  }
}

long obscure(long key, unsigned long seed)
{
  unsigned int m1 = seed * (key ^ (key >> 16));
  unsigned int m2 = seed * (m1 ^ (m1 >> 16));
  return m2 ^ (m2 >> 16);
}

/*
 * NEW PACKET FORMAT:
 *
 * Byte     Bits
 *  0     AAAA AAAA    device address
 *  1     AAAA AAAA
 *  2     AAAA AAAA
 *  3     00aa 0000    aa = 10 or 01
 *
 *  4     vvvv vvvv    vertical speed
 *  5     xxxx xxvv
 *  6     gggg gggg    GPS status
 *  7     tttt gggg    plane type
 *
 *  8     LLLL LLLL    Latitude
 *  9     LLLL LLLL
 * 10     aaaa aLLL
 * 11     aaaa aaaa    Altitude
 *
 * 12     NNNN NNNN    Longitude
 * 13     NNNN NNNN
 * 14     xxxx NNNN
 * 15     FFxx xxxx    multiplying factor
 *
 * 16     SSSS SSSS    as in version 4
 * 17     ssss ssss
 * 18     KKKK KKKK
 * 19     kkkk kkkk
 *
 * 20     EEEE EEEE
 * 21     eeee eeee
 * 22     PPPP PPPP
 * 24     pppp pppp
 * */

/*
 * https://en.wikipedia.org/wiki/XXTEA
 */

void btea(uint32_t *v, int n, uint32_t const key[4])
{
  uint32_t y, z, sum;
  unsigned p, rounds, e;
  if (n > 1)
  { /* Coding Part */
    /* Unused, should remove? */
    rounds = 6 + 52 / n;
    sum = 0;
    z = v[n - 1];
    do
    {
      sum += DELTA;
      e = (sum >> 2) & 3;
      for (p = 0; p < (unsigned)n - 1; p++)
      {
        y = v[p + 1];
        z = v[p] += MX;
      }
      y = v[0];
      z = v[n - 1] += MX;
    } while (--rounds);
  }
  else if (n < -1)
  { /* Decoding Part */
    n = -n;
    rounds = 6; // + 52 / n;
    sum = rounds * DELTA;
    y = v[0];
    do
    {
      e = (sum >> 2) & 3;
      for (p = n - 1; p > 0; p--)
      {
        z = v[p - 1];
        y = v[p] -= MX;
      }
      z = v[n - 1];
      y = v[0] -= MX;
      sum -= DELTA;
    } while (--rounds);
  }
}