#!/bin/bash
# spin_deploy.sh -- install g1_block as the hunt's driver (atomic; running drivers finish on the old one); the current one is kept as
# g1_fermat_v3.spin. Rollback: cp -p /root/beacon/p3/g1_fermat_v3.spin /root/beacon/p3/g1_fermat_v3
set -eu; P3=/root/beacon/p3; cd $P3; [ -x g1_block ] || { echo "run spin_gate.sh first"; exit 1; }
[ -f g1_fermat_v3.spin ] || cp -p g1_fermat_v3 g1_fermat_v3.spin
cp g1_block g1_fermat_v3.new && mv g1_fermat_v3.new g1_fermat_v3 && echo "driver -> blocking sync ($(sha256sum g1_fermat_v3 | cut -c1-12)); previous kept as g1_fermat_v3.spin"
bash $P3/canary.sh && tail -$(nvidia-smi -L | wc -l) /root/beacon/raid610/canary.log | awk '{print $3,$4}' | tr '\n' ' '; echo
sleep 60; echo "drivers now:"; ps -eo pcpu,args --sort=-pcpu | grep "[g]1_fermat_v3" | head -6 | cut -c1-60
