#!/usr/bin/env python3
"""fleet_sync -- git dead-drop transport for the BEACON fleet.

Why: shredder is inbound-blocked (VPN); rented boxes have no stable address
(trycloudflare hostnames rotate on every restart). Git needs only OUTBOUND
HTTPS from both ends, so it works everywhere, forever, with no tunnels.

    box1  --push--> [private repo] <--pull--  shredder
    (logs + heartbeat up)          (code + configs down)

Layout in the repo (one branch, disjoint per-box paths => rebase never
conflicts, concurrent pushes just retry):
    logs/<box>/w*/livefire_log.csv
    logs/<box>/HEARTBEAT.txt      # ts, rows/worker, optional status output
    tools/                        # code flowing DOWN to the boxes

Trust: the notary re-derives every find from (k, zdesign, jleft, jright) on
owned hardware, so a tampered log cannot produce a certificate. The repo is
a transport, never an authority. Keep it PRIVATE anyway -- uncertified finds
are competitive information.

Usage on a hunter box (cron every 15-30 min):
    python3 fleet_sync.py push --repo ~/fleet --box box1 --src ~/beacon/p3 \
        --status "nvidia-smi --query-gpu=index,utilization.gpu,power.draw \
                  --format=csv,noheader"
Usage on shredder:
    python3 fleet_sync.py collect --repo ~/fleet
    # then pipeline.conf:
    #   "remote_pulls": ["python3 fleet_sync.py collect --repo /path/fleet --quiet"]
    #   "log_globs":    ["w*/livefire_log.csv", "/path/fleet/logs/*/w*/livefire_log.csv"]

Token setup (per box, revocable independently):
    GitHub -> Settings -> Developer settings -> Fine-grained tokens
    Repository access: ONLY this repo | Permissions: Contents = Read+Write
    git remote set-url origin https://<TOKEN>@github.com/<user>/<repo>.git
"""
import argparse, glob, os, shutil, subprocess, sys, time


def git(repo, *args, check=True, quiet=False):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True,
                       text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    if not quiet and r.stdout.strip():
        pass
    return r


def datarows(path):
    if not os.path.exists(path): return 0
    with open(path) as f:
        return max(0, sum(1 for l in f if l.strip()) - 1)


def cmd_push(a):
    prefix = a.dest_prefix or os.path.join("logs", a.box)
    dest_root = os.path.join(a.repo, prefix)
    os.makedirs(dest_root, exist_ok=True)
    git(a.repo, "fetch", "-q", "origin", check=False)
    git(a.repo, "pull", "-q", "--rebase", check=False)

    copied, skipped, rowinfo, data_changed = 0, 0, [], False
    srcs = []
    for g in a.glob:
        srcs.extend(glob.glob(os.path.join(a.src, g)))
    for src in sorted(set(srcs)):
        if os.path.isdir(src): continue
        rel = os.path.relpath(src, a.src)
        dst = os.path.join(dest_root, rel)
        new, old = datarows(src), datarows(dst)
        if src.endswith(".csv") and new < old and not a.force:
            print(f"  {rel}: REFUSED -- local {new} rows < repo {old} "
                  f"(--force to override)")
            skipped += 1
            continue
        tailed = (a.tail_bytes and not src.endswith(".csv")
                  and os.path.getsize(src) > a.tail_bytes)
        if tailed:                                  # diagnostics: keep the tail
            with open(src, "rb") as f:
                f.seek(-a.tail_bytes, os.SEEK_END)
                payload = b"...[truncated]...\n" + f.read()
        else:
            payload = open(src, "rb").read()
        same = (os.path.exists(dst) and open(dst, "rb").read() == payload)
        if not same: data_changed = True
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".tmp"
        with open(tmp, "wb") as f: f.write(payload)
        os.replace(tmp, dst)
        copied += 1
        rowinfo.append((rel.split(os.sep)[0], new, new - old))

    hbp = os.path.join(dest_root, "HEARTBEAT.txt")
    hb_age = 1e9
    if os.path.exists(hbp):
        for line in open(hbp):
            if line.startswith("ts="):
                hb_age = time.time() - int(line.split("=")[1])
    if not data_changed and hb_age < a.heartbeat_every:
        print(f"  nothing new (heartbeat {hb_age/60:.0f}m old, refresh at "
              f"{a.heartbeat_every//60}m)")
        return 1 if skipped else 0

    hb = [f"box={a.box}", f"ts={int(time.time())}",
          f"utc={time.strftime('%F %T', time.gmtime())}",
          f"host={os.uname().nodename}", f"uptime={_uptime()}"]
    for w, n, d in rowinfo:
        hb.append(f"worker {w}: {n} rows (+{d})")
    if a.status:
        r = subprocess.run(a.status, shell=True, capture_output=True, text=True)
        hb.append("--- status ---")
        hb.append(r.stdout.strip() or r.stderr.strip())
    open(hbp, "w").write("\n".join(hb) + "\n")

    git(a.repo, "add", "-A", prefix)
    st = git(a.repo, "status", "--porcelain", prefix)
    if not st.stdout.strip():
        print(f"  nothing new ({copied} files checked)"); return 0
    total = sum(n for _, n, _ in rowinfo)
    delta = sum(d for _, _, d in rowinfo)
    msg = (f"{a.box}: {len(rowinfo)} logs, {total} rows (+{delta})"
           if data_changed else f"{a.box}: heartbeat")
    git(a.repo, "commit", "-q", "-m", msg)
    for attempt in range(1, a.retries + 1):
        r = git(a.repo, "push", "-q", "origin", "HEAD", check=False)
        if r.returncode == 0:
            print(f"  pushed: {len(rowinfo)} logs, {total} rows (+{delta})"
                  + (f", {skipped} refused" if skipped else ""))
            return 1 if skipped else 0
        print(f"  push race (attempt {attempt}/{a.retries}), rebasing ...")
        git(a.repo, "pull", "-q", "--rebase", check=False)
        time.sleep(1.5 * attempt)
    print("  PUSH FAILED after retries -- commit is local, will go next run")
    return 1


def _uptime():
    try:
        return f"{float(open('/proc/uptime').read().split()[0])/3600:.1f}h"
    except OSError:
        return "?"


def cmd_collect(a):
    r = git(a.repo, "pull", "-q", "--ff-only", check=False)
    if r.returncode:
        print(f"  WARN: pull failed ({r.stderr.strip()[:80]})")
    boxes = sorted(glob.glob(os.path.join(a.repo, "logs", "*")))
    if not boxes:
        print("  no boxes reporting yet"); return 1
    now, stale = int(time.time()), 0
    for b in boxes:
        name = os.path.basename(b)
        logs = glob.glob(os.path.join(b, "w*", "livefire_log.csv"))
        rows = sum(datarows(p) for p in logs)
        hb = os.path.join(b, "HEARTBEAT.txt")
        age = "-"
        if os.path.exists(hb):
            for line in open(hb):
                if line.startswith("ts="):
                    dt = now - int(line.split("=")[1])
                    age = f"{dt//60}m" if dt < 5400 else f"{dt//3600}h"
                    if dt > a.stale_after: stale += 1
        flag = "  *** STALE ***" if age != "-" and age.endswith("h") and \
               int(age[:-1]) * 3600 > a.stale_after else ""
        if not a.quiet:
            print(f"  {name:<10} {len(logs):>3} logs  {rows:>9,} rows  "
                  f"heartbeat {age:>5} ago{flag}")
    if not a.quiet:
        print(f"  {len(boxes)} boxes" + (f", {stale} STALE" if stale else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("push")
    p.add_argument("--repo", required=True); p.add_argument("--box", required=True)
    p.add_argument("--src", required=True)
    p.add_argument("--glob", nargs="+", default=["w*/livefire_log.csv"])
    p.add_argument("--dest-prefix", default=None,
                   help="repo subdir (default logs/<box>); e.g. certs")
    p.add_argument("--tail-bytes", type=int, default=0,
                   help="for non-csv files bigger than this, push only the tail")
    p.add_argument("--status", default=None)
    p.add_argument("--retries", type=int, default=5)
    p.add_argument("--force", action="store_true")
    p.add_argument("--heartbeat-every", type=int, default=3600,
                   help="seconds; refresh liveness this often even when idle")
    c = sub.add_parser("collect")
    c.add_argument("--repo", required=True)
    c.add_argument("--stale-after", type=int, default=7200)
    c.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    return cmd_push(a) if a.cmd == "push" else cmd_collect(a)


if __name__ == "__main__":
    sys.exit(main())
