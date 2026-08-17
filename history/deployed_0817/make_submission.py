#!/usr/bin/env python3
"""make_submission -- BEACON wave submitter. Certs in, submission-ready out.

Pipeline per cert (notary_cert_gap*.json):
  1. VALIDATE: verdict VALID, mr_rounds>=50, zero pseudoprimes/alarms,
     endpoint flags true, interior accounting closes
     (sieve_factored + fermat_composite == gap - 1).
  2. RECONSTRUCT: p1 = k * zdesign# + jleft (primorial cached per zd);
     digits and merit recomputed independently and cross-checked vs cert.
  3. EXPRESSION: '<k>*<zd>#<+/-off>' built, then re-parsed by an
     independent mini-evaluator and asserted equal to p1 (format fence).
  4. OCCUPANCY vs a CURRENT allgaps.sql (git pull first!): vacant -> NEW;
     held at more digits -> IMPROVE; held at <= our digits -> DEAD (loud
     skip -- the find died at the finish line).
  5. EMIT: exact-format INSERT lines (schema taken from the live upstream
     file, 2026-07) + a portal field block for primegaps.cloudygo.com.
  6. --verify-endpoints N: Fermat base-2 + N MR rounds on both endpoints
     (smoke re-verification; MR-50 remains the notary's certificate).

gapcert policy: 'AUTO' samples the 30 nearest-primedigits rows in the
current table and adopts the majority convention, reporting the sample --
match the community, don't guess it.

Usage (shredder):
  git -C prime-gap-list pull
  python3 make_submission.py --certs 'notary_cert_gap*.json' \
      --sql prime-gap-list/allgaps.sql --discoverer Djuk8 \
      --verify-endpoints 1 --out wave1a
Selftest (real flagship cert vs real upstream snapshot):
  python3 make_submission.py --selftest [--selftest-prp]
"""
import argparse, glob, json, math, os, re, sys, time
import gmpy2

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

ROW_RE = re.compile(r"^INSERT INTO gaps VALUES\((\d+),(\d+),'([^']*)',"
                    r"'([^']*)','([^']*)','([^']*)',(-?\d+),([0-9.]+),(\d+),")

_PCACHE = {}


def primorial(zd):
    if zd not in _PCACHE:
        n = zd + 1
        s = bytearray([1]) * n
        s[0:2] = b"\x00\x00"
        for i in range(2, int(zd ** 0.5) + 1):
            if s[i]: s[i * i::i] = bytearray(len(range(i * i, n, i)))
        P = gmpy2.mpz(1)
        for p in range(2, n):
            if s[p]: P *= p
        _PCACHE[zd] = P
    return _PCACHE[zd]


def ndigits(x):
    return len(gmpy2.digits(x, 10))


def load_table(path):
    rows = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        m = ROW_RE.match(line)
        if m:
            g = int(m.group(1))
            rows[g] = dict(digits=int(m.group(9)), disc=m.group(6),
                           year=int(m.group(7)), merit=float(m.group(8)),
                           gapcert=m.group(5))
    return rows


def gapcert_auto(rows, digits, k=30):
    near = sorted(rows.values(), key=lambda r: abs(r["digits"] - digits))[:k]
    tally = {}
    for r in near:
        tally[r["gapcert"]] = tally.get(r["gapcert"], 0) + 1
    best = max(tally, key=tally.get)
    return best, tally


def eval_expr(expr):
    m = re.fullmatch(r"(\d+)\*(\d+)#([+-]\d+)", expr)
    assert m, f"expression format: {expr!r}"
    return int(m.group(1)) * primorial(int(m.group(2))) + int(m.group(3))


def process_cert(c, rows, disc, year, gapcert, verify):
    errs = []
    req = lambda cond, msg: cond or errs.append(msg)
    req(c.get("verdict") == "VALID", "verdict != VALID")
    req(c.get("mr_rounds", 0) >= 50, "mr_rounds < 50")
    it = c.get("interior", {})
    req(it.get("pseudoprimes", 1) == 0, "pseudoprimes != 0")
    req(not c.get("interior", {}).get("prp_alarms", ["x"]), "prp_alarms nonempty")
    req(it.get("sieve_factored", 0) + it.get("fermat_composite", 0)
        == c["gap"] - 1, "interior accounting open")
    for e in ("p1", "p2"):
        ep = c.get("endpoints", {}).get(e, {})
        req(ep.get("fermat_bases_pass") and ep.get("is_prime_mr"),
            f"{e} endpoint flags")
    if errs:
        return dict(status="REJECT", why="; ".join(errs), gap=c.get("gap"))

    k, zd, jl, jr, gap = (c["k"], c["zdesign"], c["jleft"], c["jright"],
                          c["gap"])
    P = primorial(zd)
    p1 = int(k) * P + jl
    dg = ndigits(p1)
    merit = gap / float(gmpy2.log(p1))
    if abs(merit - c["merit"]) > 5e-4:
        return dict(status="REJECT", why=f"merit mismatch {merit:.6f} vs "
                                         f"{c['merit']}", gap=gap)
    note = ""
    if abs(dg - c["n0_digits"]) > 6:   # design label slack ~ log10(zd)
        return dict(status="REJECT", why=f"digits {dg} vs cert "
                    f"{c['n0_digits']} (|diff|>6)", gap=gap)
    if dg != c["n0_digits"]:
        note = (f"measured {dg}d (cert label {c['n0_digits']} = design D; "
                f"list gets measured)")
    expr = f"{k}*{zd}#{jl:+d}"
    assert eval_expr(expr) == p1, "expression roundtrip failed"
    assert jr - jl == gap, "fence/gap inconsistency"

    inc = rows.get(gap)
    if inc is None:
        status = "NEW"
    elif inc["digits"] > dg:
        status = f"IMPROVE(beats {inc['digits']}d {inc['disc']} {inc['year']})"
    else:
        return dict(status="DEAD", why=f"held at {inc['digits']}d by "
                    f"{inc['disc']} {inc['year']} (<= ours)", gap=gap)

    if verify:
        for name, pp in (("p1", p1), ("p2", int(k) * P + jr)):
            assert gmpy2.powmod(2, pp - 1, pp) == 1, f"{name} Fermat FAIL"
            assert gmpy2.is_prime(pp, verify), f"{name} MR FAIL"

    line = (f"INSERT INTO gaps VALUES({gap},0,'C','?','{gapcert}',"
            f"'{disc}',{year},{merit:.4f},{dg},'{expr}');")
    assert ROW_RE.match(line), "emitted line fails the upstream row regex"
    # primegaps.cloudygo.com format (SethTro, mersenneforum #137):
    #   <GAP> <MERIT> <NUMBER>    e.g. "22558 23.779 104304433*977#/7#-15234"
    # NUMBER is the gap-start (low endpoint); expr = k*zd#+jleft is exactly that.
    # 6-digit merit per MJansen (#138). Set Discoverer + date in the web form.
    portal = f"{gap} {merit:.6f} {expr}"
    return dict(status=status, gap=gap, merit=merit, digits=dg, expr=expr,
                sql=line, portal=portal, note=note)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--certs", default="notary_cert_gap*.json")
    ap.add_argument("--sql", default="prime-gap-list/allgaps.sql")
    ap.add_argument("--discoverer", default="Djuk8")
    ap.add_argument("--fullname", default="")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--gapcert", default="AUTO")
    ap.add_argument("--verify-endpoints", type=int, default=0,
                    help="0 = trust the notary's MR-50 (fast, default); "
                         "N>0 = re-prove both endpoints with N MR rounds "
                         "(~1 min/find at 24k digits, paranoid final pass)")
    ap.add_argument("--out", default="wave")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--selftest-prp", action="store_true")
    a = ap.parse_args()
    if a.selftest or a.selftest_prp:
        return selftest(a)

    rows = load_table(a.sql)
    print(f"table: {len(rows):,} gap rows from {a.sql}")
    files = sorted(glob.glob(a.certs))
    if not files:
        raise SystemExit(f"no certs match {a.certs!r}")
    certs = [json.load(open(f)) for f in files]
    gc = a.gapcert
    if gc == "AUTO":
        gc, tally = gapcert_auto(rows, certs[0]["n0_digits"])
        print(f"gapcert AUTO -> '{gc}' (nearest-digit sample: {tally})")

    results, t0 = [], time.time()
    for c in certs:
        r = process_cert(c, rows, a.discoverer, a.year, gc,
                         a.verify_endpoints)
        results.append(r)
        print(f"  gap {r['gap']:>9,}: {r['status']}"
              + (f"  merit {r['merit']:.4f}" if "merit" in r else
                 f"  [{r['why']}]")
              + (f"  ({r['note']})" if r.get("note") else ""))
    good = [r for r in results if r["status"] not in ("DEAD",) and
            not r["status"].startswith("REJECT")]
    with open(f"{a.out}.sql", "w") as f:
        if a.fullname:
            f.write(f"INSERT INTO credits VALUES('{a.discoverer}',"
                    f"'{a.fullname}','','{a.fullname}');\n")
        for r in good: f.write(r["sql"] + "\n")
    with open(f"{a.out}_portal.txt", "w") as f:
        for r in good: f.write(r["portal"] + "\n")
    print(f"\n{len(good)}/{len(results)} submittable -> {a.out}.sql, "
          f"{a.out}_portal.txt  [{time.time()-t0:.0f}s]")
    print("SUBMIT AT: primegaps.cloudygo.com (per prime-gap-list README); "
          "re-run this tool after a FRESH git pull immediately before "
          "submitting.")


FIXTURE = dict(handle="djuk8", verdict="VALID", k=2740807, zdesign=55603,
               jleft=-68399, jright=62483, gap=130882, merit=2.368494,
               n0_digits=24000,
               endpoints=dict(p1=dict(fermat_bases_pass=True,
                                      is_prime_mr=True),
                              p2=dict(fermat_bases_pass=True,
                                      is_prime_mr=True)),
               interior=dict(count=130881, sieve_factored=129939,
                             fermat_composite=942, pseudoprimes=0,
                             prp_alarms=[]),
               mr_rounds=50)


def selftest(a):
    n = [0]
    def ok(cond, msg):
        print(("  pass: " if cond else "  FAIL: ") + msg)
        if not cond: sys.exit(1)
        n[0] += 1
    t0 = time.time()
    upstream = "allgaps_upstream.sql"
    if os.path.exists(upstream):
        rows = load_table(upstream)
        ok(len(rows) > 100_000, f"S1 upstream parsed ({len(rows):,} rows)")
    else:
        rows = {}
        ok(True, "S1 (no upstream snapshot; using synthetic only)")
    gc, tally = gapcert_auto(rows or {0: dict(digits=1, disc="", year=0,
                             merit=0, gapcert="P")}, 24000)
    print(f"    (info) gapcert AUTO near 24,000 digits -> '{gc}' {tally}")

    r = process_cert(dict(FIXTURE), rows, "Djuk8", 2026, gc, 0)
    ok(r["status"] == "NEW" and abs(r["merit"] - 2.368494) < 5e-4
       and r["digits"] == 23999 and "measured" in r["note"],
       f"S2 real cert 130882: {r['status']}, merit {r.get('merit', 0):.6f} "
       f"(cert 2.368494), digits {r.get('digits')} [{r.get('note', '')}]")
    ok(r["expr"] == "2740807*55603#-68399" and
       eval_expr(r["expr"]) == 2740807 * primorial(55603) - 68399,
       f"S3 expression + independent roundtrip: {r['expr']}")
    ok(ROW_RE.match(r["sql"]) is not None, f"S4 emitted line format-exact: "
       f"{r['sql'][:70]}...")

    # displacement stub vs live table (GPU find 229062 @ 9,800d)
    stub = dict(FIXTURE, k=1533084, zdesign=22717, jleft=-162823,
                jright=66239, gap=229062, n0_digits=9800, merit=10.1490,
                interior=dict(count=229061, sieve_factored=228000,
                              fermat_composite=1061, pseudoprimes=0,
                              prp_alarms=[]))
    stub["merit"] = 229062 / float(gmpy2.log(
        1533084 * primorial(22717) - 162823))
    r2 = process_cert(stub, rows, "Djuk8", 2026, gc, 0)
    ok(r2["status"].startswith("IMPROVE(beats 11843d"),
       f"S5 live displacement check 229062: {r2['status']} "
       f"(measured {r2.get('digits')}d)")

    # synthetic DEAD + REJECT
    rows_s = dict(rows); rows_s[130882] = dict(digits=9000, disc="X",
                                               year=2026, merit=9.9,
                                               gapcert=gc)
    r3 = process_cert(dict(FIXTURE), rows_s, "Djuk8", 2026, gc, 0)
    ok(r3["status"] == "DEAD", f"S6 finish-line death detected: {r3['why']}")
    bad = dict(FIXTURE); bad["interior"] = dict(FIXTURE["interior"],
                                                fermat_composite=941)
    r4 = process_cert(bad, rows, "Djuk8", 2026, gc, 0)
    ok(r4["status"] == "REJECT" and "accounting" in r4["why"],
       f"S7 broken interior accounting rejected")

    if a.selftest_prp:
        tp = time.time()
        r5 = process_cert(dict(FIXTURE), rows, "Djuk8", 2026, gc, 1)
        ok(not r5["status"].startswith("REJECT"),
           f"S8 REAL endpoint re-verification (Fermat b2 + MR) "
           f"[{time.time()-tp:.0f}s]")
    print(f"\nSUBMITTER SELFTEST: ALL CHECKS PASS -- {n[0]} checks "
          f"[{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
