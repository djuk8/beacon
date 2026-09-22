#!/bin/bash
# gate_make.sh v1.0 -- C make gates (C, 2026-08-21).  Runs anywhere with gcc + python3 (numpy, gmpy2).
#   M0 build fastmake_c.so (gcc), record sha
#   M1 rung-1 make, same seed, three ways: REF = unpatched production scanhunt (SCANHUNT_REF),
#      NP = patched scanhunt with the numpy kernel (stable order), C = patched scanhunt with the C kernel+pack.
#      C vs NP: bin AND manifest byte-identical.  C vs REF: identical ks, sizes, and per-k js as sets, same candidates.
#   M2 the same on a rung-2 carry (sparse ks -> direct-mod path)
#   Times each make.  Nothing touches the theater.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); W=${W:-/tmp/gate_make}; LOG=$W/gate_make.log; PY=${PY:-python3}
REF=${SCANHUNT_REF:-$HOME/beacon/raid610/scanhunt_v0.py}; RMAP=${RMAP:-$(dirname "$REF")/resonance_map.py}
SEED=${SEED:-9101}; Q=${Q:-100000}
RINGS=1568,4374,7244,10198,13500,17734,26542
ARGS="--zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 37.8241 --Q $Q --deep-q 0 --deep-from-ring 99 --rings $RINGS --bits 2048 --kblock 20000 --seed $SEED"
rm -rf "$W"; mkdir -p "$W"; say(){ echo "$@" | tee -a "$LOG"; }
say "==== gate_make v1.1 $(date -u +%FT%TZ) ref=$REF seed=$SEED Q=$Q"
[ -f "$REF" ] && [ -f "$RMAP" ] || { say "M0: need SCANHUNT_REF (unpatched production scanhunt_v0.py) and resonance_map.py beside it"; exit 1; }
# ---- M0 build
say "--- M0 build ---"; command -v gcc >/dev/null || { say "M0: gcc missing (apt-get install -y gcc)"; exit 1; }
cd "$HERE" && { gcc -O3 -march=native -shared -fPIC -o fastmake_c.so fastmake_c.c 2>/dev/null || gcc -O3 -shared -fPIC -o fastmake_c.so fastmake_c.c; } || { say "M0: build failed"; exit 1; }
say "  fastmake_c.so $(sha256sum fastmake_c.so | cut -c1-12)  src $(sha256sum fastmake_c.c | cut -c1-12)  scanhunt(patched) $(sha256sum scanhunt_v0.py | cut -c1-12)  ref $(sha256sum "$REF" | cut -c1-12)"
for d in ref np c; do mkdir -p "$W/$d"; cp "$RMAP" "$W/$d/"; done
cp "$REF" "$W/ref/scanhunt_v0.py"; cp "$HERE/fastmake_numpy.py" "$W/ref/fastmake.py"                      # ref = production exactly (numpy fastmake)
for d in np c; do cp "$HERE/scanhunt_v0.py" "$HERE/fastmake.py" "$HERE/fastmake_numpy.py" "$HERE/fastmake_c.so" "$W/$d/"; done
mk(){ # $1 dir  $2 round  $3 extra env  -> prints seconds
  local t0; t0=$(date +%s.%N); ( cd "$W/$1" && env $3 $PY scanhunt_v0.py make --round "$2" $ARGS ${4:-} > "make_r$2.log" 2>&1 ) || { say "  make failed in $1 round $2: $(tail -2 "$W/$1/make_r$2.log")"; return 1; }; echo "$(date +%s.%N) - $t0" | bc; }
cmp_sets(){ # $1 dirA $2 dirB $3 stem : same ks, sizes, per-k js as sets, candidates as set
  $PY - "$W/$1/$3" "$W/$2/$3" <<'PY'
import sys, json, struct
a, b = sys.argv[1], sys.argv[2]
ma, mb = json.load(open(a + ".manifest.json")), json.load(open(b + ".manifest.json"))
ok = ma["ks"] == mb["ks"] and ma["sizes"] == mb["sizes"] and all(sorted(x) == sorted(y) for x, y in zip(ma["js"], mb["js"]))
def cands(p, sizes):
    d = open(p + ".bin", "rb").read(); mg, bits, n = struct.unpack("<IIQ", d[:16]); nb = bits // 8; body = d[16:]
    off = 0; out = []
    for s in sizes:
        out.append(sorted(body[(off + i) * nb:(off + i + 1) * nb] for i in range(s))); off += s
    return out
ok = ok and cands(a, ma["sizes"]) == cands(b, mb["sizes"])
print("SET-IDENTICAL" if ok else "SET-DIFFERENT"); sys.exit(0 if ok else 1)
PY
}
# ---- M1 rung 1
say "--- M1 rung-1 make x3 ---"
tr=$(mk ref 1 "A=1") || exit 1; tn=$(mk np 1 "FASTMAKE_IMPL=numpy" "--fast 1") || exit 1; tc=$(mk c 1 "A=1" "--fast 2") || exit 1
say "  times: ref(production) ${tr}s  patched+numpy ${tn}s  patched+C ${tc}s  -> C speedup x$(echo "scale=1; $tr/$tc" | bc) on the whole make"
grep -h "candidates" "$W"/{ref,np,c}/make_r1.log | sed 's/^/  /' | tee -a "$LOG"
stem=sc_r01_0001
cmp -s "$W/np/$stem.bin" "$W/c/$stem.bin" && cmp -s "$W/np/$stem.manifest.json" "$W/c/$stem.manifest.json" && say "  C vs NP: bin + manifest BYTE-IDENTICAL" || { say "M1: FAIL C vs NP differ"; exit 1; }
r=$(cmp_sets ref c $stem); say "  C vs REF(production): $r"; [ "$r" = "SET-IDENTICAL" ] || { say "M1: FAIL"; exit 1; }
cmp -s "$W/ref/$stem.bin" "$W/c/$stem.bin" && say "  (C vs REF even byte-identical on this block)" || say "  (C vs REF differ only in +-j tie order, as expected from numpy's unstable argsort)"
say "M1: PASS"
# ---- M2 rung 2 on an identical carry (every 5th k of the block; no verdicts needed for a make gate)
say "--- M2 rung-2 make on a carry ---"
$PY - "$W/c/$stem.manifest.json" "$W" <<'PY'
import json, sys; m = json.load(open(sys.argv[1])); ks = m["ks"][::5]
for d in ("ref", "np", "c"): json.dump(dict(ks=ks, bid=m["bid"], round=1), open(f"{sys.argv[2]}/{d}/sc_carry_r01.json", "w"))
print("carry ks:", len(ks))
PY
tr=$(mk ref 2 "A=1") || exit 1; tn=$(mk np 2 "FASTMAKE_IMPL=numpy" "--fast 1") || exit 1; tc=$(mk c 2 "A=1" "--fast 2") || exit 1
say "  times: ref ${tr}s  numpy ${tn}s  C ${tc}s"
stem=sc_r02_0001
cmp -s "$W/np/$stem.bin" "$W/c/$stem.bin" && cmp -s "$W/np/$stem.manifest.json" "$W/c/$stem.manifest.json" && say "  C vs NP: BYTE-IDENTICAL" || { say "M2: FAIL C vs NP differ"; exit 1; }
r=$(cmp_sets ref c $stem); say "  C vs REF: $r"; [ "$r" = "SET-IDENTICAL" ] || { say "M2: FAIL"; exit 1; }
say "M2: PASS"
say "--- M1D: deepened fast path vs pure-Q kernel (kblock 400, Q=1e6+deep1e8 vs Q=1e8) ---"
D=$W/m1d; rm -rf $D; mkdir -p $D/a $D/b
CRR=1568,4374,7244,10198,13500,17734,22818,31576
( cd $D/a && $PY $HOME/beacon/raid610/scanhunt_v0.py make --round 1 --zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 45.0 --Q 1000000 --deep-q ${DEEPQ:-100000000} --deep-from-ring 1 --rings $CRR --bits 2048 --seed 9310 --kblock 400 > $D/a/make.out 2>&1 )
grep -q "make path: c-pack+deep" $D/a/make.out || { say "M1D FAIL: deep make did not take the C path ($(grep -m1 'make path' $D/a/make.out))"; exit 1; }
( cd $D/b && $PY $HOME/beacon/raid610/scanhunt_v0.py make --round 1 --zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 45.0 --Q ${DEEPQ:-100000000} --deep-q 0 --deep-from-ring 99 --rings $CRR --bits 2048 --seed 9310 --kblock 400 >/dev/null 2>&1 )
$PY - "$D" <<'PYEOF'
import json, sys
d = sys.argv[1]
A = json.load(open(d+"/a/sc_r01_0001.manifest.json")); B = json.load(open(d+"/b/sc_r01_0001.manifest.json"))
bad = 0 if A["ks"]==B["ks"] else 1
bad += sum(1 for x,y in zip(A["js"],B["js"]) if list(map(int,x))!=list(map(int,y)))
print(("M1D: PASS (deep path == pure-Q kernel, order included, %d ks)" % len(A["ks"])) if bad==0 else "M1D: FAIL")
sys.exit(0 if bad==0 else 1)
PYEOF
[ $? = 0 ] || { say "M1D FAIL"; exit 1; }
say "==== gate_make: ALL PASS.  Install: bash install_make.sh (backs up the production files, hash receipt)."
