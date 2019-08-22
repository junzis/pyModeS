The Python ADS-B/Mode-S Decoder
===============================

If you find this project useful for your research, please cite our work (bibtex format):

::

  @article{sun2019pymodes,
      author={J. {Sun} and H. {V\^u} and J. {Ellerbroek} and J. M. {Hoekstra}},
      journal={IEEE Transactions on Intelligent Transportation Systems},
      title={pyModeS: Decoding Mode-S Surveillance Data for Open Air Transportation Research},
      year={2019},
      doi={10.1109/TITS.2019.2914770},
      ISSN={1524-9050},
  }



Introduction
---------------------
PyModeS is a Python library designed to decode Mode-S (including ADS-B) message.
Message with following Downlink Formats (DF) are supported:


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
- BDS 3,0: ACAS active resolution advisory
- BDS 4,0: Selected vertical intention
- BDS 4,4: Meteorological routine air report (experimental)
- BDS 4,5: Meteorological hazard report (experimental)
- BDS 5,0: Track and turn report
- BDS 6,0: Heading and speed report


**DF4 / DF20: Altitude code**

**DF5 / DF21: Identity code (squawk code)**


Resources
-----------
Checkout and contribute to this open-source project at:
https://github.com/junzis/pyModeS

Detailed manual on Mode-S decoding is published at:
https://mode-s.org/decode.

API documentation of pyModeS is at:
http://pymodes.readthedocs.io



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

  modeslive --source tcp --server [server_address] --port [tcp_port] \
    --rawtype [beast,avr,skysense] --latlon [lat] [lon]  --dumpto [folder]

  Arguments:
    -h, --help           show this help message and exit
    --source SOURCE      data source: rtlsdr or tcp
    --server SERVER      server address or IP
    --port PORT          raw data port
    --rawtype RAWTYPE    TCP data format: beast, avr or skysense
    --latlon LAT LON     receiver position
    --show-uncertainty   display uncertaint values, default off
    --dumpto             folder to dump decoded output


[experimental] If you have a RTL-SDR receiver, you can connect it directly to pyModeS:

::

  $ modeslive --source rtlsdr --latlon [lat] [lon]

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

  # BDS 4,0
  pms.commb.selalt40mcp(msg)   # MCP/FCU selected altitude (ft)
  pms.commb.selalt40fms(msg)   # FMS selected altitude (ft)
  pms.commb.p40baro(msg)    # Barometric pressure (mb)

  # BDS 5,0
  pms.commb.roll50(msg)     # Roll angle (deg)
  pms.commb.trk50(msg)      # True track angle (deg)
  pms.commb.gs50(msg)       # Ground speed (kt)
  pms.commb.rtrk50(msg)     # Track angle rate (deg/sec)
  pms.commb.tas50(msg)      # True airspeed (kt)

  # BDS 6,0
  pms.commb.hdg60(msg)      # Magnetic heading (deg)
  pms.commb.ias60(msg)      # Indicated airspeed (kt)
  pms.commb.mach60(msg)     # Mach number (-)
  pms.commb.vr60baro(msg)   # Barometric altitude rate (ft/min)
  pms.commb.vr60ins(msg)    # Inertial vertical speed (ft/min)


Meteorological routine air report (MRAR) [Experimental]
********************************************************

.. code:: python

  # BDS 4,4
  pms.commb.wind44(msg)     # Wind speed (kt) and direction (true) (deg)
  pms.commb.temp44(msg)     # Static air temperature (C)
  pms.commb.p44(msg)        # Average static pressure (hPa)
  pms.commb.hum44(msg)      # Humidity (%)


Meteorological hazard air report (MHR) [Experimental]
*******************************************************

.. code:: python

  # BDS 4,5
  pms.commb.turb45(msg)     # Turbulence level (0-3)
  pms.commb.ws45(msg)       # Wind shear level (0-3)
  pms.commb.mb45(msg)       # Microburst level (0-3)
  pms.commb.ic45(msg)       # Icing level (0-3)
  pms.commb.wv45(msg)       # Wake vortex level (0-3)
  pms.commb.temp45(msg)     # Static air temperature (C)
  pms.commb.p45(msg)        # Average static pressure (hPa)
  pms.commb.rh45(msg)       # Radio height (ft)



Customize the streaming module
******************************
The TCP client module from pyModeS can be re-used to stream and process Mode-S
data as your like. You need to re-implement the ``handle_messages()`` function from
the ``BaseClient`` class to write your own logic to handle the messages.

Here is an example:

.. code:: python

  from pyModeS.extra.tcpclient import BaseClient

  # define your custom class by extending the BaseClient
  #   - implement your handle_messages() methods
  class ADSBClient(BaseClient):
      def __init__(self, host, port, rawtype):
          super(ModesClient, self).__init__(host, port, rawtype)

      def handle_messages(self, messages):
          for msg, ts in messages:
              if len(msg) < 28:           # wrong data length
                  continue

              df = pms.df(msg)

              if df != 17:                # not ADSB
                  continue

              if '1' in pms.crc(msg):     # CRC fail
                  continue

              icao = pms.adsb.icao(msg)
              tc = pms.adsb.typecode(msg)

              # TODO: write you magic code here
              print ts, icao, tc, msg

  # run new client, change the host, port, and rawtype if needed
  client = ADSBClient(host='127.0.0.1', port=30334, rawtype='beast')
  client.run()


Unit test
---------
To perform unit tests. First install ``tox`` through pip, Then, run the following commands:

.. code:: bash

  $ tox
