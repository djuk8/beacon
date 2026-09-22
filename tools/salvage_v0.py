#!/usr/bin/env python3
"""salvage_v0.py v0.3 (2026-08-24) -- per-manifest cfg/core (mixed venues safe); NEVER moves a manifest it
did not walk or fully account for; empty-ks and foreign-venue fossils stay in place, loudly.
v0.3.1: archive names keep the hunt-dir prefix (basename collisions across dirs were silently
overwriting archived fossils); ledger lines carry a UTC timestamp as column 6 (loader ignores extras).
v0.2 -- harvest realized gaps from ring-N casualties.
v0.2 LIVE-LEDGER: finds are appended to salvage_finds.log IMMEDIATELY
(flushed + fsynced) after each walk, not at end-of-run -- a killed or
restarted sweep can no longer lose ledger entries and re-walk old ks.
A lockfile (.salvage.lock) refuses concurrent sweeps. Duplicate lines
already in the log are harmless (the loader dedups); never rewrite it.
Span-exceeders ("RECORD-CLASS?") are deliberately NOT ledgered so a
wider --span rerun retries them.

Every k that reaches ring 5 has a certified prime-free core (campaign
rounds 1..r-1); the ring prime that killed it usually lands on ONE
side, leaving the other side's fence far out. This walks the true
fences and banks the realized gap. Zero GPU; ~1-2 core-min per k.

  python3 salvage_v0.py            # scan hunt_s*/sc_r05_*.manifest.json
  python3 salvage_v0.py --span 220000
Outputs: salvage_finds.log + one find_salvage_*.txt per k (all gaps
reported; find files for gap >= --floor, default 155,000).
NOTE: the certified core rests on campaign fold certification; the
portal notary independently re-proves endpoints AND re-sieves the full
interior at submission, so salvage claims get the same referee as any
find. Freeze discipline: this BANKS, it does not submit.
"""
import argparse, glob, json, math, os, time, sys
import numpy as np, gmpy2
sys.set_int_max_str_digits(2000000)

LOCK = ".salvage.lock"


def primes_upto(n):
    s = np.ones(n+1, dtype=bool); s[:2] = False
    for i in range(2, int(n**.5)+1):
        if s[i]: s[i*i::i] = False
    return np.nonzero(s)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--span", type=int, default=200000)
    ap.add_argument("--floor", type=int, default=155000)
    ap.add_argument("--ring", type=int, default=5,
                    help="walk casualties of this ring (5=finalist shell, 4/3=crumb tiers)")
    ap.add_argument("--glob", default=None)
    a = ap.parse_args()
    if a.glob is None:
        a.glob = f"hunt_s*/sc_r{a.ring:02d}_*.manifest.json"
    mans = sorted(glob.glob(a.glob))
    if not mans:
        print("no manifests found for", a.glob); return
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
    except FileExistsError:
        pid = open(LOCK).read().strip()
        print(f"another salvage run holds {LOCK} (pid {pid}); "
              f"if that pid is dead, rm {LOCK} and rerun")
        return
    try:
        run(a, mans)
    finally:
        try: os.remove(LOCK)
        except FileNotFoundError: pass


def run(a, mans):
    done = set()
    try:
        for ln in open("salvage_finds.log"):
            done.add(int(ln.split()[2]))
    except FileNotFoundError:
        pass
    os.makedirs("salvaged", exist_ok=True)
    ledger = open("salvage_finds.log", "a", buffering=1)
    cfg = json.load(open(mans[0]))["cfg"]
    zd, d = cfg["zd"], cfg["d"]
    print(f"salvage v0.3: {len(mans)} manifests, zd={zd} d={d} "
          f"span +/-{a.span} (core read PER MANIFEST -- venues may coexist)")
    prs = primes_upto(10**6)
    P = gmpy2.mpz(1); p = gmpy2.mpz(2)
    while p <= zd: P *= p; p = gmpy2.next_prime(p)
    P_eff = P//d
    PEm = np.array([int(P_eff % int(q)) for q in prs], dtype=np.int64)
    out = []
    n_walked = n_skipped = n_empty = 0
    for mf in mans:
        man = json.load(open(mf))
        mc = man["cfg"]; rnd = int(man["round"])
        core = mc["edges"][rnd - 2] if rnd >= 2 else 0
        if mc["zd"] != zd or mc["d"] != d:
            print(f"{mf}: SKIP (different venue zd={mc['zd']} d={mc['d']}) -- left in place"); n_skipped += 1; continue
        if not man["ks"]:
            print(f"{mf}: EMPTY ks list -- left in place for inspection"); n_empty += 1; continue
        pending = [int(k) for k in man["ks"] if int(k) not in done]
        if not pending:
            # every k already ledgered: this alone justifies archiving
            os.rename(mf, "salvaged/" + mf.replace("/", "__")); n_skipped += 1
            continue
        n_walked += 1
        unresolved = False
        for k in pending:
            done.add(k)
            t0 = time.time()
            n0 = gmpy2.mpz(k)*P_eff
            ln = float(gmpy2.log(n0))
            n0m = (k % prs)*PEm % prs
            S = a.span
            js = np.arange(-S, S+1, dtype=np.int64)
            alive = np.ones(len(js), dtype=bool)
            par = int(n0 % 2)
            alive[(js % 2) != (0 if par else 1)] = False
            W = 2*S+1; small = prs[prs <= W]
            for i in range(1, len(small)):
                q = int(small[i]); j0 = (-int(n0m[i])) % q
                st = -S+((j0-(-S)) % q); alive[st+S::q] = False
            big = prs[len(small):]; m = n0m[len(small):]
            j0 = (-m) % big
            st = -S+((j0-(-S)) % big); ok = st <= S
            alive[(st[ok]+S).astype(np.int64)] = False
            idx = np.nonzero(alive)[0]-S
            def walk(sign):
                side = idx[idx > core] if sign > 0 else -idx[idx < -core]
                side.sort()
                for x in side:
                    j = int(x)*sign; n = n0+j
                    if gmpy2.powmod(2, n-1, n) == 1 and gmpy2.is_prime(n, 25):
                        return j
                return None
            jr = walk(+1); jl = walk(-1)
            if jr is None or jl is None:
                print(f"k={k}: fence beyond span (RECORD-CLASS?) -- "
                      f"rerun with --span {a.span+100000}")
                unresolved = True; continue
            gap = jr-jl; merit = gap/ln
            line = (f"k={k}: GAP {gap:,} merit {merit:.4f} "
                    f"(jl {jl} jr {jr}) [{time.time()-t0:.0f}s]")
            print(line); out.append((gap, merit, k, jl, jr))
            ledger.write(f"{gap} {merit:.4f} {k} {jl} {jr} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
            ledger.flush(); os.fsync(ledger.fileno())
            if gap >= a.floor:
                with open(f"find_salvage_D2702_g{gap}.txt", "w") as f:
                    f.write(f"gap {gap} merit {merit:.6f} k={k} zd={zd} "
                            f"d={d} jl={jl} jr={jr} core_certified={core} "
                            f"channel=salvage\n")
        if unresolved:
            print(f"{mf}: KEPT in place (span-exceeder pending wider sweep)")
        else:
            os.rename(mf, "salvaged/" + mf.replace("/", "__"))
    ledger.close()
    out.sort(reverse=True)
    print(f"walked {n_walked} manifests; already-ledgered {n_skipped}; empty {n_empty}")
    print(f"\n{len(out)} salvaged; largest: "
          + (f"{out[0][0]:,} @ {out[0][1]:.4f}" if out else "none"))


if __name__ == "__main__":
    main()
