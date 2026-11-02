#!/bin/bash
# deploy_856.sh -- v8.56 on a running 8-card crown box (BSD=3, two sieve cards): install the gated files, then switch the SECOND sieve
# daemon (the supply of cards 4-7) to single-class: class 1993 mod 2310 from k = 1e15, fresh seed (default 60000), bids from 2,000,000,001.
# The first daemon keeps hunting mixed classes = the in-box A/B control (ab856.py read).
#   bash deploy_856.sh NEWKIT                 deploy (after: bash NEWKIT/gate_856.sh NEWKIT  -> PASS)
#   bash deploy_856.sh NEWKIT --rollback      second daemon back to its mixed-class seed; v8.55 gbsd/bs_api/gbs/onstart restored
# Order; every check before step 2 stops with production untouched:
#  1 pre-flight: NEWKIT is v8.56; gate receipt PASS for exactly these sources; production files are the v8.55 kit's; BSD=3, DEEPR<=1,
#    second daemon running, no single-class knobs yet, the new seed has no state
#  2 install by atomic rename (running processes keep their old inode; v8.55 copies kept as *.v855; kit backup $P3/o1_kit_v855):
#    the GATED binaries bs_api.so gbs.so + gbsd.py fastmake.py onstart; new gbs_cpu.so ref856.so ab856.py
#  3 knobs SIEVESTEP2/SIEVECLASS2/SIEVEKBASE2/SIEVEBID2 + SIEVESEED2 (old seed kept in SIEVESEED2.v855.txt; its state stays for rollback)
#  4 stop the second daemon and ALL ladders: a ladder must load the v8.56 fastmake before any single-class ring reaches rung 2 (js2 on a
#    single-class carry walks 1,155 rows per window). Rings in flight are dropped once (up to 100 per card = ~1-2 min of box work).
#  5 the first single-class ring: 32 windows vs the referee at production depth (fail -> automatic rollback); A/B mark
set -uo pipefail
R=/root/beacon/raid610; P3=/root/beacon/p3; K=$P3/o1_kit; PY=/venv/main/bin/python3; W=/root/beacon/m357/gate856
NEW=$(cd "${1:?usage: deploy_856.sh NEWKIT [--rollback]}" && pwd); MODE=${2:-}; NS=${NS:-60000}
say(){ echo "$(date -u +%FT%TZ) deploy_856: $*" | tee -a $R/shadow_receipts.txt; }; die(){ say "STOP: $*"; exit 1; }
sha(){ sha256sum "$1" 2>/dev/null | cut -c1-12; }
swap(){ cp -p "$2" "$1.new.$$" && mv -f "$1.new.$$" "$1"; }          # replace $1 by $2 atomically
cd $R || exit 1
rollback() {
  [ -f SIEVESEED2.v855.txt ] || die "no SIEVESEED2.v855.txt - nothing to roll back"
  local cur; cur=$(cat SIEVESEED2.txt); say "ROLLBACK: second daemon $cur -> $(cat SIEVESEED2.v855.txt) (mixed classes)"
  rm -f SIEVESTEP2.txt SIEVECLASS2.txt SIEVEKBASE2.txt SIEVEBID2.txt; cp SIEVESEED2.v855.txt SIEVESEED2.txt
  for f in gbsd.py bs_api.so gbs.so; do [ -f $f.v855 ] && swap $R/$f $R/$f.v855; done
  [ -f /root/onstart_raid_v2.sh.v855 ] && swap /root/onstart_raid_v2.sh /root/onstart_raid_v2.sh.v855
  pkill -f "gbsd.py --seed $cur "; sleep 5; pkill -9 -f "gbsd.py --seed $cur " 2>/dev/null; rm -rf /dev/shm/gbsd_$cur
  bash /root/onstart_raid_v2.sh >> $R/onstart_856.log 2>&1
  say "ROLLBACK done (fastmake.py stays v8.56: identical on mixed rings, and queued single-class rings need it)"; }
[ "$MODE" = --rollback ] && { rollback; exit 0; }

# 1 pre-flight
grep -q -- "--kclass" $NEW/gbsd.py || die "$NEW is not a v8.56 kit"
[ -f $W/gate_856_receipt.json ] || die "no gate receipt: run bash $NEW/gate_856.sh $NEW first"
$PY - "$W/gate_856_receipt.json" "$NEW" <<'PY' || die "gate receipt is not a PASS for these sources (re-run gate_856.sh)"
import json, sys, hashlib; r = json.load(open(sys.argv[1])); new = sys.argv[2]
ok = r["result"] == "PASS" and "GB3" in r["gates"] and all(hashlib.sha256(open(f"{new}/{f}", "rb").read()).hexdigest()[:12] == h for f, h in r["hashes"].items())
sys.exit(0 if ok else 1)
PY
for f in $W/code_new/bs_api.so $W/gpu_new/gbs.so $W/code_new/gbs_cpu.so $W/code_new/ref856.so; do [ -s $f ] || die "gated binary $f missing"; done
grep -q -- "--kclass" $K/gbsd.py && die "$K already holds v8.56"
for f in gbsd.py fastmake.py; do [ "$(sha $R/$f)" = "$(sha $K/$f)" ] || die "$R/$f is not the v8.55 kit's ($(sha $R/$f) vs $(sha $K/$f)) - look first"; done
[ "$(sha /root/onstart_raid_v2.sh)" = "$(sha $K/onstart_raid_v2.sh)" ] || die "/root/onstart_raid_v2.sh is not the v8.55 kit's - look first"
[ "$(cat BSD.txt 2>/dev/null)" = 3 ] || die "BSD is not 3 (this deploy is for sieve-card boxes)"
[ "$(cat DEEPR.txt 2>/dev/null || echo 1)" -le 1 ] || die "DEEPR > 1: deepening single-class carries is not supported (set DEEPR=1 first)"
S1=$(cat SIEVESEED.txt 2>/dev/null); S2=$(cat SIEVESEED2.txt 2>/dev/null); [ -n "$S2" ] || die "no second sieve seed (SIEVESEED2.txt) - 4-card box?"
pgrep -f "gbsd.py --seed $S2 " >/dev/null || die "second sieve daemon (seed $S2) is not running"
ls SIEVESTEP*.txt >/dev/null 2>&1 && die "single-class knobs already present: $(ls SIEVESTEP*.txt | tr '\n' ' ')"
[ -f sieve_state_$NS.json ] && die "seed $NS already has a state file - choose a fresh one: NS=<seed> bash $0 $NEW"
say "pre-flight PASS: kit $NEW, gate receipt PASS, production = v8.55, daemons $S1 (mixed, stays) / $S2 (-> single-class seed $NS)"

# 2 install
for f in gbsd.py fastmake.py bs_api.so gbs.so; do [ -f $f.v855 ] || cp -p $f $f.v855; done; [ -f /root/onstart_raid_v2.sh.v855 ] || cp -p /root/onstart_raid_v2.sh /root/onstart_raid_v2.sh.v855
swap $R/fastmake.py $NEW/fastmake.py && swap $R/gbsd.py $NEW/gbsd.py && swap $R/bs_api.so $W/code_new/bs_api.so && swap $R/gbs.so $W/gpu_new/gbs.so || die "install failed (restore: bash $0 $NEW --rollback)"
cp -p $W/code_new/gbs_cpu.so $W/code_new/ref856.so $R/ && cp -p $NEW/ab856.py $R/ && chmod +x $NEW/onstart_raid_v2.sh && swap /root/onstart_raid_v2.sh $NEW/onstart_raid_v2.sh || die "install failed"
[ -d $P3/o1_kit_v855 ] || cp -a $K $P3/o1_kit_v855
for f in gbsd.py fastmake.py bs_api.c gbs.cu onstart_raid_v2.sh gbs_cpu.c ref856.c gate_856.sh gate_856_cpu.py ab856.py deploy_856.sh; do swap $K/$f $NEW/$f; done
say "installed: gbsd $(sha $R/gbsd.py) fastmake $(sha $R/fastmake.py) bs_api.so $(sha $R/bs_api.so) gbs.so $(sha $R/gbs.so) onstart $(sha /root/onstart_raid_v2.sh) (v8.55: *.v855, kit $P3/o1_kit_v855)"

# 3 knobs
cp SIEVESEED2.txt SIEVESEED2.v855.txt; echo 2310 > SIEVESTEP2.txt; echo 1993 > SIEVECLASS2.txt; echo 1000000000000000 > SIEVEKBASE2.txt; echo 2000000001 > SIEVEBID2.txt; echo $NS > SIEVESEED2.txt
say "knobs: second sieve daemon -> seed $NS, k = k0 + 2310 t, class 1993, k0 >= 1e15, bids from 2000000001 (seed $S2 state kept for rollback)"

# 4 stop + relaunch
pkill -f "gbsd.py --seed $S2 "; pkill -f "ladder.py --card"; sleep 8
pkill -9 -f "gbsd.py --seed $S2 " 2>/dev/null; pkill -9 -f "ladder.py --card" 2>/dev/null; sleep 2; rm -rf /dev/shm/gbsd_$S2
NC=$(nvidia-smi -L | wc -l); ok=0
for i in 1 2 3 4 5 6; do
  bash /root/onstart_raid_v2.sh >> $R/onstart_856.log 2>&1; sleep 10
  NL=$(for c in $(seq 0 $((NC-1))); do pgrep -f "ladder.py --card $c " >/dev/null && echo $c; done | wc -l); ND=$(pgrep -f "gbsd.py --seed $NS " | wc -l)
  [ "$NL" -ge "$NC" ] && [ "$ND" -ge 1 ] && { ok=1; break; }
done
[ $ok = 1 ] || die "relaunch incomplete (ladders $NL/$NC, single-class daemon procs $ND) - see $R/onstart_856.log; rollback: bash $0 $NEW --rollback"
say "relaunched: $NL ladders on v8.56 fastmake, single-class daemon seed $NS up ($(grep -c 'v8.56 single-class' gbsd_sieve2.log) start lines in gbsd_sieve2.log)"

# 5 first ring audit + A/B mark
M=""; for i in $(seq 1 90); do M=$(ls /dev/shm/ready/c*/sc_r01_2?????????.manifest.json /dev/shm/beacon/hunt_s*/sc_r01_2?????????.manifest.json 2>/dev/null | head -1); [ -n "$M" ] && break; sleep 10; done
[ -n "$M" ] || { tail -5 gbsd_sieve2.log; die "no single-class ring after 15 min (production keeps running on daemon 1; rollback: bash $0 $NEW --rollback)"; }
cp "$M" $W/first_single_ring.manifest.json 2>/dev/null || cp "${M%.manifest.json}.manifest.json" $W/first_single_ring.manifest.json
if $PY $R/ab856.py audit --manifest $W/first_single_ring.manifest.json --n 32 --threads 32 | tee -a $R/shadow_receipts.txt | grep -q "^AUDIT PASS"; then
  $PY $R/ab856.py mark | tee -a $R/shadow_receipts.txt
  say "LIVE v8.56: single-class daemon seed $NS (class 1993, k >= 1e15) feeds cards 4-7; mixed daemon seed $S1 = control. Read: $PY $R/ab856.py read"
  say "expect: single-class rings in the feeder ledgers within minutes; rung-6 entries/window x1.077 readable in hours (+-2% after ~6 h), walked merit >= 30 x1.22 in 3-4 days"
else
  say "AUDIT FAILED on the first single-class ring - rolling back"; rollback; exit 1
fi
