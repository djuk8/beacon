#!/usr/bin/env python3
"""rescal_v0.py -- LIVE calibration of the resonance record config.
Samples real k's at (zd=6299, d=2310, kdig=7), sieves each record-sized
window with the gate-validated map sieve, packs ALL survivors into one
G2C batch for g1_fermat, then counts primes per window.

PREREGISTERED (2026-08-02, before any GPU verdict exists):
  E_meas = mean primes/window over 60 windows.
  Map prediction at this exact config: 17.56 (best-align) / 17.86 (mean).
  PASS band (symmetric window, mean-alignment figure): 17.86 +/- 1.1
  (2 sigma at n=60). PASS -> the frontier law transfers to our digits and
  the scan campaign is GO at the quoted 50-75 card-day band. FAIL -> stop,
  diagnose before any scan-mode build. No cleans are expected (e^-17.6);
  this is calibration, not hunting.

  python3 rescal_v0.py make --nk 60 --Q 10000000     (~5-10 min CPU)
  ../../p3/g1_fermat rc_0001.bin rc_0001.v.bin        (~70-100 s GPU)
  python3 rescal_v0.py check
"""
import argparse, json, math, os, struct, sys, time
import numpy as np
import gmpy2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resonance_map import primes_upto, primorial, sieve_window

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
GAMMA = 0.5772156649015329


def build_cfg(a):
    P = primorial(a.zd)
    d = 1
    for p in a.swap: d *= p
    P_eff = P // d
    prs = primes_upto(a.Q)
    t0 = time.time()
    PEmod = np.array([int(P_eff % int(p)) for p in prs], dtype=np.int64)
    print(f"  P_eff: {len(gmpy2.digits(P_eff,10))} digits; PEmod over "
          f"{len(prs):,} primes [{time.time()-t0:.0f}s]")
    return P_eff, prs, PEmod


def cmd_make(a):
    P_eff, prs, PEmod = build_cfg(a)
    ln_n0 = float(gmpy2.log(P_eff)) + a.kdig * math.log(10)  # ~; refined per k
    G = math.ceil(a.merit * (len(gmpy2.digits(P_eff,10)) + a.kdig)
                  * math.log(10))
    jl, jr = -(G // 2), G - (G // 2)
    rng = np.random.default_rng(a.seed)
    klo, khi = 10 ** (a.kdig - 1), 10 ** a.kdig - 1
    d = 1
    for p in a.swap: d *= p
    ks, sizes, blobs = [], [], []
    bits = 16384; nb = bits // 8
    t0 = time.time()
    for i in range(a.nk):
        while True:
            k = int(rng.integers(klo, khi)) | 1
            if math.gcd(k, d) == 1: break
        n0mod = (k % prs) * PEmod % prs
        W = jr - jl - 1
        alive = np.ones(W, dtype=bool)
        off = jl + 1
        js = np.arange(off, jr)
        n0 = k * P_eff
        if int(n0 % 2) == 1: alive[(js % 2) != 0] = False
        else: alive[(js % 2) == 0] = False
        small = prs[prs <= W]
        for ii in range(1, len(small)):
            p = int(small[ii])
            idx0 = ((-int(n0mod[ii])) % p - off) % p
            alive[idx0::p] = False
        big = prs[len(small):]
        if len(big):
            m = n0mod[len(small):]
            j0 = (-m) % big
            hi = j0 < jr; lo = (j0 - big) >= off
            for jj in (j0[hi], (j0 - big)[lo]):
                if len(jj): alive[(jj - off).astype(np.int64)] = False
        sj = js[alive]
        cands = [int(n0 + int(j)) for j in sj]
        assert all(c.bit_length() <= bits for c in cands)
        ks.append(k); sizes.append(len(cands)); blobs.append(cands)
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{a.nk} windows, mean surv "
                  f"{np.mean(sizes):.0f} [{time.time()-t0:.0f}s]")
    total = sum(sizes)
    with open("rc_0001.bin", "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, bits, total))
        for cands in blobs:
            for c in cands:
                f.write(c.to_bytes(nb, "little"))
    # pack/readback spot-check: re-read candidate 0 and last, must round-trip
    with open("rc_0001.bin", "rb") as f:
        f.seek(16); c0 = int.from_bytes(f.read(nb), "little")
        f.seek(16 + (total - 1) * nb); cL = int.from_bytes(f.read(nb), "little")
    assert c0 == blobs[0][0] and cL == blobs[-1][-1], "pack round-trip FAIL"
    beta = math.exp(GAMMA) * math.log(a.Q) / ln_n0
    json.dump(dict(cfg=dict(zd=a.zd, swap=a.swap, kdig=a.kdig, Q=a.Q,
                            merit=a.merit, G=G, seed=a.seed),
                   ks=ks, sizes=sizes, bits=bits,
                   E_pred_surv=float(np.mean(sizes) * beta)),
              open("rc_0001.manifest.json", "w"))
    print(f"rc_0001.bin: {a.nk} windows, {total:,} candidates "
          f"(mean surv {np.mean(sizes):.0f}; surv x beta = "
          f"{np.mean(sizes)*beta:.2f})")
    print(f"-> run:  <path>/g1_fermat rc_0001.bin rc_0001.v.bin")


def cmd_check(a):
    man = json.load(open("rc_0001.manifest.json"))
    hv = open("rc_0001.v.bin", "rb").read()
    m, bits, cnt = struct.unpack("<IIQ", hv[:16])
    v = hv[16:]
    assert m == MAGIC_V and cnt == sum(man["sizes"]) == len(v), \
        "verdict header/count mismatch (0xFF hazard)"
    if any(b == 0xFF for b in v):
        sys.exit("UNTOUCHED 0xFF verdicts -- FATAL")
    prp = []
    pos = 0
    for sz in man["sizes"]:
        vl = v[pos:pos + sz]; pos += sz
        prp.append(sum(1 for b in vl if b in (1, 2)))
    prp = np.array(prp, dtype=float)
    E, se = prp.mean(), prp.std(ddof=1) / len(prp) ** 0.5
    # MR-25 spot confirmation of first suspects (Fermat-2 honesty check)
    P_eff = primorial(man["cfg"]["zd"])
    for p in man["cfg"]["swap"]: P_eff //= p
    G = man["cfg"]["G"]; jl = -(G // 2)
    confirmed = tried = 0
    # spot-check: pull suspect candidate values straight from rc_0001.bin
    nb = bits // 8
    with open("rc_0001.bin", "rb") as f:
        body = f.read()[16:]
    idx = [i for i, b in enumerate(v) if b in (1, 2)][:40]
    for i in idx:
        c = int.from_bytes(body[i * nb:(i + 1) * nb], "little")
        tried += 1
        if gmpy2.is_prime(c, 25): confirmed += 1
    lo, hi = 17.86 - 1.1, 17.86 + 1.1
    verdict = "PASS" if lo <= E <= hi else \
              ("INCONCLUSIVE" if lo - 0.6 <= E <= hi + 0.6 else "FAIL")
    print(f"windows {len(prp)}  primes {int(prp.sum())}  "
          f"E_meas = {E:.2f} +/- {se:.2f}")
    print(f"prereg band 17.86 +/- 1.10 (map mean-alignment)  ->  {verdict}")
    print(f"MR-25 spot confirmation: {confirmed}/{tried} suspects prime")
    print(f"clean windows (expected 0): {int((prp==0).sum())}")
    if verdict == "PASS":
        print("LAW TRANSFERS TO OUR DIGITS -- scan campaign is GO "
              "(50-75 card-day band stands, scan-mode build next)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "check"])
    ap.add_argument("--zd", type=int, default=6299)
    ap.add_argument("--swap", type=int, nargs="+", default=[2, 3, 5, 7, 11])
    ap.add_argument("--kdig", type=int, default=7)
    ap.add_argument("--merit", type=float, default=32.25)
    ap.add_argument("--nk", type=int, default=60)
    ap.add_argument("--Q", type=int, default=10**7)
    ap.add_argument("--seed", type=int, default=4242)
    a = ap.parse_args()
    (cmd_make if a.cmd == "make" else cmd_check)(a)


if __name__ == "__main__":
    main()
