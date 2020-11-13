from pyModeS import common

"""
Warpper for short roll call surveillance replies DF=4/5
"""
def fs(msg):
    '''tell the flight status of the aircraft, returns airborne, ground or None'''
    if common.df(msg) in [4,5]:
        binaryraw=common.hex2bin(msg)
        fs=int(binaryraw[5:8],2)
        if fs in [0,2]:
            return "airborne"
        if fs in [1,3]:
            return "ground"
        else:
            return None
    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def alert(msg):
    '''returns True if there is an alert, False otherwise '''
    #The alert indicates that the TXPPR Mode A code is changed manually by the pilot. Icao Annex10, Vol IV, 3.1.2.6.10.1.1
    if common.df(msg) in [4,5]:
        binaryraw = common.hex2bin(msg)
        fs = int(binaryraw[5:8], 2)
        if fs in [2,3,4]:
            return True
        if fs in [0,1,5]:
            return False
        else:
            return None
    else:
        raise RuntimeError("Incorrect or inconsistent message types")


def SPI(msg):
    '''returns True if there there is Special Pulse Indicator, False otherwise '''
    if common.df(msg) in [4, 5]:
        binaryraw = common.hex2bin(msg)
        fs = int(binaryraw[5:8], 2)
        if fs in [4, 5]:
            return True
        if fs in [0, 1, 2, 3]:
            return False
        else:
            return None
    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def dr(msg):
    '''Returns Downlink Request Status.
     Args:
        msg (str): 14 hexdigits string,
    Returns:
        str: Downlink Request Status
    '''
    if common.df(msg) in [4,5]:
        binaryraw = common.hex2bin(msg)
        dr = int(binaryraw[8:13], 2)
        if dr in [2,3,6,7]:
            return "ACAS"
        if dr == 0:
            return "no downlink request"
        if dr == 1:
            return "request to send Comm-B message"
        if dr in 4:
            return "Comm-B broadcast 1 available"
        if dr in 5:
            return "Comm-B broadcast 2 available"
        if dr > 7 and dr < 16:
            return None
        else:
            return str(15-dr)+" downlink ELM segments available"
    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def um(msg):
    '''returns the Interrogator Identifier and the type of reservation
    Args:
        msg (str): 14 hexdigits string,
    Returns:
        int: II code of the identifier that triggered the reply
        str: type of reservation made by the interrogator
    '''
    if common.df(msg) in [4,5]:
        binaryraw = common.hex2bin(msg)
        iis = int(binaryraw[13:17], 2)
        ds = int(binaryraw[17:19], 2)
        if ds == 0:
            ds=None
        if ds == 1:
            ds='Comm-B'
        if ds == 2:
            ds='Comm-C'
        if ds == 3:
            ds='Comm-D'
        return iis, ds

    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def ac(msg):
    '''return the altitude in ft'''
    if common.df(msg) == 4:
        binaryraw = common.hex2bin(msg)
        altcode = binaryraw[19:32] # Here we could also put the common.altcode(msg).
        return common.altitude(altcode)
    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def id(msg):
    '''return the squawk code (identifier)'''
    if common.df(msg) == 5:
        binaryraw = common.hex2bin(msg)
        altcode = binaryraw[19:32]  # Here we could also put the common.idcode(msg).
        return common.squawk(altcode)
    else:
        raise RuntimeError("Incorrect or inconsistent message types")
    
