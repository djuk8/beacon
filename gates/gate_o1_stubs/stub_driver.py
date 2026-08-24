#!/usr/bin/env python3
"""STUB -- for dry-running gate_o1.sh on a box without a GPU (shredder, sandbox).
NOT the driver.  Emulates g1_fermat_v2's FILE CONTRACT only:
  in : <IIQ>(MAGIC_C, bits, n) + n candidates, little-endian, bits/8 bytes each
  out: <IIQ>(MAGIC_V, bits, n) + n verdict bytes  (0 composite, 1 PRP)
Verdicts come from gmpy2.is_prime (stronger than Fermat-2; differs only on
base-2 pseudoprimes, absent from the harness vectors)."""
import sys, struct, gmpy2, time
MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
mg, bits, n = struct.unpack("<IIQ", b[:16])
if mg != MAGIC_C: sys.stderr.write(f"bad magic 0x{mg:08x}\n"); sys.exit(3)
nb = bits // 8; body = b[16:]
if len(body) != n * nb: sys.stderr.write("length mismatch\n"); sys.exit(3)
t0 = time.time(); out = bytearray(n)
for i in range(n):
    x = int.from_bytes(body[i*nb:(i+1)*nb], "little")
    out[i] = 1 if gmpy2.is_prime(x, 2) else 0
dt = max(time.time() - t0, 1e-6)
sys.stderr.write(f"g1_fermat[STUB]: bits={bits} count={n} repeat=1 | {dt:.3f}s | {n/dt:.1f} tests/s | prp={sum(out)} gec_alarm=0\n")
with open(dst, "wb") as f:
    f.write(struct.pack("<IIQ", MAGIC_V, bits, n)); f.write(bytes(out))
