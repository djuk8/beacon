"""deep_primes.py -- self-contained primes_range fallback for the O3 deep band (kit ships this;
the repo's deepsieve.py provides the same API). Caches qd_{lo}_{hi}.npy next to the pem caches."""
import os, numpy as np
def primes_range(lo, hi, cache=".sc_cache"):
    os.makedirs(cache, exist_ok=True)
    f = os.path.join(cache, f"qd_{lo}_{hi}.npy")
    if os.path.exists(f): return np.load(f, mmap_mode="r")
    n = int(hi); sv = np.ones(n // 2, dtype=bool); sv[0] = False        # odds: i -> 2i+1
    for i in range(1, int(n ** 0.5) // 2 + 1):
        p = 2 * i + 1
        if sv[i]: sv[p * p // 2::p] = False
    odds = 2 * np.nonzero(sv)[0] + 1
    qd = odds[odds > lo].astype(np.int64)
    np.save(f + ".part.npy", qd); os.replace(f + ".part.npy", f)
    return np.load(f, mmap_mode="r")
