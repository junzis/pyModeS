
cdef extern from "core.h":
    void make_key(int*, long time, long address)
    void btea(int*, int, int*)