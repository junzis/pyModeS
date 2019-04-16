"""Comm-B Wrapper.

The Comm-B wrapper imports all functions from the following modules:

**ELS - elementary surveillance**
    - pyModeS.decoder.bds.bds10
    - pyModeS.decoder.bds.bds17
    - pyModeS.decoder.bds.bds20
    - pyModeS.decoder.bds.bds30

**EHS - enhanced surveillance**
    - pyModeS.decoder.bds.bds40
    - pyModeS.decoder.bds.bds50
    - pyModeS.decoder.bds.bds60

**MRAR and MHR**
    - pyModeS.decoder.bds.bds44
    - pyModeS.decoder.bds.bds45

"""

from __future__ import absolute_import, print_function, division

# ELS - elementary surveillance
from pyModeS.decoder.bds.bds10 import *
from pyModeS.decoder.bds.bds17 import *
from pyModeS.decoder.bds.bds20 import *
from pyModeS.decoder.bds.bds30 import *

# ELS - enhanced surveillance
from pyModeS.decoder.bds.bds40 import *
from pyModeS.decoder.bds.bds50 import *
from pyModeS.decoder.bds.bds60 import *

# MRAR and MHR
from pyModeS.decoder.bds.bds44 import *
from pyModeS.decoder.bds.bds45 import *
