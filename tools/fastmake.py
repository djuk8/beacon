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
                _lib.fm_block_js2.restype = ctypes.c_int64
                _lib.fm_block_js2.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64,
                                              ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64]
                _lib.fm_deepen.restype = ctypes.c_int64
                _lib.fm_deepen.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64]
                IMPL = "c"; break
            except OSError as e:
                sys.stderr.write(f"fastmake: {so}: {e}\n"); _lib = None
if _lib is None:
    from fastmake_numpy import block_js as _np_block_js

def block_js(ks, prs, PEm, lo, hi, qd=None, PEd=None):
    if _lib is None:
        assert qd is None, "O3 deepening requires the C kernel (no numpy fallback by design -- venue consistency)"
        return _np_block_js(ks, prs, PEm, lo, hi)
    ks = np.ascontiguousarray(np.asarray(ks, dtype=np.int64)); prs = np.ascontiguousarray(np.asarray(prs, dtype=np.int64))
    PEm = np.ascontiguousarray(np.asarray(PEm, dtype=np.int64)); nk = len(ks)
    cap = int(nk * ((int(hi) - int(lo)) // 2 + 2) * 2 + 16)
    out = np.empty(cap, dtype=np.int32); cnt = np.empty(max(nk, 1), dtype=np.int32)
    _use2 = (nk >= 500) and (__import__("os").environ.get("FM_JS2", "1") != "0")   # prime-outer bitmap sieve for rung-1 blocks. (v7.7 density guard REMOVED -- it silently forced the slow per-k path in production: 41.9k->30k, bisected 2026-09-06. js2 handles selected sparse sets fine; the walk cost is landing-proportional, not span-proportional.)
    if _use2:
        prs64 = np.ascontiguousarray(np.asarray(prs, dtype=np.int64)); PEm64 = np.ascontiguousarray(np.asarray(PEm, dtype=np.int64))
        tot = _lib.fm_block_js2(ks.ctypes.data, nk, prs64.ctypes.data, PEm64.ctypes.data, len(prs64), int(lo), int(hi), out.ctypes.data, cnt.ctypes.data, cap)
    else:
        tot = _lib.fm_block_js(ks.ctypes.data, nk, prs.ctypes.data, PEm.ctypes.data, len(prs), int(lo), int(hi), out.ctypes.data, cnt.ctypes.data, cap)
    if tot < 0: raise RuntimeError(f"fastmake_c returned {tot}")
    if qd is not None:
        qd = np.ascontiguousarray(np.asarray(qd, dtype=np.int64)); PEd = np.ascontiguousarray(np.asarray(PEd, dtype=np.int64))
        offs_pre = np.zeros(nk, dtype=np.int64); np.cumsum(cnt[:-1], out=offs_pre[1:])   # PHYSICAL segment starts (pre-deepen layout)
        kd = _lib.fm_deepen(ks.ctypes.data, nk, out.ctypes.data, cnt.ctypes.data, qd.ctypes.data, PEd.ctypes.data, len(qd), int(lo), int(hi))
        if kd < 0: raise RuntimeError("fm_deepen failed")
        tot = int(cnt.sum())   # deepen removed kills in place; the pre-deepen total is stale
        # (fm_deepen v0.2.1 writes tight; no compaction needed)
    return [a.astype(np.int64) for a in np.split(out[:int(cnt.sum())], np.cumsum(cnt)[:-1])]

def _raw(ks, prs, PEm, lo, hi, qd=None, PEd=None):
    ks = np.ascontiguousarray(np.asarray(ks, dtype=np.int64)); prs = np.ascontiguousarray(np.asarray(prs, dtype=np.int64))
    PEm = np.ascontiguousarray(np.asarray(PEm, dtype=np.int64)); nk = len(ks)
    cap = int(nk * ((int(hi) - int(lo)) // 2 + 2) * 2 + 16)
    out = np.empty(cap, dtype=np.int32); cnt = np.empty(max(nk, 1), dtype=np.int32)
    _use2 = (nk >= 500) and (__import__("os").environ.get("FM_JS2", "1") != "0")   # prime-outer bitmap sieve for rung-1 blocks. (v7.7 density guard REMOVED -- it silently forced the slow per-k path in production: 41.9k->30k, bisected 2026-09-06. js2 handles selected sparse sets fine; the walk cost is landing-proportional, not span-proportional.)
    if _use2:
        prs64 = np.ascontiguousarray(np.asarray(prs, dtype=np.int64)); PEm64 = np.ascontiguousarray(np.asarray(PEm, dtype=np.int64))
        tot = _lib.fm_block_js2(ks.ctypes.data, nk, prs64.ctypes.data, PEm64.ctypes.data, len(prs64), int(lo), int(hi), out.ctypes.data, cnt.ctypes.data, cap)
    else:
        tot = _lib.fm_block_js(ks.ctypes.data, nk, prs.ctypes.data, PEm.ctypes.data, len(prs), int(lo), int(hi), out.ctypes.data, cnt.ctypes.data, cap)
    if tot < 0: raise RuntimeError(f"fastmake_c returned {tot}")
    if qd is not None:
        qd = np.ascontiguousarray(np.asarray(qd, dtype=np.int64)); PEd = np.ascontiguousarray(np.asarray(PEd, dtype=np.int64))
        offs_pre = np.zeros(nk, dtype=np.int64); np.cumsum(cnt[:-1], out=offs_pre[1:])   # PHYSICAL segment starts (pre-deepen layout)
        kd = _lib.fm_deepen(ks.ctypes.data, nk, out.ctypes.data, cnt.ctypes.data, qd.ctypes.data, PEd.ctypes.data, len(qd), int(lo), int(hi))
        if kd < 0: raise RuntimeError("fm_deepen failed")
        tot = int(cnt.sum())   # deepen removed kills in place; the pre-deepen total is stale
        # (fm_deepen v0.2.1 writes tight; no compaction needed)
    return ks, out, cnt, int(tot)

def block_pack(ks, prs, PEm, lo, hi, P_eff, nb, qd=None, PEd=None):
    """C sieve + center-out stable order + packed candidates.  Returns (js_sorted list per k, sizes, bytes).
    Requires the C kernel (no numpy fallback: the legacy path does this in cmd_make)."""
    if _lib is None: raise RuntimeError("fastmake_c.so not available")
    ks, out, cnt, tot = _raw(ks, prs, PEm, lo, hi, qd=qd, PEd=PEd)
    peff = int(P_eff).to_bytes((int(P_eff).bit_length() + 7) // 8, "little")
    jo = np.empty(max(tot, 1), dtype=np.int32); bb = np.empty(max(tot, 1) * nb, dtype=np.uint8)
    r = _lib.fm_block_pack(ks.ctypes.data, len(ks), out.ctypes.data, cnt.ctypes.data, peff, len(peff), nb, jo.ctypes.data, bb.ctypes.data, len(bb))
    if r != tot: raise RuntimeError(f"fastmake_c pack returned {r} != {tot}")
    cn = np.asarray(cnt[:len(ks)], dtype=np.int64)
    res = [a.astype(np.int64) for a in np.split(jo[:tot], np.cumsum(cn)[:-1])]
    return res, cn.tolist(), bb[:tot * nb]          # uint8 array: write with f.write(arr), no copy


def pack_given(ks, js_list, P_eff, nb):
    """Pack candidates for ks from ALREADY-computed js (e.g. a selected subset of a deepened block). Same C packer,
    same center-out stable order; no re-sieve. Returns (js_sorted per k, sizes, bytes)."""
    if _lib is None: raise RuntimeError("fastmake_c.so not available")
    ks = np.ascontiguousarray(np.asarray(ks, dtype=np.int64)); nk = len(ks)
    cnt = np.array([len(j) for j in js_list], dtype=np.int32); tot = int(cnt.sum())
    out = np.empty(max(tot, 1), dtype=np.int32); off = 0
    for j in js_list: out[off:off + len(j)] = np.asarray(j, dtype=np.int32); off += len(j)
    peff = int(P_eff).to_bytes((int(P_eff).bit_length() + 7) // 8, "little")
    jo = np.empty(max(tot, 1), dtype=np.int32); bb = np.empty(max(tot, 1) * nb, dtype=np.uint8)
    r = _lib.fm_block_pack(ks.ctypes.data, nk, out.ctypes.data, cnt.ctypes.data, peff, len(peff), nb, jo.ctypes.data, bb.ctypes.data, len(bb))
    if r != tot: raise RuntimeError(f"fastmake_c pack returned {r} != {tot}")
    res = [a.astype(np.int64) for a in np.split(jo[:tot], np.cumsum(cnt)[:-1])]
    return res, [int(c) for c in cnt], bb[:tot * nb]


def block_sieve(ks, prs, PEm, lo, hi, qd=None, PEd=None):
    """Sieve only (js2 + deepen), no packing: for selection pools where most windows are discarded.
    Returns (ks, js list per k, cnt list)."""
    if _lib is None: raise RuntimeError("fastmake_c.so not available")
    ks, out, cnt, tot = _raw(ks, prs, PEm, lo, hi, qd=qd, PEd=PEd)
    cn = np.asarray(cnt[:len(ks)], dtype=np.int64)
    return ks, [a.astype(np.int64) for a in np.split(out[:tot], np.cumsum(cn)[:-1])], cn.tolist()
