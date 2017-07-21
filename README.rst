A Python Mode-S Decoder
=======================

Python library for Mode-S message decoding. Two separate methods are
implemented to decode the following messages:

-  Automatic Dependent Surveillance - Broadcast (ADS-B) (DF17)

   -  aircraft information that contains: ICAO address, position, altitude, velocity (ground speed), callsign, etc.

-  Mode-S Elementary Surveillance (ELS) (DF4 and DF5).

   - DF4: Altitude
   - DF5: Squawk code

-  Mode-S Enhanced Surveillance (EHS) (DF20 and DF21). Additional information in response to SSR interrogation, such as: true airspeed, indicated airspeed, mach number, wind, temperature, etc.

   - DF20: Altitude
   - DF21: Squawk code
   - BDS 2,0   Aircraft identification
   - BDS 2,1   Aircraft and airline registration markings
   - BDS 4,0   Selected vertical intention
   - BDS 4,4   Meteorological routine air report
   - BDS 5,0   Track and turn report
   - BDS 5,3   Air-referenced state vector
   - BDS 6,0   Heading and speed report

A detailed manual on Mode-S decoding is published by the author, at:
http://adsb-decode-guide.readthedocs.io


Source code
-----------
Checkout and contribute to this open source project at:
https://github.com/junzis/pyModeS

API documentation at:
http://pymodes.readthedocs.io

Install
-------

Checkout source code, or install using pip:

::

    pip install pyModeS

Usage
-----

.. code:: python

    import pyModeS as pms


Common functions:
*****************

.. code:: python

    pms.df(msg)                 # Downlink Format
    pms.crc(msg, encode=False)  # Perform CRC or generate parity bit

    pms.hex2bin(str)    # Convert hexadecimal string to binary string
    pms.bin2int(str)    # Convert binary string to integer
    pms.hex2int(str)    # Convert hexadecimal string to integer

    pms.bin2gray(str)    # Convert binary string to grey code
    pms.gray2bin(str)    # Convert grey code to binary string


Core functions for ADS-B decoding:
**********************************

.. code:: python

    pms.adsb.icao(msg)
    pms.adsb.callsign(msg)

    pms.adsb.position(msg_even, msg_odd, t_even, t_odd, lat_ref=None, lon_ref=None)
    pms.adsb.airborne_position(msg_even, msg_odd, t_even, t_odd)
    pms.adsb.surface_position(msg_even, msg_odd, t_even, t_odd, lat_ref, lon_ref)

    pms.adsb.position_with_ref(msg, lat_ref, lon_ref)
    pms.adsb.airborne_position_with_ref(msg, lat_ref, lon_ref)
    pms.adsb.surface_position_with_ref(msg, lat_ref, lon_ref)

    pms.adsb.altitude(msg)

    pms.adsb.velocity(msg)          # handles both surface & airborne messages
    pms.adsb.speed_heading(msg)     # handles both surface & airborne messages
    pms.adsb.surface_velocity(msg)
    pms.adsb.airborne_velocity(msg)


Hint: When you have a fix position of the aircraft, it is convenient to
use `position_with_ref()` method to decode with only one position message
(either odd or even). This works with both airborne and surface position
messages. But the reference position shall be with in 180NM (airborne)
or 45NM (surface) of the true position.

Core functions for ELS decoding:
********************************

.. code:: python

    pms.els.icao(msg)       # ICAO address
    pms.els.df4alt(msg)     # Altitude from any DF4 message
    pms.ehs.df5id(msg)     # Squawk code from any DF5 message


Core functions for EHS decoding:
********************************

.. code:: python

    pms.ehs.icao(msg)       # ICAO address
    pms.ehs.df20alt(msg)    # Altitude from any DF20 message
    pms.ehs.df21id(msg)     # Squawk code from any DF21 message

    pms.ehs.BDS(msg)        # Comm-B Data Selector Version

    # for BDS version 2,0
    pms.ehs.isBDS20(msg)    # Check if message is BDS 2,0
    pms.ehs.callsign(msg)   # Aircraft callsign

    # for BDS version 4,0
    pms.ehs.isBDS40(msg)    # Check if message is BDS 4,0
    pms.ehs.alt40mcp(msg)   # MCP/FCU selected altitude (ft)
    pms.ehs.alt40fms(msg)   # FMS selected altitude (ft)
    pms.ehs.p40baro(msg)    # Barometric pressure (mb)

    # for BDS version 4,4
    pms.ehs.isBDS44(msg, rev=False) # Check if message is BDS 4,4
    pms.ehs.wind44(msg, rev=False)  # wind speed (kt) and heading (deg)
    pms.ehs.temp44(msg, rev=False)  # temperature (C)
    pms.ehs.p44(msg, rev=False)     # pressure (hPa)
    pms.ehs.hum44(msg, rev=False)   # humidity (%)

    # for BDS version 5,0
    pms.ehs.isBDS50(msg)    # Check if message is BDS 5,0
    pms.ehs.roll50(msg)     # roll angle (deg)
    pms.ehs.trk50(msg)      # track angle (deg)
    pms.ehs.gs50(msg)       # ground speed (kt)
    pms.ehs.rtrk50(msg)     # track angle rate (deg/sec)
    pms.ehs.tas50(msg)      # true airspeed (kt)

    # for BDS version 5,3
    pms.ehs.isBDS53(msg)    # Check if message is BDS 5,3
    pms.ehs.hdg53(msg)      # magnetic heading (deg)
    pms.ehs.ias53(msg)      # indicated airspeed (kt)
    pms.ehs.mach53(msg)     # MACH number
    pms.ehs.tas53(msg)      # true airspeed (kt)
    pms.ehs.vr53(msg)       # vertical rate (fpm)

    # for BDS version 6,0
    pms.ehs.isBDS60(msg)    # Check if message is BDS 6,0
    pms.ehs.hdg60(msg)      # heading (deg)
    pms.ehs.ias60(msg)      # indicated airspeed (kt)
    pms.ehs.mach60(msg)     # MACH number
    pms.ehs.vr60baro(msg)   # barometric altitude rate (ft/min)
    pms.ehs.vr60ins(msg)    # inertial vertical speed (ft/min)

Developement
------------
To run tests, run the following commands:
```
$ tox
```
