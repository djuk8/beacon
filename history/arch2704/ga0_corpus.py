#!/usr/bin/env python3
"""ga0_corpus.py -- G-A0 gate, architect-labeled slice.

Builds candidate files in the exact G2C format from architect FIND FILES,
which are ground truth: both fences are proven PRP, every interior survivor
is proven composite. The reference verdict is the DRIVER's own semantics
(Fermat base-2: pow(2, n-1, n) == 1), computed with gmpy2 -- so a base-2
pseudoprime among the interiors is handled correctly, not mislabeled.

Two-part G-A0 (per PUMP_PLAN S3):
  BULK (generic, existing machinery unchanged):
      python3 g2_harness.py --driver ./g1_fermat --plan 16384:1000000 --gpu-only
      # then --check-only with the reference stage on shredder's cores
  ARCHITECT SLICE (this tool):
      python3 ga0_corpus.py --make find_D2700_g*.txt --arch ../architect_v2.py
      ./g1_fermat ga0_c_<bits>.bin ga0_v_<bits>.bin        # however you
                                                           # invoke the driver
      python3 ga0_corpus.py --check
  Exit nonzero on ANY mismatch. Zero tolerance; a single flipped verdict
  fails the gate, prints the candidate index, value class, and context
  (left-fence / interior / right-fence, which find, which offset).

Classes follow the driver: candidate padded to the smallest of
2048/4096/8192/16384/32768 bits that holds it.
"""
import argparse, glob, os, re, struct, sys
import gmpy2

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
CLASSES = [2048, 4096, 8192, 16384, 32768]


def bit_class(n):
    b = int(n).bit_length()
    for c in CLASSES:
        if b <= c:
            return c
    raise ValueError(f"{b} bits exceeds largest class")


def load_arch(path):
    ns = {}
    src = open(path).read().replace('if __name__ == "__main__":\n    main()', "")
    exec(compile(src, path, "exec"), ns)
    return ns


def rebuild(find_path, arch):
    """find file -> (list of (n, expected_context)) with contexts labeled."""
    txt = open(find_path).read()
    g = int(re.search(r"# gap (\d+)", txt).group(1))
    dsn = re.search(r"# design D=(\d+) zd=(\d+) L=(\d+) Q=(\d+) "
                    r"swap=\[?([\d, ]+)\]? seed=(\d+) lift_seed=(\S+) t=(\d+)", txt)
    assert dsn, f"{find_path}: design line does not parse -- format drift"
    D, zd, L, Q = (int(dsn.group(i)) for i in range(1, 5))
    swap = [int(x) for x in dsn.group(5).replace(" ", "").split(",")]
    seed, t = int(dsn.group(6)), int(dsn.group(8))
    jl, jr, d = (int(x) for x in
                 re.search(r"# jl (-?\d+) jr (-?\d+) d (\d+)", txt).groups())
    k = int(re.search(r"k=(\d+)", txt).group(1))

    dz = arch["design"](D, zd, L, Q, swap, seed, verbose=False)
    arch["prep_lift"](dz)
    kk = int(dz["crt_r"] + dz["crt_M"] * (dz["crt_t0"] + t))
    assert kk == k, f"{find_path}: rebuilt k != stored k -- design drifted"
    n0 = gmpy2.mpz(k) * dz["P_eff"]
    surv = [int(j) for j in arch["incidental_survivors"](dz, t)]

    out = [(int(n0 + jl), f"{os.path.basename(find_path)} LEFT FENCE j={jl}")]
    for j in surv:
        if jl < j < jr:
            out.append((int(n0 + j), f"{os.path.basename(find_path)} interior j={j}"))
    out.append((int(n0 + jr), f"{os.path.basename(find_path)} RIGHT FENCE j={jr}"))
    # sanity on the labels themselves (independent of the driver)
    assert gmpy2.is_prime(out[0][0], 25) and gmpy2.is_prime(out[-1][0], 25), \
        f"{find_path}: a fence fails CPU re-proof -- corrupt find file"
    return out


def fermat2(n):
    return 1 if gmpy2.powmod(2, n - 1, n) == 1 else 0


def make(finds, arch_path):
    arch = load_arch(arch_path)
    byclass = {}
    for fp in finds:
        for n, ctx in rebuild(fp, arch):
            byclass.setdefault(bit_class(n), []).append((n, ctx))
    for bits, items in sorted(byclass.items()):
        nb = bits // 8
        with open(f"ga0_c_{bits}.bin", "wb") as f:
            f.write(struct.pack("<IIQ", MAGIC_C, bits, len(items)))
            for n, _ in items:
                f.write(int(n).to_bytes(nb, "little"))
        with open(f"ga0_ref_{bits}.bin", "wb") as f:
            f.write(struct.pack("<IIQ", MAGIC_V, bits, len(items)))
            f.write(bytes(fermat2(n) for n, _ in items))
        with open(f"ga0_ctx_{bits}.txt", "w") as f:
            for i, (_, ctx) in enumerate(items):
                f.write(f"{i}\t{ctx}\n")
        npsp = sum(1 for n, c in items
                   if "interior" in c and fermat2(n) == 1)
        print(f"class {bits}: {len(items):,} candidates "
              f"({sum(1 for _,c in items if 'FENCE' in c)} fences, "
              f"{npsp} interior base-2 pseudoprimes -- reference handles them)")
        print(f"  wrote ga0_c_{bits}.bin ga0_ref_{bits}.bin ga0_ctx_{bits}.txt")
    print("\nnow run the driver on each ga0_c_*.bin -> ga0_v_*.bin, "
          "then: python3 ga0_corpus.py --check")


def check():
    fail = 0
    cands = sorted(glob.glob("ga0_c_*.bin"))
    if not cands:
        print("NO ga0_c_*.bin candidate files here -- run --make first. "
              "A gate with nothing to check does NOT pass.")
        sys.exit(2)
    for cf in cands:
        bits = int(re.search(r"_(\d+)\.bin", cf).group(1))
        vf, rf, xf = (f"ga0_{p}_{bits}.{'bin' if p!='ctx' else 'txt'}"
                      for p in ("v", "ref", "ctx"))
        if not os.path.exists(vf):
            print(f"class {bits}: NO DRIVER OUTPUT ({vf} missing)"); fail += 1
            continue
        hv, hr = open(vf, "rb").read(), open(rf, "rb").read()
        mv, bv, cv = struct.unpack("<IIQ", hv[:16])
        mr, br, cr = struct.unpack("<IIQ", hr[:16])
        ctx = [l.rstrip("\n").split("\t", 1)[1] for l in open(xf)]
        if not (mv == MAGIC_V and bv == bits and cv == cr):
            print(f"class {bits}: BAD VERDICT HEADER"); fail += 1; continue
        gpu, ref = hv[16:], hr[16:]
        if len(gpu) != cr:
            print(f"class {bits}: verdict length {len(gpu)} != {cr} "
                  f"(untouched-verdict hazard: 0xFF bytes are FATAL)")
            fail += 1; continue
        bad = [i for i in range(cr)
               if gpu[i] != ref[i] and not (gpu[i] == 2)]   # 2 = GEC retest
        gec = sum(1 for b in gpu if b == 2)
        untouched = sum(1 for b in gpu if b == 0xFF)
        if untouched:
            print(f"class {bits}: {untouched} UNTOUCHED (0xFF) verdicts -- FATAL")
            fail += 1
        for i in bad[:10]:
            print(f"class {bits}: MISMATCH idx {i}: gpu={gpu[i]} "
                  f"ref={ref[i]}  <- {ctx[i]}")
        if bad:
            fail += 1
        print(f"class {bits}: {cr:,} candidates, {len(bad)} mismatches, "
              f"{gec} GEC-retest verdicts ({'FAIL' if bad or untouched else 'PASS'})")
    print("\nG-A0 architect slice:", "FAILED -- do not run hot" if fail else
          "PASS (combine with the bulk g2_harness stage before trusting)")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--make", nargs="+", metavar="FIND_FILE")
    ap.add_argument("--arch", default="../architect_v2.py")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.make:
        make(a.make, a.arch)
    elif a.check:
        check()
    else:
        ap.error("--make FIND... or --check")
