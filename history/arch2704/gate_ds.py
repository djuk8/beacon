#!/usr/bin/env python3
"""gate_ds.py -- the deep-sieve-Q gate. Nothing touches a card or the fleet
before this exits 0. A gate with nothing to check does NOT pass (asserts on
empty kill sets, empty survivor sets, zero lifts). Checks:

  DS0  segmented sieve vs pi(x) anchors and vs architect primes_upto
  DS1  residue bit-exactness vs gmpy2 at production shape (>=1e6 pairs,
       edge primes, huge multi-limb t)
  DS2  every deep kill re-proven by divisibility, gate-side (non-empty)
  DS3a exhaustive small-D brute-force referee (deepsieve selftest, subproc)
  DS3b missed-kill referee at production shape: gcd of survivor-product vs
       deep-prime chunk products -- INDEPENDENT of the A/B/PE tables --
       with a live-detector injection (a known-killed candidate must fire)
  DS4  survivor cut vs Mertens lnQ/lnQ' (statistical: report, sanity-fail
       only on impossible values)
  DS5  full pipeline round-trip at D=400: make --deep-q -> reference
       Fermat-2 driver -> fold; then negative tests: 0xFF injection,
       truncated verdicts, tampered manifest sizes must all exit nonzero
  DS6  --deep-q 0 regression: candidate .bin byte-identical to gpu_lift v1

  python3 gate_ds.py --arch architect_v2.py --v1 gpu_lift.py \
      --v2 gpu_lift_v2.py
"""
import argparse, glob, hashlib, json, math, os, shutil, struct, subprocess
import sys, time
import numpy as np
import gmpy2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deepsieve import DeepSieve, primes_range, PI

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

RES = []
def report(name, ok, msg=""):
    RES.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {msg}")
    return ok


def load_arch(path):
    ns = {}
    src = open(path).read().replace('if __name__ == "__main__":\n    main()',
                                    "")
    exec(compile(src, path, "exec"), ns)
    return ns


def ref_driver(cbin, vbin):
    """Reference GPU driver: honest Fermat base-2 verdicts, driver file
    contract (header + one byte per candidate)."""
    h = open(cbin, "rb").read()
    m, bits, cnt = struct.unpack("<IIQ", h[:16])
    nb = bits // 8
    out = bytearray([0xFF]) * cnt          # prefill 0xFF, then overwrite all
    body = h[16:]
    for i in range(cnt):
        c = int.from_bytes(body[i * nb:(i + 1) * nb], "little")
        out[i] = 1 if gmpy2.powmod(2, c - 1, c) == 1 else 0
    with open(vbin, "wb") as f:
        f.write(struct.pack("<IIQ", 0x31563247, bits, cnt))
        f.write(bytes(out))
    return cnt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default="architect_v2.py")
    ap.add_argument("--v1", default="gpu_lift.py")
    ap.add_argument("--v2", default="gpu_lift_v2.py")
    ap.add_argument("--deep-q", type=int, default=10**7,
                    help="deep bound for the production-shape checks")
    ap.add_argument("--fast", action="store_true",
                    help="smaller production-shape design (D=1000)")
    a = ap.parse_args()
    HERE = os.path.dirname(os.path.abspath(__file__))
    arch = load_arch(a.arch)
    t00 = time.time()

    # ---------------------------------------------------------------- DS0
    ok = True
    for hi in (10**5, 10**6, 10**7):
        n = len(primes_range(0, hi, None))
        if n != PI[hi]:
            ok = False
    p1 = primes_range(0, 2_000_000, None)
    p2 = arch["primes_upto"](2_000_000)
    ok &= (len(p1) == len(p2)) and bool((p1 == p2).all())
    report("DS0 sieve: pi anchors 1e5/1e6/1e7 + primes_upto equality", ok)

    # ------------------------------------------- production-shape design
    if a.fast:
        D, zd, L, sw = 1000, 199, 20000, [3, 5, 7, 11, 13]
    else:
        D, zd, L, sw = 2700, 401, 62000, [3, 5, 7, 11, 13, 17, 19, 23, 29]
    Q = 200_000
    t0 = time.time()
    dz = arch["design"](D, zd, L, Q, sw, 1, verbose=False)
    arch["prep_lift"](dz)
    import random
    dz["rng"] = random.Random(4242)
    print(f"  production-shape design D={D} zd={zd} L={L}: "
          f"{int(dz['alive'].sum()):,} design survivors "
          f"[{time.time()-t0:.0f}s]")
    t0 = time.time()
    ds = DeepSieve(dz, a.deep_q, cache_dir=".ds_cache", verbose=False)
    print(f"  deep tables (Q,{a.deep_q:,}]: {len(ds.q):,} primes "
          f"[{time.time()-t0:.0f}s]")

    # ---------------------------------------------------------------- DS1
    rng = np.random.default_rng(11)
    nq, nt = 25_000, 40
    tvals = [int(dz["rng"].randrange(dz["span"])) for _ in range(nt - 1)]
    tvals.append(int(gmpy2.mpz(2) ** 199 + 987654321))       # huge t
    edge = np.concatenate([np.arange(64), len(ds.q) - 1 - np.arange(64)])
    bad = 0; checked = 0
    for t in tvals:
        k = int(dz["crt_r"] + dz["crt_M"] * (dz["crt_t0"] + t))
        n0 = gmpy2.mpz(k) * dz["P_eff"]
        got = ds.n0_mod(t)
        idx = np.unique(np.concatenate(
            [rng.choice(len(ds.q), nq, replace=False), edge]))
        for i in idx.tolist():
            checked += 1
            if int(n0 % int(ds.q[i])) != int(got[i]):
                bad += 1
    report("DS1 residues bit-exact vs gmpy2",
           bad == 0 and checked >= 1_000_000,
           f"({checked:,} pairs incl. edge primes + 2^199-scale t, "
           f"{bad} mismatches)")

    # ----------------------------------------------------------- DS2/DS4
    cuts, killtot, gate_bad_tot = [], 0, 0
    lifts_meta = []
    NL = 8 if not a.fast else 12
    for _ in range(NL):
        k, t = arch["crt_lift"](dz)
        n0 = gmpy2.mpz(k) * dz["P_eff"]
        js = arch["incidental_survivors"](dz, t)
        surv, nk = ds.filter(js, t, n0=n0, certify=True)
        jk, qk = ds.kills(t)
        bmp = np.zeros(L, dtype=bool)
        bmp[(np.asarray(js, np.int64) + (L - 1)) >> 1] = True
        inset = bmp[(jk + (L - 1)) >> 1]
        jk, qk = jk[inset], qk[inset]
        gate_bad_tot += sum(1 for j, q in zip(jk.tolist(), qk.tolist())
                            if (n0 + j) % q != 0)
        killtot += len(jk)
        cuts.append(len(surv) / len(js))
        lifts_meta.append((t, n0, js, surv, jk, qk))
    report("DS2 every deep kill divisibility-proven, gate-side",
           killtot > 0 and gate_bad_tot == 0,
           f"({killtot:,} kills over {NL} lifts, {gate_bad_tot} failures)")

    # ---------------------------------------------------------------- DS3a
    r = subprocess.run([sys.executable, os.path.join(HERE, "deepsieve.py"),
                        "selftest", "--arch", a.arch, "--trials", "3"],
                       capture_output=True, text=True)
    report("DS3a exhaustive small-D brute-force referee (selftest)",
           r.returncode == 0, (r.stdout.strip().splitlines() or ["?"])[-1][:60])

    # ---------------------------------------------------------------- DS3b
    t, n0, js, surv, jk, qk = lifts_meta[0]
    CH = 2048
    qs = ds.q.tolist()
    chunks = [qs[i:i + CH] for i in range(0, len(qs), CH)]
    Bs = [math.prod(c) for c in chunks]
    # live-detector injection: a candidate KNOWN to be deep-divisible must
    # trip the referee, or the referee is decorative.
    assert len(jk) > 0, "no kills to inject -- gate cannot certify itself"
    inj_j, inj_q = int(jk[0]), int(qk[0])
    inj_ci = next(i for i, c in enumerate(chunks)
                  if c[0] <= inj_q <= c[-1])
    fired = False
    accI = gmpy2.mpz(1)
    Bi = gmpy2.mpz(Bs[inj_ci])
    for j in list(surv.tolist()) + [inj_j]:
        accI = accI * ((n0 + j) % Bi) % Bi
    fired = gmpy2.gcd(accI, Bi) > 1
    # the real sweep: product of all FINAL survivors vs every chunk
    missed = 0
    for ci, B in enumerate(Bs):
        B = gmpy2.mpz(B)
        acc = gmpy2.mpz(1)
        for j in surv.tolist():
            acc = acc * ((n0 + j) % B) % B
        if gmpy2.gcd(acc, B) > 1:
            missed += 1
    report("DS3b missed-kill referee (gcd vs chunk products, independent "
           "of A/B/PE)", fired and missed == 0,
           f"(injected detector fired={fired}; {len(Bs)} chunks x "
           f"{len(surv):,} survivors, {missed} hits)")

    # ---------------------------------------------------------------- DS4
    mert = ds.mertens_factor()
    mc, sd = float(np.mean(cuts)), float(np.std(cuts, ddof=1))
    z = (mc - mert) / (sd / math.sqrt(len(cuts)) + 1e-12)
    report("DS4 cut factor vs Mertens (statistical, heuristic reference)",
           0 < mc <= 1.0 and killtot > 0,
           f"(measured {mc:.4f} +/- {sd/math.sqrt(len(cuts)):.4f} vs "
           f"lnQ/lnQ' {mert:.4f}, z={z:+.1f})")

    # ---------------------------------------------------------------- DS5
    wd = os.path.abspath("gate_ds5"); shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(wd)
    args5 = ["--arch", os.path.abspath(a.arch), "--digits", "400", "--zd",
             "349", "--L", "2000", "--Q", "200000", "--swap", "3,5,7",
             "--seed", "1", "--lift-seed", "77", "--batches", "1",
             "--batch-lifts", "20", "--deep-q", "3000000",
             "--ds-cache", os.path.join(wd, ".dsc")]
    r = subprocess.run([sys.executable, os.path.join(HERE, a.v2), "make"]
                       + args5, cwd=wd, capture_output=True, text=True)
    okm = r.returncode == 0 and os.path.exists(f"{wd}/gl_0001.bin")
    cnt = ref_driver(f"{wd}/gl_0001.bin", f"{wd}/gl_0001.v.bin") if okm else 0
    rf = subprocess.run([sys.executable, os.path.join(HERE, a.v2), "fold",
                         "--batch", "gl_0001"] + args5, cwd=wd,
                        capture_output=True, text=True)
    man = json.load(open(f"{wd}/gl_0001.manifest.json")) if okm else {}
    folded = rf.returncode == 0 and man.get("status") == "done"
    nclean = rf.stdout.count("GPU-CLEAN"); nfail = rf.stdout.count("FAILED")
    report("DS5 round-trip: make --deep-q -> reference Fermat-2 driver -> "
           "fold", okm and folded and cnt > 0 and (nclean + nfail) == 20,
           f"({cnt} candidates, {nclean} clean / {nfail} failed lifts, "
           f"{rf.stdout.count('REALIZED')} realized)")

    # negative tests -- each must exit nonzero
    def refold(mut):
        w2 = wd + "_neg"; shutil.rmtree(w2, ignore_errors=True)
        shutil.copytree(wd, w2)
        mut(w2)
        rr = subprocess.run([sys.executable, os.path.join(HERE, a.v2),
                             "fold", "--batch", "gl_0001", "--force",
                             "--arch", os.path.abspath(a.arch),
                             "--ds-cache", os.path.join(wd, ".dsc")],
                            cwd=w2, capture_output=True, text=True)
        shutil.rmtree(w2, ignore_errors=True)
        return rr.returncode
    def mut_ff(w):
        b = bytearray(open(f"{w}/gl_0001.v.bin", "rb").read())
        b[16 + 3] = 0xFF
        open(f"{w}/gl_0001.v.bin", "wb").write(bytes(b))
    def mut_trunc(w):
        b = open(f"{w}/gl_0001.v.bin", "rb").read()
        open(f"{w}/gl_0001.v.bin", "wb").write(b[:-2])
    def mut_sizes(w):
        m = json.load(open(f"{w}/gl_0001.manifest.json"))
        m["sizes"][0] += 1; m["sizes"][1] -= 1
        json.dump(m, open(f"{w}/gl_0001.manifest.json", "w"))
    r1, r2, r3 = refold(mut_ff), refold(mut_trunc), refold(mut_sizes)
    report("DS5n tamper: 0xFF / truncated verdicts / manifest sizes all "
           "fatal", r1 != 0 and r2 != 0 and r3 != 0,
           f"(exit codes {r1}/{r2}/{r3})")

    # ---------------------------------------------------------------- DS6
    wa, wb = os.path.abspath("gate_ds6a"), os.path.abspath("gate_ds6b")
    for w in (wa, wb):
        shutil.rmtree(w, ignore_errors=True); os.makedirs(w)
    args6 = ["--arch", os.path.abspath(a.arch), "--digits", "400", "--zd",
             "349", "--L", "2000", "--Q", "200000", "--swap", "3,5,7",
             "--seed", "1", "--lift-seed", "99", "--batches", "1",
             "--batch-lifts", "4"]
    ra = subprocess.run([sys.executable, os.path.join(HERE, a.v1), "make"]
                        + args6, cwd=wa, capture_output=True, text=True)
    rb = subprocess.run([sys.executable, os.path.join(HERE, a.v2), "make"]
                        + args6 + ["--deep-q", "0"], cwd=wb,
                        capture_output=True, text=True)
    ha = hashlib.sha256(open(f"{wa}/gl_0001.bin", "rb").read()).hexdigest() \
        if ra.returncode == 0 else "a"
    hb = hashlib.sha256(open(f"{wb}/gl_0001.bin", "rb").read()).hexdigest() \
        if rb.returncode == 0 else "b"
    ok6 = (ra.returncode == 0 and rb.returncode == 0
           and os.path.exists(f"{wa}/gl_0001.manifest.json")
           and os.path.exists(f"{wb}/gl_0001.manifest.json"))
    if ok6:
        ma = json.load(open(f"{wa}/gl_0001.manifest.json"))
        mb = json.load(open(f"{wb}/gl_0001.manifest.json"))
        same = (ha == hb and ma["ts"] == mb["ts"]
                and ma["sizes"] == mb["sizes"] and ma["bits"] == mb["bits"])
        report("DS6 --deep-q 0 byte-identical to gpu_lift v1",
               same, f"(bin sha {ha[:12]} == {hb[:12]}: {ha == hb})")
    else:
        e1 = ((ra.stderr or ra.stdout).strip().splitlines() or ["no output"])[-1][:90]
        report("DS6 --deep-q 0 byte-identical to gpu_lift v1", False,
               f"(v1 exit {ra.returncode}: {e1} | v2 exit {rb.returncode})")

    # ---------------------------------------------------------------- DS7
    cnt7 = ref_driver(f"{wa}/gl_0001.bin", f"{wa}/gl_0001.v.bin")
    r7 = subprocess.run([sys.executable, os.path.join(HERE, a.v2), "fold",
                         "--batch", "gl_0001", "--arch",
                         os.path.abspath(a.arch)],
                        cwd=wa, capture_output=True, text=True)
    man7 = json.load(open(f"{wa}/gl_0001.manifest.json"))
    n7 = r7.stdout.count("GPU-CLEAN") + r7.stdout.count("FAILED")
    report("DS7 v2 fold on a v1-made manifest (no deep_q key, deep-off "
           "path)", r7.returncode == 0 and man7.get("status") == "done"
           and n7 == 4, f"({n7}/4 lifts adjudicated, exit {r7.returncode})")

    # ---------------------------------------------------------------- DS8
    af = os.path.join(".ds_cache", f"abpe_{ds.fp}A.npy")
    raw = bytearray(open(af, "rb").read())
    raw[-3] ^= 0x5A
    open(af, "wb").write(bytes(raw))
    try:
        DeepSieve(dz, a.deep_q, cache_dir=".ds_cache", verbose=False)
        ok8 = False
    except RuntimeError as e:
        ok8 = "CORRUPT" in str(e)
    raw[-3] ^= 0x5A
    open(af, "wb").write(bytes(raw))
    ds8b = DeepSieve(dz, a.deep_q, cache_dir=".ds_cache", verbose=False)
    ok8 = ok8 and bool((ds8b.n0_mod(7) == ds.n0_mod(7)).all())
    report("DS8 poisoned-cache refusal (sha) + clean reload bit-equal",
           ok8)

    print(f"\nGATE {'PASS -- deep-sieve-Q cleared for the boxes' if all(RES) else 'FAIL'}"
          f"  ({sum(RES)}/{len(RES)} checks, {time.time()-t00:.0f}s)")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
