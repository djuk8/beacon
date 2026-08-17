#!/usr/bin/env python3
"""gpu_lift_v2.py -- gpu_lift + deep-sieve-Q. Runs ONLY after G-A0.

v2 delta (2026-08-01): --deep-q N extends the incidental sieve from Q to N
(< 2^31) via deepsieve.py before candidates are packed for the GPU. Every
deep kill is certified by explicit divisibility at make AND at fold
(E-invariance enforced at runtime: no prime can ever be removed). Survivor
count per lift drops ~ln Q/ln deep_q (Mertens); GPU tests/lift drop by the
same factor. The manifest records deep_q; fold re-derives the identical
deep-filtered survivor set before its determinism assert. --deep-q 0 (the
default) is byte-identical to gpu_lift v1. The claim path is UNCHANGED:
fold's final verify_and_realize re-proves the full SHALLOW survivor set on
CPU exactly as before -- the deep sieve only reduces GPU screening work.

Division of labor (doctrine: GPU is a SCREEN, nothing more):
  make : CPU factory. Loads the design via architect_v2, generates lifts
         (scored or random, dedup'd), computes each lift's survivor set with
         the gated bit-exact sieve (+ deep sieve when --deep-q), packs
         BATCH_LIFTS lifts into one G2C candidate file + a tiny manifest
         (per-lift t only -- the sieve is deterministic, re-derived at fold).
  fold : reads the driver's verdict file. Per lift:
           any verdict==1 -> CPU MR-25 adjudication (a Fermat-2 pseudoprime
                             must NOT fail a lift); true prime -> lift failed
           any verdict==2 -> GEC retest on CPU
           all clear      -> hand the lift to architect_v2.verify_and_realize
                             (early_exit=False): the SAME gated CPU path the
                             fleet uses re-proves every survivor, walks the
                             fences, writes the find file. GPU verdicts are
                             never the basis of a claim.
  The driver invocation between make and fold is yours:
      ./g1_fermat gl_c_<batch>.bin gl_v_<batch>.bin

  python3 gpu_lift_v2.py make --arch ../architect_v2.py --digits 2700 \
      --zd 401 --L 62000 --Q 200000 --swap 3,5,7,11,13,17,19,23,29 --seed 1 \
      --lift-seed 9001 --batches 4 --batch-lifts 40 --score 30000 \
      --deep-q 1000000000
  python3 gpu_lift_v2.py fold --arch ../architect_v2.py --batch gl_0001
"""
import argparse, glob, json, math, os, re, struct, sys, time
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
    raise ValueError("candidate exceeds largest class")


def load_arch(path):
    ns = {}
    src = open(path).read().replace('if __name__ == "__main__":\n    main()', "")
    exec(compile(src, path, "exec"), ns)
    return ns


def build_design(arch, a):
    if a.swap == "all":
        swap = [int(p) for p in arch["primes_upto"](a.zd) if p != 2]
    else:
        swap = [int(x) for x in a.swap.split(",")]
    g = getattr(a, "greedy", "ascending")
    try:
        dz = arch["design"](a.digits, a.zd, a.L, a.Q, swap, a.seed,
                            verbose=False, greedy=g)
    except TypeError:
        dz = arch["design"](a.digits, a.zd, a.L, a.Q, swap, a.seed,
                            verbose=False)
    arch["prep_lift"](dz)
    assert dz["span"] < 2 ** 62, \
        (f"span {dz['span']:.2e} exceeds the int64-safe range of "
         f"architect_v2.incidental_survivors (t %% pr): the window is "
         f"(near-)fully covered -- not a liftable design. Fail loudly.")
    if a.lift_seed is not None:
        import random
        dz["rng"] = random.Random(a.lift_seed)
    return dz


def build_deep(dz, a):
    dq = int(getattr(a, "deep_q", 0) or 0)
    if not dq:
        return None
    from deepsieve import DeepSieve
    return DeepSieve(dz, dq, cache_dir=getattr(a, "ds_cache", ".ds_cache"),
                     block=int(getattr(a, "ds_block", 4_000_000)))


def used_ts(prefix="gl_"):
    ts = set()
    for mf in glob.glob(f"{prefix}*.manifest.json"):
        ts.update(json.load(open(mf))["ts"])
    return ts


def cmd_make(arch, a):
    dz = build_design(arch, a)
    ds = build_deep(dz, a)
    taken = used_ts()
    dz.setdefault("t_used", set()).update(taken)
    print(f"design ready: span {dz['span']:,}, {len(taken)} lifts already "
          f"issued by prior batches")
    if ds:
        print(f"deep sieve armed: (Q={a.Q:,}, deep_q={a.deep_q:,}] "
              f"{len(ds.q):,} primes, Mertens cut {ds.mertens_factor():.4f}")

    order = None
    if a.score:
        t0 = time.time()
        pool = []
        while len(pool) < a.score:
            t = dz["rng"].randrange(dz["span"])
            if t not in dz["t_used"] and t not in {p for p, _ in pool}:
                pool.append((t, None))
        sc = [(len(arch["incidental_survivors"](dz, t, qmax=a.score_q)), t)
              for t, _ in pool]
        sc.sort()
        order = [t for _, t in sc]
        print(f"scored {len(sc):,} candidates to q<={a.score_q:,}: "
              f"{sc[0][0]}..{sc[-1][0]}  [{time.time()-t0:.0f}s]")

    seq = 1
    while os.path.exists(f"gl_{seq:04d}.manifest.json"):
        seq += 1
    oi = 0
    sh_tot = dp_tot = 0
    for b in range(a.batches):
        name = f"gl_{seq+b:04d}"
        ts, blobs, sizes = [], [], []
        bits = None
        for _ in range(a.batch_lifts):
            if order is not None:
                if oi >= len(order):
                    break
                t = order[oi]; oi += 1
                dz["t_used"].add(t)
                k, kt = arch["crt_lift"](dz, t=t)
            else:
                k, kt = arch["crt_lift"](dz)
            n0 = gmpy2.mpz(k) * dz["P_eff"]
            js = arch["incidental_survivors"](dz, kt)
            if ds:
                sh_tot += len(js)
                js, _ = ds.filter(js, kt, n0=n0, certify=True)
                dp_tot += len(js)
            cands = [int(n0 + int(j)) for j in js]
            bc = max(bit_class(c) for c in cands)
            bits = max(bits or 0, bc)
            ts.append(int(kt)); sizes.append(len(cands)); blobs.append(cands)
        nb = bits // 8
        total = sum(sizes)
        with open(f"{name}.bin", "wb") as f:
            f.write(struct.pack("<IIQ", MAGIC_C, bits, total))
            for cands in blobs:
                for c in cands:
                    f.write(c.to_bytes(nb, "little"))
        json.dump(dict(design=vars(a), ts=ts, sizes=sizes, bits=bits,
                       status="pending"),
                  open(f"{name}.manifest.json", "w"))
        print(f"  {name}.bin: {len(ts)} lifts, {total:,} candidates, "
              f"class {bits}   -> run:  ./g1_fermat {name}.bin {name}.v.bin")
    if ds and sh_tot:
        print(f"deep sieve: {sh_tot:,} shallow -> {dp_tot:,} packed "
              f"(cut {dp_tot/sh_tot:.4f} vs Mertens "
              f"{ds.mertens_factor():.4f}; {ds.n_kills:,} kills certified)")


def cmd_fold(arch, a):
    mf = f"{a.batch}.manifest.json"
    man = json.load(open(mf))
    if man["status"] == "done" and not a.force:
        print(f"{a.batch}: already folded"); return
    d = argparse.Namespace(**man["design"])
    dz = build_design(arch, d)
    ds = build_deep(dz, d)
    vf = f"{a.batch}.v.bin"
    hv = open(vf, "rb").read()
    m, bits, cnt = struct.unpack("<IIQ", hv[:16])
    assert m == MAGIC_V and bits == man["bits"], "verdict header mismatch"
    v = hv[16:]
    assert len(v) == cnt == sum(man["sizes"]), \
        f"verdict count {len(v)} != {sum(man['sizes'])} (0xFF hazard)"
    if any(b == 0xFF for b in v):
        sys.exit(f"{a.batch}: UNTOUCHED 0xFF verdicts -- FATAL, driver fault")

    pos = 0
    for t, sz in zip(man["ts"], man["sizes"]):
        vl = v[pos:pos + sz]; pos += sz
        k, _ = arch["crt_lift"](dz, t=t)
        n0 = gmpy2.mpz(k) * dz["P_eff"]
        js = arch["incidental_survivors"](dz, t)
        if ds:
            js, _ = ds.filter(js, t, n0=n0, certify=True)
        assert len(js) == sz, f"lift t={t}: sieve non-determinism ({len(js)} vs {sz})"
        suspects = [int(js[i]) for i in range(sz) if vl[i] in (1, 2)]
        true_primes = [j for j in suspects if gmpy2.is_prime(n0 + j, 25)]
        if true_primes:
            print(f"  t={t}: FAILED, prime at j={true_primes[0]} "
                  f"({len(suspects)} GPU suspects, {len(true_primes)} confirmed)")
            continue
        print(f"  t={t}: GPU-CLEAN ({len(suspects)} suspects, all composite "
              f"on CPU) -> full CPU verify_and_realize ...")
        r = arch["verify_and_realize"](dz, k, t, realize=True, early_exit=False)
        if r.get("gap"):
            fn = (f"find_D{d.digits}_g{r['gap']}_zd{d.zd}_gl{t}.txt")
            with open(fn, "w") as fh:
                fh.write(f"# gap {r['gap']} merit {r['merit']:.6f} "
                         f"digits {r['n0_digits']}\n")
                fh.write(f"# design D={d.digits} zd={d.zd} L={d.L} Q={d.Q} "
                         f"swap={d.swap} seed={d.seed} "
                         f"greedy={getattr(d,'greedy','ascending')} lift_seed={d.lift_seed} t={t}\n")
                fh.write(f"# jl {r['jl']} jr {r['jr']} d {dz['d']}\n")
                fh.write(f"# SUBMIT: {r['gap']} {r['merit']:.6f} "
                         f"<k> * {d.zd}# / {dz['d']} {r['jl']:+d}\n")
                fh.write(f"k={k}\n")
            print(f"    REALIZED gap {r['gap']:,} merit {r['merit']:.3f} "
                  f"-> {fn}")
        else:
            print(f"    CPU pass found an interior prime the GPU missed at "
                  f"{r['interior_primes'][:2]} -- LOG THIS, it is a G-A0 "
                  f"escalation, not a shrug")
    man["status"] = "done"
    json.dump(man, open(mf, "w"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "fold"])
    ap.add_argument("--arch", default="../architect_v2.py")
    ap.add_argument("--digits", type=int, default=2700)
    ap.add_argument("--zd", type=int, default=401)
    ap.add_argument("--L", type=int, default=62000)
    ap.add_argument("--Q", type=int, default=200000)
    ap.add_argument("--swap", default="3,5,7,11,13,17,19,23,29")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lift-seed", type=int, default=None)
    ap.add_argument("--batches", type=int, default=2)
    ap.add_argument("--batch-lifts", type=int, default=40)
    ap.add_argument("--score", type=int, default=0)
    ap.add_argument("--score-q", type=int, default=20000)
    ap.add_argument("--greedy", choices=["ascending", "value"],
                    default="ascending")
    ap.add_argument("--deep-q", type=int, default=0,
                    help="extend incidental sieve to this bound (<2^31); "
                         "0 = off (byte-identical to gpu_lift v1)")
    ap.add_argument("--ds-cache", default=".ds_cache")
    ap.add_argument("--ds-block", type=int, default=4_000_000)
    ap.add_argument("--batch", help="fold: gl_NNNN")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    arch = load_arch(a.arch)
    (cmd_make if a.cmd == "make" else cmd_fold)(arch, a)


if __name__ == "__main__":
    main()
