#!/usr/bin/env python3
"""gate_notary -- G-NOTARY. The notary is the campaign's authority; changed
notary code is ungated code until this passes.

Legs (fast: constructed small gaps, z=1e5, seconds not hours):
  A big-k parse fence: a 9,655-digit k via --k-file survives argparse and
    the py>=3.11 int-str limit (the on-box catch that motivated the patch).
  B --parse-only reports digits/merit without running a verification.
  C VALID path: a genuine maximal gap (both endpoints prime, every interior
    integer composite) certifies VALID with closed interior accounting.
  D INVALID path: a jl/jr pair straddling an interior prime raises the PRP
    alarm and certifies INVALID -- the notary must be able to say NO.
  E certificate schema: token + k_digits recorded, gap/merit consistent.
  F backward compatibility: small-k --k still works exactly as before.
"""
import json, os, shutil, subprocess, sys, time
import gmpy2

sys.set_int_max_str_digits(2_000_000)
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
NOT = os.path.join(HERE, "notary_v1.py")
WORK = os.path.join(HERE, "gnot")
N = [0]


def ok(cond, msg):
    print(("  pass: " if cond else "  FAIL: ") + msg)
    if not cond: sys.exit(1)
    N[0] += 1


def primorial(zd):
    P = gmpy2.mpz(1)
    p = 2
    while p <= zd:
        P *= p
        p = int(gmpy2.next_prime(p))
    return P


def run(args, cwd):
    return subprocess.run([PY, NOT, *args], cwd=cwd, capture_output=True,
                          text=True)


def main():
    t0 = time.time()
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)

    # ---- construct a real maximal gap around a small anchor -------------
    zd = 29
    P = primorial(zd)
    k = 123456789
    n0 = k * P
    lo = int(gmpy2.prev_prime(n0))
    hi = int(gmpy2.next_prime(n0))
    jl, jr = lo - n0, hi - n0
    gap = jr - jl
    print(f"constructed anchor: k*P#({zd}) has "
          f"{len(gmpy2.digits(gmpy2.mpz(n0), 10))} digits, "
          f"gap {gap} (jl={jl}, jr={jr})")

    print("[C] VALID path (true maximal gap)")
    r = run(["--k", str(k), "--zd", str(zd), "--jl", str(jl), "--jr", str(jr),
             "--z", "1e5", "--mr", "25", "--token", "gateT1"], WORK)
    ok(r.returncode == 0 and "VERDICT: VALID" in r.stdout,
       f"C1 verdict VALID  ({r.stdout.strip().splitlines()[-2][:60] if r.stdout else r.stderr[:80]})")
    cert = json.load(open(os.path.join(WORK, f"notary_cert_gap{gap}.json")))
    ok(cert["verdict"] == "VALID"
       and cert["interior"]["sieve_factored"] + cert["interior"]["fermat_composite"]
           == gap - 1
       and not cert["interior"]["prp_alarms"],
       "C2 interior accounting closes, no alarms")

    print("[E] certificate schema")
    ok(cert.get("token") == "gateT1" and cert.get("k_digits") == len(str(k)),
       f"E1 token + k_digits recorded ({cert.get('token')}, "
       f"{cert.get('k_digits')} digits)")
    ok(abs(cert["merit"] - gap / float(gmpy2.log(n0))) < 1e-4,
       f"E2 merit consistent ({cert['merit']})")

    print("[D] INVALID path (interior prime present)")
    lo2 = int(gmpy2.prev_prime(lo))
    r = run(["--k", str(k), "--zd", str(zd), "--jl", str(lo2 - n0),
             "--jr", str(jr), "--z", "1e5", "--mr", "25"], WORK)
    ok("VERDICT: INVALID" in r.stdout and "ALARM" in r.stdout,
       "D1 interior prime detected -> INVALID + alarm")
    c2 = json.load(open(os.path.join(WORK, f"notary_cert_gap{jr - (lo2 - n0)}.json")))
    ok(c2["verdict"] == "INVALID" and c2["interior"]["prp_alarms"],
       f"D2 certificate records the alarm at {c2['interior']['prp_alarms']}")

    print("[A/B] big-k fence (the on-box failure)")
    bigk = int("7" + "3141592653" * 965)          # 9,651 digits
    kf = os.path.join(WORK, "bigk.txt")
    open(kf, "w").write(str(bigk) + "\n")
    r = run(["--k-file", kf, "--zd", "349", "--jl", "-219371", "--jr", "69383",
             "--z", "1e5", "--parse-only", "--token", "s5101t2864"], WORK)
    ok(r.returncode == 0 and "invalid int value" not in r.stderr,
       "A1 9,651-digit k parses (no int-str limit crash)")
    ok("PARSE-ONLY" in r.stdout and "9651" in r.stdout.replace(",", ""),
       f"B1 parse-only reports k digits without verifying "
       f"({r.stdout.strip().splitlines()[-1][:70]})")
    ok("<9651-digit k>" in r.stdout or "s5101t2864" in r.stdout,
       "B2 big k printed as a token/summary, not 9,651 digits of noise")

    print("[G] BIG-K FULL VERIFICATION (the hole leg A/B did not cover)")
    # parse-only exits before the interior sieve, so it never exercised the
    # residue path that actually broke on box2. Use a 100-digit k (> 62 bits,
    # takes the big-k branch) with a small anchor so the run finishes in ms.
    kbig = int("9" + "1234567890" * 9 + "7")          # 101 digits
    Pb = primorial(29)
    n0b = kbig * Pb
    lob = int(gmpy2.prev_prime(n0b)); hib = int(gmpy2.next_prime(n0b))
    jlb, jrb, gapb = lob - n0b, hib - n0b, hib - lob
    kfb = os.path.join(WORK, "kbig.txt"); open(kfb, "w").write(str(kbig))
    r = run(["--k-file", kfb, "--zd", "29", "--jl", str(jlb), "--jr", str(jrb),
             "--z", "1e5", "--mr", "25", "--token", "gateBIG"], WORK)
    ok("OverflowError" not in r.stderr,
       "G1 big-k interior sieve does not overflow (reproduces the box2 crash)")
    ok(r.returncode == 0 and "VERDICT: VALID" in r.stdout,
       f"G2 big-k find certifies VALID (gap {gapb}, k {len(str(kbig))} digits)")
    ok("big-k path" in r.stdout, "G3 big-k branch actually taken")
    cb = json.load(open(os.path.join(WORK, f"notary_cert_gap{gapb}.json")))
    ok(cb["interior"]["sieve_factored"] + cb["interior"]["fermat_composite"]
       == gapb - 1 and not cb["interior"]["prp_alarms"],
       "G4 big-k interior accounting closes")

    print("[F] backward compatibility")
    r = run(["--k", str(k), "--zd", str(zd), "--jl", str(jl), "--jr", str(jr),
             "--z", "1e5", "--mr", "25"], WORK)
    ok("VERDICT: VALID" in r.stdout, "F1 plain --k path unchanged")

    print(f"\nNOTARY GATE: ALL CHECKS PASS -- {N[0]} checks [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
