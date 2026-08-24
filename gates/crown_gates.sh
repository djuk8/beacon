#!/bin/bash
# crown_gates.sh v1.13 -- consolidated CROWN_PREREG gate runner.
# v1.12 -> v1.13: S9 parses the unknowns files for TRUE per-window
# counts ('saving X/Y' semantics misread -> S7 measurement leg
# retracted pending this). P-S8a REFUTED (5.55 core-ms/window);
# O3-via-CPU REFUTED at fleet scale; ladder restructured O1-first.
# v1.11 -> v1.12: S8 marginal-cost pair (minc 100 vs 2100 @ Q=1e9)
# -- fixed prime-enumeration cost amortizes at production minc; the
# gate metric is d(cpu)/d(window). Plus wc -l on all unknowns files.
# v1.10 -> v1.11: mstart cap is 1e10 (tool validation; 1e13 tier
# retired -> O3b integration workstream); SL 26542 -> 26620 = 2^2*5*11^3
# (gcd(SL,K)=1 required; 26542 = 2*23*577 tripped it). Gate validity:
# sieve cost and canary are m-magnitude independent.
# v1.9 -> v1.10: mkdir unknowns/ -- gap_common.cpp:890 prepends
# 'unknowns/' to bare -u filenames; dir absent in a fresh clone.
# v1.8 -> v1.9: filename-driven invocations per the README flow
# (--save-unknowns without -u builds an unopenable default path);
# fresh db per stage run for idempotency.
# v1.7 -> v1.8: combined_sieve caps threads at 16; -t 32 -> -t 16
# (this cap was also the true cause of the original S7 failures).
# v1.6 -> v1.7: S7 rebuilt -- db bootstrap (schema.sql), known-good
# control run, mstart trisection (1e13/4e9/1e9), full error capture
# (head+tail; the old tail-only filter ate the diagnosis).
# v1.5 -> v1.6: S7 = O3 depth benchmark on combined_sieve at the live
# theater config (p=1439, d=2310, sieve-length 26542, mstart=1e13),
# depths Q=1e8 and 1e9; T1 canary = avg unknowns 1054 / 937 per window.
# v1.4 -> v1.5: S6 builds explicit targets (combined_sieve, gap_stats)
# only -- bare make also builds the optional Google-benchmark harness.
# v1.3 -> v1.4: S6 gains a dependency preflight (gmp/sqlite3/primesieve
# headers) that prints the exact install line instead of failing mid-make.
# v1.2 -> v1.3: S6 combined_sieve toolchain probe (build + selftest +
# help dump) for the O3 depth gate; G-FS closed (docstring stale,
# measured tests/k ~120-143; kit docstring fix queued).
# v1.1 -> v1.2: stages no longer self-mark (runner marks on success);
# S1 superseded by arxiv_sync.sh; S5 ladder/config probe added.
# v1 -> v1.1: brace-closure bug fixed (functions now close on own line);
# syntax-gated with bash -n before shipping.
# Usage:  bash crown_gates.sh          (shredder: runs all pending stages)
#         bash crown_gates.sh s2      (box1: fold-stat stage only)
#         bash crown_gates.sh status
set -uo pipefail
GD=~/lab/beacon/gates; mkdir -p "$GD"
LOG="$GD/gates_log.txt"; ST="$GD/state"; touch "$ST"

done_s(){ grep -qx "$1" "$ST"; }
mark(){ echo "$1" >> "$ST"; }
hdr(){
  echo "" | tee -a "$LOG"
  echo "==== [$1] $(date -u +'%F %TZ') host=$(hostname) ====" | tee -a "$LOG"
}

s0(){
  hdr "S0 freeze-teeth"
  R=$(sqlite3 ~/lab/vault/gaps.db "select gapsize,merit,primedigits,year \
    from gaps where discoverer='Djuk8' and gapsize in \
    (426520,209420,201646,52868,1348726,1263196,1118828);")
  if [ -z "$R" ]; then
    echo "ZERO ROWS -- freeze INTACT" | tee -a "$LOG"
  else
    echo "!! ROWS FOUND -- FREEZE BREACH, ALL GATES HALTED:" | tee -a "$LOG"
    echo "$R" | tee -a "$LOG"
    exit 1
  fi
}

s1(){
  hdr "S1 (superseded)"
  echo "S1 is superseded by arxiv_sync.sh -- run: bash arxiv_sync.sh" | tee -a "$LOG"
}

s3(){
  hdr "S3 O2 recon: kit entrypoints + ladder config"
  {
    ls -la ~/lab/deploy/kit_v1/
    grep -n "argparse\|add_argument\|def cmd_\|RINGS\|ring\|cum_e\|CUM_E\|dE\|DELTA" \
      ~/lab/deploy/kit_v1/*.py 2>/dev/null | grep -v "^Binary" | head -40
  } 2>&1 | tee -a "$LOG"
}

s4(){
  hdr "S4 O3 recon: combined_sieve clone"
  {
    test -d ~/lab/tools/prime-gap || \
      git clone --depth 1 https://github.com/sethtroisi/prime-gap \
        ~/lab/tools/prime-gap 2>&1 | tail -2
    ls ~/lab/tools/prime-gap
    sed -n '1,50p' ~/lab/tools/prime-gap/README.md 2>/dev/null
  } 2>&1 | tee -a "$LOG"
}

s2(){
  hdr "S2 fold-stat (box1, read-only)"
  cd ~/beacon/raid610 || {
    echo "s2 must run on box1 (raid610 not found)" | tee -a "$LOG"
    return 1
  }
  python3 - <<'PYFS' 2>&1 | tee -a "$LOG"
import json, glob, collections
fs = sorted(glob.glob("hunt_s101/sc_r*_*.manifest.json"))
rounds = collections.Counter()
ksr = collections.Counter()
tsr = collections.Counter()
for f in fs:
    m = json.load(open(f))
    r = m.get("round")
    rounds[r] += 1
    ksr[r] += len(m.get("ks", []))
    tsr[r] += sum(m.get("sizes", []))
print("manifests/round:", dict(sorted(rounds.items())))
print("ks/round:       ", dict(sorted(ksr.items())))
print("tests/round:    ", dict(sorted(tsr.items())))
tot = sum(tsr.values())
r1 = min(ksr) if ksr else None
k1 = ksr.get(r1, 0)
print(f"TOTAL tests={tot}  ks entering round {r1}={k1}  "
      f"tests/k={tot/max(k1,1):.1f}   "
      f"bands: closed-form 119-143 | docstring 300-400")
PYFS
}

s5(){
  hdr "S5 ladder + sieve-depth config probe"
  {
    echo "--- ladder610.json ---"
    cat ~/lab/deploy/kit_v1/ladder610.json
    echo ""
    echo "--- scanhunt sieve/ring defaults ---"
    grep -n "deep_q\|deep-from\|deep_from\|DEEP\|--q\|\"q\"\|1e6\|1000000\|1e9\|shallow\|W =\|width" \
      ~/lab/deploy/kit_v1/scanhunt_v0.py 2>/dev/null | head -30
    echo "--- raid_loop invocation flags ---"
    grep -n "scanhunt\|fastmake\|--" ~/lab/deploy/kit_v1/raid_loop.sh | head -20
  } 2>&1 | tee -a "$LOG"
}

s6(){
  hdr "S6 combined_sieve toolchain probe (O3 vehicle)"
  cd ~/lab/tools/prime-gap || {
    echo "clone missing -- rerun s4" | tee -a "$LOG"; return 1; }
  MISS=""
  echo "#include <gmp.h>" | g++ -E -x c++ - >/dev/null 2>&1 \
    || MISS="$MISS libgmp-dev"
  echo "#include <sqlite3.h>" | g++ -E -x c++ - >/dev/null 2>&1 \
    || MISS="$MISS libsqlite3-dev"
  echo "#include <primesieve.hpp>" | g++ -E -x c++ - >/dev/null 2>&1 \
    || MISS="$MISS libprimesieve-dev"
  if [ -n "$MISS" ]; then
    {
      echo "MISSING DEV PACKAGES:$MISS"
      echo "run:  sudo apt-get update && sudo apt-get install -y$MISS"
      echo "then: bash crown_gates.sh s6"
      echo "(if libprimesieve-dev is unavailable on this distro, build"
      echo " github.com/kimwalisch/primesieve: cmake . && make -j && sudo make install)"
    } | tee -a "$LOG"
    return 1
  fi
  {
    echo "--- build (explicit targets) ---"
    make -j"$(nproc)" combined_sieve gap_stats 2>&1 | tail -15
    echo "--- binaries ---"
    ls -la combined_sieve gap_stats 2>/dev/null
    echo "--- combined_sieve --help (head) ---"
    ./combined_sieve --help 2>&1 | head -45
    echo "--- gap_stats --help (head) ---"
    ./gap_stats --help 2>&1 | head -20
  } 2>&1 | tee -a "$LOG"
  test -x ./combined_sieve
}

s7(){
  hdr "S7 O3 depth benchmark v3 (filename-driven, per README flow)"
  cd ~/lab/tools/prime-gap || { echo "rerun s4" | tee -a "$LOG"; return 1; }
  test -x ./combined_sieve || { echo "rerun s6" | tee -a "$LOG"; return 1; }
  rm -f o3.db && sqlite3 o3.db < schema.sql
  mkdir -p unknowns
  echo "db ready: o3.db (fresh); unknowns/ present" | tee -a "$LOG"
  runcs(){
    local TAG="$1" FN="$2"
    local OUT="/tmp/cs_${TAG}.log"
    rm -f "unknowns/$FN"
    echo "--- $TAG  ($FN) ---" | tee -a "$LOG"
    /usr/bin/time -f "wall=%es cpu=%Us rss=%MKB" \
      ./combined_sieve --save-unknowns --search-db o3.db \
        -t 16 -u "$FN" > "$OUT" 2>&1
    local RC=$?
    { echo "[exit=$RC]  first lines:"
      sed -n '1,16p' "$OUT"
      echo "  ... last lines:"
      tail -10 "$OUT"
    } | tee -a "$LOG"
    return $RC
  }
  runcs control "809_1841070_11244000_50_s15000_l100M.txt" \
    || { echo "CONTROL FAILED -- stop" | tee -a "$LOG"; return 1; }
  for MS in 9999999900 1000000000; do
    if runcs "raid_ms${MS}_mp100" \
         "1439_2310_${MS}_100_s26620_l100M.txt"; then
      echo "ACCEPTED mstart=$MS -> depth run" | tee -a "$LOG"
      runcs "raid_ms${MS}_mp1000" \
        "1439_2310_${MS}_100_s26620_l1000M.txt"
      echo "canary: expect avg unknowns ~1057/window @100M, ~940 @1000M" \
        | tee -a "$LOG"
      echo "threshold: <=4.3 core-ms/window @1000M feeds the 4x5090 box" \
        | tee -a "$LOG"
      return 0
    fi
  done
  echo "ALL mstart tiers rejected -- paste log; fork-patch likely" | tee -a "$LOG"
  return 1
}

s8(){
  hdr "S8 O3 marginal cost (minc slope @ 1000M) + window counts"
  cd ~/lab/tools/prime-gap || { echo "rerun s4" | tee -a "$LOG"; return 1; }
  mkdir -p unknowns
  runm(){
    local MINC="$1"
    local FN="1439_2310_9999990000_${MINC}_s26620_l1000M.txt"
    rm -f "unknowns/$FN"
    local OUT="/tmp/cs_minc${MINC}.log"
    /usr/bin/time -f "MINC=${MINC} wall=%es cpu=%Us" \
      ./combined_sieve --save-unknowns --search-db o3.db \
        -t 16 -u "$FN" > "$OUT" 2>&1
    local RC=$?
    { grep -E "MINC=|expect .* left|Saving unknowns|saving " "$OUT" | tail -4
      echo "windows: $(wc -l < "unknowns/$FN" 2>/dev/null) ($FN)"
    } | tee -a "$LOG"
    return $RC
  }
  runm 100  || { echo "minc-100 run failed" | tee -a "$LOG"; return 1; }
  runm 2100 || { echo "minc-2100 run failed" | tee -a "$LOG"; return 1; }
  echo "--- v1.11 file window counts (retro-confirm N) ---" | tee -a "$LOG"
  wc -l unknowns/1439_2310_9999999900_100_s26620_l100M.txt \
        unknowns/1439_2310_9999999900_100_s26620_l1000M.txt \
        2>/dev/null | tee -a "$LOG"
  echo "marginal core-ms/window = (cpu2100-cpu100)/(win2100-win100)*1000" \
    | tee -a "$LOG"
  echo "P-S8a: PASS if <= 2.0 (threshold 4.3)" | tee -a "$LOG"
}

s9(){
  hdr "S9 true unknowns/window from files (settles retracted S7 leg)"
  cd ~/lab/tools/prime-gap/unknowns || { echo "no unknowns dir" | tee -a "$LOG"; return 1; }
  python3 - <<'PYS9' 2>&1 | tee -a "$LOG"
import glob, re, statistics
for fn in sorted(glob.glob("1439_2310_*_s26620_l*.txt")):
    per = []
    for line in open(fn):
        m = re.match(r"\s*\d+\s*:\s*-(\d+)\s*\+(\d+)\s*\|", line)
        if m:
            per.append(int(m.group(1)) + int(m.group(2)))
    if per:
        print(f"{fn}: N={len(per)}  avg={statistics.mean(per):.1f}"
              f"  sd={statistics.pstdev(per):.1f}"
              f"  min={min(per)} max={max(per)}")
    else:
        print(f"{fn}: PARSE MISS -- first line follows")
        print("   ", open(fn).readline().rstrip()[:120])
print("P-S9a: 1000M files avg 940 +/- 3% and mutually consistent;")
print("       100M file avg 1057 +/- 3%")
PYS9
}

case "${1:-auto}" in
  status)
    echo "done stages:"; cat "$ST"
    ;;
  s2)
    s2 && mark s2 || echo "STAGE s2 FAILED" | tee -a "$LOG"
    ;;
  s5)
    s5 && mark s5 || echo "STAGE s5 FAILED" | tee -a "$LOG"
    ;;
  s6)
    s6 && mark s6 || echo "STAGE s6 FAILED" | tee -a "$LOG"
    ;;
  s7)
    s7 && mark s7 || echo "STAGE s7 FAILED" | tee -a "$LOG"
    ;;
  s8)
    s8 && mark s8 || echo "STAGE s8 FAILED" | tee -a "$LOG"
    ;;
  s9)
    s9 && mark s9 || echo "STAGE s9 FAILED" | tee -a "$LOG"
    ;;
  *)
    run(){ done_s "$1" && return 0
           "$1" && mark "$1" || echo "STAGE $1 FAILED (not marked)" | tee -a "$LOG"; }
    run s0
    run s1
    run s3
    run s4
    run s5
    run s6
    run s7
    run s8
    run s9
    echo "" | tee -a "$LOG"
    echo ">> shredder stages complete. Remaining: on box1 run:" | tee -a "$LOG"
    echo ">>   bash crown_gates.sh s2   then send gates_log.txt (both hosts)" | tee -a "$LOG"
    ;;
esac
