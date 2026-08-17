#!/usr/bin/env python3
"""architect_v0 -- designed prime deserts. The constructive tier, stage 1.

Model: n0 = k * P#(zd) / d, candidates n0 + j for odd j in [-L, L].
  * base comb: every odd p <= zd with p not in the swap set divides n0,
    so p kills j = 0 mod p. Free coverage, no budget.
  * steerable combs: the swap set S (primes divided out of P via d) and the
    middle primes q in (zd, Q]. For each, k's residue chooses WHERE the
    comb lands: prime r kills j = t_r (mod r) for a t_r WE pick.
  * THE BUDGET: k has only D - digits(P/d) digits of entropy, so
    sum(log10(r)) over steered primes must fit inside it. Every swapped
    prime p adds log10(p) of budget back -- the divisor trick of every
    top record, priced exactly instead of chosen by folklore (paper 1).

Greedy v0: steer primes ascending, accepting a comb while its marginal
kills-per-digit beat the sniper rate (one kill per ~6 digits from large
primes), then snipe leftovers. Optimal selection under the budget is the
research knob the pilot explores with the certified posterior.

Verification is not optional: every claimed kill is re-proven by explicit
divisibility on the reconstructed n0, survivors are PRP-tested, and if all
are composite the realized gap is measured by walking the fences outward.

  python3 architect_v0.py --digits 1000 --zd 97 --L 4000 --Q 200000 \
      --swap 3,5,7 --seed 1 --realize
"""
import argparse, math, random, sys, time
import numpy as np, gmpy2

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass


def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.nonzero(s)[0]


def design(D, zd, L, Q, swap, seed, verbose=True):
    rng = random.Random(seed)
    pr = primes_upto(Q)
    base = [int(p) for p in pr[pr <= zd]]
    assert 2 in base, "keep 2 in the primorial (odd-candidate model)"
    swap = sorted(set(swap))
    for p in swap:
        assert p in base and p != 2, f"swap prime {p} must be an odd base prime"
    P = gmpy2.mpz(1)
    for p in base: P *= p
    d = 1
    for p in swap: d *= p
    P_eff = P // d
    digP = len(gmpy2.digits(P_eff, 10))
    budget = (D - 1) - digP - 1          # digits of k entropy, one digit margin
    assert budget > 3, f"no design budget at D={D} (P/d has {digP} digits)"

    # candidates: odd j in [-L, L] -> index i = (j + L) // 2 needs L even; use
    # j = -L+1, -L+3, ..., L-1  (n = L odd offsets each side of 0 exclusive)
    js = np.arange(-L + 1, L, 2, dtype=np.int64)
    alive = np.ones(len(js), dtype=bool)
    # base comb (free): odd base primes not swapped kill j = 0 mod p
    for p in base:
        if p == 2 or p in swap: continue
        alive[js % p == 0] = False
    n_base = int(alive.sum())

    # steerable: swap primes first (they ADD budget), then middles ascending
    steer = [(int(p), True) for p in swap] + \
            [(int(q), False) for q in pr[pr > zd]]
    plan, used, spent = [], 0.0, []
    SNIPE = math.log10(Q)                 # cost of one late sniper kill
    for r, is_swap in steer:
        if not alive.any(): break
        # v1 FIX: a swapped prime refunds its entropy via the divisor (the
        # budget is already log10(d) bigger), but it STILL multiplies into the
        # CRT modulus M. Charging it 0 let M overrun the k range: the 6-swap
        # crash, and the 2-3-value t range that made lifts repeat. Charge
        # every steered prime log10(r) against the (already-refunded) budget,
        # and keep HEADROOM digits so >= 10^HEADROOM distinct lifts exist.
        HEADROOM = 4.0
        eff_cost = math.log10(r)
        if used + eff_cost > budget - HEADROOM: continue
        idx = np.nonzero(alive)[0]
        if len(idx) == 0: break
        cls = js[idx] % r
        counts = np.bincount(cls, minlength=r)
        t = int(counts.argmax()); kills = int(counts[t])
        if kills == 0: continue
        # accept if better than sniping later, or it's free (swap)
        if not is_swap and kills / eff_cost < 1.0 / SNIPE and r > L:
            continue
        alive[idx[cls == t]] = False
        plan.append((r, t, kills, is_swap))
        used += eff_cost
        spent.append((r, kills))
    n_left = int(alive.sum())
    if verbose:
        print(f"design D={D} zd={zd} L={L} Q={Q:,} swap={swap or '-'} "
              f"seed={seed}")
        print(f"  P#/d: {digP} digits | k budget: {budget} digits | "
              f"spent {used:.1f}")
        print(f"  candidates {len(js):,} -> base comb {n_base:,} -> "
              f"steered {n_left:,} survivors "
              f"({len(plan)} combs: {sum(1 for *_, s in plan if s)} swap + "
              f"{sum(1 for *_, s in plan if not s)} middle)")
    return dict(P_eff=P_eff, d=d, plan=plan, js=js, alive=alive,
                budget=budget, used=used, base=base, swap=swap, D=D,
                zd=zd, L=L, Q=Q, rng=rng)


def prep_lift(dz):
    """CRT once; precompute per-prime residue tables so any candidate t can be
    scored or lifted in vector ops. k(t) = r + M*(t0 + t), and
    k mod p = (A_p + B_p * (t mod p)) mod p with A,B precomputed int64."""
    D, P_eff = dz["D"], dz["P_eff"]
    M, r = gmpy2.mpz(1), gmpy2.mpz(0)
    for (p, t, _, _) in dz["plan"]:
        inv = gmpy2.invert(P_eff % p, p)
        kp = (-t * inv) % p
        r = r + M * ((kp - r) * gmpy2.invert(M % p, p) % p)
        M *= p
    lo = 10 ** (D - 1) // P_eff + 1
    hi = 10 ** D // P_eff - 1
    assert M < hi - lo, "budget accounting failed: CRT modulus exceeds k range"
    t0 = (lo - r + M - 1) // M
    span = int((hi - r) // M - t0 + 1)
    pr = primes_upto(dz["Q"]); pr = pr[pr > 2].astype(np.int64)
    A = np.array([int((r + M * t0) % int(p)) for p in pr], dtype=np.int64)
    B = np.array([int(M % int(p)) for p in pr], dtype=np.int64)
    PE = np.array([int(P_eff % int(p)) for p in pr], dtype=np.int64)
    dz.update(crt_r=r, crt_M=M, crt_t0=t0, span=span,
              pr=pr, prA=A, prB=B, prPE=PE,
              js_surv=dz["js"][dz["alive"]].astype(np.int64))
    return dz


def incidental_survivors(dz, t, qmax=None):
    """Design survivors still alive after incidental kills from all odd
    p <= qmax, for candidate lift index t. Vectorized; no primality."""
    pr, A, B, PE = dz["pr"], dz["prA"], dz["prB"], dz["prPE"]
    if qmax is not None:
        m = pr <= qmax
        pr, A, B, PE = pr[m], A[m], B[m], PE[m]
    n0mod = ((A + B * (t % pr)) % pr) * PE % pr        # n0 mod p, all p
    js = dz["js_surv"]
    alive = np.ones(len(js), dtype=bool)
    CH = 4096
    for i in range(0, len(pr), CH):                    # chunk for memory
        sl = slice(i, i + CH)
        dead = ((js[:, None] + n0mod[None, sl]) % pr[None, sl] == 0).any(axis=1)
        alive &= ~dead
    return js[alive]


def crt_lift(dz, t=None):
    """Pick or accept a lift index t; return the corresponding k.
    Draws WITHOUT replacement so every lift is distinct."""
    if "span" not in dz:
        prep_lift(dz)
    rng = dz["rng"]
    used_t = dz.setdefault("t_used", set())
    if t is None:
        assert len(used_t) < dz["span"], "lift space exhausted (raise HEADROOM)"
        while True:
            t = rng.randrange(dz["span"])
            if t not in used_t: break
    used_t.add(t)
    k = int(dz["crt_r"] + dz["crt_M"] * (dz["crt_t0"] + t))
    return k, t


def verify_and_realize(dz, k, kt, max_prp=4000, mr=25, realize=True,
                       early_exit=True):
    """Re-prove every kill by divisibility, PRP survivors, walk the fences."""
    P_eff, js, alive = dz["P_eff"], dz["js"], dz["alive"]
    n0 = k * P_eff
    # 1) every steered kill really divides
    for (p, t, _, _) in dz["plan"]:
        assert (n0 + t) % p == 0, f"comb {p} misplaced"
    # 2) base comb spot check
    for p in dz["base"][:8]:
        if p != 2 and p not in dz["swap"]:
            assert n0 % p == 0
    # 3) INCIDENTAL combs: every prime <= Q not steered still divides
    #    n0 + j somewhere now that k is fixed. Apply them all -- the true
    #    survivor set shrinks (free kills), and claims match arithmetic.
    surv = [int(j) for j in incidental_survivors(dz, kt)]
    prp_used, interior_primes = 0, []
    order = list(surv)
    dz["rng"].shuffle(order)             # random order -> unbiased early exit
    for j in order:
        c = n0 + j
        prp_used += 1
        if gmpy2.powmod(2, c - 1, c) == 1 and gmpy2.is_prime(c, mr):
            interior_primes.append(j)
            if early_exit:
                break                    # failed lift: stop at first prime
    core_clean = not interior_primes
    out = dict(n0_digits=len(gmpy2.digits(n0, 10)), survivors=len(surv),
               surv_js=surv, interior_primes=interior_primes,
               core_clean=core_clean, prp_used=prp_used)
    if not (realize and core_clean):
        return out
    # 4) fences: walk outward past +-L; base+steered combs pre-sieve cheaply
    def fence(direction):
        nonlocal prp_used
        j = dz["L"] + 1 if direction > 0 else -dz["L"] - 1
        combs = [(p, 0) for p in dz["base"] if p != 2 and p not in dz["swap"]]
        combs += [(p, t) for (p, t, _, _) in dz["plan"]]
        while prp_used < max_prp:
            if j % 2 == 0:
                j += 2 * direction; continue
            if any((j - t) % p == 0 for (p, t) in combs):
                j += 2 * direction; continue
            c = n0 + j
            prp_used += 1
            if gmpy2.powmod(2, c - 1, c) == 1 and gmpy2.is_prime(c, mr):
                return j
            j += 2 * direction
        return None
    jr, jl = fence(+1), fence(-1)
    if jl is not None and jr is not None:
        gap = jr - jl
        merit = gap / float(gmpy2.log(n0))
        out.update(jl=jl, jr=jr, gap=gap, merit=merit)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, default=1000)
    ap.add_argument("--zd", type=int, default=97)
    ap.add_argument("--L", type=int, default=4000)
    ap.add_argument("--Q", type=int, default=200_000)
    ap.add_argument("--swap", default="", help="comma list, e.g. 3,5,7")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lifts", type=int, default=8,
                    help="k lifts to try until the core PRPs clean")
    ap.add_argument("--score", type=int, default=0,
                    help="score this many candidate lifts by incidental kills "
                         "(cheap, no primality) and lift best-first. 0 = off.")
    ap.add_argument("--score-q", type=int, default=20000,
                    help="prime depth for the cheap score")
    ap.add_argument("--lift-seed", type=int, default=None,
                    help="seed for the lift stream only; same --seed + "
                         "different --lift-seed = identical design, disjoint "
                         "k streams for parallel workers")
    ap.add_argument("--realize", action="store_true")
    a = ap.parse_args()
    swap = [int(x) for x in a.swap.split(",") if x]
    t0 = time.time()
    dz = design(a.digits, a.zd, a.L, a.Q, swap, a.seed)
    if a.lift_seed is not None:
        dz["rng"] = random.Random(a.lift_seed)
    prep_lift(dz)
    order = None
    if a.score:
        ts = dz["rng"].sample(range(dz["span"]), min(a.score, dz["span"]))
        sc = [(len(incidental_survivors(dz, t, qmax=a.score_q)), t) for t in ts]
        sc.sort()
        order = [t for _, t in sc]
        print(f"  scored {len(ts):,} candidate lifts to q<={a.score_q:,}: "
              f"proxy survivors {sc[0][0]}..{sc[-1][0]} "
              f"(median {sc[len(sc)//2][0]})  [{time.time()-t0:.0f}s]")
    fails = 0
    for att in range(1, a.lifts + 1):
        k, kt = crt_lift(dz, t=(order[att - 1] if order and att <= len(order)
                                else None))
        r = verify_and_realize(dz, k, kt, realize=a.realize)
        if r.get("gap"):
            print(f"  lift {att}: {r['survivors']} survivors, CLEAN -> "
                  f"REALIZED gap {r['gap']:,} "
                  f"(jl={r['jl']}, jr={r['jr']}) merit {r['merit']:.3f} "
                  f"at {r['n0_digits']} digits  [{time.time()-t0:.0f}s]")
            print(f"  reconstruction: k*{a.zd}#/{dz['d']}{r['jl']:+d} .. "
                  f"{r['jr']:+d}  (k = {len(str(k))} digits, t = {kt})")
            fn = (f"find_D{a.digits}_g{r['gap']}_zd{a.zd}"
                  f"_ls{a.lift_seed if a.lift_seed is not None else a.seed}.txt")
            with open(fn, "w") as fh:
                fh.write(f"# gap {r['gap']} merit {r['merit']:.6f} "
                         f"digits {r['n0_digits']}\n")
                fh.write(f"# design D={a.digits} zd={a.zd} L={a.L} Q={a.Q} "
                         f"swap={a.swap} seed={a.seed} "
                         f"lift_seed={a.lift_seed} t={kt}\n")
                fh.write(f"# jl {r['jl']} jr {r['jr']} d {dz['d']}\n")
                fh.write(f"# SUBMIT: {r['gap']} {r['merit']:.6f} "
                         f"<k> * {a.zd}# / {dz['d']} {r['jl']:+d}\n")
                fh.write(f"k={k}\n")
            print(f"  find written to {fn}  (contains full k -- the record "
                  f"is only complete with this file)")
            return
        if r["core_clean"]:
            print(f"  lift {att}: {r['survivors']} survivors, CLEAN CORE "
                  f"verified (design-only; rerun with --realize to walk "
                  f"the fences)  [{time.time()-t0:.0f}s]")
            return
        fails += 1
        if att <= 10 or att % 50 == 0:
            print(f"  lift {att}: {r['survivors']} survivors, interior prime "
                  f"at {r['interior_primes'][0]} after {r['prp_used']} tests "
                  f"-> re-lifting")
    print(f"  {fails}/{a.lifts} lifts failed; E[interior primes] too high. "
          f"Shrink L, raise --lifts, or add swap/Q.")


if __name__ == "__main__":
    main()
