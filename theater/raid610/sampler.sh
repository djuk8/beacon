#!/bin/bash
# sampler.sh -- every 15 s: load, GPU util per card, daemons, fallback delta, r1 reqs waiting. Appended to ~/beacon/raid610/sampler.log. Runs beside anything.
set -u; R=$HOME/beacon/raid610; PREV=$(cat $R/fallback_c*.log 2>/dev/null | wc -l)
while :; do
  NOW=$(cat $R/fallback_c*.log 2>/dev/null | wc -l); RQ=$(ls $R/queue/c*/reqs/ 2>/dev/null | grep -c json)
  echo "$(date -u +%T) load $(cut -d' ' -f1 /proc/loadavg) gpu $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | tr '\n' ',') daemons $(pgrep -fc '[b]sd.py --seed') fallback +$((NOW-PREV)) r1reqs $RQ ready $(ls /dev/shm/ready/c*/*.manifest.json 2>/dev/null | wc -l)" >> $R/sampler.log
  PREV=$NOW; sleep 15
done
