"""pyModeS 2.21.1 equivalent of rs1090.decode, vendored from jet1090.

Source: jet1090 python/examples/bench_pms.py
URL:    https://github.com/xoolive/jet1090
Commit: da4ed8509ce948d8816ecb047cc8b010cd618494

Vendored so that scripts/benchmark_decode.py can measure pyModeS v3
against the SAME v2 dispatch path jet1090 measured in its published
benchmark chart — apples-to-apples, no methodology drift.

Only runs under `uv run --no-project --with 'pyModeS==2.21.1'`.
Do not modify the logic. If jet1090's bench_pms.py updates, sync
manually.
"""

from typing import Any

from pyModeS import adsb, bds, commb, py_common  # type: ignore


def decode(msg: str, common: Any = py_common) -> dict[str, Any]:
    """rs1090.decode coded in pyModeS

    This is a rough equivalement of the rs1090 decode function (with few
    fields left undecoded). Let's say it's not a big deal.

    There **must** be some imprecisions, but that's enough for benchmarking.

    """

    df = common.df(msg)
    icao = common.icao(msg)

    decoded = {"msg": msg, "icao": icao, "df": df}

    if df == 17:
        decoded["tc"] = tc = common.typecode(msg)

        if tc is None:
            return decoded

        if 1 <= tc <= 4:  # callsign
            callsign = adsb.callsign(msg)
            decoded["bds"] = 10
            decoded["callsign"] = callsign

        if 5 <= tc <= 8:  # surface position
            decoded["bds"] = "06"
            oe = adsb.oe_flag(msg)
            msgbin = common.hex2bin(msg)
            cprlat = common.bin2int(msgbin[54:71]) / 131072.0
            cprlon = common.bin2int(msgbin[71:88]) / 131072.0
            v = adsb.surface_velocity(msg)
            decoded["oddflag"] = "odd" if oe else "even"
            decoded["cprlat"] = cprlat
            decoded["cprlon"] = cprlon
            decoded["speed"] = v[0]
            decoded["track"] = v[1]

        if 9 <= tc <= 18:  # airborne position
            decoded["bds"] = "05"
            alt = adsb.altitude(msg)
            oe = adsb.oe_flag(msg)
            msgbin = common.hex2bin(msg)
            cprlat = common.bin2int(msgbin[54:71]) / 131072.0
            cprlon = common.bin2int(msgbin[71:88]) / 131072.0
            decoded["oddflag"] = "odd" if oe else "even"
            decoded["cprlat"] = cprlat
            decoded["cprlon"] = cprlon
            decoded["altitude"] = alt

        if tc == 19:
            decoded["bds"] = "09"
            velocity = adsb.velocity(msg)
            if velocity is not None:
                spd, trk, vr, t = velocity
                types = {"GS": "Ground speed", "TAS": "True airspeed"}
                decoded[types[t]] = spd
                decoded["track"] = trk
                decoded["vertical_rate"] = vr

        if 20 <= tc <= 22:  # airborne position
            decoded["bds"] = "05"
            alt = adsb.altitude(msg)
            oe = adsb.oe_flag(msg)
            msgbin = common.hex2bin(msg)
            cprlat = common.bin2int(msgbin[54:71]) / 131072.0
            cprlon = common.bin2int(msgbin[71:88]) / 131072.0
            decoded["oddflag"] = "odd" if oe else "even"
            decoded["cprlat"] = cprlat
            decoded["cprlon"] = cprlon
            decoded["altitude"] = alt

        if tc == 29:  # target state and status
            decoded["bds"] = "62"
            subtype = common.bin2int((common.hex2bin(msg)[32:])[5:7])
            tcas_operational = adsb.tcas_operational(msg)
            types_29 = {0: "Not Engaged", 1: "Engaged"}
            tcas_operational_types = {0: "Not Operational", 1: "Operational"}
            if subtype == 0:
                emergency_types = {
                    0: "No emergency",
                    1: "General emergency",
                    2: "Lifeguard/medical emergency",
                    3: "Minimum fuel",
                    4: "No communications",
                    5: "Unlawful interference",
                    6: "Downed aircraft",
                    7: "Reserved",
                }
                vertical_horizontal_types = {
                    1: "Acquiring mode",
                    2: "Capturing/Maintaining mode",
                }
                tcas_ra_types = {0: "Not active", 1: "Active"}
                alt, alt_source, alt_ref = adsb.target_altitude(msg)
                angle, angle_type, angle_source = adsb.target_angle(msg)
                vertical_mode = adsb.vertical_mode(msg)
                horizontal_mode = adsb.horizontal_mode(msg)
                tcas_ra = adsb.tcas_ra(msg)
                emergency_status = adsb.emergency_status(msg)
                decoded["target_alt"] = alt
                decoded["alt_source"] = alt_source
                decoded["alt_reference"] = alt_ref
                decoded["angle"] = angle
                decoded["angle_type"] = angle_type
                decoded["angle_source"] = angle_source
                if vertical_mode is not None:
                    decoded["vnav_mode"] = (vertical_horizontal_types[vertical_mode],)

                if horizontal_mode is not None:
                    decoded["lnav_mode"] = (vertical_horizontal_types[horizontal_mode],)
                decoded["tcas"] = (
                    tcas_operational_types[tcas_operational]
                    if tcas_operational
                    else None,
                )
                decoded["tcas_type"] = tcas_ra_types[tcas_ra]
                decoded["emergency_status"] = emergency_types[emergency_status]
            else:
                alt, alt_source = adsb.selected_altitude(msg)
                baro = adsb.baro_pressure_setting(msg)
                hdg = adsb.selected_heading(msg)
                autopilot = adsb.autopilot(msg)
                vnav = adsb.vnav_mode(msg)
                alt_hold = adsb.altitude_hold_mode(msg)
                app = adsb.approach_mode(msg)
                lnav = adsb.lnav_mode(msg)
                decoded["selected_alt"] = alt
                decoded["alt_source"] = alt_source
                decoded["barometric_setting"] = baro
                decoded["selected_hdg"] = hdg
                if not (common.bin2int((common.hex2bin(msg)[32:])[46]) == 0):
                    decoded["autopilot"] = types_29[autopilot] if autopilot else None
                    decoded["vnav_mode"] = types_29[vnav] if vnav else None
                    decoded["alt_hold"] = (types_29[alt_hold] if alt_hold else None,)
                    decoded["app_mode"] = types_29[app] if app else None
                    decoded["tcas"] = (
                        tcas_operational_types[tcas_operational]
                        if tcas_operational
                        else None,
                    )
                    decoded["lnav_mode"] = types_29[lnav] if lnav else None

    if df == 20:
        decoded["altitude"] = common.altcode(msg)

    if df == 21:
        decoded["squawk"] = common.idcode(msg)

    if df == 20 or df == 21:
        decoded["bds"] = BDS = bds.infer(msg, mrar=True)

        if BDS == "BDS20":
            decoded["callsign"] = callsign = commb.cs20(msg)

        if BDS == "BDS40":
            decoded["selected_mcp"] = commb.selalt40mcp(msg)
            decoded["selected_fms"] = commb.selalt40fms(msg)
            decoded["selected_baro"] = commb.p40baro(msg)

        if BDS == "BDS50":
            decoded["Roll angle"] = commb.roll50(msg)
            decoded["Track angle"] = commb.trk50(msg)
            decoded["Track rate"] = commb.rtrk50(msg)
            decoded["Ground speed"] = commb.gs50(msg)
            decoded["True airspeed"] = commb.tas50(msg)

        if BDS == "BDS60":
            decoded["Megnatic Heading"] = commb.hdg60(msg)
            decoded["Indicated airspeed"] = commb.ias60(msg)
            decoded["Mach number"] = commb.mach60(msg)
            decoded["Vertical rate (Baro)"] = commb.vr60baro(msg)
            decoded["Vertical rate (INS)"] = commb.vr60ins(msg)

        if BDS == "BDS44":
            decoded["Wind speed"] = commb.wind44(msg)[0]
            decoded["Wind direction"] = commb.wind44(msg)[1]
            decoded["Temperature 1"] = commb.temp44(msg)[0]
            decoded["Temperature 2"] = commb.temp44(msg)[1]
            decoded["Pressure"] = commb.p44(msg)
            decoded["Humidity"] = commb.hum44(msg)
            decoded["Turbulence"] = commb.turb44(msg)

        if BDS == "BDS45":
            decoded["Turbulence"] = commb.turb45(msg)
            decoded["Wind shear"] = commb.ws45(msg)
            decoded["Microbust"] = commb.mb45(msg)
            decoded["Icing"] = commb.ic45(msg)
            decoded["Wake vortex"] = commb.wv45(msg)
            decoded["Temperature"] = commb.temp45(msg)
            decoded["Pressure"] = commb.p45(msg)
            decoded["Radio height"] = commb.rh45(msg)

    return decoded
