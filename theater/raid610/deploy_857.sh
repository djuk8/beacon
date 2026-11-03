#!/bin/bash
# deploy_857.sh -- v8.57 on a running single-class box (v8.56, BSD=3, two sieve cards): install the gated files, restart the ladders once
# (they must load the v8.57 scanhunt_v0.py to use a carried ring 2), then switch the SECOND sieve daemon to --gpu-rings 2: it resumes
# its own seed from the state file, only the sieve width changes. The first daemon stays at --gpu-rings 1 = the A/B control.
#   bash deploy_857.sh NEWKIT                   deploy (after: bash NEWKIT/gate_857.sh NEWKIT -> PASS)
#   bash deploy_857.sh NEWKIT --rollback        second daemon back to --gpu-rings 1 (the v8.57 code then behaves as v8.56)
#   bash deploy_857.sh NEWKIT --rollback-files  the same + the v8.56 gbsd / scanhunt / bs_api / gbs / onstart restored (*.v856)
# Order; every check before step 2 stops with production untouched:
#  1 pre-flight: NEWKIT is v8.57; gate receipt PASS for exactly these sources (incl. GB1); production files are the v8.56 kit's;
#    BSD=3, DEEPR<=1, both daemons single-class and running, no SIEVERINGS knobs yet
#  2 install by atomic rename (running processes keep their old inode; v8.56 copies kept as *.v856; kit backup $P3/o1_kit_v856)
#  3 restart the ladders (in-flight rings dropped once, ~1-2 min of box work); 4 knob SIEVERINGS2=2 + restart of the second daemon
#  5 the first ring with a ring-2 payload: 32 windows, ring 1 AND ring 2, vs the referee at production depth (fail -> rollback); A/B mark
set -uo pipefail
R=/root/beacon/raid610; P3=/root/beacon/p3; K=$P3/o1_kit; PY=/venv/main/bin/python3; W=/root/beacon/m357/gate857
NEW=$(cd "${1:?usage: deploy_857.sh NEWKIT [--rollback|--rollback-files]}" && pwd); MODE=${2:-}
say(){ echo "$(date -u +%FT%TZ) deploy_857: $*" | tee -a $R/shadow_receipts.txt; }; die(){ say "STOP: $*"; exit 1; }
sha(){ sha256sum "$1" 2>/dev/null | cut -c1-12; }
swap(){ cp -p "$2" "$1.new.$$" && mv -f "$1.new.$$" "$1"; }          # replace $1 by $2 atomically
cd $R || exit 1
relaunch() { local i; for i in 1 2 3 4 5 6; do bash /root/onstart_raid_v2.sh >> $R/onstart_857.log 2>&1; sleep 10
  NL=$(for c in $(seq 0 $(($(nvidia-smi -L | wc -l)-1))); do pgrep -f "ladder.py --card $c " >/dev/null && echo $c; done | wc -l)
  [ "$NL" -ge "$(nvidia-smi -L | wc -l)" ] && pgrep -f "gbsd.py --seed $(cat SIEVESEED2.txt) " >/dev/null && pgrep -f "gbsd.py --seed $(cat SIEVESEED.txt) " >/dev/null && return 0; done; return 1; }
rollback() {
  local s2; s2=$(cat SIEVESEED2.txt); say "ROLLBACK: second daemon (seed $s2) back to --gpu-rings 1"
  rm -f SIEVERINGS2.txt
  if [ "$MODE" = --rollback-files ]; then for f in gbsd.py scanhunt_v0.py bs_api.so gbs.so gbs_cpu.so; do [ -f $f.v856 ] && swap $R/$f $R/$f.v856; done
    [ -f /root/onstart_raid_v2.sh.v856 ] && swap /root/onstart_raid_v2.sh /root/onstart_raid_v2.sh.v856; say "v8.56 files restored (*.v856)"; fi
  pkill -f "gbsd.py --seed $s2 "; sleep 5; pkill -9 -f "gbsd.py --seed $s2 " 2>/dev/null; rm -rf /dev/shm/gbsd_$s2
  relaunch || say "relaunch incomplete - check $R/onstart_857.log"
  say "ROLLBACK done (rings already carrying a ring 2 are still read correctly by either scanhunt)"; }
case "$MODE" in --rollback|--rollback-files) rollback; exit 0;; esac

# 1 pre-flight
grep -q -- "--gpu-rings" $NEW/gbsd.py || die "$NEW is not a v8.57 kit"
[ -f $W/gate_857_receipt.json ] || die "no gate receipt: run bash $NEW/gate_857.sh $NEW first"
$PY - "$W/gate_857_receipt.json" "$NEW" <<'PY' || die "gate receipt is not a PASS for these sources (re-run gate_857.sh)"
import json, sys, hashlib; r = json.load(open(sys.argv[1])); new = sys.argv[2]
ok = r["result"] == "PASS" and "GB1" in r["gates"] and all(hashlib.sha256(open(f"{new}/{f}", "rb").read()).hexdigest()[:12] == h for f, h in r["hashes"].items())
sys.exit(0 if ok else 1)
PY
for f in $W/code_new/bs_api.so $W/gpu_new/gbs.so $W/code_new/gbs_cpu.so; do [ -s $f ] || die "gated binary $f missing"; done
grep -q -- "--gpu-rings" $K/gbsd.py && die "$K already holds v8.57"
grep -q -- "--kclass" $K/gbsd.py || die "$K is not v8.56"
for f in gbsd.py fastmake.py scanhunt_v0.py; do [ "$(sha $R/$f)" = "$(sha $K/$f)" ] || die "$R/$f is not the v8.56 kit's ($(sha $R/$f) vs $(sha $K/$f)) - look first"; done
[ "$(sha /root/onstart_raid_v2.sh)" = "$(sha $K/onstart_raid_v2.sh)" ] || die "/root/onstart_raid_v2.sh is not the v8.56 kit's - look first"
[ "$(cat BSD.txt 2>/dev/null)" = 3 ] || die "BSD is not 3"; [ "$(cat DEEPR.txt 2>/dev/null || echo 1)" -le 1 ] || die "DEEPR > 1"
[ "$(cat SIEVESTEP.txt 2>/dev/null)" = 2310 ] && [ "$(cat SIEVESTEP2.txt 2>/dev/null)" = 2310 ] || die "both daemons must be single-class for this A/B (v8.56 deploy + daemon-1 switch first)"
S1=$(cat SIEVESEED.txt); S2=$(cat SIEVESEED2.txt)
pgrep -f "gbsd.py --seed $S1 " >/dev/null && pgrep -f "gbsd.py --seed $S2 " >/dev/null || die "a sieve daemon (seed $S1 / $S2) is not running"
ls SIEVERINGS*.txt >/dev/null 2>&1 && die "SIEVERINGS knobs already present"
say "pre-flight PASS: kit $NEW, gate receipt PASS, production = v8.56, daemons $S1 (control) / $S2 (-> --gpu-rings 2)"

# 2 install
for f in gbsd.py scanhunt_v0.py bs_api.so gbs.so gbs_cpu.so; do [ -f $f.v856 ] || cp -p $f $f.v856; done; [ -f /root/onstart_raid_v2.sh.v856 ] || cp -p /root/onstart_raid_v2.sh /root/onstart_raid_v2.sh.v856
swap $R/gbsd.py $NEW/gbsd.py && swap $R/scanhunt_v0.py $NEW/scanhunt_v0.py && swap $R/bs_api.so $W/code_new/bs_api.so && swap $R/gbs.so $W/gpu_new/gbs.so \
  && swap $R/gbs_cpu.so $W/code_new/gbs_cpu.so && cp -p $NEW/ab857.py $R/ && chmod +x $NEW/onstart_raid_v2.sh && swap /root/onstart_raid_v2.sh $NEW/onstart_raid_v2.sh \
  || die "install failed (restore: bash $0 $NEW --rollback-files)"
[ -d $P3/o1_kit_v856 ] || cp -a $K $P3/o1_kit_v856
for f in gbsd.py bs_api.c gbs.cu gbs_cpu.c scanhunt_v0.py onstart_raid_v2.sh gate_857.sh gate_857_cpu.py deploy_857.sh ab857.py; do swap $K/$f $NEW/$f; done
say "installed: gbsd $(sha $R/gbsd.py) scanhunt $(sha $R/scanhunt_v0.py) bs_api.so $(sha $R/bs_api.so) gbs.so $(sha $R/gbs.so) onstart $(sha /root/onstart_raid_v2.sh) (v8.56: *.v856, kit $P3/o1_kit_v856)"

# 3 ladders onto the v8.57 scanhunt; 4 second daemon onto --gpu-rings 2
pkill -f "ladder.py --card"; sleep 8; pkill -9 -f "ladder.py --card" 2>/dev/null; sleep 2
echo 2 > SIEVERINGS2.txt; pkill -f "gbsd.py --seed $S2 "; sleep 8; pkill -9 -f "gbsd.py --seed $S2 " 2>/dev/null; rm -rf /dev/shm/gbsd_$S2
relaunch || die "relaunch incomplete - see $R/onstart_857.log; rollback: bash $0 $NEW --rollback"
say "relaunched: ladders on the v8.57 scanhunt, daemon $S2 resuming with --gpu-rings 2 (its prime init takes ~4-5 min; cards 4-7 borrow from daemon 1 meanwhile)"

# 5 first ring with a ring-2 payload: audit, then the A/B mark
M=""; for i in $(seq 1 120); do
  M=$(grep -l '"r2": {"lo"' /dev/shm/ready/c*/sc_r01_2?????????.manifest.json /dev/shm/beacon/hunt_s*/sc_r01_2?????????.manifest.json 2>/dev/null | head -1); [ -n "$M" ] && break; sleep 10; done
[ -n "$M" ] || { tail -5 gbsd_sieve2.log; die "no ring with a ring-2 payload after 20 min (daemon 1 keeps the box fed; rollback: bash $0 $NEW --rollback)"; }
cp "$M" $W/first_r2_ring.manifest.json
if $PY $R/ab857.py audit --manifest $W/first_r2_ring.manifest.json --n 32 --threads 32 --need-r2 | tee -a $R/shadow_receipts.txt | grep -q "^AUDIT PASS"; then
  $PY $R/ab857.py mark | tee -a $R/shadow_receipts.txt
  say "LIVE v8.57: daemon $S2 sends ring 2 pre-sieved to $(cat BSDQ.txt) with every ring (cards 4-7); daemon $S1 = control. Read: $PY $R/ab857.py read"
  say "expect: ring-2 pass rate unchanged (the canary), round-2 tests per entering window ~x0.5, tests per window ~x0.86, readable in ~2-3 h"
else
  say "AUDIT FAILED on the first ring-2 payload - rolling back"; MODE=--rollback; rollback; exit 1
fi
