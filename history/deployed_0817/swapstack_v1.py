#!/usr/bin/env python3
"""BEACON swap-stack v1 -- dropped-family screening at D=400 (mechanism test).

Construction: drop set S of edge design primes; restore size via k ~ prod(S)
(bignum anchors, kernel2 R0 blobs). Positions +/-q (q in S) become scoreable
holes; selection hunts anchors where the holes are sieve-dead and k's own
factors assassinate candidates for free. Families: S0 (standard), S8, S16.
Prereg instrument: exact per-anchor posterior ONLY (shorthand retired).
Stage A: screens + validation + preregistration -> swapstack_state.json
Stage B: real trials on all selected anchors -> verdict.
"""
import json, math, subprocess, sys, time
import numpy as np, gmpy2

EG = 1.7810724179901979
LN10 = math.log(10)
D, ZS, ZT = 400, 10 ** 5, 10 ** 6
L = D * LN10
W = int(10 * L)
GTARGET = int(6 * L)            # merit-6 scoring window & success target
NSCREEN, TOP, PREREG_N = 500_000, 1500, 60      # ~line 20

def primes_upto(n):
    s = np.ones(n + 1, bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

PR = primes_upto(ZT)
cum = np.cumsum(np.log(PR.astype(float)))
i0 = int(np.searchsorted(cum, (D - 8) * LN10))
ZD = int(PR[i0 - 1]) if cum[i0] > (D - 8) * LN10 else int(PR[i0])
DESIGN = PR[PR <= ZD]
P_FULL = gmpy2.mpz(1)
for p in DESIGN: P_FULL *= int(p)

def family(s_count, rng):
    S = DESIGN[-s_count:].copy() if s_count else np.array([], np.int64)
    R = 1
    for q in S: R *= int(q)
    P_S = P_FULL // gmpy2.mpz(R) if s_count else P_FULL
    design_S = DESIGN[:-s_count] if s_count else DESIGN
    offs_S = np.sort(np.concatenate([S, PR[(PR > ZD) & (PR <= W)]]))
    scrp = np.concatenate([S, PR[(PR > ZD) & (PR <= ZS)]])       # screen primes incl. S
    Pmod = np.array([int(P_S % int(p)) for p in scrp], np.int64)
    k0 = int(rng.integers(10 ** 6, 10 ** 7)) * R                  # size-restored bignum k
    return dict(S=S, R=R, P=P_S, design=design_S, offs=offs_S, scrp=scrp,
                Pmod=Pmod, k0=k0)

def screen(fam):
    wvd = np.zeros(W + 1)
    wvd[fam["offs"][fam["offs"] <= GTARGET // 2]] = 1.0            # target-windowed
    R0 = np.array([int((fam["k0"] * int(m)) % int(p))
                   for m, p in zip(fam["Pmod"], fam["scrp"])], np.int64)
    with open("sb", "wb") as f:
        np.array([len(fam["scrp"])], np.int64).tofile(f)
        fam["scrp"].tofile(f); fam["Pmod"].tofile(f); R0.tofile(f)
        np.array([W], np.int64).tofile(f); wvd.tofile(f)
    t0 = time.time()
    subprocess.run(["./screen_kernel2", "sb", str(NSCREEN), "so"], check=True)
    sc = np.fromfile("so")
    # validation: exact-Mertens mean of KILLED weight
    tau = math.exp(float(np.sum(np.log1p(-1.0 / fam["scrp"]))))
    nwin = int((fam["offs"] <= GTARGET // 2).sum())
    mu_pred = 2 * nwin * (1 - tau)
    print(f"  screen {NSCREEN:,} in {time.time()-t0:.0f}s | killed-wt mu={sc.mean():.1f} "
          f"(exact pred {mu_pred:.1f}) sigma={sc.std():.2f} | window {nwin} cands/side", flush=True)
    assert abs(sc.mean() - mu_pred) < 5 * sc.std() / math.sqrt(NSCREEN) * 3 + 1.5, "mean check"
    return sc

def pattern(k, fam):
    off = fam["offs"]; colmap = {int(o): i for i, o in enumerate(off)}
    kP = np.zeros(len(off), bool); kM = np.zeros(len(off), bool)
    for p, m in zip(fam["scrp"], fam["Pmod"]):
        p = int(p); r = int((k * int(m)) % p)
        for base, K in (((p - r) % p or p, kP), (r or p, kM)):
            h = base
            while h <= W:
                if h in colmap: K[colmap[h]] = True
                h += p
    return off[~kP], off[~kM]

def posterior(k, fam, dl, dr):
    lnn = float(gmpy2.log(int(k) * fam["P"]))
    q = EG * math.log(ZS) / lnn
    beta = EG * math.log(ZD) / lnn
    offs2 = PR[(PR > W) & (PR <= int(30 * L))]
    def leg(dlist):
        pmf = [(q * (1 - q) ** i, int(d)) for i, d in enumerate(dlist)]
        pW = (1 - q) ** len(dlist)
        for i, o in enumerate(offs2): pmf.append((pW * beta * (1 - beta) ** i, int(o)))
        E = sum(w * d for w, d in pmf)
        def Sf(x):
            if x <= 0: return 1.0
            n = int(np.searchsorted(dlist, x))
            if x <= W: return (1 - q) ** n
            return (1 - q) ** len(dlist) * (1 - beta) ** int(np.searchsorted(offs2, x))
        return pmf, E, Sf
    pl, EL, _ = leg(dl); pr_, ER, SR = leg(dr)
    return sum(w * SR(GTARGET - d) for w, d in pl), EL + ER

def stage_a():
    rng = np.random.default_rng(41)
    state = {}
    for name, sc_n in (("S0", 0), ("S8", 8), ("S16", 16)):
        print(f"[{name}] dropping {sc_n} edge primes", flush=True)
        fam = family(sc_n, rng)
        sc = screen(fam)
        best = np.argsort(-sc)[:TOP]
        ks = [str(fam["k0"] + int(i)) for i in best]
        samp = rng.choice(TOP, PREREG_N, replace=False)
        tot = 0.0; Em = []
        t0 = time.time()
        for j in samp:
            k = int(ks[j]); dl, dr = pattern(k, fam)
            Pk, E = posterior(k, fam, dl, dr)
            tot += Pk; Em.append(E)
        prereg = tot / PREREG_N * TOP
        print(f"  PREREGISTERED: ~{prereg:.1f} merit-6 successes in {TOP} trials | "
              f"pred mean gap {np.mean(Em):,.0f}  ({time.time()-t0:.0f}s)", flush=True)
        state[name] = dict(S=[int(x) for x in fam["S"]], k0=str(fam["k0"]),
                           ks=ks, prereg=prereg, pred_mean=float(np.mean(Em)))
    json.dump(state, open("swapstack_state.json", "w"))
    print("state saved -> stage B runs trials")

def trial(k, fam, deepT, rPT, Wside):
    n0 = int(k) * fam["P"]; Wt = 2 * Wside + 1
    alive = np.ones(Wt, bool)
    for qd in fam["design"]: alive[Wside % int(qd)::int(qd)] = False
    r0 = np.array([int((k * int(P_ % int(p))) % int(p)) for P_, p in [(fam["P"], pp) for pp in deepT]], np.int64) if False else None
    # fast residues: reuse precomputed rPT = P_S mod deepT
    r0 = (np.array([k % int(p) for p in deepT], object).astype(np.int64) * rPT) % deepT if False else None
    raise SystemExit("use stage_b path")

def stage_b():
    state = json.load(open("swapstack_state.json"))
    rng = np.random.default_rng(7)
    Wside = int(25 * L)
    for name, sc_n in (("S0", 0), ("S8", 8), ("S16", 16)):
        fam = family(sc_n, rng)          # rebuild structures (k0 differs; use stored ks)
        fam["k0"] = int(state[name]["k0"])
        deepT = np.concatenate([fam["S"], PR[(PR > ZD) & (PR <= ZT)]]).astype(np.int64)
        rPT = np.array([int(fam["P"] % int(p)) for p in deepT], np.int64)
        gaps = []
        t0 = time.time()
        for kstr in state[name]["ks"]:
            k = int(kstr); n0 = k * fam["P"]
            alive = np.ones(2 * Wside + 1, bool)
            for qd in fam["design"]: alive[Wside % int(qd)::int(qd)] = False
            kr = np.array([k % int(p) for p in deepT], np.int64)
            r0 = (kr * rPT) % deepT
            lo = (r0 - Wside) % deepT
            med = deepT < 2 * Wside + 1
            for p, rl in zip(deepT[med], lo[med]): alive[(int(p) - int(rl)) % int(p)::int(p)] = False
            idx = (deepT[~med] - lo[~med]) % deepT[~med]; hit = idx < 2 * Wside + 1
            alive[idx[hit]] = False
            so = np.flatnonzero(alive) - Wside
            order = so[np.argsort(np.abs(so), kind="stable")]
            jl = jr = None
            for j in order:
                if j == 0 or (j < 0 and jl is not None) or (j > 0 and jr is not None): continue
                c = n0 + int(j)
                if gmpy2.powmod(2, c - 1, c) == 1 and gmpy2.is_prime(c, 25):
                    if j < 0: jl = int(j)
                    else: jr = int(j)
                    if jl is not None and jr is not None: break
            gaps.append(jr - jl)
        g = np.array(gaps)
        succ = int((g >= GTARGET).sum())
        print(f"[{name}] MEASURED: {succ} successes | mean gap {g.mean():,.0f} "
              f"(prereg {state[name]['prereg']:.1f}, pred mean {state[name]['pred_mean']:,.0f}) "
              f"({time.time()-t0:.0f}s)", flush=True)

if __name__ == "__main__":
    (stage_a if sys.argv[-1] == "A" else stage_b)()
