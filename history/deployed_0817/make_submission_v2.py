#!/usr/bin/env python3
"""make_submission_v2.py -- build a submission file that the project's OWN
validator accepts, and prove it line by line before you paste anything.

Reads check_records.py scan output (or any text with the same
`gap G merit M ... k=K zd=Z jl=A jr=B` shape) and emits SethTro format:

    <GAP> <MERIT> <startprime>

CRITICAL FORMAT NOTE. parse_num in prime-gap-list/check.py has SIX regexes
and EVERY primorial form requires a divisor:
    RE_1  m*(p#)/d+a        RE_2  (p#)/d+a       RE_5  m*p#/d#+a
There is NO regex for `m*p#+a`. A d=1 anchor written the obvious way does
not parse and the submission is silently unprocessable. Write `/1`.
Zero of the 121,397 live entries use a bare m*p#+a.

Integrity checks run on every find before it is emitted:
  * gap == jr - jl
  * both offsets ODD           (d=1 anchor -> n0 even -> candidates odd)
  * both |offsets| are zd-ROUGH: 1, or prime > zd. Under n0 = k*P#(zd) a
    fence at a non-rough offset is arithmetically impossible, so a failure
    means a corrupt log line, not a bad prime.
  * the emitted string round-trips through the real parse_num and equals
    the reconstructed p1
NOTE this does NOT re-verify primality or that the interior is composite.
That is the notary's job and it is not replaced here.

  python3 make_submission_v2.py scan.txt --discoverer djuk8 -o submit.txt
"""
import argparse, math, re, sys
import gmpy2
from gmpy2 import mpz

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

LINE = re.compile(r"gap\s+([\d,]+)\s+merit\s+[\d.]+.*?k=(\d+)\s+zd=(\d+)\s+"
                  r"jl=(-?\d+)\s+jr=(-?\d+)")

# the real thing, copied from prime-gap-list/check.py
RE_1 = re.compile(r"^(\d+)\*\(?(\d+)#\)?/(\d+)([+-]\d+)$")


def parse_num(start):
    m = RE_1.match(start.replace(" ", ""))
    if not m:
        return None
    mm, p, d, a = map(int, m.groups())
    K = mm * gmpy2.primorial(p)
    if K % d:
        return None
    return K // d + a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scan")
    ap.add_argument("-o", "--out", default="submission.txt")
    ap.add_argument("--discoverer", default="djuk8")
    ap.add_argument("--divisor", type=int, default=1,
                    help="d of the anchor. 1 = primorial, 2 = drop-2.")
    a = ap.parse_args()

    if not re.fullmatch(r"[\w.&]*", a.discoverer) or len(a.discoverer) > 8:
        sys.exit(f"discoverer {a.discoverer!r} violates the CI regex "
                 r"'[\w.&]*' or the 8-char field. No spaces.")

    finds = []
    for ln in open(a.scan):
        m = LINE.search(ln)
        if m:
            g, k, zd, jl, jr = (int(x.replace(",", "")) for x in m.groups())
            finds.append((g, k, zd, jl, jr))
    if not finds:
        sys.exit("no finds parsed -- check the scan format")
    print(f"parsed {len(finds)} finds, discoverer={a.discoverer}, d={a.divisor}")

    zds = {f[2] for f in finds}
    prim = {z: gmpy2.primorial(z) for z in zds}
    print(f"primorials built for zd in {sorted(zds)}")

    out, bad = [], 0
    for g, k, zd, jl, jr in sorted(finds):
        why = []
        if jr - jl != g:
            why.append(f"gap {g} != jr-jl {jr-jl}")
        for j in (jl, jr):
            if j % 2 == 0 and a.divisor == 1:
                why.append(f"offset {j} is EVEN under a d=1 anchor")
            r = abs(j)
            if r != 1 and not (r > zd and gmpy2.is_prime(r, 25)):
                why.append(f"offset {j} is not zd-rough")
        base = prim[zd] // a.divisor
        p1 = mpz(k) * base + jl
        s = f"{k}*{zd}#/{a.divisor}{jl:+d}"
        if parse_num(s) != p1:
            why.append("does not round-trip through parse_num")
        digits = p1.num_digits(10)
        merit = g / float(gmpy2.log(p1))
        if why:
            bad += 1
            print(f"  REJECT gap {g:,}: " + "; ".join(why))
            continue
        out.append((g, merit, s, digits))

    with open(a.out, "w") as fh:
        for g, merit, s, _ in out:
            fh.write(f"{g} {merit:.6f} {s}\n")

    print(f"\n{len(out)} lines written to {a.out}, {bad} rejected")
    if out:
        d = [o[3] for o in out]
        print(f"start-prime digits: {min(d):,} to {max(d):,}")
        print(f"merit: {min(o[1] for o in out):.4f} to {max(o[1] for o in out):.4f}")
        print(f"gap:   {min(o[0] for o in out):,} to {max(o[0] for o in out):,}")
        print("\nfirst 3 and last 2 lines:")
        for g, m_, s, _ in out[:3] + out[-2:]:
            print(f"  {g} {m_:.6f} {s}")
    print("\nNOT CHECKED HERE: primality of either endpoint, and that every "
          "interior survivor is composite. That is the notary.")


if __name__ == "__main__":
    main()
