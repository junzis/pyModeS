#include "demod2400.h"

static inline int slice_phase0(uint16_t *m)
{
    return 5 * m[0] - 3 * m[1] - 2 * m[2];
}
static inline int slice_phase1(uint16_t *m)
{
    return 4 * m[0] - m[1] - 3 * m[2];
}
static inline int slice_phase2(uint16_t *m)
{
    return 3 * m[0] + m[1] - 4 * m[2];
}
static inline int slice_phase3(uint16_t *m)
{
    return 2 * m[0] + 3 * m[1] - 5 * m[2];
}
static inline int slice_phase4(uint16_t *m)
{
    return m[0] + 5 * m[1] - 5 * m[2] - m[3];
}

int demodulate2400(uint16_t *mag, uint8_t *msg, int len_mag, int *len_msg)
{

    uint32_t j;
    for (j = 0; j < len_mag / 2 - 300; j++)
    { // SALE

        uint16_t *preamble = &mag[j];
        int high;
        uint32_t base_signal, base_noise;

        // quick check: we must have a rising edge 0->1 and a falling edge 12->13
        if (!(preamble[0] < preamble[1] && preamble[12] > preamble[13]))
            continue;

        if (preamble[1] > preamble[2] &&                               // 1
            preamble[2] < preamble[3] && preamble[3] > preamble[4] &&  // 3
            preamble[8] < preamble[9] && preamble[9] > preamble[10] && // 9
            preamble[10] < preamble[11])
        { // 11-12
            // peaks at 1,3,9,11-12: phase 3
            high = (preamble[1] + preamble[3] + preamble[9] + preamble[11] + preamble[12]) / 4;
            base_signal = preamble[1] + preamble[3] + preamble[9];
            base_noise = preamble[5] + preamble[6] + preamble[7];
        }
        else if (preamble[1] > preamble[2] &&                               // 1
                 preamble[2] < preamble[3] && preamble[3] > preamble[4] &&  // 3
                 preamble[8] < preamble[9] && preamble[9] > preamble[10] && // 9
                 preamble[11] < preamble[12])
        { // 12
            // peaks at 1,3,9,12: phase 4
            high = (preamble[1] + preamble[3] + preamble[9] + preamble[12]) / 4;
            base_signal = preamble[1] + preamble[3] + preamble[9] + preamble[12];
            base_noise = preamble[5] + preamble[6] + preamble[7] + preamble[8];
        }
        else if (preamble[1] > preamble[2] &&                                // 1
                 preamble[2] < preamble[3] && preamble[4] > preamble[5] &&   // 3-4
                 preamble[8] < preamble[9] && preamble[10] > preamble[11] && // 9-10
                 preamble[11] < preamble[12])
        { // 12
            // peaks at 1,3-4,9-10,12: phase 5
            high = (preamble[1] + preamble[3] + preamble[4] + preamble[9] + preamble[10] + preamble[12]) / 4;
            base_signal = preamble[1] + preamble[12];
            base_noise = preamble[6] + preamble[7];
        }
        else if (preamble[1] > preamble[2] &&                                 // 1
                 preamble[3] < preamble[4] && preamble[4] > preamble[5] &&    // 4
                 preamble[9] < preamble[10] && preamble[10] > preamble[11] && // 10
                 preamble[11] < preamble[12])
        { // 12
            // peaks at 1,4,10,12: phase 6
            high = (preamble[1] + preamble[4] + preamble[10] + preamble[12]) / 4;
            base_signal = preamble[1] + preamble[4] + preamble[10] + preamble[12];
            base_noise = preamble[5] + preamble[6] + preamble[7] + preamble[8];
        }
        else if (preamble[2] > preamble[3] &&                                 // 1-2
                 preamble[3] < preamble[4] && preamble[4] > preamble[5] &&    // 4
                 preamble[9] < preamble[10] && preamble[10] > preamble[11] && // 10
                 preamble[11] < preamble[12])
        { // 12
            // peaks at 1-2,4,10,12: phase 7
            high = (preamble[1] + preamble[2] + preamble[4] + preamble[10] + preamble[12]) / 4;
            base_signal = preamble[4] + preamble[10] + preamble[12];
            base_noise = preamble[6] + preamble[7] + preamble[8];
        }
        else
        {
            // no suitable peaks
            continue;
        }

        // Check for enough signal
        if (base_signal * 2 < 3 * base_noise) // about 3.5dB SNR
            continue;

        // Check that the "quiet" bits 6,7,15,16,17 are actually quiet
        if (preamble[5] >= high ||
            preamble[6] >= high ||
            preamble[7] >= high ||
            preamble[8] >= high ||
            preamble[14] >= high ||
            preamble[15] >= high ||
            preamble[16] >= high ||
            preamble[17] >= high ||
            preamble[18] >= high)
        {
            continue;
        }

        // // try all phases
        // Modes.stats_current.demod_preambles++;
        // bestmsg = NULL; bestscore = -2; bestphase = -1;
        for (int try_phase = 4; try_phase <= 8; ++try_phase)
        {
            uint16_t *pPtr;
            int phase, i, bytelen;

            // Decode all the next 112 bits, regardless of the actual message
            // size. We'll check the actual message type later

            pPtr = &mag[j + 19] + (try_phase / 5);
            phase = try_phase % 5;

            bytelen = MODES_LONG_MSG_BYTES;
            for (i = 0; i < bytelen; ++i)
            {
                uint8_t theByte = 0;

                switch (phase)
                {
                case 0:
                    theByte =
                        (slice_phase0(pPtr) > 0 ? 0x80 : 0) |
                        (slice_phase2(pPtr + 2) > 0 ? 0x40 : 0) |
                        (slice_phase4(pPtr + 4) > 0 ? 0x20 : 0) |
                        (slice_phase1(pPtr + 7) > 0 ? 0x10 : 0) |
                        (slice_phase3(pPtr + 9) > 0 ? 0x08 : 0) |
                        (slice_phase0(pPtr + 12) > 0 ? 0x04 : 0) |
                        (slice_phase2(pPtr + 14) > 0 ? 0x02 : 0) |
                        (slice_phase4(pPtr + 16) > 0 ? 0x01 : 0);

                    phase = 1;
                    pPtr += 19;
                    break;

                case 1:
                    theByte =
                        (slice_phase1(pPtr) > 0 ? 0x80 : 0) |
                        (slice_phase3(pPtr + 2) > 0 ? 0x40 : 0) |
                        (slice_phase0(pPtr + 5) > 0 ? 0x20 : 0) |
                        (slice_phase2(pPtr + 7) > 0 ? 0x10 : 0) |
                        (slice_phase4(pPtr + 9) > 0 ? 0x08 : 0) |
                        (slice_phase1(pPtr + 12) > 0 ? 0x04 : 0) |
                        (slice_phase3(pPtr + 14) > 0 ? 0x02 : 0) |
                        (slice_phase0(pPtr + 17) > 0 ? 0x01 : 0);

                    phase = 2;
                    pPtr += 19;
                    break;

                case 2:
                    theByte =
                        (slice_phase2(pPtr) > 0 ? 0x80 : 0) |
                        (slice_phase4(pPtr + 2) > 0 ? 0x40 : 0) |
                        (slice_phase1(pPtr + 5) > 0 ? 0x20 : 0) |
                        (slice_phase3(pPtr + 7) > 0 ? 0x10 : 0) |
                        (slice_phase0(pPtr + 10) > 0 ? 0x08 : 0) |
                        (slice_phase2(pPtr + 12) > 0 ? 0x04 : 0) |
                        (slice_phase4(pPtr + 14) > 0 ? 0x02 : 0) |
                        (slice_phase1(pPtr + 17) > 0 ? 0x01 : 0);

                    phase = 3;
                    pPtr += 19;
                    break;

                case 3:
                    theByte =
                        (slice_phase3(pPtr) > 0 ? 0x80 : 0) |
                        (slice_phase0(pPtr + 3) > 0 ? 0x40 : 0) |
                        (slice_phase2(pPtr + 5) > 0 ? 0x20 : 0) |
                        (slice_phase4(pPtr + 7) > 0 ? 0x10 : 0) |
                        (slice_phase1(pPtr + 10) > 0 ? 0x08 : 0) |
                        (slice_phase3(pPtr + 12) > 0 ? 0x04 : 0) |
                        (slice_phase0(pPtr + 15) > 0 ? 0x02 : 0) |
                        (slice_phase2(pPtr + 17) > 0 ? 0x01 : 0);

                    phase = 4;
                    pPtr += 19;
                    break;

                case 4:
                    theByte =
                        (slice_phase4(pPtr) > 0 ? 0x80 : 0) |
                        (slice_phase1(pPtr + 3) > 0 ? 0x40 : 0) |
                        (slice_phase3(pPtr + 5) > 0 ? 0x20 : 0) |
                        (slice_phase0(pPtr + 8) > 0 ? 0x10 : 0) |
                        (slice_phase2(pPtr + 10) > 0 ? 0x08 : 0) |
                        (slice_phase4(pPtr + 12) > 0 ? 0x04 : 0) |
                        (slice_phase1(pPtr + 15) > 0 ? 0x02 : 0) |
                        (slice_phase3(pPtr + 17) > 0 ? 0x01 : 0);

                    phase = 0;
                    pPtr += 20;
                    break;
                }

                msg[i] = theByte;
                if (i == 0)
                {
                    switch (msg[0] >> 3)
                    {
                    case 0:
                    case 4:
                    case 5:
                    case 11:
                        bytelen = MODES_SHORT_MSG_BYTES;
                        *len_msg = MODES_SHORT_MSG_BYTES;
                        break;

                    case 16:
                    case 17:
                    case 18:
                    case 20:
                    case 21:
                    case 24:
                        *len_msg = MODES_LONG_MSG_BYTES;
                        break;

                    default:
                        bytelen = 1; // unknown DF, give up immediately
                        break;
                    }
                }
            }

            return j + 1;
        }

        // Score the mode S message and see if it's any good.
        // score = scoreModesMessage(msg, i*8);
        // if (score > bestscore) {
        //     // new high score!
        //     bestmsg = msg;
        //     bestscore = score;
        //     bestphase = try_phase;
        //     // swap to using the other buffer so we don't clobber our demodulated data
        //     // (if we find a better result then we'll swap back, but that's OK because
        //     // we no longer need this copy if we found a better one)
        //     msg = (msg == msg1) ? msg2 : msg1;
        // }
    }
    return 0;
}