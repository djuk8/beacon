#!/usr/bin/env python3
"""compare_vbin.py -- early-exit v.bin vs legacy full v.bin for one ring: tested prefixes byte-identical, survivors identical, no PRP beyond prefix, prefix on a schedule boundary, uniform marker. exit 0 PASS."""
import sys, json, struct
stem, chunk, growth = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
new_p = sys.argv[4] if len(sys.argv) > 4 else stem + ".v.bin"; leg_p = sys.argv[5] if len(sys.argv) > 5 else stem + ".legacy.v.bin"
man = json.load(open(stem + ".manifest.json")); sizes = man["sizes"]
def body(p):
    b = open(p, "rb").read(); mg, bits, n = struct.unpack("<IIQ", b[:16]); assert mg == 0x31563247 and n == sum(sizes) and len(b) == 16 + n, p; return b[16:]
new, leg = body(new_p), body(leg_p)
S = max(sizes); bnd = {0}; c = float(chunk); x = 0
while x < S: x = min(S, x + max(1, int(round(c)))); bnd.add(x); c = c * growth if growth > 1 else c
off = 0; fails = []; tested = 0; markers = set(); prp = 0
for k, s in enumerate(sizes):
    L = leg[off:off + s]; N = new[off:off + s]; off += s
    t = next((i for i, b in enumerate(N) if b not in (0, 1, 2)), s)     # tested prefix = up to first marker
    if any(b == 0xFF for b in N): fails.append(f"k{k}: 0xFF")
    if N[:t] != L[:t]: fails.append(f"k{k}: prefix differs")
    h = next((i for i, b in enumerate(L) if b in (1, 2)), None)
    if h is None:
        if t != s: fails.append(f"k{k}: survivor not fully tested ({t}/{s})")
    else:
        prp += 1
        if t < h + 1: fails.append(f"k{k}: stopped before legacy first PRP")
        if t != s and t not in bnd and t != min(s, max(b for b in bnd if b <= t) ): fails.append(f"k{k}: prefix {t} not on a schedule boundary {sorted(bnd)}")
        if any(b in (1, 2) for b in N[t:]): fails.append(f"k{k}: PRP beyond prefix")
    markers.update(N[t:]); tested += t
if len(markers) > 1: fails.append(f"marker not uniform {markers}")
print(f"COMPARE {stem}: ks={len(sizes)} prp_ks={prp} tested={tested}/{sum(sizes)} ({tested/sum(sizes):.3f}) marker={sorted(markers)} {'PASS' if not fails else 'FAIL '+str(fails[:4])}")
sys.exit(0 if not fails else 1)
