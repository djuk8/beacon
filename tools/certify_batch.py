#!/usr/bin/env python3
"""certify_batch.py -- certify every parade claim: notary v2 (interior proven composite, endpoints PRP) + ECPP (CM ecpp) on both endpoints.
Input : campaign_ledger.log (gap merit k jl jr ts rung), arbitrage_map_v0.csv (per-gap-size current record merit)
Output: parade_certified.txt (gap C merit year djuk8 digits start-expr), certs/<gap>_<k>/{notary.json,p1.cert,p2.cert}, certify.log
Resumable: claims already in certs/ with all three files are skipped.
Usage (shredder): python3 certify_batch.py --ledger campaign_ledger.log --table arbitrage_map_v0.csv --jobs 60 [--min-merit 0] [--limit N]
"""
import argparse, csv, json, os, subprocess, sys, time, concurrent.futures as cf, gmpy2
ZD, SWAP = 1439, [2, 3, 5, 7, 11]
def primorial_over(zd, swap):
    P = gmpy2.mpz(1); s = bytearray([1]) * (zd + 1); s[0] = s[1] = 0
    for i in range(2, int(zd ** 0.5) + 1):
        if s[i]: s[i*i::i] = bytearray(len(s[i*i::i]))
    for p in range(2, zd + 1):
        if s[p]: P *= p
    for q in swap: P //= q
    return P
P = primorial_over(ZD, SWAP)
def certify(item, ecpp, notary):
    gap, merit, k, jl, jr = item; d = f"certs/{gap}_{k}"; os.makedirs(d, exist_ok=True)
    if all(os.path.exists(f"{d}/{f}") for f in ("notary.json", "p1.cert", "p2.cert", "ok")): return (gap, k, "skip")
    n0 = k * P; p1, p2 = n0 + jl, n0 + jr
    try:
        r = subprocess.run([sys.executable, notary, "--k", str(k), "--zd", str(ZD), "--swap", *map(str, SWAP), "--jl", str(jl), "--jr", str(jr), "--z", "1e9"], capture_output=True, text=True, cwd=d, timeout=900)
        if "VERDICT: VALID" not in r.stdout: return (gap, k, "NOTARY-INVALID: " + r.stdout[-200:].replace("\n", " "))
        cert = [f for f in os.listdir(d) if f.startswith("notary_cert_")]
        if cert: os.replace(f"{d}/{cert[0]}", f"{d}/notary.json")
        for tag, p in (("p1", p1), ("p2", p2)):
            cf_ = f"{d}/{tag}.cert"
            def pari_ok():
                if not (os.path.exists(cf_) and os.path.getsize(cf_) > 1000): return False
                r = subprocess.run(["gp", "-q"], input=f'print(primecertisvalid(read("{cf_}")))\n', capture_output=True, text=True, timeout=1800)
                return r.stdout.strip().splitlines()[-1:] == ["1"]
            if not pari_ok():
                for f in (cf_, cf_ + ".cert1", cf_ + ".cert2", cf_ + ".primo"):
                    try: os.remove(f)
                    except OSError: pass
                subprocess.run([ecpp, "-n", str(p), "-f", cf_], capture_output=True, text=True, timeout=1800)   # verdict comes from PARI, not from ecpp's text
                if not pari_ok(): return (gap, k, f"ECPP-FAIL {tag}: certificate missing or PARI primecertisvalid != 1")
        open(f"{d}/ok", "w").write(time.strftime("%FT%TZ", time.gmtime()) + "\n"); return (gap, k, "ok")
    except Exception as e: return (gap, k, f"ERROR {type(e).__name__}: {e}")
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ledger", required=True); ap.add_argument("--table", required=True); ap.add_argument("--jobs", type=int, default=60)
    ap.add_argument("--min-merit", type=float, default=0.0); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--ecpp", default="/usr/local/bin/ecpp"); ap.add_argument("--notary", default=os.path.abspath("notary_v2.py"))
    a = ap.parse_args()
    rec = {int(r["gapsize"]): float(r["current_merit"]) for r in csv.DictReader(open(a.table))}
    items = {}
    for ln in open(a.ledger):
        f = ln.split()
        if len(f) < 5: continue
        try: gap, merit, k, jl, jr = int(f[0]), float(f[1]), int(f[2]), int(f[3]), int(f[4])
        except ValueError: continue
        if merit < a.min_merit: continue
        if gap in rec and merit > rec[gap] and (gap not in items or merit > items[gap][1]): items[gap] = (gap, merit, k, jl, jr)   # best claim per gap size
    todo = sorted(items.values(), key=lambda x: -x[1]); todo = todo[:a.limit] if a.limit else todo
    print(f"claims to certify: {len(todo)} (best per gap size, merit >= {a.min_merit})", flush=True); os.makedirs("certs", exist_ok=True); t0 = time.time(); ok = bad = skip = 0
    with cf.ThreadPoolExecutor(a.jobs) as ex, open("certify.log", "a") as lg, open("parade_certified.txt", "a") as out:
        futs = {ex.submit(certify, it, a.ecpp, a.notary): it for it in todo}
        for i, fu in enumerate(cf.as_completed(futs), 1):
            gap, k, st = fu.result(); it = futs[fu]; lg.write(f"{gap} {k} {st}\n"); lg.flush()
            if st in ("ok", "skip"):
                if st == "ok": ok += 1
                else: skip += 1
                out.write(f"{gap}  C  {it[1]:.4f}  2026  djuk8  611  {k}*1439#/2310{it[3]:+d}\n"); out.flush()
            else: bad += 1
            if i % 100 == 0 or i == len(todo): print(f"  {i}/{len(todo)}  ok {ok}  skipped {skip}  failed {bad}  {(time.time()-t0)/60:.1f} min", flush=True)
    print(f"done: {ok} certified, {skip} already, {bad} failed -> parade_certified.txt, certs/ (see certify.log)")
if __name__ == "__main__": main()
