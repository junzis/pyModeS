def tell(msg: str) -> None:
    from .. import common, adsb, commb, bds

    def _print(label, value, unit=None):
        print("%28s: " % label, end="")
        print("%s " % value, end="")
        if unit:
            print(unit)
        else:
            print()

    df = common.df(msg)
    icao = common.icao(msg)

    _print("Message", msg)
    _print("ICAO address", icao)
    _print("Downlink Format", df)

    if df == 17:
        _print("Protocol", "Mode-S Extended Squitter (ADS-B)")

        tc = common.typecode(msg)

        if tc is None:
            _print("ERROR", "Unknown typecode")
            return

        if 1 <= tc <= 4:  # callsign
            callsign = adsb.callsign(msg)
            _print("Type", "Identification and category")
            _print("Callsign:", callsign)

        if 5 <= tc <= 8:  # surface position
            _print("Type", "Surface position")
            oe = adsb.oe_flag(msg)
            msgbin = common.hex2bin(msg)
            cprlat = common.bin2int(msgbin[54:71]) / 131072.0
            cprlon = common.bin2int(msgbin[71:88]) / 131072.0
            v = adsb.surface_velocity(msg)
            _print("CPR format", "Odd" if oe else "Even")
            _print("CPR Latitude", cprlat)
            _print("CPR Longitude", cprlon)
            _print("Speed", v[0], "knots")
            _print("Track", v[1], "degrees")

        if 9 <= tc <= 18:  # airborne position
            _print("Type", "Airborne position (with barometric altitude)")
            alt = adsb.altitude(msg)
            oe = adsb.oe_flag(msg)
            msgbin = common.hex2bin(msg)
            cprlat = common.bin2int(msgbin[54:71]) / 131072.0
            cprlon = common.bin2int(msgbin[71:88]) / 131072.0
            _print("CPR format", "Odd" if oe else "Even")
            _print("CPR Latitude", cprlat)
            _print("CPR Longitude", cprlon)
            _print("Altitude", alt, "feet")

        if tc == 19:
            _print("Type", "Airborne velocity")
            velocity = adsb.velocity(msg)
            if velocity is not None:
                spd, trk, vr, t = velocity
                types = {"GS": "Ground speed", "TAS": "True airspeed"}
                _print("Speed", spd, "knots")
                _print("Track", trk, "degrees")
                _print("Vertical rate", vr, "feet/minute")
                _print("Type", types[t])

        if 20 <= tc <= 22:  # airborne position
            _print("Type", "Airborne position (with GNSS altitude)")
            alt = adsb.altitude(msg)
            oe = adsb.oe_flag(msg)
            msgbin = common.hex2bin(msg)
            cprlat = common.bin2int(msgbin[54:71]) / 131072.0
            cprlon = common.bin2int(msgbin[71:88]) / 131072.0
            _print("CPR format", "Odd" if oe else "Even")
            _print("CPR Latitude", cprlat)
            _print("CPR Longitude", cprlon)
            _print("Altitude", alt, "feet")

        if tc == 29:  # target state and status
            _print("Type", "Target State and Status")
            subtype = common.bin2int((common.hex2bin(msg)[32:])[5:7])
            _print("Subtype", subtype)
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
                _print("Target altitude", alt, "feet")
                _print("Altitude source", alt_source)
                _print("Altitude reference", alt_ref)
                _print("Angle", angle, "°")
                _print("Angle Type", angle_type)
                _print("Angle Source", angle_source)
                if vertical_mode is not None:
                    _print(
                        "Vertical mode",
                        vertical_horizontal_types[vertical_mode],
                    )
                if horizontal_mode is not None:
                    _print(
                        "Horizontal mode",
                        vertical_horizontal_types[horizontal_mode],
                    )
                _print(
                    "TCAS/ACAS",
                    tcas_operational_types[tcas_operational]
                    if tcas_operational
                    else None,
                )
                _print("TCAS/ACAS RA", tcas_ra_types[tcas_ra])
                _print("Emergency status", emergency_types[emergency_status])
            else:
                alt, alt_source = adsb.selected_altitude(msg)  # type: ignore
                baro = adsb.baro_pressure_setting(msg)
                hdg = adsb.selected_heading(msg)
                autopilot = adsb.autopilot(msg)
                vnav = adsb.vnav_mode(msg)
                alt_hold = adsb.altitude_hold_mode(msg)
                app = adsb.approach_mode(msg)
                lnav = adsb.lnav_mode(msg)
                _print("Selected altitude", alt, "feet")
                _print("Altitude source", alt_source)
                _print(
                    "Barometric pressure setting",
                    baro,
                    "" if baro is None else "millibars",
                )
                _print("Selected Heading", hdg, "°")
                if not (common.bin2int((common.hex2bin(msg)[32:])[46]) == 0):
                    _print(
                        "Autopilot", types_29[autopilot] if autopilot else None
                    )
                    _print("VNAV mode", types_29[vnav] if vnav else None)
                    _print(
                        "Altitude hold mode",
                        types_29[alt_hold] if alt_hold else None,
                    )
                    _print("Approach mode", types_29[app] if app else None)
                    _print(
                        "TCAS/ACAS",
                        tcas_operational_types[tcas_operational]
                        if tcas_operational
                        else None,
                    )
                    _print("LNAV mode", types_29[lnav] if lnav else None)

    if df == 20:
        _print("Protocol", "Mode-S Comm-B altitude reply")
        _print("Altitude", common.altcode(msg), "feet")

    if df == 21:
        _print("Protocol", "Mode-S Comm-B identity reply")
        _print("Squawk code", common.idcode(msg))

    if df == 20 or df == 21:
        labels = {
            "BDS10": "Data link capability",
            "BDS17": "GICB capability",
            "BDS20": "Aircraft identification",
            "BDS30": "ACAS resolution",
            "BDS40": "Vertical intention report",
            "BDS50": "Track and turn report",
            "BDS60": "Heading and speed report",
            "BDS44": "Meteorological routine air report",
            "BDS45": "Meteorological hazard report",
            "EMPTY": "[No information available]",
        }

        BDS = bds.infer(msg, mrar=True)
        if BDS is not None and BDS in labels.keys():
            _print("BDS", "%s (%s)" % (BDS, labels[BDS]))
        else:
            _print("BDS", BDS)

        if BDS == "BDS20":
            callsign = commb.cs20(msg)
            _print("Callsign", callsign)

        if BDS == "BDS40":
            _print("MCP target alt", commb.selalt40mcp(msg), "feet")
            _print("FMS Target alt", commb.selalt40fms(msg), "feet")
            _print("Pressure", commb.p40baro(msg), "millibar")

        if BDS == "BDS50":
            _print("Roll angle", commb.roll50(msg), "degrees")
            _print("Track angle", commb.trk50(msg), "degrees")
            _print("Track rate", commb.rtrk50(msg), "degree/second")
            _print("Ground speed", commb.gs50(msg), "knots")
            _print("True airspeed", commb.tas50(msg), "knots")

        if BDS == "BDS60":
            _print("Megnatic Heading", commb.hdg60(msg), "degrees")
            _print("Indicated airspeed", commb.ias60(msg), "knots")
            _print("Mach number", commb.mach60(msg))
            _print("Vertical rate (Baro)", commb.vr60baro(msg), "feet/minute")
            _print("Vertical rate (INS)", commb.vr60ins(msg), "feet/minute")

        if BDS == "BDS44":
            _print("Wind speed", commb.wind44(msg)[0], "knots")
            _print("Wind direction", commb.wind44(msg)[1], "degrees")
            _print("Temperature 1", commb.temp44(msg)[0], "Celsius")
            _print("Temperature 2", commb.temp44(msg)[1], "Celsius")
            _print("Pressure", commb.p44(msg), "hPa")
            _print("Humidity", commb.hum44(msg), "%")
            _print("Turbulence", commb.turb44(msg))

        if BDS == "BDS45":
            _print("Turbulence", commb.turb45(msg))
            _print("Wind shear", commb.ws45(msg))
            _print("Microbust", commb.mb45(msg))
            _print("Icing", commb.ic45(msg))
            _print("Wake vortex", commb.wv45(msg))
            _print("Temperature", commb.temp45(msg), "Celsius")
            _print("Pressure", commb.p45(msg), "hPa")
            _print("Radio height", commb.rh45(msg), "feet")
