The Python ADS-B/Mode-S Decoder
==========================================

Python library for ADS-B/Mode-S message decoding. Supported Downlink Formats (DF) are:

**DF17 / DF18: Automatic Dependent Surveillance - Broadcast (ADS-B)**

- TC=1-4  / BDS 0,8: Aircraft identification and category
- TC=5-8  / BDS 0,6: Surface position
- TC=9-18 / BDS 0,5: Airborne position
- TC=19   / BDS 0,9: Airborne velocity
- TC=28   / BDS 6,1: Airborne status [to be implemented]
- TC=29   / BDS 6,2: Target state and status information [to be implemented]
- TC=31   / BDS 6,5: Aircraft operational status [to be implemented]


**DF20 / DF21: Mode-S Comm-B replies**

- BDS 1,0: Data link capability report
- BDS 1,7: Common usage GICB capability report
- BDS 2,0: Aircraft identification
- BDS 2,1: Aircraft and airline registration markings
- BDS 3,0: ACAS active resolution advisory
- BDS 4,0: Selected vertical intention
- BDS 4,4: Meteorological routine air report
- BDS 5,0: Track and turn report
- BDS 5,3: Air-referenced state vector
- BDS 6,0: Heading and speed report


**DF4 / DF20: Altitude code**

**DF5 / DF21: Identity code (squawk code)**

Detailed manual on Mode-S decoding is published by the author, at:
https://mode-s.org/decode


New features in v2.0
---------------------
- New structure of the libraries
- ADS-B and Comm-B data streaming
- Active aircraft viewing (terminal curses)
- Improved BDS identification
- Optimizing decoding speed


Source code
-----------
Checkout and contribute to this open-source project at:
https://github.com/junzis/pyModeS

API documentation at:
http://pymodes.readthedocs.io
[To be updated]


Install
-------

To install latest version from the GitHub:

::

  pip install git+https://github.com/junzis/pyModeS


To install the stable version (2.0) from pip:

::

  pip install pyModeS



Live view traffic (modeslive)
----------------------------------------------------
Supports **Mode-S Beast** and **AVR** raw stream

::

  modeslive --server [server_address] --port [tcp_port] --rawtype [beast,avr,skysense] --latlon [lat] [lon]  --dumpto [folder]

  Arguments:
    -h, --help           show this help message and exit
    --server SERVER      server address or IP
    --port PORT          raw data port
    --rawtype RAWTYPE    beast, avr or skysense
    --latlon LAT LON     receiver position
    --show-uncertainty   display uncertaint values, default off
    --dumpto             folder to dump decoded output


If you have a RTL-SDR receiver or Mode-S Beast, use modesmixer2 (http://xdeco.org/?page_id=48) to create raw beast TCP stream:

::

  $ modesmixer2 --inSeriel port[:speed[:flow_control]] --outServer beast:[tcp_port]

Example screenshot:

.. image:: https://github.com/junzis/pyModeS/raw/master/doc/modeslive-screenshot.png
   :width: 700px

Use the library
---------------

.. code:: python

  import pyModeS as pms


Common functions
*****************

.. code:: python

  pms.df(msg)                 # Downlink Format
  pms.icao(msg)               # Infer the ICAO address from the message
  pms.crc(msg, encode=False)  # Perform CRC or generate parity bit

  pms.hex2bin(str)      # Convert hexadecimal string to binary string
  pms.bin2int(str)      # Convert binary string to integer
  pms.hex2int(str)      # Convert hexadecimal string to integer
  pms.gray2int(str)     # Convert grey code to interger


Core functions for ADS-B decoding
*********************************

.. code:: python

  pms.adsb.icao(msg)
  pms.adsb.typecode(msg)

  # Typecode 1-4
  pms.adsb.callsign(msg)

  # Typecode 5-8 (surface), 9-18 (airborne, barometric height), and 9-18 (airborne, GNSS height)
  pms.adsb.position(msg_even, msg_odd, t_even, t_odd, lat_ref=None, lon_ref=None)
  pms.adsb.airborne_position(msg_even, msg_odd, t_even, t_odd)
  pms.adsb.surface_position(msg_even, msg_odd, t_even, t_odd, lat_ref, lon_ref)

  pms.adsb.position_with_ref(msg, lat_ref, lon_ref)
  pms.adsb.airborne_position_with_ref(msg, lat_ref, lon_ref)
  pms.adsb.surface_position_with_ref(msg, lat_ref, lon_ref)

  pms.adsb.altitude(msg)

  # Typecode: 19
  pms.adsb.velocity(msg)          # Handles both surface & airborne messages
  pms.adsb.speed_heading(msg)     # Handles both surface & airborne messages
  pms.adsb.surface_velocity(msg)
  pms.adsb.airborne_velocity(msg)


Note: When you have a fix position of the aircraft, it is convenient to
use `position_with_ref()` method to decode with only one position message
(either odd or even). This works with both airborne and surface position
messages. But the reference position shall be with in 180NM (airborne)
or 45NM (surface) of the true position.


Decode altitude replies in DF4 / DF20
**************************************
.. code:: python

  pms.common.altcode(msg)   # Downlink format must be 4 or 20


Decode identity replies in DF5 / DF21
**************************************
.. code:: python

  pms.common.idcode(msg)   # Downlink format must be 5 or 21



Common Mode-S functions
************************

.. code:: python

  pms.icao(msg)           # Infer the ICAO address from the message
  pms.bds.infer(msg)      # Infer the Modes-S BDS register

  # Check if BDS is 5,0 or 6,0, give reference speed, track, altitude (from ADS-B)
  pms.bds.is50or60(msg, spd_ref, trk_ref, alt_ref)

  # Check each BDS explicitly
  pms.bds.bds10.is10(msg)
  pms.bds.bds17.is17(msg)
  pms.bds.bds20.is20(msg)
  pms.bds.bds30.is30(msg)
  pms.bds.bds40.is40(msg)
  pms.bds.bds44.is44(msg)
  pms.bds.bds50.is50(msg)
  pms.bds.bds60.is60(msg)



Mode-S Elementary Surveillance (ELS)
*************************************

.. code:: python

  pms.commb.ovc10(msg)      # Overlay capability, BDS 1,0
  pms.commb.cap17(msg)      # GICB capability, BDS 1,7
  pms.commb.cs20(msg)       # Callsign, BDS 2,0


Mode-S Enhanced Surveillance (EHS)
***********************************

.. code:: python

  # For BDS register 4,0
  pms.commb.alt40mcp(msg)   # MCP/FCU selected altitude (ft)
  pms.commb.alt40fms(msg)   # FMS selected altitude (ft)
  pms.commb.p40baro(msg)    # Barometric pressure (mb)

  # For BDS register 5,0
  pms.commb.roll50(msg)     # Roll angle (deg)
  pms.commb.trk50(msg)      # True track angle (deg)
  pms.commb.gs50(msg)       # Ground speed (kt)
  pms.commb.rtrk50(msg)     # Track angle rate (deg/sec)
  pms.commb.tas50(msg)      # True airspeed (kt)

  # For BDS register 6,0
  pms.commb.hdg60(msg)      # Magnetic heading (deg)
  pms.commb.ias60(msg)      # Indicated airspeed (kt)
  pms.commb.mach60(msg)     # Mach number (-)
  pms.commb.vr60baro(msg)   # Barometric altitude rate (ft/min)
  pms.commb.vr60ins(msg)    # Inertial vertical speed (ft/min)


Meteorological routine air report (MRAR) [Experimental]
*******************************************************

.. code:: python

  # For BDS register 4,4
  pms.commb.wind44(msg, rev=False)  # Wind speed (kt) and direction (true) (deg)
  pms.commb.temp44(msg, rev=False)  # Static air temperature (C)
  pms.commb.p44(msg, rev=False)     # Average static pressure (hPa)
  pms.commb.hum44(msg, rev=False)   # Humidity (%)


Developement
------------
To perform unit tests. First install ``tox`` through pip, Then, run the following commands:

.. code:: bash

  $ tox
