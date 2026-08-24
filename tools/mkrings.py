#!/usr/bin/env python3
"""mkrings.py -- synthetic rings in scanhunt make layout (bin + manifest) with planted beta, plus legacy v.bin via --driver. For gates only."""
import sys, os, json, struct, random, argparse, subprocess, gmpy2
ap = argparse.ArgumentParser(); ap.add_argument("outdir"); ap.add_argument("--n", type=int, default=4); ap.add_argument("--ks", type=int, default=300)
ap.add_argument("--S", type=int, default=97); ap.add_argument("--bits", type=int, default=512); ap.add_argument("--beta", type=float, default=0.0174)
ap.add_argument("--round", type=int, default=1); ap.add_argument("--bid0", type=int, default=1000); ap.add_argument("--seed", type=int, default=101); ap.add_argument("--driver", default=None)
a = ap.parse_args(); random.seed(a.bid0 * 7 + a.seed); nb = a.bits // 8; os.makedirs(a.outdir, exist_ok=True)
def comp():
    while True:
        x = random.getrandbits(a.bits) | 1 | (1 << (a.bits - 1))
        if not gmpy2.is_prime(x): return x
def prime(): return int(gmpy2.next_prime(gmpy2.mpz(random.getrandbits(a.bits - 2) | (1 << (a.bits - 3)))))
for i in range(a.n):
    bid = a.bid0 + i; name = os.path.join(a.outdir, f"sc_r{a.round:02d}_{bid:04d}")
    sizes = [max(1, a.S + random.randint(-5, 5)) for _ in range(a.ks)]; ks = [10**12 + bid * 1000 + k for k in range(a.ks)]
    cands = []
    for s in sizes:
        cands += [prime() if random.random() < a.beta else comp() for _ in range(s)]
    with open(name + ".bin", "wb") as f:
        f.write(struct.pack("<IIQ", 0x31433247, a.bits, len(cands)))
        for c in cands: f.write(c.to_bytes(nb, "little"))
    json.dump(dict(cfg=dict(bits=a.bits, seed=a.seed, Q=100000, deep_q=0), round=a.round, bid=bid, ks=ks, js=[list(range(s)) for s in sizes], sizes=sizes), open(name + ".manifest.json", "w"))
    if a.driver: subprocess.run([a.driver, name + ".bin", name + ".legacy.v.bin"], check=True)
    print(name, len(cands))
