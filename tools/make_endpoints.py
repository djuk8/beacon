#!/usr/bin/env python3
"""make_endpoints.py -- write the four endpoints of the two record gaps as decimal, plus Primo (.in) and CM/ecpp inputs, plus submission lines.
Run on shredder or box1:  python3 make_endpoints.py   (needs gmpy2). Verifies each endpoint is PRP before writing."""
import gmpy2, json
def primorial_over(zd, swap):
    P = gmpy2.mpz(1); s = bytearray([1]) * (zd + 1); s[0] = s[1] = 0
    for i in range(2, int(zd ** 0.5) + 1):
        if s[i]: s[i*i::i] = bytearray(len(s[i*i::i]))
    for p in range(2, zd + 1):
        if s[p]: P *= p
    for q in swap: P //= q
    return P
P = primorial_over(1439, [2, 3, 5, 7, 11])
finds = [dict(k=17440361647223, jl=-21464, jr=38260, gap=59724, merit=42.5192), dict(k=17325055497313, jl=-29514, jr=28902, gap=58416, merit=41.5882)]
lines = []
for f in finds:
    n0 = f["k"] * P
    for tag, j in (("p1", f["jl"]), ("p2", f["jr"])):
        p = n0 + j; assert gmpy2.is_prime(p, 25), f"{tag} of gap {f['gap']} is not PRP?!"
        name = f"gap{f['gap']}_{tag}"
        open(name + ".dec", "w").write(str(p) + "\n")
        open(name + ".in", "w").write(f"[Candidate]\nN={p}\n")                       # Primo 4.x candidate file
        print(f"{name}: {p.num_digits(10)} digits, PRP ok -> {name}.dec / {name}.in")
    expr = f"{f['k']}*1439#/2310{f['jl']:+d}"                                          # start prime as a primorial expression
    lines.append(f"{f['gap']}  C?P  {f['merit']:.4f}  2026  djuk8  611  {expr}")
open("submission_lines.txt", "w").write("\n".join(lines) + "\n"); print("\nsubmission lines (start prime = expression; status C?P until the ECPP certificates replace ?P with C):"); print("\n".join(lines))
