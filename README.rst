A Python Mode-S Decoder
=======================

Python library for Mode-S message decoding. Two seprate methods are
develop to decode the following messages:

-  Automatic Dependent Surveillance - Broadcast (ADS-B) (DF17)

   -  aircraft infomation that cotains: icao address, position,
      altitude, velocity (ground speed), and callsign, etc.

-  Mode-S Enhanced Surveillance (EHS) (DF20 and DF21)

   -  additional information in response to SSR interogation, such as:
      true airspeed, indicated airspeed, mach number, track angle,
      heading, and roll angle, etc.

A detailed manuel on Mode-S decoding is published by the author, at:  
http://adsb-decode-guide.readthedocs.org


Source code
-----------
Checkourt and contribute to this open source project at:   
https://github.com/junzis/pyModeS


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
    pms.adsb.position(msg_even, msg_odd, t_even, t_odd)
    pms.adsb.position_with_ref(msg, lat_ref, lon_ref)
    pms.adsb.altitude(msg)
    pms.adsb.velocity(msg)
    pms.adsb.speed_heading(msg)

**Hint: When you have a fix position of the aircraft or you know the
location of your receiver, it is convinent to use `position_with_ref()` method
to decode with only one position message (either odd or even)**

Core functions for EHS decoding:

.. code:: python

    pms.ehs.icao(msg)       # icao address
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

Some helper functions:

.. code:: python

    pms.df(msg)             # downlink format of a Mode-S message
    pms.hex2bin(msg)        # convert hexadecimal string to binary string
    pms.hex2int(msg)        # convert hexadecimal string to integer
    pms.bin2int(msg)        # convert binary string to integer
