#!/bin/bash
# onstart_raid_v2.sh -- watchdog target: feeders first (one per card), then the loops. Pattern-free cron line unchanged.
export PATH=/venv/main/bin:$PATH
exec 9>/tmp/onstart_raid.lock; flock -n 9 || exit 0   # one onstart at a time (cron overlap spawned duplicate feeders)
export Q=${Q:-$(cat /root/beacon/raid610/Q.txt 2>/dev/null || echo 100000)}   # box settings live in raid610/*.txt
KWIN=${KWIN:-$(cat /root/beacon/raid610/KWIN.txt 2>/dev/null || echo 165000)}
EXTRA=${EXTRA:-$(cat /root/beacon/raid610/EXTRA.txt 2>/dev/null || echo 0)}
VENUE=${VENUE:-$(cat /root/beacon/raid610/VENUE.txt 2>/dev/null || echo raid610)}; export VENUE
SEED0=$([ "$VENUE" = crown ] && echo 1101 || echo 101)   # crown 1101-1460; raid610 101-460; 462-701 reserved box4/5; extra band SEED0+601
sleep 20; cd /root/beacon/raid610 || exit 0
for c in 0 1 2 3; do
  EE=""; [ -x /root/beacon/p3/g1_fermat_v3 ] && EE="--driver-ee /root/beacon/p3/g1_fermat_v3"
  EES="/venv/main/bin/python3 /root/beacon/p3/ee_serve.py --queue /root/beacon/raid610/queue/c$c --gpu $c --driver /root/beacon/p3/g1_fermat_v2 $EE"
  n=$(pgrep -fc "ee_serve.py --queue /root/beacon/raid610/queue/c$c .*--lanes r1 ")
  for i in $(seq $((n+1)) 3); do echo "$(date -u) FEEDER c$c r1 #$i"; setsid nohup $EES --lanes r1 --kwin $KWIN --tmax 20 --workers 1 >> feeder_c$c.log 2>&1 </dev/null & done
  pgrep -f "ee_serve.py --queue /root/beacon/raid610/queue/c$c .*--lanes hi " >/dev/null || { echo "$(date -u) FEEDER c$c hi"; setsid nohup $EES --lanes hi --tmax-hi 1.5 --workers 1 >> feeder_c$c.log 2>&1 </dev/null & }
done
pgrep -f raid_loop_v2.sh && exit 0
echo "$(date -u) WATCHDOG RELAUNCH"
LPC=${LPC:-$(cat /root/beacon/raid610/LPC.txt 2>/dev/null || echo 90)}    # loops per card; seeds 101 .. 100+4*LPC (<= 460 keeps box4/box5 blocks free)
for c in 0 1 2 3; do
  for s in $(seq $((SEED0+c*LPC)) $((SEED0-1+(c+1)*LPC))) $(seq $((SEED0+601+c*EXTRA)) $((SEED0+600+(c+1)*EXTRA))); do
    pgrep -f "raid_loop_v2.sh $s " >/dev/null || { setsid nohup ./raid_loop_v2.sh $s $c >> hunt_s$s.log 2>&1 </dev/null & sleep 1; }
  done
done
