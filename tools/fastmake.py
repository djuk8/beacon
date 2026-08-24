#!/usr/bin/env python3
"""fastmake.py v2 -- drop-in for scanhunt's `import fastmake; fastmake.block_js(ks, prs, PEm, lo, hi)`.
Tries the C kernel (fastmake_c.so beside this file, or $FASTMAKE_SO) and falls back to the
numpy kernel (fastmake_numpy.py, the former fastmake.py, byte-for-byte) if it is absent.
Contract unchanged: per k, negative side ascending then positive side ascending, pre-argsort.
Set FASTMAKE_IMPL=numpy to force the fallback (gates compare the two)."""
import os, sys, ctypes, numpy as np
_here = os.path.dirname(os.path.abspath(__file__))
_lib = None; IMPL = "numpy"
if os.environ.get("FASTMAKE_IMPL", "c") != "numpy":
    for so in (os.environ.get("FASTMAKE_SO", ""), os.path.join(_here, "fastmake_c.so")):
        if so and os.path.exists(so):
            try:
                _lib = ctypes.CDLL(so)
                _lib.fm_block_js.restype = ctypes.c_int
                _lib.fm_block_js.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                             ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64]
                _lib.fm_block_pack.restype = ctypes.c_int64
                _lib.fm_block_pack.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                               ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64]
                IMPL = "c"; break
            except OSError as e:
                sys.stderr.write(f"fastmake: {so}: {e}\n"); _lib = None
if _lib is None:
    from fastmake_numpy import block_js as _np_block_js

def block_js(ks, prs, PEm, lo, hi):
    if _lib is None:
        return _np_block_js(ks, prs, PEm, lo, hi)
    ks = np.ascontiguousarray(np.asarray(ks, dtype=np.int64)); prs = np.ascontiguousarray(np.asarray(prs, dtype=np.int64))
    PEm = np.ascontiguousarray(np.asarray(PEm, dtype=np.int64)); nk = len(ks)
    cap = int(nk * ((int(hi) - int(lo)) // 2 + 2) * 2 + 16)
    out = np.empty(cap, dtype=np.int32); cnt = np.empty(max(nk, 1), dtype=np.int32)
    tot = _lib.fm_block_js(ks.ctypes.data, nk, prs.ctypes.data, PEm.ctypes.data, len(prs), int(lo), int(hi), out.ctypes.data, cnt.ctypes.data, cap)
    if tot < 0: raise RuntimeError(f"fastmake_c returned {tot}")
    res = []; off = 0
    for i in range(nk):
        n = int(cnt[i]); res.append(out[off:off + n].astype(np.int64)); off += n
    return res

def _raw(ks, prs, PEm, lo, hi):
    ks = np.ascontiguousarray(np.asarray(ks, dtype=np.int64)); prs = np.ascontiguousarray(np.asarray(prs, dtype=np.int64))
    PEm = np.ascontiguousarray(np.asarray(PEm, dtype=np.int64)); nk = len(ks)
    cap = int(nk * ((int(hi) - int(lo)) // 2 + 2) * 2 + 16)
    out = np.empty(cap, dtype=np.int32); cnt = np.empty(max(nk, 1), dtype=np.int32)
    tot = _lib.fm_block_js(ks.ctypes.data, nk, prs.ctypes.data, PEm.ctypes.data, len(prs), int(lo), int(hi), out.ctypes.data, cnt.ctypes.data, cap)
    if tot < 0: raise RuntimeError(f"fastmake_c returned {tot}")
    return ks, out, cnt, int(tot)

def block_pack(ks, prs, PEm, lo, hi, P_eff, nb):
    """C sieve + center-out stable order + packed candidates.  Returns (js_sorted list per k, sizes, bytes).
    Requires the C kernel (no numpy fallback: the legacy path does this in cmd_make)."""
    if _lib is None: raise RuntimeError("fastmake_c.so not available")
    ks, out, cnt, tot = _raw(ks, prs, PEm, lo, hi)
    peff = int(P_eff).to_bytes((int(P_eff).bit_length() + 7) // 8, "little")
    jo = np.empty(max(tot, 1), dtype=np.int32); bb = np.empty(max(tot, 1) * nb, dtype=np.uint8)
    r = _lib.fm_block_pack(ks.ctypes.data, len(ks), out.ctypes.data, cnt.ctypes.data, peff, len(peff), nb, jo.ctypes.data, bb.ctypes.data, len(bb))
    if r != tot: raise RuntimeError(f"fastmake_c pack returned {r} != {tot}")
    res = []; off = 0
    for i in range(len(ks)):
        n = int(cnt[i]); res.append(jo[off:off + n].astype(np.int64)); off += n
    return res, [int(c) for c in cnt[:len(ks)]], bb[:tot * nb]          # uint8 array: write with f.write(arr), no copy
