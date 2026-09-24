#!/usr/bin/env python3
"""fastmake.py -- vectorized ring-survivor kernel for scanhunt make.

Replaces the per-k double survivors() call in cmd_make with ONE batched
computation across the whole k-block: per prime, kills are computed as
vectors over all ks simultaneously instead of per-k vectors over all
primes. Shallow sieve only (deep_q must be 0 or the round below
deep-from-ring); the caller falls back to legacy otherwise.

BYTE-IDENTITY CONTRACT (gated, not assumed): block_js(ks, prs, PEm,
lo, hi)[i] must equal, elementwise,
    np.concatenate([survivors(k, -hi, -lo-1 or -1),
                    survivors(k,  lo+1 or 1,  hi)])
for k = ks[i] -- i.e. negative side ascending, then positive side
ascending, BEFORE the caller's np.argsort(np.abs(js)). Same landing
arithmetic as ScanSieve.survivors: small primes (p <= W, p odd) stride
2p from the first even landing >= jlo; big primes (p > W) single even
landing; p = 2 skipped (n0 odd, even-j template).

Cost model: elementwise modulo work ~ len(prs) x nk is the numpy floor;
expect ~4-8x on the 610d ring-1 make (66 s -> ~8-18 s), more on later
rings. The next lever beyond this is a Q amendment, not more numpy.
"""
import numpy as np


def _side(ks, prs, PEm, jlo, jhi, chunk=256):
    """Survivor positions + alive matrix for one side [jlo, jhi]."""
    nk = len(ks)
    js0 = jlo + (jlo & 1)
    pos = np.arange(js0, jhi + 1, 2, dtype=np.int64)
    m = len(pos)
    alive = np.ones((nk, m), dtype=bool)
    W = jhi - jlo + 1
    nsmall = int(np.searchsorted(prs, W, side="right"))
    # --- small odd primes: stride kills, vectorized over k -------------
    for i in range(1, nsmall):                    # i=0 is p=2: skipped
        p = int(prs[i])
        n0m = (ks % p) * (int(PEm[i]) % p) % p
        j0 = (-n0m) % p
        st = j0 + ((jlo - j0 + p - 1) // p) * p   # first landing >= jlo
        st = np.where(st & 1, st + p, st)         # p odd: next even landing
        ok = st <= jhi
        i0 = (st - js0) >> 1                      # index step = p
        for q in range(m // p + 2):
            c = i0 + q * p
            sel = ok & (c < m)
            if not sel.any():
                break
            alive[np.nonzero(sel)[0], c[sel]] = False
    # --- big primes: single even landing, chunked 2D -------------------
    big = prs[nsmall:].astype(np.int64)
    pem = PEm[nsmall:].astype(np.int64)
    rows = np.arange(nk)
    for s in range(0, len(big), chunk):
        pc = big[s:s + chunk][:, None]            # (C,1)
        pe = pem[s:s + chunk][:, None]
        km = ks[None, :] % pc                     # (C,nk)
        j0 = (-(km * pe % pc)) % pc
        st = jlo + ((j0 - jlo) % pc)
        st = np.where(st & 1, st + pc, st)
        ok = st <= jhi
        if ok.any():
            cols = (st - js0) >> 1
            rsel = np.broadcast_to(rows, st.shape)[ok]
            alive[rsel, cols[ok]] = False
    return pos, alive


def block_js(ks, prs, PEm, lo, hi):
    """Legacy-ordered survivor js per k for ring (lo, hi], whole block.

    ks: int64 array (already gcd-filtered); prs/PEm: ScanSieve's arrays.
    Returns list of int64 arrays, one per k, in the exact pre-argsort
    order cmd_make's legacy path produces.
    """
    ks = np.asarray(ks, dtype=np.int64)
    if lo:
        nlo, nhi, plo, phi = -hi, -lo - 1, lo + 1, hi
    else:
        nlo, nhi, plo, phi = -hi, -1, 1, hi
    npos, nalive = _side(ks, prs, PEm, nlo, nhi)
    ppos, palive = _side(ks, prs, PEm, plo, phi)
    return [np.concatenate([npos[nalive[i]], ppos[palive[i]]])
            for i in range(len(ks))]
