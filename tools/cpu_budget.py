#!/usr/bin/env python3
"""cpu_budget.py -- where the box's CPU goes, by component, without a profiler (reads /proc; works in containers without ptrace).
For every process: (utime + stime + reaped children's time) / lifetime = average cores used. Drivers spawned and reaped by a feeder
are counted inside that feeder's line (cutime), live ones on their own line. Run twice a few minutes apart if processes just restarted."""
import os, collections
HZ = os.sysconf(os.sysconf_names["SC_CLK_TCK"]); up = float(open("/proc/uptime").read().split()[0])
def kind(a):
    for key, name in (("gbsd.py", "sieve daemons (gbsd)"), ("ladder.py", "ladder managers + workers"), ("ee_serve", "feeders (+ reaped drivers)"),
                      ("g1_fermat", "drivers (live)"), ("salvage", "harvest/walk"), ("shard_walk", "harvest/walk"), ("harvest", "harvest/walk"),
                      ("canary", "canary"), ("sampler", "sampler")):
        if key in a: return name
    return "other"
cores = collections.Counter(); n = collections.Counter(); thr = collections.Counter()
for pid in filter(str.isdigit, os.listdir("/proc")):
    try:
        a = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="ignore").strip()
        st = open(f"/proc/{pid}/stat").read()
    except Exception: continue
    if not a: continue
    f = st[st.rindex(")") + 2:].split()                     # f[0] = field 3 (state); field N -> f[N-3]
    t = (int(f[11]) + int(f[12]) + int(f[13]) + int(f[14])) / HZ; life = up - int(f[19]) / HZ
    if life < 30: continue
    k = kind(a); cores[k] += t / life; n[k] += 1; thr[k] += int(f[17])   # field 20 = num_threads
tot = sum(cores.values())
print(f"{'component':28} {'procs':>5} {'threads':>7} {'avg cores':>9} {'share':>6}")
for k, c in cores.most_common(): print(f"{k:28} {n[k]:5} {thr[k]:7} {c:9.1f} {100*c/tot:5.1f}%")
print(f"{'total':28} {sum(n.values()):5} {sum(thr.values()):7} {tot:9.1f}   (machine: {os.cpu_count()} threads)")
