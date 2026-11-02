#!/bin/bash
# onstart_raid_v2.sh -- watchdog target: feeders first (one per card), then the loops. Pattern-free cron line unchanged.
export PATH=/venv/main/bin:$PATH
exec 9>/tmp/onstart_raid.lock
if ! flock -n 9; then                                                   # singleton; a holder older than 30 min is a stuck run -> kill it (self-heal), retry next tick
  for p in $(fuser /tmp/onstart_raid.lock 2>/dev/null); do [ "$p" != "$$" ] && [ "$(ps -o etimes= -p $p 2>/dev/null | tr -d ' ')" -gt 1800 ] 2>/dev/null && kill $p; done; exit 0; fi   # one onstart at a time (cron overlap spawned duplicate feeders)
export Q=${Q:-$(cat /root/beacon/raid610/Q.txt 2>/dev/null || echo 100000)}   # box settings live in raid610/*.txt
KWIN=${KWIN:-$(cat /root/beacon/raid610/KWIN.txt 2>/dev/null || echo 165000)}
EXTRA=${EXTRA:-$(cat /root/beacon/raid610/EXTRA.txt 2>/dev/null || echo 0)}
VENUE=${VENUE:-$(cat /root/beacon/raid610/VENUE.txt 2>/dev/null || echo raid610)}; export VENUE
SEED0=$([ "$VENUE" = crown ] && echo 1101 || echo 101)   # crown 1101-1460; raid610 101-460; 462-701 reserved box4/5; extra band SEED0+601
sleep 20; cd /root/beacon/raid610 || exit 0
R610=/root/beacon/raid610
kn() { cat $R610/$1.txt 2>/dev/null | tr -d ' \n' | grep -q . && cat $R610/$1.txt | tr -d ' \n' || echo "$2"; }
BSD=$(kn BSD 0)
BSDQ=$(kn BSDQ 1000000000)
BSDT=$(kn BSDT 4)
BSDN=$(kn BSDN auto)
BSDS=$(kn BSDS 2)
BSDNICE=$(kn BSDNICE 0)   # v8.55: 0 - in rental containers a nice value cannot be lowered again
BSDPB=$(kn BSDPB 100000)
BSDALPHA=$(kn BSDALPHA 0.6)
TMAXHI=$(kn TMAXHI 1.5)
NPT=$(nproc); NGPU=$(nvidia-smi -L 2>/dev/null | wc -l); [ "$NGPU" -ge 1 ] || NGPU=4; GC=$((NGPU*8)); [ $GC -gt $((NPT/2)) ] && GC=$((NPT/2))
GPUCORES=$(kn GPUCORES 0-$((GC-1)))         # feeders: 8 threads per card by default (pin to the GPUs' NUMA node on multi-socket boxes: nvidia-smi topo -m)
HERDCORES=$(kn HERDCORES $GC-$((NPT-1)))    # sieve, ladders, harvest: the rest
NCARDS=$(kn NCARDS $(nvidia-smi -L 2>/dev/null | wc -l)); [ "$NCARDS" -ge 1 ] || NCARDS=4; ALLCARDS=$(seq -s " " 0 $((NCARDS-1)))
SIEVECARD=$(kn SIEVECARD $((NCARDS>4 ? 3 : NCARDS-1)))   # first sieve card; with more than 4 cards a second sieve card serves cards 4..7 (SIEVECARD2, seed SIEVESEED2.txt = SIEVESEED+250 by default)
SIEVECARD2=$(kn SIEVECARD2 $((NCARDS>4 ? 7 : -1)))
SIEVETEST=$(kn SIEVETEST 1)
LADDER=$(kn LADDER 1)
read VZD VBITS VRINGS VLAD <<< "$(cd /root/beacon/raid610 && PYTHONPATH=/root/beacon/raid610:/root/beacon/p3/o1_kit /venv/main/bin/python3 -c "import venue; v=venue.load(); print(v['zd'], v['bits'], v['rings'], v['ladder'])")"
LWORKERS=$(kn LWORKERS 12)
LMAXR1=$(kn LMAXR1 100)
if [ "$BSD" = 3 ] && [ "$SIEVETEST" = 0 ]; then CARDS=$(for c in $ALLCARDS; do [ $c != $SIEVECARD ] && [ $c != $SIEVECARD2 ] && printf "%s " $c; done); else CARDS="$ALLCARDS"; fi   # SIEVETEST=1: the sieve card also tests (the daemon takes ~6% of it)
if [ "$BSDN" = auto ]; then
  NP=$(nproc); NG=$(nvidia-smi -L 2>/dev/null | wc -l); [ "$NG" -gt 0 ] || NG=4; FREEG=$(free -g | awk '/Mem:/{print $7}'); STATEG=$(( BSDQ / 45000000 + 1 ))
  BSDN=$(( (NP - 12*NG - 40) / 10 / NG )); [ $BSDN -gt 4 ] && BSDN=4; MAXMEM=$(( (FREEG - 60) / (STATEG * NG) )); [ $BSDN -gt $MAXMEM ] && BSDN=$MAXMEM; [ $BSDN -lt 0 ] && BSDN=0
  echo "$(date -u) BSD auto-size: nproc $NP gpus $NG free ${FREEG}G state ~${STATEG}G/daemon -> $BSDN daemons/card"
fi
if [ "$BSD" = 0 ]; then echo 0 > $R610/BSDN_EFF.txt; elif [ "$BSD" = 3 ]; then echo 1 > $R610/BSDN_EFF.txt; else echo "$BSDN" > $R610/BSDN_EFF.txt; fi   # BSD=3: the sieve card IS the daemon -> loops wait
echo "$(date -u) knobs: LADDER=$LADDER GPUCORES=$GPUCORES HERDCORES=$HERDCORES BSD=$BSD SIEVECARD=$SIEVECARD CARDS=[$CARDS] BSDQ=$BSDQ BSDN=$BSDN BSDT=$BSDT BSDS=$BSDS BSDNICE=$BSDNICE BSDPB=$BSDPB BSDALPHA=$BSDALPHA TMAXHI=$TMAXHI"
if [ "$BSD" = 1 ] || [ "$BSD" = 2 ] || [ "$BSD" = 3 ]; then mkdir -p /dev/shm/ready; [ -L /root/beacon/raid610/ready ] || { rm -rf /root/beacon/raid610/ready; ln -sfn /dev/shm/ready /root/beacon/raid610/ready; }; pgrep -f "sampler.sh" >/dev/null || ( setsid -f nohup bash /root/beacon/p3/o1_kit/sampler.sh > /dev/null 2>&1 < /dev/null 9>&- & )   # 9>&- : never inherit onstart's singleton lock (the sampler held it and every later onstart exited at once)
for c in $ALLCARDS; do mkdir -p /dev/shm/ready/c$c; done
X1=""; [ "$(kn SIEVESTEP 2)" = 2310 ] && X1="--step 2310 --kclass $(kn SIEVECLASS 317) --kbase $(kn SIEVEKBASE 1000000000000000) --bid-start $(kn SIEVEBID 1000000001)"   # v8.56: one residue class mod 2310 per sieve daemon; bids >= 1e9 mark its rings in the feeder ledgers
X2=""; [ "$(kn SIEVESTEP2 2)" = 2310 ] && X2="--step 2310 --kclass $(kn SIEVECLASS2 1993) --kbase $(kn SIEVEKBASE2 1000000000000000) --bid-start $(kn SIEVEBID2 2000000001)"
if [ "$BSD" = 3 ]; then
  SEED=$(cat /root/beacon/raid610/SIEVESEED.txt 2>/dev/null || echo $((2001+SIEVECARD))); SERVE=$(for c in $CARDS; do [ $c -lt 4 ] && printf "%s," $c; done | sed 's/,$//'); [ "$NCARDS" -le 4 ] && SERVE=$(echo $CARDS | tr ' ' ',')
  pgrep -f "gbsd.py --seed $SEED " >/dev/null || { echo "$(date -u) SIEVE CARD c$SIEVECARD seed $SEED serving $SERVE${X1:+ | $X1}"; ( cd /root/beacon/raid610 && setsid -f nohup nice -n $BSDNICE taskset -c $HERDCORES /venv/main/bin/python3 /root/beacon/raid610/gbsd.py --seed $SEED --card $SIEVECARD --out /dev/shm/ready --serve $SERVE --zd $VZD --bits $VBITS --rings $VRINGS --deepq $BSDQ --select $(cat /root/beacon/raid610/SELECT.txt 2>/dev/null || echo 12) --ahead 48 --pred-pb $BSDPB --alpha $BSDALPHA --api /root/beacon/raid610/bs_api.so --gpu-api /root/beacon/raid610/gbs.so $X1 >> /root/beacon/raid610/gbsd_sieve.log 2>&1 </dev/null 9>&- & ); }
  if [ "$SIEVECARD2" -ge 0 ]; then
    SEED2=$(cat /root/beacon/raid610/SIEVESEED2.txt 2>/dev/null || echo $((SEED+250))); SERVE2=$(for c in $CARDS; do [ $c -ge 4 ] && printf "%s," $c; done | sed 's/,$//')
    [ -n "$SERVE2" ] && { pgrep -f "gbsd.py --seed $SEED2 " >/dev/null || { echo "$(date -u) SIEVE CARD c$SIEVECARD2 seed $SEED2 serving $SERVE2${X2:+ | $X2}"; ( cd /root/beacon/raid610 && setsid -f nohup nice -n $BSDNICE taskset -c $HERDCORES /venv/main/bin/python3 /root/beacon/raid610/gbsd.py --seed $SEED2 --card $SIEVECARD2 --out /dev/shm/ready --serve $SERVE2 --zd $VZD --bits $VBITS --rings $VRINGS --deepq $BSDQ --select $(cat /root/beacon/raid610/SELECT.txt 2>/dev/null || echo 12) --ahead 48 --pred-pb $BSDPB --alpha $BSDALPHA --api /root/beacon/raid610/bs_api.so --gpu-api /root/beacon/raid610/gbs.so $X2 >> /root/beacon/raid610/gbsd_sieve2.log 2>&1 </dev/null 9>&- & ); }; }
  fi
fi
for c in $( [ "$BSD" = 3 ] && echo "" || echo "$ALLCARDS" ); do
  if [ "$BSD" = 2 ]; then SEED=$((2001+c)); pgrep -f "gbsd.py --seed $SEED " >/dev/null || { echo "$(date -u) GBS daemon c$c seed $SEED (GPU-resident sieve)"; ( cd /root/beacon/raid610 && setsid -f nohup nice -n $BSDNICE /venv/main/bin/python3 /root/beacon/raid610/gbsd.py --seed $SEED --card $c --out /root/beacon/raid610/ready/c$c --deepq $BSDQ --select $(cat /root/beacon/raid610/SELECT.txt 2>/dev/null || echo 12) --ahead 64 --api /root/beacon/raid610/bs_api.so --gpu-api /root/beacon/raid610/gbs.so >> /root/beacon/raid610/gbsd_c$c.log 2>&1 </dev/null 9>&- & ); }; continue; fi
  for d in $(seq 0 $((BSDN-1))); do SEED=$((2001+c+10*d))
    pgrep -f "bsd.py --seed $SEED " >/dev/null || { echo "$(date -u) BSD daemon c$c #$d seed $SEED"; ( cd /root/beacon/raid610 && setsid -f nohup nice -n $BSDNICE /venv/main/bin/python3 /root/beacon/raid610/bsd.py --seed $SEED --card $c --out /root/beacon/raid610/ready/c$c --deepq $BSDQ --threads $BSDT --shallow-threads $BSDS --pred-pb $BSDPB --alpha $BSDALPHA --pred-threads 4 --select $(cat /root/beacon/raid610/SELECT.txt 2>/dev/null || echo 12) --ahead 24 --bid-start $((d+1)) --bid-step $BSDN >> /root/beacon/raid610/bsd_c${c}_$d.log 2>&1 </dev/null 9>&- & ); }
  done
done; fi
for c in $CARDS; do
  EE=""; [ -x /root/beacon/p3/g1_fermat_v3 ] && EE="--driver-ee /root/beacon/p3/g1_fermat_v3"
  CHUNK=${CHUNK:-$(cat /root/beacon/raid610/CHUNK.txt 2>/dev/null || echo 6)}; GROWTH=${GROWTH:-$(cat /root/beacon/raid610/GROWTH.txt 2>/dev/null || echo 1.15)}   # O4 wave schedule, venue knobs
GPUBIND=""   # v7.4: GPU path UNBOUND. membind to node 0 measured -6% (driver loads are bandwidth-heavy; one socket halves them). Do not re-pin.
EES="/venv/main/bin/python3 /root/beacon/p3/ee_serve.py --queue /root/beacon/raid610/queue/c$c --gpu $c --driver /root/beacon/p3/g1_fermat_v2 $EE"
  for i in $(seq 1 ${R1FEEDERS:-2}); do flock -n /root/beacon/raid610/.feeder_c${c}_r1_$i.lock true 2>/dev/null || continue; echo "$(date -u) FEEDER c$c r1 #$i"; setsid -f nohup flock -n /root/beacon/raid610/.feeder_c${c}_r1_$i.lock taskset -c $GPUCORES $EES --lanes r1 --kwin $KWIN --tmax ${TMAX:-25} --chunk $CHUNK --growth $GROWTH --workers 1 >> feeder_c$c.log 2>&1 </dev/null 9>&- & done
  flock -n /root/beacon/raid610/.feeder_c${c}_hi.lock true 2>/dev/null && { echo "$(date -u) FEEDER c$c hi"; setsid -f nohup flock -n /root/beacon/raid610/.feeder_c${c}_hi.lock taskset -c $GPUCORES $EES --lanes hi --tmax-hi $TMAXHI --chunk $CHUNK --growth $GROWTH --workers 1 >> feeder_c$c.log 2>&1 </dev/null 9>&- & }
done
pgrep -f raid_loop_v2.sh && exit 0
echo "$(date -u) WATCHDOG RELAUNCH"
LPC=${LPC:-$(cat /root/beacon/raid610/LPC.txt 2>/dev/null || echo 90)}    # loops per card; seeds 101 .. 100+4*LPC (<= 460 keeps box4/box5 blocks free)
if [ "$LADDER" = 1 ]; then
  for c in $CARDS; do SEEDS="$((SEED0+c*LPC))-$((SEED0-1+(c+1)*LPC)),$((SEED0+NCARDS*LPC+1+c*EXTRA))-$((SEED0+NCARDS*LPC+(c+1)*EXTRA))"
    pgrep -f "ladder.py --card $c " >/dev/null || { echo "$(date -u) LADDER c$c seeds $SEEDS workers $LWORKERS"; ( cd /root/beacon/raid610 && setsid -f nohup nice -n 10 taskset -c $HERDCORES /venv/main/bin/python3 /root/beacon/raid610/ladder.py --card $c --seeds $SEEDS --workers $LWORKERS --max-r1 ${LMAXR1:-100} --kitdir /root/beacon/raid610 >> /root/beacon/raid610/ladder_c$c.log 2>&1 </dev/null 9>&- & ); }
  done
else
for c in $CARDS; do
  for s in $(seq $((SEED0+c*LPC)) $((SEED0-1+(c+1)*LPC))) $(seq $((SEED0+601+c*EXTRA)) $((SEED0+600+(c+1)*EXTRA))); do
    pgrep -f "raid_loop_v2.sh $s " >/dev/null || { setsid -f nohup nice -n 10 taskset -c $HERDCORES ./raid_loop_v2.sh $s $c >> hunt_s$s.log 2>&1 </dev/null 9>&- & sleep 0.25; }
  done
done
fi
