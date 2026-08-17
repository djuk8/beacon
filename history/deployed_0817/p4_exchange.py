#!/usr/bin/env python3
"""BEACON P4 -- exchange-rate harness (conditional-swap ascent, exact posterior).

Decision instrument for the SCALE_PLAN Stage-1 DAY-6 FORK. Measures, per
anchor, how much exact-posterior mass P(gap >= GTARGET) a budget of
conditional swaps of the dropped set S buys, versus a random-walk control
with the same move set and budget. Swapstack v1 measured the conservation
law (GENERIC dropped families net-negative); P4 asks whether CONDITIONING
on the anchor turns the sign, and at what price.

Instrument lineage: pattern()/posterior() are the CERTIFIED swapstack_v1
functions, parameterized. gate_p4.py leg A proves bit-agreement with
swapstack_v1 at its exact config before any real run (doctrine: changed
code is ungated code).

MOVE SET (all moves change n0 -- fixed-truth certificate refinement is
EXCLUDED by design; see P4_NOTES.md "n0-invariance"):
  EXCHANGE(q_out in S, q_in in EDGE\\S): S'=S-{q_out}+{q_in},
      k' = round(k * q_in / q_out)          (size drift ~ 0)
  DEEPEN(q_in in EDGE\\S):  S'=S+{q_in},  k' = k * q_in   (size exact)
  RESTORE(q_out in S):      S'=S-{q_out}, k' = round(k / q_out)
Guards: S subset of EDGE pool (largest EPOOL design primes), |S| <= SMAX,
|digits(n0') - D| <= DRIFT_DIGITS.

ARMS (paired, same start anchor, same budget B of exact-posterior evals):
  guided: greedy -- each step exact-scores a seeded random shortlist of C
          legal moves, takes best if dlogP > 0, else counts a plateau step;
          stops on budget or PATIENCE consecutive plateaus.
  random: same shortlist stream, accepts a uniformly chosen legal move
          each step regardless of sign (the conservation-law control).

PRIMARY PREREGISTERED METRIC (see P4_NOTES.md): median over anchors of
paired (guided - random) log10 posterior lift at budget B, bootstrap 95% CI.
Exchange rate: accepted nats per posterior-eval and per core-second.

Resume: one atomic JSON per (anchor, arm) in --out; SIGKILL-safe; reruns
skip finished units; per-anchor seeding makes results order/parallelism
independent (gate leg C proves determinism + resume identity).
"""
import argparse, hashlib, json, math, os, subprocess, sys, time
import numpy as np, gmpy2

EG = 1.7810724179901979
LN10 = math.log(10)


# ---------------------------------------------------------------- engine
def primes_upto(n):
    s = np.ones(n + 1, bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)


class Engine:
    """swapstack_v1 machinery, parameterized. Formulas verbatim (gate leg A)."""

    def __init__(self, D, ZS, ZT, gmult=6.0, wmult=10.0, epool=64):
        self.D, self.ZS, self.ZT = int(D), int(ZS), int(ZT)
        D, ZS, ZT = self.D, self.ZS, self.ZT
        self.L = D * LN10
        self.W = int(wmult * self.L)
        self.GTARGET = int(gmult * self.L)
        self.PR = primes_upto(ZT)
        cum = np.cumsum(np.log(self.PR.astype(float)))
        i0 = int(np.searchsorted(cum, (D - 8) * LN10))
        self.ZD = int(self.PR[i0 - 1]) if cum[i0] > (D - 8) * LN10 else int(self.PR[i0])
        self.DESIGN = self.PR[self.PR <= self.ZD]
        self.P_FULL = gmpy2.mpz(1)
        for p in self.DESIGN: self.P_FULL *= int(p)
        self.EDGE = self.DESIGN[-epool:]
        self.offs2 = self.PR[(self.PR > self.W) & (self.PR <= int(30 * self.L))]
        self._mid = self.PR[(self.PR > self.ZD) & (self.PR <= self.W)]
        self._scr_mid = self.PR[(self.PR > self.ZD) & (self.PR <= self.ZS)]
        self.n_posterior_evals = 0

    def family_from_S(self, S):
        S = np.sort(np.asarray(S, np.int64))
        R = 1
        for q in S: R *= int(q)
        P_S = self.P_FULL // gmpy2.mpz(R) if len(S) else self.P_FULL
        Sset = set(int(x) for x in S)
        design_S = np.array([p for p in self.DESIGN if int(p) not in Sset], np.int64)
        offs_S = np.sort(np.concatenate([S, self._mid]))
        scrp = np.concatenate([S, self._scr_mid])
        Pmod = np.array([int(P_S % int(p)) for p in scrp], np.int64)
        return dict(S=S, R=R, P=P_S, design=design_S, offs=offs_S,
                    scrp=scrp, Pmod=Pmod)

    def pattern(self, k, fam):                      # verbatim swapstack_v1
        off = fam["offs"]; colmap = {int(o): i for i, o in enumerate(off)}
        kP = np.zeros(len(off), bool); kM = np.zeros(len(off), bool)
        for p, m in zip(fam["scrp"], fam["Pmod"]):
            p = int(p); r = int((k * int(m)) % p)
            for base, K in (((p - r) % p or p, kP), (r or p, kM)):
                h = base
                while h <= self.W:
                    if h in colmap: K[colmap[h]] = True
                    h += p
        return off[~kP], off[~kM]

    def posterior(self, k, fam, dl, dr):            # verbatim swapstack_v1
        self.n_posterior_evals += 1
        lnn = float(gmpy2.log(int(k) * fam["P"]))
        q = EG * math.log(self.ZS) / lnn
        beta = EG * math.log(self.ZD) / lnn
        offs2 = self.offs2

        def leg(dlist):
            pmf = [(q * (1 - q) ** i, int(d)) for i, d in enumerate(dlist)]
            pW = (1 - q) ** len(dlist)
            for i, o in enumerate(offs2): pmf.append((pW * beta * (1 - beta) ** i, int(o)))
            E = sum(w * d for w, d in pmf)
            def Sf(x):
                if x <= 0: return 1.0
                n = int(np.searchsorted(dlist, x))
                if x <= self.W: return (1 - q) ** n
                return (1 - q) ** len(dlist) * (1 - beta) ** int(np.searchsorted(offs2, x))
            return pmf, E, Sf
        pl, EL, _ = leg(dl); pr_, ER, SR = leg(dr)
        return sum(w * SR(self.GTARGET - d) for w, d in pl), EL + ER

    def score(self, k, fam):
        dl, dr = self.pattern(k, fam)
        P, E = self.posterior(k, fam, dl, dr)
        return P, E

    def digits(self, k, fam):
        return float(gmpy2.log10(int(k) * fam["P"]))

    # -------------------------------------------------------- screen (stage A)
    def write_blob(self, fam, k0, path="sb"):       # byte-layout == swapstack_v1
        wvd = np.zeros(self.W + 1)
        wvd[fam["offs"][fam["offs"] <= self.GTARGET // 2]] = 1.0
        R0 = np.array([int((k0 * int(m)) % int(p))
                       for m, p in zip(fam["Pmod"], fam["scrp"])], np.int64)
        with open(path, "wb") as f:
            np.array([len(fam["scrp"])], np.int64).tofile(f)
            fam["scrp"].tofile(f); fam["Pmod"].tofile(f); R0.tofile(f)
            np.array([self.W], np.int64).tofile(f); wvd.tofile(f)
        return R0

    def screen_scores(self, fam, k0, nscreen, binary=None, tag="."):
        """Killed-weight score per anchor k0+i. C kernel if given, else python
        fallback (same semantics, windowed offsets only). Blob/score files
        live under `tag` so concurrent runs never collide."""
        sb, so = os.path.join(tag, "sb"), os.path.join(tag, "so")
        if binary:
            self.write_blob(fam, k0, sb)
            subprocess.run([binary, sb, str(nscreen), so], check=True)
            return np.fromfile(so)
        R0 = self.write_blob(fam, k0, sb)
        win = fam["offs"][fam["offs"] <= self.GTARGET // 2]
        sc = np.zeros(nscreen)
        i_idx = np.arange(nscreen, dtype=np.int64)
        for p, m, r0 in zip(fam["scrp"], fam["Pmod"], R0):
            p, m, r0 = int(p), int(m), int(r0)
            if m == 0: continue
            minv = pow(m, -1, p)
            for o in (int(x) for x in win):
                # side +o killed iff r0 + i*m + o == 0 (mod p); side -o analog
                for tgt in ((-r0 - o) % p, (-r0 + o) % p):
                    j0 = (tgt * minv) % p
                    sc[j0::p] += 1.0
        return sc


# ---------------------------------------------------------------- ascent
def legal_moves(eng, S):
    Sset = set(int(x) for x in S)
    ins = [int(q) for q in eng.EDGE if int(q) not in Sset]
    outs = [int(q) for q in S]
    mv = [("X", o, i) for o in outs for i in ins]
    mv += [("D", 0, i) for i in ins]
    mv += [("R", o, 0) for o in outs]
    return mv


def apply_move(eng, S, k, mv, smax, drift, ref):
    t, qo, qi = mv
    Sset = set(int(x) for x in S)
    if t == "X":
        S2 = sorted((Sset - {qo}) | {qi}); k2 = int(round(k * qi / qo))
    elif t == "D":
        if len(Sset) >= smax: return None
        S2 = sorted(Sset | {qi}); k2 = k * qi
    else:
        S2 = sorted(Sset - {qo}); k2 = int(round(k / qo))
    if k2 < 2: return None
    fam2 = eng.family_from_S(np.array(S2, np.int64))
    if abs(eng.digits(k2, fam2) - ref) > drift: return None
    return S2, k2, fam2


def run_arm(eng, arm, S0, k0, budget, C, patience, smax, drift, seed):
    rng = np.random.default_rng(seed)
    S, k = [int(x) for x in S0], int(k0)
    fam = eng.family_from_S(np.array(S, np.int64))
    e0 = eng.n_posterior_evals
    t0 = time.time(); c0 = time.process_time()
    P, E = eng.score(k, fam)
    d0 = eng.digits(k, fam)          # size shell anchored to the unit's own start
    logP = math.log(max(P, 1e-300))
    rows = [dict(step=0, move="init", dlogP=0.0, logP=logP, P=P, Egap=E,
                 evals=eng.n_posterior_evals - e0, t_s=round(time.time() - t0, 3))]
    plateau, step, sl_ledger = 0, 0, []
    while eng.n_posterior_evals - e0 + C <= budget and plateau < patience:
        step += 1
        mvs = legal_moves(eng, S)
        idx = rng.choice(len(mvs), size=min(C, len(mvs)), replace=False)
        cands = []
        for j in idx:
            ap = apply_move(eng, S, k, mvs[j], smax, drift, d0)
            if ap is None: continue
            S2, k2, fam2 = ap
            P2, E2 = eng.score(k2, fam2)
            cands.append((math.log(max(P2, 1e-300)), mvs[j], S2, k2, fam2, P2, E2))
        sl_ledger.append(len(cands))
        if not cands: break
        if arm == "guided":
            best = max(cands, key=lambda c: c[0])
            take = best[0] > logP
        else:
            best = cands[int(rng.integers(len(cands)))]
            take = True
        if take:
            d = best[0] - logP
            logP, (_, mv, S, k, fam, P, E) = best[0], best
            rows.append(dict(step=step, move=f"{mv[0]}:{mv[1]}>{mv[2]}",
                             dlogP=d, logP=logP, P=P, Egap=E,
                             evals=eng.n_posterior_evals - e0,
                             t_s=round(time.time() - t0, 3)))
            if arm == "guided": plateau = 0
        else:
            plateau += 1
    return dict(rows=rows, final_logP=logP, final_S=S, final_k=str(k),
                evals=eng.n_posterior_evals - e0, sl_ledger=sl_ledger,
                t_s=round(time.time() - t0, 3),
                cpu_s=round(time.process_time() - c0, 3),
                lift_log10=(rows[-1]["logP"] - rows[0]["logP"]) / LN10)


def traj_hash(unit):
    s = json.dumps([[r["step"], r["move"], round(r["logP"], 12)] for r in unit["rows"]])
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--D", type=int, default=400)
    ap.add_argument("--zs", type=float, default=1e5)
    ap.add_argument("--zt", type=float, default=1e6)
    ap.add_argument("--anchors", type=int, default=120)
    ap.add_argument("--budget", type=int, default=300)
    ap.add_argument("--shortlist", type=int, default=8)
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--smax", type=int, default=24)
    ap.add_argument("--drift", type=float, default=2.0)
    ap.add_argument("--s-init", type=int, default=8)
    ap.add_argument("--nscreen", type=int, default=20000)
    ap.add_argument("--screen-bin", default=None)
    ap.add_argument("--seed", type=int, default=23)
    ap.add_argument("--out", default="p4_out")
    ap.add_argument("--max-anchors", type=int, default=None)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.smoke:
        a.anchors, a.budget, a.shortlist, a.nscreen = 4, 24, 6, 600

    os.makedirs(a.out, exist_ok=True)
    eng = Engine(a.D, a.zs, a.zt)
    rng = np.random.default_rng(a.seed)

    # stage A: one screened family provides the anchor pool (v1 semantics)
    S0 = eng.DESIGN[-a.s_init:]
    fam0 = eng.family_from_S(S0)
    R = fam0["R"]
    k0 = int(rng.integers(10 ** 6, 10 ** 7)) * R
    sc = eng.screen_scores(fam0, k0, a.nscreen, a.screen_bin, tag=a.out)
    best = np.argsort(-sc)[:a.anchors]
    anchors = [k0 + int(i) for i in best]
    json.dump(dict(config=vars(a), ZD=eng.ZD, k0=str(k0),
                   S0=[int(x) for x in S0],
                   anchors=[str(k) for k in anchors]),
              open(f"{a.out}/manifest.json", "w"), indent=1)

    n = len(anchors) if a.max_anchors is None else min(a.max_anchors, len(anchors))
    for ai in range(n):
        for arm in ("guided", "random"):
            path = f"{a.out}/a{ai:04d}_{arm}.json"
            if os.path.exists(path): continue
            unit = run_arm(eng, arm, S0, anchors[ai], a.budget, a.shortlist,
                           a.patience, a.smax, a.drift,
                           seed=a.seed * 1_000_003 + ai * 2 + (arm == "random"))
            unit["anchor_idx"], unit["arm"] = ai, arm
            unit["hash"] = traj_hash(unit)
            tmp = path + ".tmp"
            json.dump(unit, open(tmp, "w")); os.replace(tmp, path)
            print(f"[a{ai:04d} {arm:6s}] lift {unit['lift_log10']:+.3f} log10 "
                  f"| evals {unit['evals']} | {unit['t_s']:.1f}s", flush=True)

    # ------------------------------------------------------------- summary
    G, Rn = {}, {}
    for f in sorted(os.listdir(a.out)):
        if f.endswith("_guided.json"): G[f[:5]] = json.load(open(f"{a.out}/{f}"))
        if f.endswith("_random.json"): Rn[f[:5]] = json.load(open(f"{a.out}/{f}"))
    keys = sorted(set(G) & set(Rn))
    if keys:
        dg = np.array([G[x]["lift_log10"] for x in keys])
        dr = np.array([Rn[x]["lift_log10"] for x in keys])
        d = dg - dr
        bs = np.array([np.median(np.random.default_rng(9 + i).choice(d, len(d)))
                       for i in range(2000)])
        ev = sum(G[x]["evals"] for x in keys)
        ts = sum(G[x].get("cpu_s", G[x]["t_s"]) for x in keys)
        acc_nats = float(sum(max(0.0, r["dlogP"]) for x in keys for r in G[x]["rows"]))
        summ = dict(n=len(keys),
                    guided_med=float(np.median(dg)), random_med=float(np.median(dr)),
                    paired_med=float(np.median(d)),
                    ci95=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))],
                    evals=ev, core_s=round(ts, 1),
                    nats_per_eval=acc_nats / max(ev, 1),
                    nats_per_core_s=acc_nats / max(ts, 1e-9),
                    equiv_screen_factor=float(10 ** np.median(d)))
        json.dump(summ, open(f"{a.out}/summary.json", "w"), indent=1)
        print(f"\nP4 SUMMARY n={summ['n']}: paired median lift "
              f"{summ['paired_med']:+.3f} log10 [CI {summ['ci95'][0]:+.3f},"
              f"{summ['ci95'][1]:+.3f}] | guided {summ['guided_med']:+.3f} vs "
              f"random {summ['random_med']:+.3f} | {summ['nats_per_eval']:.4f} "
              f"nats/eval | {summ['nats_per_core_s']:.4f} nats/core-s | "
              f"equiv screen factor {summ['equiv_screen_factor']:.2f}x", flush=True)


if __name__ == "__main__":
    main()
