The Python ADS-B/Mode-S Decoder
===============================

PyModeS is a Python library designed to decode Mode-S (including ADS-B) messages. It can be imported to your python project or used as a standalone tool to view and save live traffic data.

This is a project created by Junzi Sun, who works at `TU Delft <https://www.tudelft.nl/en/>`_, `Aerospace Engineering Faculty <https://www.tudelft.nl/en/ae/>`_, `CNS/ATM research group <http://cs.lr.tudelft.nl/atm/>`_. It is supported by many `contributors <https://github.com/junzis/pyModeS/graphs/contributors>`_ from different institutions.

Introduction
------------

pyModeS supports the decoding of following types of messages:

- DF4 / DF20: Altitude code
- DF5 / DF21: Identity code (squawk code)

- DF17 / DF18: Automatic Dependent Surveillance-Broadcast (ADS-B)

  - TC=1-4  / BDS 0,8: Aircraft identification and category
  - TC=5-8  / BDS 0,6: Surface position
  - TC=9-18 / BDS 0,5: Airborne position
  - TC=19   / BDS 0,9: Airborne velocity
  - TC=28   / BDS 6,1: Airborne status [to be implemented]
  - TC=29   / BDS 6,2: Target state and status information [to be implemented]
  - TC=31   / BDS 6,5: Aircraft operational status [to be implemented]

- DF20 / DF21: Mode-S Comm-B messages

  - BDS 1,0: Data link capability report
  - BDS 1,7: Common usage GICB capability report
  - BDS 2,0: Aircraft identification
  - BDS 3,0: ACAS active resolution advisory
  - BDS 4,0: Selected vertical intention
  - BDS 4,4: Meteorological routine air report (experimental)
  - BDS 4,5: Meteorological hazard report (experimental)
  - BDS 5,0: Track and turn report
  - BDS 6,0: Heading and speed report



If you find this project useful for your research, please considering cite this tool as::

  @article{sun2019pymodes,
      author={J. {Sun} and H. {V\^u} and J. {Ellerbroek} and J. M. {Hoekstra}},
      journal={IEEE Transactions on Intelligent Transportation Systems},
      title={pyModeS: Decoding Mode-S Surveillance Data for Open Air Transportation Research},
      year={2019},
      doi={10.1109/TITS.2019.2914770},
      ISSN={1524-9050},
  }




Resources
-----------
Check out and contribute to this open-source project at:
https://github.com/junzis/pyModeS

Detailed manual on Mode-S decoding is published at:
https://mode-s.org/decode

The API documentation of pyModeS is at:
https://mode-s.org/api



Basic installation
-------------------

Installation examples::

  # stable version
  pip install pyModeS

  # conda (compiled) version
  conda install -c conda-forge pymodes

  # development version
  pip install git+https://github.com/junzis/pyModeS


Dependencies ``numpy``, and ``pyzmq`` are installed automatically during previous installations processes. 

If you need to connect pyModeS to a RTL-SDR receiver, ``pyrtlsdr`` need to be installed manually::

  pip install pyrtlsdr


Advanced installation (using c modules)
------------------------------------------

If you want to make use of the (faster) c module, install ``pyModeS`` as follows::

  # conda (compiled) version
  conda install -c conda-forge pymodes

  # stable version
  pip install pyModeS

  # development version
  git clone https://github.com/junzis/pyModeS
  cd pyModeS
  poetry install -E rtlsdr


View live traffic (modeslive)
----------------------------------------------------

General usage::

  $ modeslive [-h] --source SOURCE [--connect SERVER PORT DATAYPE]
              [--latlon LAT LON] [--show-uncertainty] [--dumpto DUMPTO]

  arguments:
   -h, --help            show this help message and exit
   --source SOURCE       Choose data source, "rtlsdr" or "net"
   --connect SERVER PORT DATATYPE
                         Define server, port and data type. Supported data
                         types are: ['raw', 'beast', 'skysense']
   --latlon LAT LON      Receiver latitude and longitude, needed for the surface
                         position, default none
   --show-uncertainty    Display uncertainty values, default off
   --dumpto DUMPTO       Folder to dump decoded output, default none


Live with RTL-SDR
*******************

If you have an RTL-SDR receiver connected to your computer, you can use the ``rtlsdr`` source switch (require ``pyrtlsdr`` package), with command::

  $ modeslive --source rtlsdr


Live with network data
***************************

If you want to connect to a TCP server that broadcast raw data. use can use ``net`` source switch, for example::

  $ modeslive --source net --connect localhost 30002 raw
  $ modeslive --source net --connect 127.0.0.1 30005 beast



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
  pms.gray2int(str)     # Convert grey code to integer


Core functions for ADS-B decoding
*********************************

.. code:: python

  pms.adsb.icao(msg)
  pms.adsb.typecode(msg)

  # Typecode 1-4
  pms.adsb.callsign(msg)

  # Typecode 5-8 (surface), 9-18 (airborne, barometric height), and 20-22 (airborne, GNSS height)
  pms.adsb.position(msg_even, msg_odd, t_even, t_odd, lat_ref=None, lon_ref=None)
  pms.adsb.airborne_position(msg_even, msg_odd, t_even, t_odd)
  pms.adsb.surface_position(msg_even, msg_odd, t_even, t_odd, lat_ref, lon_ref)
  pms.adsb.surface_velocity(msg)

  pms.adsb.position_with_ref(msg, lat_ref, lon_ref)
  pms.adsb.airborne_position_with_ref(msg, lat_ref, lon_ref)
  pms.adsb.surface_position_with_ref(msg, lat_ref, lon_ref)

  pms.adsb.altitude(msg)

  # Typecode: 19
  pms.adsb.velocity(msg)          # Handles both surface & airborne messages
  pms.adsb.speed_heading(msg)     # Handles both surface & airborne messages
  pms.adsb.airborne_velocity(msg)


Note: When you have a fix position of the aircraft, it is convenient to use `position_with_ref()` method to decode with only one position message (either odd or even). This works with both airborne and surface position messages. But the reference position shall be within 180NM (airborne) or 45NM (surface) of the true position.


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


Meteorological reports [Experimental]
**************************************

To identify BDS 4,4 and 4,5 codes, you must set ``mrar`` argument to ``True`` in the ``infer()`` function:

.. code:: python

  pms.bds.infer(msg. mrar=True) 

Once the correct MRAR and MHR messages are identified, decode them as follows:


Meteorological routine air report (MRAR)
+++++++++++++++++++++++++++++++++++++++++

.. code:: python

  # BDS 4,4
  pms.commb.wind44(msg)     # Wind speed (kt) and direction (true) (deg)
  pms.commb.temp44(msg)     # Static air temperature (C)
  pms.commb.p44(msg)        # Average static pressure (hPa)
  pms.commb.hum44(msg)      # Humidity (%)


Meteorological hazard air report (MHR)
+++++++++++++++++++++++++++++++++++++++++

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
The TCP client module from pyModeS can be re-used to stream and process Mode-S data as you like. You need to re-implement the ``handle_messages()`` function from the ``TcpClient`` class to write your own logic to handle the messages.

Here is an example:

.. code:: python

  import pyModeS as pms
  from pyModeS.extra.tcpclient import TcpClient

  # define your custom class by extending the TcpClient
  #   - implement your handle_messages() methods
  class ADSBClient(TcpClient):
      def __init__(self, host, port, rawtype):
          super(ADSBClient, self).__init__(host, port, rawtype)

      def handle_messages(self, messages):
          for msg, ts in messages:
              if len(msg) != 28:  # wrong data length
                  continue

              df = pms.df(msg)

              if df != 17:  # not ADSB
                  continue

              if pms.crc(msg) !=0:  # CRC fail
                  continue

              icao = pms.adsb.icao(msg)
              tc = pms.adsb.typecode(msg)

              # TODO: write you magic code here
              print(ts, icao, tc, msg)

  # run new client, change the host, port, and rawtype if needed
  client = ADSBClient(host='127.0.0.1', port=30005, rawtype='beast')
  client.run()


Unit test
---------

.. code:: bash

  uv sync --dev --all-extras
  uv run pytest
