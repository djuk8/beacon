#!/usr/bin/env python3
"""scanhunt_v0.py -- the resonance record campaign engine.

Construction (frontier-law, measured 2026-08-02): n0 = k * zd# / d with
zd ~ 1.01 x ln n0, small-swap d, k a sequential odd scan. A k SUCCEEDS if
the prime-free interval straddling the center reaches the target gap G:
P(L + R >= G). Live-calibrated at the record config: E(full window) =
17.80 +/- 0.61 (rescal, PASS).

RING LADDER (GPU economics): candidates are tested center-out in rings.
Any prime inside an inner ring kills every G-gap through the thin zone,
so ks are ABANDONED at the first ring containing a prime; survivors of
ring r advance to ring r+1 in the next round. Expected GPU tests per k
~ ring-1 size + geometric tail ~ 300-400 at the default ladder.

Rounds are the proven make -> g1_fermat -> fold cycle with a carry file:
  round 1: make --round 1                (fresh k block)
  round r: make --round r                (reads carry from round r-1)
  each:    <driver> sc_rNNNN.bin sc_rNNNN.v.bin ; fold --round r
Final-ring survivors go to `finish`: CPU re-proof of the full interior +
exact fence walk (its own PRP budget) -> find file + SUBMIT line. GPU
verdicts are never claim basis (doctrine unchanged).

Deep extension: k(t) = k0 + 2t, so n0(t) mod q = ((k0 + 2t) mod q) *
PE_q mod q -- the ABPE linear form with M=2. Primes (Q, deep_q] each land
at most once per ring; EVERY deep kill is divisibility-certified.

  python3 scanhunt_v0.py make  --round 1 --kblock 20000
  python3 scanhunt_v0.py fold  --round 1
  python3 scanhunt_v0.py finish
  python3 scanhunt_v0.py status
"""
import argparse, json, math, os, struct, sys, time
import numpy as np
import gmpy2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resonance_map import primes_upto, primorial

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
GAMMA = 0.5772156649015329
BITS = 16384


# ---------------------------------------------------------------- config ---
def cfg_of(a):
    d = 1
    for p in a.swap: d *= p
    P = primorial(a.zd)
    P_eff = P // d
    kmid = 5 * 10 ** (a.kdig - 1)
    ln_n0 = float(gmpy2.log(gmpy2.mpz(kmid) * P_eff))
    G = math.ceil(a.merit * ln_n0)
    # ring edges in |j|: E-geometric ladder to the far edge (G*extent)
    edges = [int(x) for x in a.rings.split(",")]
    return dict(zd=a.zd, swap=list(a.swap), d=d, kdig=a.kdig, merit=a.merit,
                Q=a.Q, deep_q=a.deep_q, G=G, edges=edges, seed=a.seed,
                ln_n0=ln_n0), P_eff


SEED_SPAN_T = None   # set per kdig: 4*10^(kdig-2) t-units per seed

def kstart(cfg):
    """Seed s owns the disjoint in-decade k-range
    [base + 2*s*SPAN, base + 2*(s+1)*SPAN): machine identity = seed block.
    Convention: box1 seeds 1-4, box2 5-8, rental 11-18, experiments 90+."""
    span = 4 * 10 ** (cfg["kdig"] - 2)
    base = 10 ** (cfg["kdig"] - 1) + 1
    return (base + 2 * cfg["seed"] * span) | 1


# ------------------------------------------------------------- sieve core ---
class ScanSieve:
    """Shallow (<=Q) + deep (Q, deep_q] residues for n0 = k * P_eff over a
    j-window, k = k0 + 2t. Deep kills divisibility-certified."""
    def __init__(self, cfg, P_eff, cache=".sc_cache"):
        self.cfg, self.P_eff = cfg, P_eff
        os.makedirs(cache, exist_ok=True)
        self.prs = primes_upto(cfg["Q"])
        f1 = os.path.join(cache, f"pem_{cfg['zd']}_{cfg['d']}_{cfg['Q']}.npy")
        if os.path.exists(f1):
            self.PEm = np.load(f1)
        else:
            self.PEm = np.array([int(P_eff % int(p)) for p in self.prs],
                                dtype=np.int64)
            np.save(f1, self.PEm)
        self.dq = int(cfg["deep_q"])
        if self.dq:
            from deepsieve import primes_range
            self.qd = primes_range(cfg["Q"], self.dq, cache)
            f2 = os.path.join(cache,
                              f"pemd_{cfg['zd']}_{cfg['d']}_{self.dq}.npy")
            if os.path.exists(f2):
                self.PEd = np.load(f2, mmap_mode="r")
            else:
                mm = np.lib.format.open_memmap(f2, mode="w+", dtype=np.int32,
                                               shape=(len(self.qd),))
                B = 4_000_000
                for i in range(0, len(self.qd), B):
                    ql = self.qd[i:i + B].tolist()
                    mm[i:i + len(ql)] = [P_eff % p for p in ql]
                mm.flush(); del mm
                self.PEd = np.load(f2, mmap_mode="r")
        if self.dq:
            self.qd = self.qd.astype(np.int64)
            self.PEd64 = self.PEd[:].astype(np.int64)   # ~0.4 GB in RAM

    def survivors(self, k, jlo, jhi, n0=None, certify=True, use_deep=True):
        """Even-j survivors of [jlo, jhi] (n0 odd), shallow+deep sieved.
        Returns sorted js. Deep kills certified on n0 when certify."""
        js = np.arange(jlo + (jlo & 1), jhi + 1, 2, dtype=np.int64)
        alive = np.ones(len(js), dtype=bool)
        n0m = (int(k) % self.prs) * self.PEm % self.prs
        W = jhi - jlo + 1
        small = self.prs[self.prs <= W]
        for i in range(1, len(small)):
            p = int(small[i])
            j0 = (-int(n0m[i])) % p
            # first even landing >= jlo
            st = j0 + ((jlo - j0 + p - 1) // p) * p
            if (st & 1):
                st += p if (p & 1) else 0
                if st & 1: st = None
            if st is not None and st <= jhi:
                step = p if p % 2 == 0 else 2 * p
                alive[(st - js[0]) // 2::step // 2] = False
        big = self.prs[len(small):]
        if len(big):
            m = n0m[len(small):]
            j0 = (-m) % big
            st = jlo + ((j0 - jlo) % big)      # first landing >= jlo
            odd = (st & 1) == 1
            st = np.where(odd, st + big, st)   # odd p: next even landing
            ok = st <= jhi
            if ok.any():
                alive[((st[ok] - js[0]) // 2).astype(np.int64)] = False
        if self.dq and use_deep:
            km = np.asarray(int(k) % self.qd, dtype=np.int64)
            n0d = km * self.PEd64 % self.qd
            j0 = (-n0d) % self.qd
            st = jlo + ((j0 - jlo) % self.qd)
            odd = (st & 1) == 1
            st = np.where(odd, st + self.qd, st)
            ok = st <= jhi
            kills = []
            if ok.any():
                idx = ((st[ok] - js[0]) // 2).astype(np.int64)
                live = alive[idx]
                kills.append((st[ok][live], self.qd[ok][live]))
                alive[idx] = False
            if certify and kills:
                n0 = gmpy2.mpz(n0 if n0 is not None else k * self.P_eff)
                for jj, qq in kills:
                    for j, q in zip(jj.tolist(), qq.tolist()):
                        assert (n0 + j) % q == 0, \
                            f"SCAN DEEP CERT FAIL j={j} q={q}"
        return js[alive]


# ---------------------------------------------------------------- rounds ---
def ring_bounds(cfg, r):
    e = cfg["edges"]
    lo = 0 if r == 1 else e[r - 2]
    return lo, e[r - 1]


def cmd_make(a):
    cfg, P_eff = cfg_of(a)
    sv = ScanSieve(cfg, P_eff)
    r = a.round
    if r == 1:
        st = json.load(open("sc_state.json")) if os.path.exists(
            "sc_state.json") else dict(cfg=cfg, next_t=0, blocks=[])
        assert st["cfg"]["zd"] == cfg["zd"] and st["cfg"]["seed"] == cfg["seed"]
        t0 = st["next_t"]
        ks = [kstart(cfg) + 2 * (t0 + i) for i in range(a.kblock)]
        ks = [k for k in ks if math.gcd(k, cfg["d"]) == 1]
        st["next_t"] = t0 + a.kblock
        assert st["next_t"] < 4 * 10 ** (cfg["kdig"] - 2), \
            "seed k-span exhausted -- move to a fresh seed"
        bid = len(st["blocks"]) + 1
        st["blocks"].append(bid)
        json.dump(st, open("sc_state.json", "w"))
    else:
        carry = json.load(open(f"sc_carry_r{r-1:02d}.json"))
        ks = carry["ks"]; bid = carry["bid"]
        if not ks:
            print(f"round {r}: no survivors carried -- nothing to make")
            return
    lo, hi = ring_bounds(cfg, r)
    ud = r >= getattr(a, "deep_from_ring", 3)
    name = f"sc_r{r:02d}_{bid:04d}"
    sizes, blobs = [], []
    nb = BITS // 8
    t0 = time.time()
    for i, k in enumerate(ks):
        n0 = k * P_eff
        js = np.concatenate([
            sv.survivors(k, -hi, -lo - 1, n0=n0, use_deep=ud) if lo else
            sv.survivors(k, -hi, -1, n0=n0, use_deep=ud),
            sv.survivors(k, lo + 1 if lo else 1, hi, n0=n0, use_deep=ud)])
        order = np.argsort(np.abs(js))          # center-out inside the ring
        js = js[order]
        cands = [int(n0 + int(j)) for j in js]
        sizes.append(len(cands)); blobs.append((k, js.tolist(), cands))
        if (i + 1) % 500 == 0:
            print(f"  {i+1}/{len(ks)} ks, mean ring surv "
                  f"{np.mean(sizes):.0f} [{time.time()-t0:.0f}s]")
    total = sum(sizes)
    import shutil as _sh
    need = total * nb * 1.05 + 2 * 10 ** 8
    free = _sh.disk_usage(".").free
    assert free > need, (f"DISK GUARD: need {need/1e9:.2f} GB for {name}.bin, "
                         f"only {free/1e9:.2f} GB free -- clear space first")
    with open(f"{name}.bin", "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, BITS, total))
        for _, _, cands in blobs:
            for c in cands:
                f.write(c.to_bytes(nb, "little"))
    with open(f"{name}.bin", "rb") as f:
        f.seek(16); c0 = int.from_bytes(f.read(nb), "little")
        f.seek(16 + (total - 1) * nb); cL = f.read(nb)
        assert len(cL) == nb and c0 == blobs[0][2][0] \
            and int.from_bytes(cL, "little") == blobs[-1][2][-1], \
            f"{name}.bin TRUNCATED/CORRUPT on write -- do not drive it"
    json.dump(dict(cfg=cfg, round=r, bid=bid,
                   ks=[b[0] for b in blobs],
                   js=[b[1] for b in blobs], sizes=sizes),
              open(f"{name}.manifest.json", "w"))
    beta = math.exp(GAMMA) * math.log(cfg["deep_q"] or cfg["Q"]) / cfg["ln_n0"]
    print(f"{name}.bin: {len(ks)} ks, {total:,} candidates "
          f"(mean {np.mean(sizes):.0f}/k, ring E ~ "
          f"{np.mean(sizes)*beta:.2f})  -> run: <driver> {name}.bin "
          f"{name}.v.bin")


def cmd_fold(a):
    r = a.round
    import glob
    if getattr(a, "bin", None):
        name = a.bin[:-4] if a.bin.endswith(".bin") else a.bin
        assert os.path.exists(name + ".manifest.json"),             f"no manifest for {a.bin}"
    else:
        mfs = sorted(glob.glob(f"sc_r{r:02d}_*.manifest.json"))
        assert mfs, f"no round-{r} manifests"
        name = mfs[-1][:-len(".manifest.json")]
    man = json.load(open(name + ".manifest.json"))
    hv = open(f"{name}.v.bin", "rb").read()
    m, bits, cnt = struct.unpack("<IIQ", hv[:16])
    v = hv[16:]
    assert m == MAGIC_V and cnt == sum(man["sizes"]) == len(v), \
        "verdict header/count mismatch (0xFF hazard)"
    if any(b == 0xFF for b in v):
        sys.exit("UNTOUCHED 0xFF verdicts -- FATAL")
    pos = 0
    surv_ks = []
    prp_tot = 0
    for k, js, sz in zip(man["ks"], man["js"], man["sizes"]):
        vl = v[pos:pos + sz]; pos += sz
        hits = [js[i] for i in range(sz) if vl[i] in (1, 2)]
        prp_tot += len(hits)
        if not hits:
            surv_ks.append(k)
    json.dump(dict(ks=surv_ks, bid=man["bid"], round=r),
              open(f"sc_carry_r{r:02d}.json", "w"))
    nk = len(man["ks"])
    print(f"round {r}: {nk} ks -> {len(surv_ks)} advance "
          f"(pass rate {len(surv_ks)/max(nk,1):.4f}; ring E_meas "
          f"{prp_tot/max(nk,1):.3f} primes/k)")
    if r == len(man["cfg"]["edges"]):
        print(f"FINAL RING CLEAR: {len(surv_ks)} candidate ks -> run finish")


def cmd_finish(a):
    cfg, P_eff = cfg_of(a)
    r = len(cfg["edges"])
    cf = f"sc_carry_r{r:02d}.json"
    if not os.path.exists(cf):
        print("finish: ladder emptied before the final ring -- "
              "no finalists this block")
        return
    carry = json.load(open(cf))
    if not carry["ks"]:
        print("finish: no finalists this block")
        return
    sv = ScanSieve(cfg, P_eff)
    G = cfg["G"]
    for k in carry["ks"]:
        n0 = gmpy2.mpz(k) * P_eff
        # exact fences: walk beyond the ladder edge until primes both sides
        legs = {}
        for s in (+1, -1):
            j = cfg["edges"][-1] + 1
            j += (j + (0 if s > 0 else 0)) & 1  # even j
            found = None
            prp = 0
            while prp < a.max_prp:
                jj = s * j
                c = n0 + jj
                if all(c % int(p) for p in sv.prs[1:2000]):
                    prp += 1
                    if gmpy2.is_prime(c, 25):
                        found = jj; break
                j += 2
            legs[s] = found
        # interior full re-proof (doctrine: CPU re-proves the whole span)
        jlo = legs[-1] + 2 if legs[-1] else -cfg["edges"][-1]
        jhi = legs[+1] - 2 if legs[+1] else cfg["edges"][-1]
        js = sv.survivors(k, jlo, jhi, n0=n0)
        interior = [int(j) for j in js if gmpy2.is_prime(n0 + int(j), 25)]
        if interior:
            print(f"k={k}: interior prime at j={interior[0]} on CPU re-proof "
                  f"-- ring escalation, LOG IT")
            continue
        gap = legs[+1] - legs[-1]
        ln_act = float(gmpy2.log(n0))
        merit = gap / ln_act
        G = math.ceil(cfg["merit"] * ln_act)     # per-find exact target
        with open("legs.csv", "a") as lf:        # every finalist leg is
            lf.write(f"{k},{legs[-1]},{legs[+1]},{gap},{merit:.6f},"  # paper-1
                     f"{cfg['zd']},{cfg['d']}\n")                     # data
        print(f"k={k}: GAP {gap:,} merit {merit:.4f} "
              f"(jl {legs[-1]} jr {legs[+1]}) "
              f"{'>>> TARGET MET' if gap >= G else '(below target, bank it)'}")
        fn = f"find_scan_D{int(round(cfg['ln_n0']/math.log(10)))}_g{gap}.txt"
        with open(fn, "w") as fh:
            fh.write(f"# gap {gap} merit {merit:.6f}\n"
                     f"# scan zd={cfg['zd']} d={cfg['d']} k={k} "
                     f"seed={cfg['seed']}\n"
                     f"# SUBMIT: {gap} {merit:.6f} {k} * {cfg['zd']}# / "
                     f"{cfg['d']} {legs[-1]:+d}\n")
        print(f"    -> {fn}")


def cmd_status(a):
    if os.path.exists("sc_state.json"):
        st = json.load(open("sc_state.json"))
        print(f"ks issued: {st['next_t']:,}  blocks: {len(st['blocks'])}")
    import glob
    for c in sorted(glob.glob("sc_carry_r*.json")):
        j = json.load(open(c))
        print(f"  {c}: {len(j['ks'])} survivors")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "fold", "finish", "status"])
    ap.add_argument("--zd", type=int, default=6299)
    ap.add_argument("--swap", type=int, nargs="+", default=[2, 3, 5, 7, 11])
    ap.add_argument("--kdig", type=int, default=9)
    ap.add_argument("--merit", type=float, default=32.25)
    ap.add_argument("--Q", type=int, default=10**7)
    ap.add_argument("--deep-q", type=int, default=0)
    ap.add_argument("--rings", default="16858,36956,55914,77570,100293")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--bin", default=None,
                    help="fold exactly this bin (pipelined loops MUST pass "
                         "it; latest-manifest guessing breaks under prefetch)")
    ap.add_argument("--deep-from-ring", type=int, default=3,
                    help="apply the 1e9 deep sieve only from this ring on "
                         "(early rings shallow: +~28%% GPU tests there, "
                         "~60x cheaper make)")
    ap.add_argument("--kblock", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-prp", type=int, default=60000)
    a = ap.parse_args()
    dict(make=cmd_make, fold=cmd_fold, finish=cmd_finish,
         status=cmd_status)[a.cmd](a)


if __name__ == "__main__":
    main()
