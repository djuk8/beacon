#!/usr/bin/env python3
"""arch_info.py -- architect fleet report. Run in any log directory.

Groups logs by their ACTUAL design line (D, L, scored-or-not), so mixed
batches can never contaminate a calibration again (the E=7.07 lesson).
Reports per group: cleans, censored-MLE lifts-to-clean, E_eff, survivors,
beta_eff, tests-to-first-prime. Then cross-group: score worth per design,
L-exponent refit, and the theory check beta vs e^gamma*lnQ/ln(n0).

  python3 arch_info.py            # scans *.log in cwd
  python3 arch_info.py DIR ...    # scans DIR/*.log for each DIR
"""
import glob, math, re, sys
import statistics as st

EG = math.e ** 0.5772156649015329
LN10 = math.log(10)


def scan_file(path):
    txt = open(path, errors="replace").read()
    m = re.search(r"design D=(\d+) zd=(\d+) L=(\d+) Q=([\d,]+)", txt)
    if not m:
        return None
    D, zd, L, Q = int(m.group(1)), int(m.group(2)), int(m.group(3)), \
        int(m.group(4).replace(",", ""))
    scored = "scored" if "scored" in txt.split("\n", 6)[-1][:400] or \
        re.search(r"scored [\d,]+ candidate lifts", txt) else "no-score"
    surv, tests = [], []
    clean_at, last = None, 0
    for ln in txt.splitlines():
        mm = re.search(r"lift (\d+): (\d+) survivors", ln)
        if mm:
            last = int(mm.group(1)); surv.append(int(mm.group(2)))
            t = re.search(r"after (\d+) tests", ln)
            if t: tests.append(int(t.group(1)))
            if "REALIZED" in ln or "CLEAN CORE" in ln:
                clean_at = last
    mf = re.search(r"(\d+)/\d+ lifts failed", txt)
    lifts = clean_at if clean_at else (int(mf.group(1)) if mf else last)
    finds = re.findall(r"REALIZED gap ([\d,]+).*merit ([\d.]+)", txt)
    return dict(D=D, zd=zd, L=L, Q=Q, scored=scored, surv=surv,
                tests=tests, clean_at=clean_at, lifts=lifts,
                finds=[(int(g.replace(",", "")), float(mm)) for g, mm in finds])


def group_key(r):
    return (r["D"], r["L"], r["scored"])


def report(key, rows):
    D, L, scored = key
    n_clean = sum(1 for r in rows if r["clean_at"])
    lifts = sum(r["lifts"] for r in rows)
    surv = [s for r in rows for s in r["surv"]]
    tests = [t for r in rows for t in r["tests"]]
    cleans = sorted(r["clean_at"] for r in rows if r["clean_at"])
    print(f"\n=== D={D:,} L={L:,} [{scored}]  {len(rows)} workers, "
          f"{n_clean} cleans, ~{lifts:,} lifts")
    ln_n0 = D * LN10
    beta_th = EG * math.log(rows[0]["Q"]) / ln_n0
    ms = st.mean(surv) if surv else 0
    if surv:
        print(f"  survivors  mean {ms:,.0f}  sd {st.pstdev(surv):.0f}  "
              f"(n={len(surv)})   floor merit {2*L/ln_n0:.2f}")
        print(f"  E_theory = surv x beta_th = {ms*beta_th:.2f}   "
              f"(beta_th = e^g lnQ/ln n0 = {beta_th:.5f})")
    if cleans:
        mle = lifts / n_clean
        print(f"  lifts-to-clean {cleans}")
        print(f"  censored-MLE mean {mle:,.0f}   E_eff {math.log(mle):.2f}"
              f"   beta_eff {math.log(mle)/ms:.5f}" if ms else "")
        if surv:
            d = ms * beta_th - math.log(mle)
            print(f"  Delta-E vs theory = {d:+.2f}  "
                  f"({'score/selection effect' if scored=='scored' else 'theory anchor'})")
    if tests:
        print(f"  tests-to-first-prime mean {st.mean(tests):.0f} "
              f"(SE ~{st.mean(tests)/max(len(tests),1)**.5:.0f})")
    gaps = sorted((g for r in rows for g, _ in r["finds"]), reverse=True)
    if gaps:
        print(f"  finds: {len(gaps)}  largest {gaps[0]:,}  "
              f"({', '.join(f'{g:,}' for g in gaps[:6])}{'...' if len(gaps)>6 else ''})")
    return dict(ms=ms, mle=(lifts / n_clean if n_clean else None),
                n_clean=n_clean, lifts=lifts)


def main():
    dirs = sys.argv[1:] or ["."]
    rows = []
    for d in dirs:
        for f in glob.glob(f"{d}/*.log"):
            r = scan_file(f)
            if r: rows.append(r)
    if not rows:
        sys.exit(f"no parseable logs in {dirs} -- is this the right directory?")
    groups = {}
    for r in rows:
        groups.setdefault(group_key(r), []).append(r)
    out = {}
    for key in sorted(groups):
        out[key] = report(key, groups[key])

    # cross-group: score worth, per identical (D, L)
    print()
    for (D, L) in sorted({(k[0], k[1]) for k in out}):
        a, b = out.get((D, L, "scored")), out.get((D, L, "no-score"))
        if a and b and a["mle"] and b["mle"]:
            print(f"SCORE WORTH at D={D:,} L={L:,}: {b['mle']/a['mle']:.2f}x "
                  f"fewer lifts  [control: {b['n_clean']} cleans in "
                  f"{b['lifts']:,} lifts -- CI is wide below ~5 cleans]")
        elif a and b and b["mle"] is None:
            lo = b["lifts"] / 3.0        # 0 cleans: 95% lower bound ~ N/3
            print(f"SCORE WORTH at D={D:,} L={L:,}: control has 0 cleans in "
                  f"{b['lifts']:,} lifts -> control mean > {lo:,.0f} (95%), "
                  f"worth > {lo/a['mle']:.1f}x" if a["mle"] else "")

    # L-exponent refit across scored groups at the same D
    for D in sorted({k[0] for k in out}):
        pts = sorted((k[1], v["ms"]) for k, v in out.items()
                     if k[0] == D and k[2] == "scored" and v["ms"])
        if len(pts) >= 2:
            (L1, s1), (L2, s2) = pts[0], pts[-1]
            a = math.log(s2 / s1) / math.log(L2 / L1)
            print(f"L-EXPONENT at D={D:,}: surv ~ L^{a:.2f} from L={L1:,}"
                  f"->{L2:,}  (record math assumed 1.64; E at the merit-32 "
                  f"design scales accordingly)")


if __name__ == "__main__":
    main()
