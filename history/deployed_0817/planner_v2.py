"""Planner v2 -- prices the campaign on the EXACT anchored-trial structure
validated by M1a live fire (shredder, 2026-07):

  trial gap = 2*zd (desert floor, the theta(z) anchoring subsidy)
              + two excess legs over PRIME offsets j > zd,
  each prime offset is prime with prob beta = e^gamma * ln(zd) / ln(n0)
  (Mertens tilt; HL pair corrections disclosed as ~few %, --beta-scale to probe).

Validated at D=3000, z=1e8, N=20: all gaps >= 2*zd; mean gap pred 21,986 vs
meas 20,735; tests pred 421 vs meas 348. beta_eff/beta = 1.17 (within noise;
pinned by the 200-trial run).

Reads: prime-gap-list/allgaps.sql (claimed slots). PRP curve: shredder fit.
Usage: python3 planner_v2.py [--beta-scale 1.0]
"""
import argparse, math, sqlite3
import numpy as np

A_FIT, B_FIT = 2.147e-10, 2.514          # shredder PRP fit (livefire bench)
T_prp = lambda D: A_FIT * D ** B_FIT
EGAM = 1.7810724179901979                # e^gamma
PI_Z = {1e9: 50_847_534, 1e10: 455_052_511, 1e11: 4_118_054_813}
SIEVE_NS_PER_PRIME = 3e-9
LN10 = math.log(10)

def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

PR = primes_upto(1_500_000)
LOGP = np.log(PR.astype(float))
CUM = np.cumsum(LOGP)

def zd_for(D):
    """largest prime with theta(zd) <= (D-8)*ln10 (matches livefire build_base)."""
    i = int(np.searchsorted(CUM, (D - 8) * LN10))
    return int(PR[i - 1]) if CUM[min(i, len(CUM)-1)] > (D-8)*LN10 else int(PR[i])

def gap_pmf(D, beta_scale):
    L = D * LN10
    zd = zd_for(D)
    beta = beta_scale * EGAM * math.log(zd) / L
    offs = PR[PR > zd]
    K = int(16 / beta)
    assert K < len(offs), "extend prime sieve"
    offs = offs[:K]
    mass = beta * (1 - beta) ** np.arange(K)
    A = np.zeros(int(offs[-1]) + 1)
    np.add.at(A, offs, mass)
    n = 1 << int(math.ceil(math.log2(2 * len(A))))
    g = np.fft.irfft(np.fft.rfft(A, n) ** 2, n)      # sum of two legs
    g = np.clip(g, 0, None)
    return zd, beta, g                                # gap s = index (desert included: offsets ARE distances)

def beat_array(claimed, n, D):
    b = np.ones(n, dtype=np.float64)
    for s, d in claimed.items():
        if s < n and d <= D:
            b[s] = 0.0
    return b

def price(D, z, claimed, beta_scale):
    L = D * LN10
    zd, beta, g = gap_pmf(D, beta_scale)
    b = beat_array(claimed, len(g), D)
    R = float(np.dot(g, b))
    s_idx = np.arange(len(g))
    merit_mean = float(np.dot(g * b, s_idx)) / (R * L) if R else 0.0
    tests = 2 * (math.log(zd) / math.log(z)) / beta
    t_trial = tests * T_prp(D) + PI_Z[z] * SIEVE_NS_PER_PRIME
    return dict(D=D, z=z, zd=zd, tests=int(tests), t_trial=t_trial,
                mean_gap_L=float(np.dot(g, s_idx)) / L,
                trials_per_rec=1 / R if R else float("inf"),
                coredays_per_rec=t_trial / R / 86400 if R else float("inf"),
                rec_per_coreday=R * 86400 / t_trial,
                mean_merit=merit_mean)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beta-scale", type=float, default=1.0)
    a = ap.parse_args()
    con = sqlite3.connect(":memory:")
    con.executescript(open("prime-gap-list/allgaps.sql").read())
    claimed = {}
    for s, d in con.execute("SELECT gapsize, primedigits FROM gaps WHERE primecat='C'"):
        claimed[s] = min(d, claimed.get(s, 10 ** 9))
    rows = [price(D, z, claimed, a.beta_scale)
            for D in range(8000, 26001, 2000) for z in PI_Z]
    rows.sort(key=lambda r: -r["rec_per_coreday"])
    print(f"beta_scale = {a.beta_scale}  (1.0 = Mertens; livefire N=20 hinted ~1.17)")
    for r in rows[:12]:
        print(f"D={r['D']:>6,} z={r['z']:.0e} zd={r['zd']:>6,} trial={r['t_trial']:>6.0f}s "
              f"tests={r['tests']:>5} gap~{r['mean_gap_L']:.2f}L trials/rec={r['trials_per_rec']:>6.1f} "
              f"coredays/rec={r['coredays_per_rec']:>5.2f} rec/coreday={r['rec_per_coreday']:.3f} "
              f"merit={r['mean_merit']:.2f}")

if __name__ == "__main__":
    main()
