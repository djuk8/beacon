#!/bin/bash
# exp.sh -- one unattended experiment: relaunch the crown venue with env overrides, wait for the receipt,
# read the ledger for READ seconds (default 1500), append ONE line to ~/beacon/raid610/experiments.log.
# usage: bash exp.sh NAME [KEY=VAL ...]     e.g.  bash exp.sh kwin300 KWIN=300000     bash exp.sh base
set -uo pipefail
NAME=$1; shift; R=$HOME/beacon/raid610; K=$HOME/beacon/p3/o1_kit; READ=${READ:-1500}; SETTLE=${SETTLE:-300}
for kv in "$@"; do export "$kv"; done
T0=$(date -u +%FT%TZ)
bash $K/go_crown.sh > $R/exp_$NAME.launch.log 2>&1
grep -q "CROWN START" $R/exp_$NAME.launch.log || { echo "$T0 $NAME LAUNCH FAILED (see exp_$NAME.launch.log)" | tee -a $R/experiments.log; exit 1; }
sleep 150                                                       # launch check: the theater must be ALIVE before we spend a read on it
FE=$(pgrep -fc '^/venv/main/bin/python3 /root/beacon/p3/ee_serve.py'); LO=$(pgrep -fc raid_loop_v2.sh); DA=$(pgrep -fc '[b]sd.py --seed'); NEED=$(cat $R/BSDN_EFF.txt 2>/dev/null || echo 0)
NCARDS=$( [ "$(cat $R/BSD.txt 2>/dev/null)" = 3 ] && [ "$(cat $R/SIEVETEST.txt 2>/dev/null)" = 0 ] && echo 3 || echo 4 ); LAD=$(pgrep -fc "ladder.py --card"); if [ "$(cat $R/LADDER.txt 2>/dev/null)" = 1 ]; then LO=$((LAD*175)); fi; if [ "$FE" -lt $((3*NCARDS)) ] || [ "$LO" -lt $((150*NCARDS)) ] || { [ "$NEED" -gt 0 ] && [ "$DA" -lt 1 ]; }; then
  echo "$T0 $NAME LAUNCH UNHEALTHY: feeders $FE loops $LO daemons $DA (need $NEED/card) -- see exp_$NAME.launch.log and feeder/bsd logs" | tee -a $R/experiments.log; exit 1; fi
sleep $((SETTLE > 150 ? SETTLE - 150 : 1))                       # rest of the settle
sleep $READ
EXPNAME=$NAME /venv/main/bin/python3 - "$READ" <<'PY' | tee -a $R/experiments.log
import json, time, sys, os
READ=int(sys.argv[1]); now=time.time(); W=T=0; n=0; SV=0
for c in '0123':
    p=os.path.expanduser(f'~/beacon/raid610/queue/c{c}/ledger.jsonl')
    with open(p,'rb') as f:
        try: f.seek(-40_000_000,2)
        except OSError: f.seek(0)
        f.readline()
        for ln in f:
            try: d=json.loads(ln)
            except Exception: continue
            if d['ts']>now-READ and int(d['round'])==1: W+=d['ks']; T+=d['tested']; n+=1; SV+=int(d.get('survivors',0))
name=os.environ.get('EXPNAME','?'); cfg=' '.join(f'{k}={os.environ[k]}' for k in ('KWIN','CHUNK','GROWTH','MAKESLOTS','EXTRA','DEEPQ','TMAX','R1FEEDERS','SELECT','DEEPR','BSD','BSDQ','BSDT','BSDN','BSDS','BSDNICE','BSDPB','BSDALPHA','TMAXHI','SIEVECARD','SIEVETEST','GPUCORES','HERDCORES','LADDER','LWORKERS','LMAXR1','SETTLE','FM_DENSE_GUARD') if k in os.environ)
import glob, re
mk=[]
for f in glob.glob(os.path.expanduser('~/beacon/raid610/hunt_s11[0-4]?.log')):
    try:
        for ln in open(f, 'rb').read()[-60000:].decode(errors='ignore').splitlines():
            m=re.search(r'make wall ([0-9.]+)s', ln)
            if m: mk.append(float(m.group(1)))
    except Exception: pass
mk=mk[-500:]; mks=(sum(mk)/len(mk)) if mk else float('nan')
samp=[]
try:
    for ln in open(os.path.expanduser('~/beacon/raid610/sampler.log')).read().splitlines()[-int(READ/15):]:
        f=ln.split(); samp.append((float(f[2]), sum(float(x) for x in f[4].strip(',').split(','))/4, int(f[8].lstrip('+'))))
except Exception: pass
sl=(sum(s[0] for s in samp)/len(samp)) if samp else float('nan'); sg=(sum(s[1] for s in samp)/len(samp)) if samp else float('nan'); sf=sum(s[2] for s in samp) if samp else -1
p1=SV/max(W,1); print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())} {name:<12} w/s {W/READ:>7,.0f}  r1 t/s {T/READ:>9,.0f}  t/w(r1) {T/max(W,1):5.1f}  pass1 {p1:.4f}  lam-eff w/s {W/READ*p1/0.1766:>7,.0f}  megas {n:>5}  make_s {mks:4.1f}  load {sl:5.0f}  gpu% {sg:5.1f}  fallback {sf:>5}  [{cfg}]")
PY
