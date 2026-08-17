#!/usr/bin/env python3
"""BEACON pipeline -- discovery -> notary -> submission, automated.

One cycle (run --once from cron, or --loop):
  1. INGEST   remote log pulls (rsync cmds from conf), tolerate failures
  2. FRESHEN  git pull the prime-gap-list clone (conf.git_pull)
  3. SCAN     all log dirs; record-worthy rows -> DISCOVERED (deduped)
  4. RACE     any tracked find whose slot is now held at <= our digits by
              someone else -> DEAD (loud). Our discoverer appearing -> CONFIRMED.
  5. DISPATCH fill notary slots (largest gap first); window tokens are
              reconstructed via livefire_gw --reconstruct-k; every job runs
              through a limit-raising shim in its own jobs/<id>/ dir
  6. COLLECT  finished certs validated (make_submission core) ->
              CERTIFIED | INVALID
  7. STAGE    certified finds -> waves/wave_<ts>.sql + _portal.txt via the
              submitter (fresh-table race check inside) -> STAGED
  8. SUBMIT   mode=stage (DEFAULT): stop; a human submits the staged wave.
              mode=auto: run ./submit_hook.sh <wave.sql> <portal.txt> --
              only after you have captured the portal recipe there.

State machine per find: DISCOVERED -> CERTIFYING -> CERTIFIED -> STAGED ->
SUBMITTED -> CONFIRMED, with DEAD / INVALID / FAILED exits. State in
pipeline_state.json (atomic), append-only audit in pipeline_audit.jsonl --
the provenance chain, every transition timestamped.

Doctrine preserved: notary runs where this daemon runs (owned hardware);
finds stay private until certified; fresh pull before every scan and every
stage; default mode keeps a human on the publish button.

  python3 pipeline.py --init          # write pipeline.conf template
  python3 pipeline.py --once          # one cycle
  python3 pipeline.py --loop 600      # daemon, 10-min cycles
"""
import argparse, csv, glob, hashlib, json, os, re, runpy, shlex, subprocess
import sys, time

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_submission as msub

STATE, AUDIT, LOCK = "pipeline_state.json", "pipeline_audit.jsonl", ".pipeline.lock"
TOKEN_RE = re.compile(r"s\d+t\d+")

CONF_TEMPLATE = dict(
    log_globs=["w*/livefire_log.csv", "gpu_logs/*/w*/livefire_log.csv"],
    remote_pulls=[],           # e.g. "rsync -a root@box1:~/beacon/p3/w5*/ gpu_logs/box1/"
    repo_dir="prime-gap-list", git_pull=True,
    notary="notary_v1.py", notary_slots=8, z="1e9", mr=50,
    gw="livefire_gw.py",       # for token reconstruction (window arm)
    discoverer="Djuk8", fullname="", year=2026,
    verify_endpoints=1, mode="stage",
    d_min=0, d_max=10 ** 9, skip_gaps=[], cert_dir=None, auto_adopt=True,
    cert_glob=["notary_cert_gap*.json", "certs_in/notary_cert_gap*.json"])


def now(): return int(time.time())


def audit(fid, frm, to, detail=""):
    with open(AUDIT, "a") as f:
        f.write(json.dumps(dict(ts=now(), find=fid, frm=frm, to=to,
                                detail=detail)) + "\n")


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save_state(st):
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w"), indent=1)
    os.replace(tmp, STATE)


def move(st, fid, to, detail=""):
    frm = st[fid]["status"]
    st[fid]["status"] = to
    st[fid]["ts_" + to.lower()] = now()
    if detail: st[fid]["detail"] = detail
    audit(fid, frm, to, detail)
    print(f"  {fid}: {frm} -> {to}" + (f"  ({detail})" if detail else ""))


def find_id(row):
    key = f"{row['D']}:{row['zdesign']}:{row['gap']}:{row['k']}"
    return f"g{row['gap']}_{hashlib.sha256(key.encode()).hexdigest()[:8]}"


def external_notary_gaps():
    """Gaps already being certified by a notary this pipeline did not start
    (e.g. hand-launched runs). Never dispatch these twice."""
    gaps = set()
    try:
        out = subprocess.run(["pgrep", "-af", "notary_v1"],
                             capture_output=True, text=True).stdout
    except Exception:
        return gaps
    for line in out.splitlines():
        m = re.search(r"--gap\s+(\d+)", line)
        if m:
            gaps.add(int(m.group(1)))
        else:                       # --log w30/... form: read the gap from --jr/--jl
            mj = re.search(r"--jl\s+(-?\d+).*--jr\s+(-?\d+)", line)
            if mj:
                gaps.add(int(mj.group(2)) - int(mj.group(1)))
    return gaps


def alive(pid):
    try:
        os.kill(pid, 0); return True
    except (ProcessLookupError, PermissionError):
        return False


def pid_cmdline(pid):
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read().decode(
            errors="replace")
    except OSError:
        return ""


def alive_job(pid, marker):
    """Pid-reuse-proof: alive AND still our notary shim for this find."""
    return alive(pid) and "--exec-notary" in pid_cmdline(pid) \
        and marker in pid_cmdline(pid)


def reconstruct_k(conf, D, zd, token):
    r = subprocess.run([sys.executable, conf["gw"], "--digits", str(D),
                        "--z", "1e9", "--zd-override", str(zd),
                        "--reconstruct-k", token],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip().splitlines()[-1]


def cycle(conf, dry=False):
    st = load_state()
    # 1 ingest
    for cmd in conf["remote_pulls"]:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode:
            err = (r.stderr or r.stdout).strip().splitlines()
            why = err[-1][:150] if err else f"exit {r.returncode}"
            print(f"  WARN ingest failed: {cmd!r}\n         -> {why}")
    # 2 freshen
    if conf["git_pull"]:
        r = subprocess.run(["git", "-C", conf["repo_dir"], "pull", "-q"],
                           capture_output=True, text=True)
        if r.returncode: print("  WARN git pull failed (table may be stale)")
    table = msub.load_table(os.path.join(conf["repo_dir"], "allgaps.sql"))
    # 3 scan
    for g in conf["log_globs"]:
        for path in glob.glob(g):
            for row in csv.DictReader(open(path)):
                try:
                    gap, D = int(row["gap"]), int(row["D"])
                except (KeyError, ValueError):
                    continue
                inc = table.get(gap)
                if inc is not None and inc["digits"] <= D:
                    continue
                fid = find_id(row)
                if fid in st: continue
                st[fid] = dict(status="DISCOVERED", gap=gap, D=D,
                               zd=int(row["zdesign"]), k=row["k"],
                               jl=int(row["jleft"]), jr=int(row["jright"]),
                               src=path, ts_discovered=now())
                audit(fid, "-", "DISCOVERED", path)
                print(f"  {fid}: DISCOVERED  merit~{gap/(D*2.302585):.2f} ({path})")
    # 4 race / confirm
    for fid, f in st.items():
        inc = table.get(f["gap"])
        if inc is None: continue
        if inc["disc"] == conf["discoverer"] and f["status"] == "SUBMITTED":
            move(st, fid, "CONFIRMED", "upstream row present")
        elif (inc["digits"] <= f["D"] and inc["disc"] != conf["discoverer"]
              and f["status"] in ("DISCOVERED", "CERTIFYING", "CERTIFIED",
                                  "STAGED")):
            move(st, fid, "DEAD", f"slot taken at {inc['digits']}d by "
                                  f"{inc['disc']} {inc['year']}")
    # 5 dispatch
    running = [f for f in st.values() if f["status"] == "CERTIFYING"]
    free = conf["notary_slots"] - len(running)
    ext = external_notary_gaps()
    if ext:
        print(f"  external notaries running on gaps: "
              f"{', '.join(f'{g:,}' for g in sorted(ext))} (not dispatched)")
    dmin, dmax = conf.get("d_min", 0), conf.get("d_max", 10 ** 9)
    queue = sorted((f for f in st.values()
                    if f["status"] == "DISCOVERED"
                    and dmin <= f["D"] <= dmax
                    and f["gap"] not in ext
                    and f["gap"] not in set(conf.get("skip_gaps", []))),
                   key=lambda f: -f["gap"])
    for f in queue[:max(free, 0)]:
        fid = [k for k, v in st.items() if v is f][0]
        jd = os.path.join("jobs", fid)
        if dry:
            print(f"  DRY: would dispatch {fid} -> {jd}"); continue
        os.makedirs(jd, exist_ok=True)
        kval = f["k"]
        if TOKEN_RE.fullmatch(kval):
            kval = reconstruct_k(conf, f["D"], f["zd"], kval)
        cmd = [sys.executable, os.path.abspath(__file__), "--exec-notary",
               os.path.abspath(conf["notary"]), "--",
               "--k", kval, "--zd", str(f["zd"]), "--jl", str(f["jl"]),
               "--jr", str(f["jr"]), "--z", conf["z"], "--mr",
               str(conf["mr"])]
        p = subprocess.Popen(cmd, cwd=jd,
                             stdout=open(os.path.join(jd, "notary.log"), "w"),
                             stderr=subprocess.STDOUT,
                             start_new_session=True)   # survive Ctrl-C on the
                                                       # pipeline: a 3-core-hour
                                                       # verification is not
                                                       # collateral damage
        f["pid"], f["jobdir"] = p.pid, jd
        move(st, fid, "CERTIFYING", f"pid {p.pid}")
        save_state(st)
    # 6 collect
    for fid, f in st.items():
        if f["status"] != "CERTIFYING": continue
        cert = os.path.join(f["jobdir"], f"notary_cert_gap{f['gap']}.json")
        if os.path.exists(cert):
            c = json.load(open(cert))
            r = msub.process_cert(c, {}, conf["discoverer"], conf["year"],
                                  "D", 0)
            if r["status"].startswith("REJECT") or c["verdict"] != "VALID":
                move(st, fid, "INVALID", r.get("why", c["verdict"]))
            else:
                f["cert"] = cert
                cd = conf.get("cert_dir")
                if cd:
                    os.makedirs(cd, exist_ok=True)
                    try:
                        import shutil as _sh
                        _sh.copy2(cert, cd)
                    except Exception as e:
                        print(f"  WARN cert_dir copy failed: {e}")
                move(st, fid, "CERTIFIED",
                     f"merit {r['merit']:.4f}, {r['digits']}d")
        elif not alive_job(f.get("pid", -1), str(f["jl"])):
            move(st, fid, "FAILED", "notary exited without certificate")
    # 6b auto-adopt: certificates produced elsewhere (the second courthouse
    #    rsyncs them in) become CERTIFIED here without manual gluing.
    if conf.get("auto_adopt", True):
        globs = conf.get("cert_glob", "notary_cert_gap*.json")
        if isinstance(globs, str): globs = [globs]
        for g in globs:
            for cert in glob.glob(g):
                try:
                    c = json.load(open(cert))
                except Exception:
                    continue            # mid-write; next cycle picks it up
                for fid, f in st.items():
                    if (f["gap"] == c.get("gap") and f["zd"] == c.get("zdesign")
                            and f["status"] in ("DISCOVERED", "FAILED")):
                        f["cert"] = os.path.abspath(cert)
                        move(st, fid,
                             "CERTIFIED" if c.get("verdict") == "VALID"
                             else "INVALID",
                             f"adopted {os.path.basename(cert)}")
                        break

    # 7 stage
    ready = {k: v for k, v in st.items() if v["status"] == "CERTIFIED"}
    wave = None
    if conf.get("mode") == "certify":
        if ready:
            print(f"  mode=certify: {len(ready)} certified, staging is another "
                  f"machine's job (cert_dir={conf.get('cert_dir')})")
        ready = {}
    if ready and not dry:
        os.makedirs("waves", exist_ok=True)
        gc, tally = msub.gapcert_auto(table,
                                      next(iter(ready.values()))["D"])
        wave = os.path.join("waves", f"wave_{now()}")
        good = []
        for fid, f in ready.items():
            c = json.load(open(f["cert"]))
            r = msub.process_cert(c, table, conf["discoverer"], conf["year"],
                                  gc, conf["verify_endpoints"])
            if r["status"] == "DEAD":
                move(st, fid, "DEAD", r["why"]); continue
            if r["status"].startswith("REJECT"):
                move(st, fid, "INVALID", r["why"]); continue
            good.append((fid, r))
        if good:
            with open(wave + ".sql", "w") as fs, \
                 open(wave + "_portal.txt", "w") as fp:
                if conf["fullname"]:
                    fs.write(f"INSERT INTO credits VALUES("
                             f"'{conf['discoverer']}','{conf['fullname']}',"
                             f"'','{conf['fullname']}');\n")
                for fid, r in good:
                    fs.write(r["sql"] + "\n"); fp.write(r["portal"] + "\n")
                    st[fid]["wave"] = wave
                    move(st, fid, "STAGED", f"gapcert '{gc}'")
            print(f"  wave staged: {wave}.sql ({len(good)} finds)")
    # 8 submit
    staged = [k for k, v in st.items() if v["status"] == "STAGED"]
    if staged and conf["mode"] == "auto" and not dry:
        w = st[staged[0]]["wave"]
        if os.path.exists("submit_hook.sh"):
            r = subprocess.run(["bash", "submit_hook.sh", w + ".sql",
                                w + "_portal.txt"], capture_output=True,
                               text=True)
            for fid in staged:
                move(st, fid, "SUBMITTED" if r.returncode == 0 else "STAGED",
                     "hook rc=%d" % r.returncode)
        else:
            print("  mode=auto but no submit_hook.sh -- staying STAGED")
    save_state(st)
    tally = {}
    for f in st.values():
        tally[f["status"]] = tally.get(f["status"], 0) + 1
    print("  status: " + "  ".join(f"{k}:{v}" for k, v in sorted(tally.items())))
    return st


def main():
    if "--exec-notary" in sys.argv:      # limit-raising shim, own jobdir cwd
        i = sys.argv.index("--exec-notary")
        target = sys.argv[i + 1]
        sys.argv = [target] + sys.argv[i + 3:]
        runpy.run_path(target, run_name="__main__")
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--conf", default="pipeline.conf")
    ap.add_argument("--adopt", action="store_true",
                    help="mark finds CERTIFIED from certificates already on "
                         "disk (run once at cutover; prevents re-verifying)")
    ap.add_argument("--retry-failed", action="store_true",
                    help="return FAILED finds to the dispatch queue "
                         "(e.g. after notaries died with a killed pipeline)")
    ap.add_argument("--mark-submitted", default=None, metavar="WAVE",
                    help="record that WAVE (waves/wave_<ts>) was submitted")
    a = ap.parse_args()
    if a.adopt:
        # one DRY cycle: discovers finds and auto-adopts every certificate
        # already on disk (local or rsynced in), dispatching nothing.
        conf = dict(CONF_TEMPLATE, **json.load(open(a.conf)))
        st = cycle(conf, dry=True)
        n = sum(1 for f in st.values()
                if "adopted" in str(f.get("detail", "")))
        cert = sum(1 for f in st.values() if f["status"] == "CERTIFIED")
        print(f"adopted {n} existing certificates "
              f"({cert} finds now CERTIFIED, nothing dispatched)")
        return

    if a.retry_failed:
        st = load_state()
        n = 0
        for fid, f in st.items():
            if f["status"] == "FAILED":
                f.pop("pid", None)
                move(st, fid, "DISCOVERED", "retry after failure")
                n += 1
        save_state(st)
        print(f"{n} FAILED finds returned to the queue")
        return

    if a.mark_submitted:
        st = load_state()
        n = 0
        for fid, f in st.items():
            if f.get("wave") == a.mark_submitted and f["status"] == "STAGED":
                move(st, fid, "SUBMITTED", "human submit recorded"); n += 1
        save_state(st)
        print(f"{n} finds marked SUBMITTED for {a.mark_submitted}")
        return
    if a.init:
        json.dump(CONF_TEMPLATE, open(a.conf, "w"), indent=1)
        print(f"wrote {a.conf} -- edit it, then run --once"); return
    conf = dict(CONF_TEMPLATE, **json.load(open(a.conf)))
    if os.path.exists(LOCK):
        pid = int(open(LOCK).read() or 0)
        if pid and alive(pid) and "pipeline.py" in pid_cmdline(pid):
            raise SystemExit(f"pipeline already running (pid {pid})")
    open(LOCK, "w").write(str(os.getpid()))
    try:
        while True:
            print(f"== cycle @ {time.strftime('%F %T')} ==")
            cycle(conf, dry=a.dry_run)
            if not a.loop: break
            time.sleep(a.loop)
    finally:
        os.remove(LOCK)


if __name__ == "__main__":
    main()
