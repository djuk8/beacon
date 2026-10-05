#!/venv/main/bin/python3
"""prewarm_cache.py -- build the shared residue cache (pem_{zd}_{d}_{Q}.npy) ONCE before loops start.
360 loops np.save-ing the same file concurrently is a torn-file corruption; a pre-warmed read-only cache is not."""
import sys, os, numpy as np
sys.path.insert(0, os.path.expanduser("~/beacon/raid610"))
from resonance_map import primes_upto, primorial
import venue as _venue; _V = _venue.load(); ZD, D = _V["zd"], _V["d"]
Q = int(open(os.path.expanduser("~/beacon/raid610/Q.txt")).read().strip())
cache = os.path.expanduser("~/beacon/raid610/.sc_cache"); os.makedirs(cache, exist_ok=True)
f1 = os.path.join(cache, f"pem_{ZD}_{D}_{Q}.npy")
if not os.path.exists(f1):
    P_eff = primorial(ZD) // D; prs = primes_upto(Q)
    np.save(f1 + ".part.npy", np.array([int(P_eff % int(p)) for p in prs], dtype=np.int64)); os.replace(f1 + ".part.npy", f1)
dq = 0
try: dq = int(open(os.path.expanduser("~/beacon/raid610/DEEPQ.txt")).read().strip())
except Exception: pass
if dq > Q:
    from deep_primes import primes_range
    qd = primes_range(Q, dq, cache)
    f2 = os.path.join(cache, f"pemd_{ZD}_{D}_{dq}.npy")
    if dq >= 2 ** 31 and not os.path.exists(os.path.join(cache, f"pemd64_{ZD}_{D}_{dq}.npy")):     # deep: int64 table directly (residues exceed int32)
        f3 = os.path.join(cache, f"pemd64_{ZD}_{D}_{dq}.npy")
        mm = np.lib.format.open_memmap(f3 + ".part.npy", mode="w+", dtype=np.int64, shape=(len(qd),))
        Pf = primorial(ZD) // D; B = 4_000_000
        for i in range(0, len(qd), B): mm[i:i+len(qd[i:i+B])] = [int(Pf % int(x)) for x in qd[i:i+B].tolist()]
        mm.flush(); del mm; os.replace(f3 + ".part.npy", f3)
    if dq < 2 ** 31 and not os.path.exists(f2):
        mm = np.lib.format.open_memmap(f2 + ".part.npy", mode="w+", dtype=np.int32, shape=(len(qd),))
        Pf = primorial(ZD) // D; B = 4_000_000
        for i in range(0, len(qd), B):
            mm[i:i+len(qd[i:i+B])] = [int(Pf % int(x)) for x in qd[i:i+B].tolist()]
        mm.flush(); del mm; os.replace(f2 + ".part.npy", f2)
    f3 = os.path.join(cache, f"pemd64_{ZD}_{D}_{dq}.npy")                     # int64 twin (zero-copy in makes; v8.5)
    if not os.path.exists(f3) and os.path.exists(f2):
        src = np.load(f2, mmap_mode="r")
        mm = np.lib.format.open_memmap(f3 + ".part.npy", mode="w+", dtype=np.int64, shape=(len(qd),))
        B = 8_000_000
        for i in range(0, len(qd), B): mm[i:i+B] = src[i:i+B]
        mm.flush(); del mm; os.replace(f3 + ".part.npy", f3)
    print(f"deep cache ready: {len(qd):,} band primes + pemd + pemd64")
print(f"cache ready: {f1} ({os.path.getsize(f1)} bytes)")
