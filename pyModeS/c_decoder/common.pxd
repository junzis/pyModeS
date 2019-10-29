# cython: language_level=3

cdef int char_to_int(unsigned char binstr)
cdef unsigned char int_to_char(unsigned char i)

cpdef bytearray hex2bin(bytes hexstr)
cpdef long bin2int(bytearray binstr)
cpdef long hex2int(bytearray binstr)

cpdef unsigned char df(bytes msg)
cpdef long crc(bytes msg, bint encode=*)

cpdef long floor(double x)
cpdef str icao(bytes msg)
cpdef bint is_icao_assigned(bytes icao)

cpdef int typecode(bytes msg)
cpdef int cprNL(double lat)
cpdef str idcode(bytes msg)
cpdef int altcode(bytes msg)

cdef bytes data(bytes msg)
cpdef bint allzeros(bytes msg)
