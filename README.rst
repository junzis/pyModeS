A Python Mode-S Decoder
=======================

Python library for Mode-S message decoding. Two separate methods are
implemented to decode the following messages:

-  Automatic Dependent Surveillance - Broadcast (ADS-B) (DF17)

   -  aircraft information that contains: ICAO address, position,
      altitude, velocity (ground speed), callsign, etc.

-  Mode-S Enhanced Surveillance (EHS) (DF20 and DF21)

   -  additional information in response to SSR interrogation, such as:
      true airspeed, indicated airspeed, mach number, track angle,
      heading, roll angle, etc.

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


Common function for Mode-S message:

.. code:: python

    pms.df(msg)                 # Downlink Format
    pms.crc(msg, encode=False)  # Perform CRC or generate parity bit

    pms.hex2bin(str)    # Convert hexadecimal string to binary string
    pms.bin2int(str)    # Convert binary string to integer
    pms.hex2int(str)    # Convert hexadecimal string to integer


Core functions for ADS-B decoding:

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


**Hint: When you have a fix position of the aircraft, it is convenient to
use `position_with_ref()` method to decode with only one position message
(either odd or even). This works with both airborne and surface position
messages. But the reference position shall be with in 180NM (airborne)
or 45NM (surface) of the true position.**

Core functions for EHS decoding:

.. code:: python

    pms.ehs.icao(msg)       # ICAO address
    pms.ehs.BDS(msg)        # Comm-B Data Selector Version

    # for BDS version 2,0
    pms.ehs.callsign(msg)   # Aircraft callsign

    # for BDS version 4,0
    pms.ehs.alt_mcp(msg)    # MCP/FCU selected altitude (ft)
    pms.ehs.alt_fms(msg)    # FMS selected altitude (ft)
    pms.ehs.alt_pbaro(msg)  # Barometric pressure (mb)

    # for BDS version 5,0
    pms.ehs.roll(msg)       # roll angle (deg)
    pms.ehs.track(msg)      # track angle (deg)
    pms.ehs.gs(msg)         # ground speed (kt)
    pms.ehs.rtrack(msg)     # track angle rate (deg/sec)
    pms.ehs.tas(msg)        # true airspeed (kt)

    # for BDS version 6,0
    pms.ehs.heading(msg)    # heading (deg)
    pms.ehs.ias(msg)        # indicated airspeed (kt)
    pms.ehs.mach(msg)       # MACH number
    pms.ehs.baro_vr(msg)    # barometric altitude rate (ft/min)
    pms.ehs.ins_vr(msg)     # inertial vertical speed (ft/min)

Developement
------------
To run tests, run the following commands:
```
$ tox
```
