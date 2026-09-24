#!/usr/bin/env python3
"""ladder610.py -- ring-ladder designer + mint gate for the 610d raid.

  python3 ladder610.py edges                # -> --rings string + design dE
  python3 ladder610.py gate sc_r01_0001     # G-F1 + G-F2 on a minted block

edges: samples nk ks at the preregistered config (zd=1439, T={2,3,5,7,11},
kdig=13, merit>37.8241, Q=1e6, shallow), dense-sieves the full +/-G/2
window, and places ring edges at cumulative-E targets
[1.7, 3.4, 5.4, 7.8, 10.8, 15.0] + final edge = G/2 (cum-E ~ 24.7).

gate: INDEPENDENT verification of a minted block -- a from-scratch dense
sieve (different code path from ScanSieve's landing arithmetic) recomputes
every k's ring-1 survivor js, byte-compares the candidates in the .bin,
and checks the sample's cum-E ladder against design within 2%.
Exit codes: 0 pass, 2 empty/mismatch (a green gate must have teeth).
"""
import json, math, struct, sys
import numpy as np
import gmpy2
from resonance_map import primes_upto, primorial

sys.set_int_max_str_digits(2_000_000)
GAMMA = 0.5772156649015329

ZD, SWAP, KDIG, MERIT, Q = 1439, (2, 3, 5, 7, 11), 13, 37.8241, 10 ** 6
ETARG = [1.7, 3.4, 5.4, 7.8, 10.8, 15.0]


def setup():
    d = math.prod(SWAP)
    P_eff = primorial(ZD) // d
    prs = primes_upto(Q)
    PEm = np.array([int(P_eff % int(p)) for p in prs], dtype=np.int64)
    kmid = 5 * 10 ** (KDIG - 1)
    ln_n0 = float(gmpy2.log(gmpy2.mpz(kmid) * P_eff))
    G = math.ceil(MERIT * ln_n0)
    beta = math.exp(GAMMA) * math.log(Q) / ln_n0
    return d, P_eff, prs, PEm, ln_n0, G, beta


def dense_survivors(k, prs, PEm, hi, lo=0):
    """Even-j survivors of (lo, hi] both sides, dense bool sieve --
    deliberately a different implementation from ScanSieve."""
    S = hi
    js = np.arange(-S, S + 1, dtype=np.int64)
    alive = (js & 1) == 0
    alive[S] = False                       # j = 0 is n0 itself
    n0m = (int(k) % prs) * PEm % prs
    for i in range(1, len(prs)):
        p = int(prs[i])
        j0 = (-int(n0m[i])) % p
        st = -S + ((j0 + S) % p)
        alive[st + S::p] = False
        if p > 2 * S:
            break
    # big primes: single landing each
    big = prs[prs > 2 * S]
    if len(big):
        m = ((int(k) % big) * (PEm[len(prs) - len(big):])) % big
        j0 = (-m) % big
        st = -S + ((j0 + S) % big)
        ok = st <= S
        alive[(st[ok] + S).astype(np.int64)] = False
    out = js[alive]
    if lo:
        out = out[np.abs(out) > lo]
    return out


def cmd_edges():
    d, P_eff, prs, PEm, ln_n0, G, beta = setup()
    half = G // 2 + (G // 2 & 1)
    print(f"config: zd={ZD} d={d} kdig={KDIG} merit>{MERIT} "
          f"ln_n0~{ln_n0:.1f} G~{G:,} half={half:,} beta={beta:.5f}")
    base = 10 ** (KDIG - 1) + 1
    ks = []
    k = base + 10 ** (KDIG - 2)            # sample away from seed-1 start
    while len(ks) < 40:
        if math.gcd(k, d) == 1:
            ks.append(k)
        k += 2
    counts = np.zeros(half + 1)
    for k in ks:
        js = dense_survivors(k, prs, PEm, half)
        a = np.abs(js)
        cnt = np.bincount(a, minlength=half + 1)
        counts += np.cumsum(cnt)
    cum_e = counts / len(ks) * beta
    edges = []
    for t in ETARG:
        edges.append(int(np.searchsorted(cum_e, t)))
    edges.append(half)
    de = [cum_e[e] for e in edges]
    print("--rings " + ",".join(str(e) for e in edges))
    print("design cum-E per ring: " +
          " ".join(f"{x:.2f}" for x in de))
    print(f"full-window E (sample) = {cum_e[half]:.2f} "
          f"(prereg 24.7-25.1; sample-of-40 sd ~ +/-0.5)")
    json.dump(dict(edges=edges, cum_e=[float(x) for x in de],
                   G=G, half=half), open("ladder610.json", "w"))
    print("-> ladder610.json (gate mode reads this)")


def cmd_gate(name):
    d, P_eff, prs, PEm, ln_n0, G, beta = setup()
    lad = json.load(open("ladder610.json"))
    man = json.load(open(name + ".manifest.json"))
    assert man["cfg"]["zd"] == ZD and man["cfg"]["d"] == d, "config mismatch"
    edges = man["cfg"]["edges"]
    assert edges == lad["edges"], "ring edges != certified ladder"
    hdr = open(name + ".bin", "rb").read(16)
    magic, bits, total = struct.unpack("<IIQ", hdr)
    assert bits == 2048, f"container bits={bits}, want 2048"
    assert total == sum(man["sizes"]) and total > 0, "count/empty FAIL"
    nb = bits // 8
    f = open(name + ".bin", "rb"); f.seek(16)
    bad = 0
    ecum = 0.0
    for k, js_m, sz in zip(man["ks"], man["js"], man["sizes"]):
        js_i = dense_survivors(k, prs, PEm, edges[0])
        if sorted(js_i.tolist()) != sorted(js_m):
            print(f"  k={k}: js MISMATCH (ind {len(js_i)} vs man {sz})")
            bad += 1
            f.seek(sz * nb, 1)
            continue
        n0 = gmpy2.mpz(k) * P_eff
        for j in js_m:
            c = int.from_bytes(f.read(nb), "little")
            if c != int(n0 + j):
                print(f"  k={k} j={j}: BYTE MISMATCH"); bad += 1; break
        ecum += len(js_m) * beta
    got = ecum / len(man["ks"])
    want = lad["cum_e"][0]
    dev = abs(got - want) / want
    print(f"ring-1 cum-E: minted {got:.3f} vs design {want:.3f} "
          f"({dev*100:.1f}% dev; gate < 2%)")
    if bad or dev > 0.02:
        print(f"GATE FAIL: {bad} mismatches, dev {dev*100:.1f}%")
        sys.exit(2)
    print(f"G-F1 + G-F2 PASS: {len(man['ks'])} ks, {total:,} candidates "
          f"byte-identical on independent sieve, ladder in-band")


if __name__ == "__main__":
    if sys.argv[1] == "edges":
        cmd_edges()
    elif sys.argv[1] == "gate":
        cmd_gate(sys.argv[2].replace(".bin", ""))
    else:
        sys.exit("usage: ladder610.py edges | gate <block>")
