def tell(msg: str) -> None:
    from pyModeS import common, adsb, commb, bds

    def _print(label, value, unit=None):
        print("%20s: " % label, end="")
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
        if 1 <= tc <= 4:  # callsign
            callsign = adsb.callsign(msg)
            _print("Type", "Identitification and category")
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
            spd, trk, vr, t = adsb.velocity(msg)
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
        if BDS in labels.keys():
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
