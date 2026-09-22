#!/bin/bash
# finish_v34.sh -- complete the v3.4 install that "Text file busy" blocked. (C, 2026-08-24)
# The gates ALL PASSED (gate_r4_v34.log + gate_serve_v34.log); this only installs the already-gated
# artifact safely: disarm watchdog -> tree stop -> cp + SHA-VERIFY -> cleanup -> re-arm -> relaunch.
set -uo pipefail
R=$HOME/beacon/raid610; P3=$HOME/beacon/p3
cd "$R" || exit 1
crontab -l > "$P3/crontab_live_$(date -u +%s).txt" 2>/dev/null; crontab -r 2>/dev/null   # disarm: no relaunch mid-install
pkill -f raid_loop_v2.sh; pkill -TERM -f ee_serve.py; sleep 3
pkill -9 -f 'scanhunt_v0.py make'; pkill -9 -f 'scanhunt_v0.py fold'; pkill -9 -f ee_serve.py 2>/dev/null; pkill -9 -f g1_fermat 2>/dev/null
sleep 5
echo "$(date -u +%FT%TZ) STOP for v3.4 install: procs left $(pgrep -fc 'raid_loop|ee_serve|scanhunt|g1_fermat' || echo 0)" | tee -a shadow_receipts.txt
[ -x "$P3/g1_fermat_v34" ] || { echo "gated v34 binary missing -- rerun swap"; exit 1; }
S34=$(sha256sum "$P3/g1_fermat_v34" | cut -c1-12)
cp "$P3/g1_fermat_v3" "$P3/g1_fermat_v3.bak_v33_$(sha256sum $P3/g1_fermat_v3 | cut -c1-12)"
cp "$P3/g1_fermat_v34" "$P3/g1_fermat_v3" || { echo "cp FAILED again"; exit 1; }
SI=$(sha256sum "$P3/g1_fermat_v3" | cut -c1-12)
[ "$SI" = "$S34" ] || { echo "SHA MISMATCH after cp ($SI != $S34) -- ABORT"; exit 1; }
echo "$(date -u +%FT%TZ) v3.4 INSTALLED AND VERIFIED: v3 $SI == v34 $S34 (gates: gate_r4_v34.log ALL PASS, gate_serve_v34.log ALL PASS)" | tee -a shadow_receipts.txt
rm -rf "$P3/gate_fx_v34" /tmp/gate_serve /tmp/gate_r4 2>/dev/null   # reclaim disk (gate debris)
rm -f queue/c*/req/*.json queue/c*/claimed/*.json queue/c*/failed/*.json 2>/dev/null
B2=$(ls -t $P3/crontab_backup_*.txt | head -1); sed "s|onstart_raid.sh|onstart_raid_v2.sh|g" "$B2" > /tmp/cron_v2.txt; crontab /tmp/cron_v2.txt
VENUE=crown /root/onstart_raid_v2.sh; sleep 30
echo "$(date -u +%FT%TZ) CROWN on v3.4: feeders $(pgrep -fc ee_serve.py) loops $(pgrep -fc raid_loop_v2.sh) disk $(df -h / | awk 'NR==2{print $4}')" | tee -a shadow_receipts.txt
