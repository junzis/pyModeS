from pyModeS import common
"""
Decoding all call replies DF=11
"""

def interrogator_code(msg):
    if common.df(msg) == 11:  # check that the msg is DF11
        '''Returns the IP code of the Mode S all-call reply (DF11)'''
        binaryraw=common.hex2bin(msg)
        PI=binaryraw[-24:]
        DATA=binaryraw[:-24]

        Gx='1111111111111010000001001000'
        Mx=DATA[::-1].zfill(len(DATA)+24)[::-1]
        initialdifference=len(Mx)-len(Gx)
        Gx = Gx[::-1].zfill(len(Mx))[::-1]
        while len(Mx)>initialdifference:
            MSB=Mx[0]
            if MSB=='1':
                result=int(Mx,2)^int(Gx,2)
                Mx = str(bin(result)[2:])
                Gx = Gx.rstrip('0')[::-1].zfill(len(Mx))[::-1]

            else: #If the Mx starts with a 0
                Mx=Mx[1:]
                Gx=Gx[:-1]

        SIcode=bin(int(Mx,2)^int(PI,2)).zfill(7) #Mx is the parity sequence and PI is the last field of the DF11.
        if int(SIcode[0:3],2)>0:
            return str("SI" + str(int(SIcode[3:],2)))
        else:
            return str("II" + str(int(SIcode,2)))
    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def flight_status(msg):
    '''returns the flight status'''
    if common.df(msg) == 11:  # check that the msg is DF11
        binaryraw=common.hex2bin(msg)
        CA = (int(binaryraw[5:8],2))
        if CA in [0, 1, 2, 3, 6, 7]: #reserved
            return None
        if CA == 4:#level 2 transponder, ability to set CA to 7 and on ground
            return "on ground"
        if CA == 5:#level 2 transponder, ability to set CA to 7 and airborn
            return "airborne"
    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def transponder_level(msg):
    '''returns the transponder level'''
    if common.df(msg) == 11:#check that the msg is DF11
        binaryraw=common.hex2bin(msg)
        CA = (int(binaryraw[5:8],2))
        if CA in [1, 2, 3, 4, 5, 6, 7]: #reserved
            return 2
        if CA == 0:
            return 1
    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def capability(msg):
    '''return the capability code'''
    if common.df(msg) == 11:#check that the msg is DF11
        binaryraw=common.hex2bin(msg)
        CA = (int(binaryraw[5:8],2))
        if CA == 0: #level 1 transponder
            return 0
        if CA in [1, 2,  3]: #reserved
            return None
        if CA == 4:#level 2 transponder, ability to set CA to 7 and on ground
            return 4
        if CA == 5:#level 2 transponder, ability to set CA to 7 and airborn
            return 5
        if CA == 6:#level 2 transponder, ability to set CA to 7 and either airborn on ground
            return 6
        if CA == 7:# (either DR field is 0 or FS field is 2,3,4 or 5), and either airborn on ground
            return 7
    else:
        raise RuntimeError("Incorrect or inconsistent message types")

def AA(msg):
    '''returns the icao code of the aircraft'''
    if common.df(msg) == 11:  # check that the msg is DF11
        return (msg[2:8])
    else:
        raise RuntimeError("Incorrect or inconsistent message types")
