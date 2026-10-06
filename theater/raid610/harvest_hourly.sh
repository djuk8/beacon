#!/bin/bash
# harvest_hourly.sh -- walk every unwalked rung-7/8 fossil (and rung-6 when present), append to the campaign ledger, archive walked manifests, re-run the claim check.
# cron: 17 * * * * /root/beacon/p3/o1_kit/harvest_hourly.sh >> /root/beacon/raid610/harvest.log 2>&1
pgrep -f salvage_v1.py >/dev/null && { echo "$(date -u +%FT%TZ) harvest: previous walk still running - skip"; exit 0; }
set -u; R=/root/beacon/raid610; K=/root/beacon/p3/o1_kit; cd $R || exit 1
exec 8>/tmp/harvest.lock; flock -n 8 || exit 0
N=$(find hunt_s* -maxdepth 1 -name 'sc_r0[678]_*.manifest.json' 2>/dev/null | wc -l); [ "$N" -gt 0 ] || { echo "$(date -u +%FT%TZ) harvest: nothing to walk"; exit 0; }
echo "$(date -u +%FT%TZ) harvest: $N fossil manifests"
nice -n 10 taskset -c 32-255 /venv/main/bin/python3 $K/salvage_v1.py --manifests 'hunt_s*/sc_r06_*.manifest.json' --manifests 'hunt_s*/sc_r07_*.manifest.json' --manifests 'hunt_s*/sc_r08_*.manifest.json' --ledger campaign_ledger.log --out campaign_ledger.log --jobs 32 --archive walked/$(date -u +%Y%m)/ 2>&1 | grep -E "accounting|done in|^ +[0-9]+ +[0-9]+\.[0-9]+ k=" | head -12
/venv/main/bin/python3 $K/claimcheck_v1.py campaign_ledger.log $R/arbitrage_map_v0.csv 2>/dev/null | head -3
