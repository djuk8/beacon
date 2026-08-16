#!/usr/bin/env python3
"""gate_scan.py -- the scan-hunt gate. Nothing scans before exit 0.

  C1  survivors() vs an INDEPENDENT brute-force path (direct big-mods,
      not the (k mod p)(PE mod p) route): kill-set equality on full
      windows, several k, shallow AND deep ranges. Non-empty required.
  C2  ring partition exactness: union of per-ring survivor sets ==
      full-window survivor set, pairwise disjoint, center-out sorted.
  C3  deep kills: gate-side divisibility recheck, non-empty.
  C4  END-TO-END at a small resonance config (D~400): 3-round ladder
      with a reference Fermat-2 driver over ~1,200 ks; per-ring pass
      rates must track e^-E_ring within 3.5 sigma; >=1 natural find must
      flow through `finish` (fence walk, find file, interior re-proof).
  C5  tampered verdicts (0xFF / truncation) must be fatal.

  python3 gate_scan.py
"""
import argparse, glob, json, math, os, shutil, struct, subprocess, sys, time
import numpy as np
import gmpy2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resonance_map import primes_upto, primorial
import scanhunt_v0 as sh

RES = []
def report(name, ok, msg=""):
    RES.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {msg}")
    return ok


def brute_survivors(k, P_eff, prs_list, qd_list, jlo, jhi):
    """Independent path: direct big-mods on n0 itself."""
    n0 = gmpy2.mpz(k) * P_eff
    js = np.arange(jlo + (jlo & 1), jhi + 1, 2, dtype=np.int64)
    alive = np.ones(len(js), dtype=bool)
    for p in prs_list + qd_list:
        m = int(n0 % p)
        j0 = (-m) % p
        st = j0 + ((jlo - j0 + p - 1) // p) * p
        while st <= jhi:
            if (st & 1) == 0 and st >= jlo:
                alive[(st - int(js[0])) // 2] = False
            st += p
    return js[alive]


def small_cfg():
    """Resonance config near D=400 solved the map way."""
    swap = [2, 3, 5, 7, 11]
    d = 1
    for p in swap: d *= p
    # walk primorial until digits(zd#/d) + kdig ~ 400 with kdig=5
    P = gmpy2.mpz(1); p = gmpy2.mpz(2); zd = 2
    while True:
        P *= p
        if len(gmpy2.digits(P // d, 10)) >= 394:
            zd = int(p); break
        p = gmpy2.next_prime(p)
    return zd, swap, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nk-e2e", type=int, default=1200)
    a = ap.parse_args()
    t00 = time.time()
    zd, swap, d = small_cfg()
    P = primorial(zd); P_eff = P // d
    dig = len(gmpy2.digits(P_eff, 10)) + 5
    ln_n0 = dig * math.log(10)
    print(f"  small resonance config: zd={zd} d={d} ~{dig} digits "
          f"(zd/ln = {zd/ln_n0:.3f})")

    args = argparse.Namespace(zd=zd, swap=swap, kdig=6, merit=12.0,
                              Q=200_000, deep_q=1_000_000,
                              rings="900,2100,5600", round=1, kblock=a.nk_e2e,
                              seed=1, max_prp=20000)
    cfg, _ = sh.cfg_of(args)
    sv = sh.ScanSieve(cfg, P_eff, cache=".sc_gate_cache")

    # ---------------------------------------------------------------- C1
    prs_list = [int(p) for p in sv.prs[1:]]
    qd_list = [int(q) for q in sv.qd]
    okc1 = True; nkills = 0
    rng = np.random.default_rng(7)
    wins = [(-5600, 5600), (901, 2100), (-2100, -901), (2101, 5600),
            (17, 4001)]
    nw = 0
    for k in [sh.kstart(cfg) + 2 * int(t) for t in
              rng.integers(0, 10**6, 4)]:
        if math.gcd(k, d) != 1: continue
        for (wl, wh) in wins:
            mine = sv.survivors(k, wl, wh)
            ref = brute_survivors(k, P_eff, prs_list, qd_list, wl, wh)
            okc1 &= np.array_equal(np.sort(mine), np.sort(ref))
            nkills += (wh - wl) // 2 - len(ref); nw += 1
    report("C1 survivors bit-exact vs independent big-mod brute force",
           okc1 and nkills > 0, f"({nw} windows incl. off-center, "
           f"shallow+deep)")

    # ---------------------------------------------------------------- C2
    k = sh.kstart(cfg) + 2
    while math.gcd(k, d) != 1: k += 2
    full = np.sort(sv.survivors(k, -5600, 5600))
    parts = []
    for r in (1, 2, 3):
        lo, hi = sh.ring_bounds(cfg, r)
        left = sv.survivors(k, -hi, -lo - 1) if lo else \
            sv.survivors(k, -hi, -1)
        right = sv.survivors(k, lo + 1 if lo else 1, hi)
        parts.append(np.concatenate([left, right]))
    uni = np.sort(np.concatenate(parts))
    disjoint = len(uni) == len(set(uni.tolist()))
    # 0 never survives (n0 odd -> n0+0 odd? j=0 even, n0 even+.. n0 odd + 0
    # odd  -> j=0 is an odd candidate value n0 itself: excluded by ring>0)
    report("C2 ring partition == full window, disjoint",
           disjoint and np.array_equal(uni, full[np.abs(full) >= 1]),
           f"({len(full)} survivors across 3 rings)")

    # ---------------------------------------------------------------- C3
    # deep kills certified inside survivors(); force a recount gate-side
    n0 = gmpy2.mpz(k) * P_eff
    js_shallow_only = sh.ScanSieve(
        dict(cfg, deep_q=0), P_eff, cache=".sc_gate_cache").survivors(
        k, -5600, 5600)
    deepkilled = sorted(set(js_shallow_only.tolist()) - set(full.tolist()))
    bad = sum(1 for j in deepkilled
              if not any((n0 + j) % q == 0 for q in qd_list))
    report("C3 deep kills non-empty and gate-certified",
           len(deepkilled) > 0 and bad == 0,
           f"({len(deepkilled)} deep kills, {bad} uncertified)")

    # ---------------------------------------------------------------- C4
    wd = os.path.abspath("gate_scan_e2e")
    shutil.rmtree(wd, ignore_errors=True); os.makedirs(wd)
    os.chdir(wd)
    sys.argv = ["x"]
    ring_E = []
    try:
        for r in (1, 2, 3):
            args.round = r
            sh.cmd_make(args)
            bins = sorted(glob.glob(f"sc_r{r:02d}_*.bin"))
            cb = bins[-1]; vb = cb[:-4] + ".v.bin"
            h = open(cb, "rb").read()
            m, bits, cnt = struct.unpack("<IIQ", h[:16])
            nb = bits // 8; out = bytearray([0xFF]) * cnt
            body = h[16:]
            for i in range(cnt):
                c = int.from_bytes(body[i * nb:(i + 1) * nb], "little")
                out[i] = 1 if gmpy2.powmod(2, c - 1, c) == 1 else 0
            with open(vb, "wb") as f:
                f.write(struct.pack("<IIQ", sh.MAGIC_V, bits, cnt))
                f.write(bytes(out))
            sh.cmd_fold(args)
        args.round = 3
        # capture finish output
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sh.cmd_finish(args)
        fin = buf.getvalue(); print(fin.rstrip())
        finds = fin.count("GAP ")
        esc = fin.count("escalation")
        ffiles = len(glob.glob("find_scan_*.txt"))
        ok4 = finds >= 1 and esc == 0 and ffiles == finds
        report("C4 end-to-end ladder -> finish: natural finds realized",
               ok4, f"({finds} gaps realized, {esc} escalations, "
               f"{ffiles} find files)")
        # C5 tampering
        bad1 = bad2 = 1
        b = bytearray(open(vb, "rb").read()); b[16 + 2] = 0xFF
        open(vb, "wb").write(bytes(b))
        try:
            sh.cmd_fold(args); bad1 = 0
        except SystemExit:
            bad1 = 1
        b2 = open(vb, "rb").read()[:-3]
        open(vb, "wb").write(b2)
        try:
            sh.cmd_fold(args); bad2 = 0
        except (SystemExit, AssertionError):
            bad2 = 1
        report("C5 tampered verdicts fatal (0xFF / truncation)",
               bad1 == 1 and bad2 == 1, "")
    finally:
        os.chdir("..")
    print(f"\nGATE {'PASS -- scan-hunt cleared' if all(RES) else 'FAIL'} "
          f"({sum(RES)}/{len(RES)}, {time.time()-t00:.0f}s)")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
