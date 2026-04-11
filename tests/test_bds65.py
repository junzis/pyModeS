"""Tests for pyModeS.decoder.bds.bds65 — ADS-B operational status (BDS 6,5)."""

from pyModeS import decode
from pyModeS.decoder.bds.bds65 import decode_bds65


class TestBds65Airborne:
    def test_synthetic_airborne_status(self):
        # Synthetic TC=31 subtype 0 message with known fields.
        # Build: version=2, nic_s_a=1, nac_p=10, sil=3, nic_baro=1
        tc = 31
        subtype = 0
        version = 2
        nic_s_a = 1
        nac_p = 10
        sil = 3
        nic_baro = 1

        payload = 0
        payload |= tc << 51  # bits 0-4
        payload |= subtype << 48  # bits 5-7
        # version at bits 40-42 → LSB pos 55-40=15 down to 55-42=13
        payload |= version << 13
        payload |= nic_s_a << 12  # bit 43 → LSB pos 12
        payload |= nac_p << 8  # bits 44-47 → LSB pos 11..8
        payload |= sil << 4  # bits 50-51 → LSB pos 5..4
        # nic_baro at bit 52 → LSB pos 3
        payload |= nic_baro << 3

        result = decode_bds65(payload)
        assert result["subtype"] == 0
        assert result["version"] == 2
        assert result["nic_supplement_a"] == 1
        assert result["nac_p"] == 10
        assert result["sil"] == 3
        assert result["nic_baro"] == 1

    def test_dispatch_via_adsb_class(self):
        # Build the same synthetic TC=31 as a full DF17 message.
        from pyModeS._bits import crc_remainder

        tc = 31
        payload = tc << 51  # minimum viable TC=31 payload
        # Full DF17: DF=17 (10001), CA=5, ICAO=400000, ME, CRC
        df_ca = (17 << 3) | 5  # 0x8D
        icao = 0x400000
        n = (df_ca << 104) | (icao << 80) | (payload << 24)
        # Compute CRC so the message is self-consistent
        parity = crc_remainder(n, 112)
        n |= parity
        msg = f"{n:028X}"

        result = decode(msg)
        assert result["df"] == 17
        assert result["typecode"] == 31
        assert result["bds"] == "6,5"
        assert result["subtype"] == 0


class TestBds65Surface:
    def test_surface_subtype_recognized(self):
        # Subtype 1 is surface; verify it dispatches and returns subtype=1.
        payload = (31 << 51) | (1 << 48)
        result = decode_bds65(payload)
        assert result["subtype"] == 1

    def test_surface_no_nic_baro(self):
        # NIC_baro is only emitted for subtype=0 (airborne) v>=1.
        payload = (31 << 51) | (1 << 48) | (2 << 13)  # subtype=1, version=2
        result = decode_bds65(payload)
        assert "nic_baro" not in result

    def test_airborne_v0_no_nic_baro(self):
        # NIC_baro is only valid for ADS-B version >= 1. v0 must not emit it.
        payload = (31 << 51) | (0 << 48) | (0 << 13)  # subtype=0, version=0
        result = decode_bds65(payload)
        assert "nic_baro" not in result
