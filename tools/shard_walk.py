#!/usr/bin/env python3
"""shard_walk.py -- pfgw-sharded fence walker for high-digit theaters.

Replaces the gmpy2 walk in salvage_v0 (4-10 s/test single-core at 90k
bits) with center-out SHARDS driven through pfgw_drv.py at -j N: sieve
the +/-span window once, order survivors by |j|, PRP them in batches of
--shard through the same driver the theater already trusts, stop the
moment both fences are found. ~8.4 s/test / N jobs => minutes per k
instead of hours. Same ledger file + format as salvage_v0
(salvage_finds.log: "gap merit k jl jr"), same done-set dedup, same
KEEP-unresolved manifest semantics, lockfile against concurrent runs.

  python3 shard_walk.py --glob 'walkbay4/*.manifest.json' --span 700000 \
      --floor 1000000 --jobs 24
  python3 shard_walk.py --finalist hunt_s1/FINALIST_0007.json --jobs 56

--finalist mode: reads a carry file (ks/bid/round), takes cfg from
sc_state.json, forces the full-interior check (every survivor inside
the ladder edge must be composite; any PRP there = ring escalation,
logged and skipped) before walking the fences -- i.e. the safe `finish`
for 90k-bit finalists. AGE-GATE DOCTRINE unchanged: never point --glob
at a live theater's hunt_s*/ -- move fossils (-mmin +240 on mono) into
a walkbay first. Freeze discipline: BANKS, does not submit.
"""
import argparse, glob, json, math, os, struct, subprocess, sys, time
import numpy as np, gmpy2

sys.set_int_max_str_digits(2_000_000)
LOCK = ".shardwalk.lock"
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
GAMMA = 0.5772156649015329


def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** .5) + 1):
        if s[i]: s[i * i::i] = False
    return np.nonzero(s)[0]


def sieve_window(k, P_eff, prs, PEm, S, n0):
    """Even-j survivors of [-S, S] (n0 odd), shallow-sieved to max(prs)."""
    js = np.arange(-S, S + 1, dtype=np.int64)
    alive = np.ones(len(js), dtype=bool)
    par = int(n0 % 2)
    alive[(js % 2) != (0 if par else 1)] = False
    n0m = (int(k) % prs) * PEm % prs
    W = 2 * S + 1
    small = prs[prs <= W]
    for i in range(1, len(small)):
        q = int(small[i]); j0 = (-int(n0m[i])) % q
        st = -S + ((j0 - (-S)) % q); alive[st + S::q] = False
    big = prs[len(small):]; m = n0m[len(small):]
    j0 = (-m) % big
    st = -S + ((j0 - (-S)) % big); ok = st <= S
    alive[(st[ok] + S).astype(np.int64)] = False
    alive[S] = False                               # j = 0
    return js[alive]


def drive_shard(cands_j, n0, bits, jobs, drv, tag):
    nb = bits // 8
    bf, vf = f"_walk_{tag}.bin", f"_walk_{tag}.v.bin"
    with open(bf, "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, bits, len(cands_j)))
        for j in cands_j:
            f.write(int(n0 + int(j)).to_bytes(nb, "little"))
    subprocess.run([sys.executable, drv, bf, vf, "-j", str(jobs)],
                   check=True)
    hv = open(vf, "rb").read()
    m, b, cnt = struct.unpack("<IIQ", hv[:16])
    v = hv[16:]
    assert m == MAGIC_V and cnt == len(cands_j) == len(v), \
        "walker verdict header/count mismatch"
    assert not any(x == 0xFF for x in v), "0xFF verdicts -- FATAL"
    os.remove(bf); os.remove(vf)
    return v


def walk_k(k, P_eff, prs, PEm, core, a, ledger, zd, d, bits, interior):
    t0 = time.time()
    n0 = gmpy2.mpz(k) * P_eff
    ln = float(gmpy2.log(n0))
    js = sieve_window(k, P_eff, prs, PEm, a.span, n0)
    inner = js[np.abs(js) <= core]
    outer = js[np.abs(js) > core]
    outer = outer[np.argsort(np.abs(outer), kind="stable")]
    if interior and len(inner):
        v = drive_shard(inner.tolist(), n0, bits, a.jobs, a.drv,
                        f"{k}_int")
        hits = [int(inner[i]) for i in range(len(inner)) if v[i] in (1, 2)]
        if hits:
            print(f"k={k}: interior prime at j={hits[0]} -- ring "
                  f"escalation, LOG IT [{time.time()-t0:.0f}s]")
            return "escalated"
    fen = {1: None, -1: None}
    for s0 in range(0, len(outer), a.shard):
        sh = outer[s0:s0 + a.shard].tolist()
        v = drive_shard(sh, n0, bits, a.jobs, a.drv, f"{k}_{s0}")
        for j, verd in zip(sh, v):
            sg = 1 if j > 0 else -1
            if verd in (1, 2) and fen[sg] is None:
                fen[sg] = int(j)
        if fen[1] is not None and fen[-1] is not None:
            break
    if fen[1] is None or fen[-1] is None:
        print(f"k={k}: fence beyond span (RECORD-CLASS?) -- rerun with "
              f"--span {a.span + 200000} [{time.time()-t0:.0f}s]")
        return "unresolved"
    gap = fen[1] - fen[-1]; merit = gap / ln
    print(f"k={k}: GAP {gap:,} merit {merit:.4f} "
          f"(jl {fen[-1]} jr {fen[1]}) [{time.time()-t0:.0f}s]")
    ledger.write(f"{gap} {merit:.4f} {k} {fen[-1]} {fen[1]}\n")
    ledger.flush(); os.fsync(ledger.fileno())
    if gap >= a.floor:
        D = int(round(ln / math.log(10)))
        with open(f"find_salvage_D{D}_g{gap}.txt", "w") as f:
            f.write(f"gap {gap} merit {merit:.6f} k={k} zd={zd} d={d} "
                    f"jl={fen[-1]} jr={fen[1]} core_certified={core} "
                    f"channel=shardwalk\n")
    return "done"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=None)
    ap.add_argument("--finalist", default=None)
    ap.add_argument("--span", type=int, default=700000)
    ap.add_argument("--floor", type=int, default=1000000)
    ap.add_argument("--shard", type=int, default=2000)
    ap.add_argument("--jobs", type=int, default=24)
    ap.add_argument("--drv", default="pfgw_drv.py")
    ap.add_argument("--bits", type=int, default=0)
    a = ap.parse_args()
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
    except FileExistsError:
        sys.exit(f"another walk holds {LOCK}; rm it if that pid is dead")
    try:
        run(a)
    finally:
        try: os.remove(LOCK)
        except FileNotFoundError: pass


def run(a):
    done = set()
    try:
        for ln in open("salvage_finds.log"):
            done.add(int(ln.split()[2]))
    except FileNotFoundError:
        pass
    ledger = open("salvage_finds.log", "a", buffering=1)
    if a.finalist:
        carry = json.load(open(a.finalist))
        cfg = json.load(open("sc_state.json"))["cfg"]
        jobsets = [(a.finalist, carry["ks"], cfg, cfg["edges"][-1], True)]
    else:
        assert a.glob, "--glob or --finalist required"
        mans = sorted(glob.glob(a.glob))
        if not mans:
            print("no manifests for", a.glob); return
        jobsets = []
        for mf in mans:
            man = json.load(open(mf))
            core = man["cfg"]["edges"][man["round"] - 2] \
                if man["round"] >= 2 else 0
            jobsets.append((mf, man["ks"], man["cfg"], core, False))
    cfg0 = jobsets[0][2]
    zd, d = cfg0["zd"], cfg0["d"]
    bits = a.bits or cfg0.get("bits", 90112)
    print(f"shard_walk: {len(jobsets)} sets, zd={zd} d={d} bits={bits} "
          f"span +/-{a.span} jobs={a.jobs}")
    prs = primes_upto(10 ** 6)
    P = gmpy2.mpz(1); p = gmpy2.mpz(2)
    while p <= zd: P *= p; p = gmpy2.next_prime(p)
    P_eff = P // d
    PEm = np.array([int(P_eff % int(q)) for q in prs], dtype=np.int64)
    os.makedirs("salvaged", exist_ok=True)
    for mf, ks, cfg, core, interior in jobsets:
        pend = [int(k) for k in ks if int(k) not in done]
        unresolved = False
        for k in pend:
            done.add(k)
            r = walk_k(k, P_eff, prs, PEm, core, a, ledger, zd, d,
                       bits, interior)
            if r == "unresolved":
                unresolved = True
        if a.finalist:
            continue                       # carry files are never archived
        if pend and unresolved:
            print(f"{mf}: KEPT (span-exceeder pending wider sweep)")
        else:
            os.rename(mf, "salvaged/" + os.path.basename(mf))
    ledger.close()


if __name__ == "__main__":
    main()
