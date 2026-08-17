#!/usr/bin/env python3
"""Asymmetric-abandon pricer -- computes the optimal abandon threshold theta*
and its cost multiplier for a targeted gap hunt (frozen BEACON model).

Protocol: scan side A to its fence at d_A; abandon unless d_A >= theta*.
Multiplier = [2/(1+S(theta))] * [P_theta/P*].  Ceiling 2x (one leg always paid).
Validated: model 1.216x/1.287x vs empirical replay 1.319x/1.307x on the
N=500 shredder livefire log (M>=5 / M>=6). Harvest regime prices to 1.000x
(target below mean gap) -- protocol is for TARGETED sieges only.

Usage: python3 abandon_pricer.py --digits 3000 --merit 10
"""
import argparse, math
import numpy as np
EG = 1.7810724179901979
LN10 = math.log(10)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, required=True)
    ap.add_argument("--merit", type=float, required=True)
    a = ap.parse_args()
    D, M = a.digits, a.merit
    L = D * LN10; G = int(M * L)
    lim = max(600_000, G + 10)
    s = np.ones(lim + 1, bool); s[:2] = False
    for i in range(2, int(lim ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    PR = np.flatnonzero(s).astype(np.int64)
    CUM = np.cumsum(np.log(PR.astype(float)))
    i = int(np.searchsorted(CUM, (D - 8) * LN10)); zd = int(PR[max(i - 1, 0)])
    offs = PR[(PR > zd) & (PR <= G)]
    beta = EG * math.log(zd) / L; l1b = math.log1p(-beta)
    n = np.arange(len(offs)); cnt2 = np.searchsorted(offs, G - offs)
    logt = math.log(beta) + l1b * (n + cnt2)
    logPs = np.logaddexp.reduce(np.append(logt, l1b * len(offs)))
    best = (1.0, 0)
    for th in offs[::max(1, len(offs) // 800)]:
        keep = offs >= th
        logPt = np.logaddexp.reduce(np.append(logt[keep], l1b * len(offs))) if keep.any() else l1b * len(offs)
        S = math.exp(l1b * np.searchsorted(offs, th))
        m = (2.0 / (1.0 + S)) * math.exp(logPt - logPs)
        if m > best[0]: best = (m, int(th))
    m, th = best
    print(f"D={D:,}  M={M}  zd={zd:,}  ->  theta* = {th:,}  multiplier = {m:.3f}x")
    print(f"rule: abandon any trial whose FIRST fence lands closer than {th:,} to the anchor")

if __name__ == "__main__":
    main()
