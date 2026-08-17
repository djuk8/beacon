"""Planner v0 -- prices gap-hunt operating points against the live record table.
Model (disclosed): Cramer baseline r=1, kappa=1, SIZE-BIASED straddling gap ~ Gamma(2,L); trial = anchor at D digits,
sieve to z, PRP outward until both nearest primes found; realized gap ~ Exp(L).
Inputs: measured T_prp fit (prp_fit.npy), allgaps.sql, sieve/memory constants.
Output: records/core-day landscape, optimal (D, z), merit + beats profile.
Re-run on target hardware: python3 planner_v0.py
"""
import sqlite3, math, numpy as np
a_fit, b_fit = np.load('prp_fit.npy')
T_prp = lambda D: a_fit * D**b_fit
EGAMMA = 0.5614594836
PI_Z   = {1e8: 5_761_455, 1e9: 50_847_534, 1e10: 455_052_511, 1e11: 4_118_054_813}
SIEVE_NS_PER_PRIME = 3e-9
con = sqlite3.connect(':memory:'); con.executescript(open('prime-gap-list/allgaps.sql').read())
claimed = {}
for g,d in con.execute("SELECT gapsize, primedigits FROM gaps WHERE primecat='C'"):
    claimed[g] = min(d, claimed.get(g, 10**9))
def price(D, z):
    L = D*math.log(10); F = EGAMMA/math.log(z); tests = 2*F*L
    t_trial = tests*T_prp(D) + PI_Z[z]*SIEVE_NS_PER_PRIME
    R = msum = beats = 0.0
    for s in range(2, int(40*L)+1, 2):
        # straddle-corrected: anchor sits inside its gap -> size-biased Gamma(2,L)
        w = (2*s/(L*L))*math.exp(-s/L); c = claimed.get(s)
        if c is None or c > D:
            R += w; msum += w*(s/L)
            if c is not None: beats += w
    return dict(D=D, z=z, t_trial=t_trial, tests=int(tests),
                rec_per_coreday=R*86400/t_trial, trials_per_rec=1/R if R else float('inf'),
                coredays_per_rec=t_trial/R/86400 if R else float('inf'),
                mean_merit=msum/R if R else 0, beat_frac=beats/R if R else 0)
if __name__ == '__main__':
    rows=[price(D,z) for D in range(6000,30001,2000) for z in PI_Z]
    rows.sort(key=lambda r:-r['rec_per_coreday'])
    for r in rows[:14]:
        print(f"D={r['D']:>6,} z={r['z']:.0e} trial={r['t_trial']:>6.0f}s tests={r['tests']:>5} "
              f"trials/rec={r['trials_per_rec']:>7.1f} coredays/rec={r['coredays_per_rec']:>6.2f} "
              f"rec/coreday={r['rec_per_coreday']:.3f} merit={r['mean_merit']:.2f} beats={100*r['beat_frac']:.1f}%")
