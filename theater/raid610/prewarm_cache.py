#!/venv/main/bin/python3
"""prewarm_cache.py -- build the shared residue cache (pem_{zd}_{d}_{Q}.npy) ONCE before loops start.
360 loops np.save-ing the same file concurrently is a torn-file corruption; a pre-warmed read-only cache is not."""
import sys, os, numpy as np
sys.path.insert(0, os.path.expanduser("~/beacon/raid610"))
from resonance_map import primes_upto, primorial
Q = int(open(os.path.expanduser("~/beacon/raid610/Q.txt")).read().strip())
cache = os.path.expanduser("~/beacon/raid610/.sc_cache"); os.makedirs(cache, exist_ok=True)
f1 = os.path.join(cache, f"pem_1439_2310_{Q}.npy")
if not os.path.exists(f1):
    P_eff = primorial(1439) // 2310; prs = primes_upto(Q)
    np.save(f1 + ".part.npy", np.array([int(P_eff % int(p)) for p in prs], dtype=np.int64)); os.replace(f1 + ".part.npy", f1)
print(f"cache ready: {f1} ({os.path.getsize(f1)} bytes)")
