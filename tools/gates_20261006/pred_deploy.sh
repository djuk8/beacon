#!/bin/bash
# pred_deploy.sh -- install bs_api_v2.so as the daemons' bs_api.so (old kept as bs_api.so.v1) and restart the two sieve daemons;
# they resume from their state files (sieve_state_<seed>.json). Rollback: cp -p bs_api.so.v1 bs_api.so; pkill -f gbsd.py; bash /root/onstart_raid_v2.sh
set -eu; R=/root/beacon/raid610; cd $R
[ -f bs_api_v2.so ] || { echo "run pred_gate.sh first"; exit 1; }
[ -f bs_api.so.v1 ] || cp -p bs_api.so bs_api.so.v1
cp bs_api_v2.so bs_api.so.new && mv bs_api.so.new bs_api.so && echo "bs_api.so -> v2 ($(sha256sum bs_api.so | cut -c1-12)); v1 kept"
pkill -f gbsd.py || true; sleep 5; bash /root/onstart_raid_v2.sh 2>&1 | grep -i "sieve card"
sleep 240; for f in gbsd_sieve.log gbsd_sieve2.log; do echo "$f: $(tail -n 8 $f | grep -o 'tail [0-9.]*s' | tr '\n' ' ')"; done
tail -n 2 gbsd_sieve.log | cut -c1-150
