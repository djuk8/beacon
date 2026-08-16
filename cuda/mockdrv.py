import struct, sys, gmpy2
d = open(sys.argv[1], "rb").read()
m, b, c = struct.unpack("<IIQ", d[:16]); assert m == 0x31433247
nb = b // 8; off = 16; v = bytearray()
for _ in range(c):
    n = int.from_bytes(d[off:off + nb], "little"); off += nb
    v.append(1 if gmpy2.powmod(2, n - 1, n) == 1 else 0)
open(sys.argv[2], "wb").write(struct.pack("<IIQ", 0x31563247, b, c) + bytes(v))
