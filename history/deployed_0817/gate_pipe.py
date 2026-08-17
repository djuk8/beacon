#!/usr/bin/env python3
"""gate_pipe -- G-PIPE for the automation daemon. Simulated world, real code.

Legs: A discovery+dedupe (incl. non-record skip)  B dispatch via shim
(incl. window-token reconstruction)  C certify+stage (wave files exact)
D idempotence  E race death  F human-submit -> CONFIRMED  G notary
failure -> FAILED  H singleton lock  I audit chain integrity.
"""
import glob, json, os, shutil, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
GT = os.path.join(HERE, "gt")
PY = sys.executable
N = [0]


def ok(cond, msg):
    print(("  pass: " if cond else "  FAIL: ") + msg)
    if not cond: sys.exit(1)
    N[0] += 1


STUB = r'''import argparse, json, time
import gmpy2
ap = argparse.ArgumentParser()
for f in ("--k", "--zd", "--jl", "--jr"): ap.add_argument(f, type=int)
ap.add_argument("--z"); ap.add_argument("--mr", type=int, default=50)
a = ap.parse_args()
def primorial(zd):
    P = gmpy2.mpz(1); s = bytearray([1])*(zd+1); s[0:2] = b"\x00\x00"
    for i in range(2, int(zd**0.5)+1):
        if s[i]: s[i*i::i] = bytearray(len(range(i*i, zd+1, i)))
    for p in range(2, zd+1):
        if s[p]: P *= p
    return P
time.sleep(0.6)
gap = a.jr - a.jl
p1 = a.k * primorial(a.zd) + a.jl
merit = gap / float(gmpy2.log(p1))
cert = dict(handle="djuk8", verdict="VALID", k=a.k, zdesign=a.zd,
            jleft=a.jl, jright=a.jr, gap=gap, merit=round(merit, 6),
            n0_digits=len(gmpy2.digits(p1, 10)),
            endpoints=dict(p1=dict(fermat_bases_pass=True, is_prime_mr=True),
                           p2=dict(fermat_bases_pass=True, is_prime_mr=True)),
            interior=dict(count=gap-1, sieve_factored=gap-4,
                          fermat_composite=3, pseudoprimes=0, prp_alarms=[]),
            z_verify=int(float(a.z)), mr_rounds=a.mr, runtime_s=0.6,
            ts=int(time.time()), notary="stub")
json.dump(cert, open(f"notary_cert_gap{gap}.json", "w"), indent=1)
'''

SQL_HEAD = ("PRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\n"
            "CREATE TABLE gaps (gapsize INTEGER,ismax BOOLEAN,primecat TEXT,"
            "isfirst TEXT,gapcert TEXT,discoverer TEXT,year INTEGER,"
            "merit REAL,primedigits INTEGER,startprime BLOB);\n")


def sqlrow(g, d, disc, gc="D"):
    return (f"INSERT INTO gaps VALUES({g},0,'C','?','{gc}','{disc}',2026,"
            f"5.0,{d},'x');\n")


def log_row(D, zd, k, gap, jl, jr):
    return f"{int(time.time())},{D},{zd},200000,{k},{gap},1.0,{jl},{jr},9,9,1.0\n"


def run_once(extra=()):
    return subprocess.run([PY, os.path.join(HERE, "pipeline.py"), "--once",
                           *extra], cwd=GT, capture_output=True, text=True)


def state():
    return json.load(open(os.path.join(GT, "pipeline_state.json")))


def by_gap(st, g):
    return next(v for v in st.values() if v["gap"] == g)


def main():
    t0 = time.time()
    shutil.rmtree(GT, ignore_errors=True)
    os.makedirs(os.path.join(GT, "repo"))
    os.makedirs(os.path.join(GT, "wlog"))
    open(os.path.join(GT, "stub_notary.py"), "w").write(STUB)
    open(os.path.join(GT, "stub_fail.py"), "w").write("import sys; sys.exit(1)\n")
    shutil.copy(os.path.join(HERE, "livefire_gw.py"), GT)
    with open(os.path.join(GT, "repo", "allgaps.sql"), "w") as f:
        f.write(SQL_HEAD)
        f.write(sqlrow(1000, 100, "Old"))       # claimed small -> not a record
        for g in range(50, 60): f.write(sqlrow(g, 10, "Hist"))
    hdr = "ts,D,zdesign,z,k,gap,merit,jleft,jright,tests,survivors,t_trial_s\n"
    with open(os.path.join(GT, "wlog", "livefire_log.csv"), "w") as f:
        f.write(hdr)
        f.write(log_row(600, 97, 123456, 5000, -3000, 2000))     # desert find
        f.write(log_row(600, 97, "s99t0", 6200, -4100, 2100))    # window token
        f.write(log_row(600, 97, 777, 1000, -600, 400))          # NOT a record
    conf = dict(log_globs=["wlog/*.csv"], remote_pulls=[], repo_dir="repo",
                git_pull=False, notary="stub_notary.py", notary_slots=2,
                z="200000", mr=50, gw="livefire_gw.py", discoverer="Djuk8",
                fullname="Test Name", year=2026, verify_endpoints=0,
                mode="stage")
    json.dump(conf, open(os.path.join(GT, "pipeline.conf"), "w"))

    print("[A/B] discovery, dedupe, dispatch (token reconstruction)")
    r = run_once()
    ok(r.returncode == 0, "A1 cycle 1 exits 0")
    st = state()
    ok(len(st) == 2, f"A2 two record-worthy finds tracked, non-record "
                     f"skipped ({len(st)})")
    ok(all(v["status"] == "CERTIFYING" for v in st.values()),
       "B1 both dispatched to notary slots")
    ok(by_gap(st, 6200)["k"] == "s99t0", "B2 window token tracked as token")

    print("[C] certify + stage")
    time.sleep(1.5)
    r = run_once()
    st = state()
    ok(all(v["status"] == "STAGED" for v in st.values()),
       "C1 both CERTIFIED then STAGED in one cycle")
    waves = [f for f in os.listdir(os.path.join(GT, "waves"))
             if f.endswith(".sql")]
    ok(len(waves) == 1, "C2 one wave file staged")
    lines = open(os.path.join(GT, "waves", waves[0])).read().splitlines()
    ok(len(lines) == 3 and lines[0].startswith("INSERT INTO credits") and
       all(l.startswith("INSERT INTO gaps VALUES(") for l in lines[1:]),
       f"C3 wave format: credits + 2 exact rows")
    ok("*97#" in lines[1] + lines[2], "C4 startprime expressions present")

    print("[D] idempotence")
    r = run_once()
    st2 = state()
    ok(len(st2) == 2 and all(v["status"] == "STAGED" for v in st2.values())
       and len([f for f in os.listdir(os.path.join(GT, "waves"))
                if f.endswith(".sql")]) == 1,
       "D1 third cycle: no dupes, no re-dispatch, no second wave")

    print("[E] race death")
    with open(os.path.join(GT, "repo", "allgaps.sql"), "a") as f:
        f.write(sqlrow(5000, 400, "R.X"))
    run_once()
    st = state()
    ok(st and by_gap(st, 5000)["status"] == "DEAD" and
       "R.X" in by_gap(st, 5000)["detail"],
       f"E1 staged find killed by upstream claim: "
       f"{by_gap(st, 5000)['detail']}")

    print("[F] human submit -> CONFIRMED")
    stf = state()
    wave = by_gap(stf, 6200)["wave"]
    r = subprocess.run([PY, os.path.join(HERE, "pipeline.py"),
                        "--mark-submitted", wave], cwd=GT,
                       capture_output=True, text=True)
    ok(r.returncode == 0 and "marked SUBMITTED" in r.stdout,
       "F0 --mark-submitted CLI records the human action")
    dg = by_gap(state(), 6200)["D"]
    with open(os.path.join(GT, "repo", "allgaps.sql"), "a") as f:
        f.write(sqlrow(6200, dg, "Djuk8"))
    run_once()
    ok(by_gap(state(), 6200)["status"] == "CONFIRMED",
       "F1 upstream row with our discoverer -> CONFIRMED")

    print("[G] notary failure path")
    with open(os.path.join(GT, "wlog", "livefire_log.csv"), "a") as f:
        f.write(log_row(600, 97, 424242, 4200, -2200, 2000))
    conf2 = dict(conf, notary="stub_fail.py")
    json.dump(conf2, open(os.path.join(GT, "pipeline.conf"), "w"))
    run_once(); time.sleep(0.5); run_once()
    ok(by_gap(state(), 4200)["status"] == "FAILED",
       "G1 notary exit-without-cert -> FAILED (evidence kept)")

    print("[H] singleton lock")
    p = subprocess.Popen([PY, os.path.join(HERE, "pipeline.py"), "--loop",
                          "30"], cwd=GT, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    r = run_once()
    ok(r.returncode != 0 and "already running" in (r.stdout + r.stderr),
       "H1 second instance refused")
    p.send_signal(signal.SIGTERM); p.wait()

    print("[I] audit chain")
    lines = [json.loads(l) for l in
             open(os.path.join(GT, "pipeline_audit.jsonl"))]
    seq = [l["to"] for l in lines if l["find"].startswith("g5000")]
    ok(seq == ["DISCOVERED", "CERTIFYING", "CERTIFIED", "STAGED", "DEAD"],
       f"I1 full lifecycle audited in order: {' -> '.join(seq)}")
    ok(all(set(l) >= {"ts", "find", "frm", "to"} for l in lines),
       f"I2 {len(lines)} audit records well-formed")

    print("[J] cutover safety: adopt + external notary + band filter")
    # fresh world: two finds, one of which already has a certificate on disk,
    # and one being certified by a hand-launched notary we must not duplicate.
    J = os.path.join(HERE, "gtj")
    shutil.rmtree(J, ignore_errors=True)
    os.makedirs(os.path.join(J, "repo")); os.makedirs(os.path.join(J, "wlog"))
    shutil.copy(os.path.join(HERE, "livefire_gw.py"), J)
    open(os.path.join(J, "stub_notary.py"), "w").write(STUB)
    with open(os.path.join(J, "repo", "allgaps.sql"), "w") as f:
        f.write(SQL_HEAD)
    hdr = "ts,D,zdesign,z,k,gap,merit,jleft,jright,tests,survivors,t_trial_s\n"
    with open(os.path.join(J, "wlog", "livefire_log.csv"), "w") as f:
        f.write(hdr)
        f.write(log_row(600, 97, 111, 7000, -3000, 4000))   # has a cert already
        f.write(log_row(600, 97, 222, 8000, -3500, 4500))   # external notary
        f.write(log_row(900, 97, 333, 9000, -4000, 5000))   # out of band
    json.dump(dict(gap=7000, zdesign=97, verdict="VALID", k=111, jleft=-3000,
                   jright=4000, merit=1.0, n0_digits=600,
                   endpoints=dict(p1=dict(fermat_bases_pass=True, is_prime_mr=True),
                                  p2=dict(fermat_bases_pass=True, is_prime_mr=True)),
                   interior=dict(count=6999, sieve_factored=6996,
                                 fermat_composite=3, pseudoprimes=0, prp_alarms=[]),
                   mr_rounds=50),
              open(os.path.join(J, "notary_cert_gap7000.json"), "w"))
    confJ = dict(log_globs=["wlog/*.csv"], remote_pulls=[], repo_dir="repo",
                 git_pull=False, notary="stub_notary.py", notary_slots=4,
                 z="200000", mr=50, gw="livefire_gw.py", discoverer="Djuk8",
                 fullname="", year=2026, verify_endpoints=0, mode="certify",
                 d_min=0, d_max=700, cert_dir="certs_out")
    json.dump(confJ, open(os.path.join(J, "pipeline.conf"), "w"))

    r = subprocess.run([PY, os.path.join(HERE, "pipeline.py"), "--adopt"],
                       cwd=J, capture_output=True, text=True)
    ok(r.returncode == 0 and "adopted 1" in r.stdout,
       f"J1 --adopt takes ownership of the existing certificate")
    stj = json.load(open(os.path.join(J, "pipeline_state.json")))
    ok(next(v for v in stj.values() if v["gap"] == 7000)["status"] == "CERTIFIED",
       "J2 already-certified find marked CERTIFIED, not re-dispatched")

    # a hand-launched notary on gap 8000 (matched via pgrep on --gap)
    fake = os.path.join(J, "notary_v1.py")
    open(fake, "w").write("import sys, time\ntime.sleep(25)\n")
    ext = subprocess.Popen([PY, fake, "--gap", "8000", "--z", "1e9"], cwd=J,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    r = subprocess.run([PY, os.path.join(HERE, "pipeline.py"), "--once"],
                       cwd=J, capture_output=True, text=True)
    ok("external notaries running on gaps: 8,000" in r.stdout,
       "J3 externally-running notary detected")
    stj = json.load(open(os.path.join(J, "pipeline_state.json")))
    ok(next(v for v in stj.values() if v["gap"] == 8000)["status"] == "DISCOVERED",
       "J4 that gap NOT dispatched (no duplicate 3-core-hour run)")
    ok(next(v for v in stj.values() if v["gap"] == 9000)["status"] == "DISCOVERED",
       "J5 out-of-band find (D=900 > d_max) left for the other courthouse")
    ext.terminate(); ext.wait()

    time.sleep(1.5)
    r = subprocess.run([PY, os.path.join(HERE, "pipeline.py"), "--once"],
                       cwd=J, capture_output=True, text=True)
    ok("mode=certify" in r.stdout and not glob.glob(os.path.join(J, "waves", "*.sql")),
       "J6 mode=certify stops before staging (staging is the hub's job)")
    time.sleep(1.0)
    r = subprocess.run([PY, os.path.join(HERE, "pipeline.py"), "--once"],
                       cwd=J, capture_output=True, text=True)
    flat = glob.glob(os.path.join(J, "certs_out", "notary_cert_gap*.json"))
    ok(bool(flat), f"J7 cert_dir holds a flat copy for rsync to the hub "
                   f"({[os.path.basename(x) for x in flat]})")

    print("[K] auto-adopt: the OTHER courthouse's certificate arrives")
    # simulate box2 rsyncing a cert for the out-of-band find (gap 9000)
    os.makedirs(os.path.join(J, "certs_in"), exist_ok=True)
    json.dump(dict(gap=9000, zdesign=97, verdict="VALID", k=333, jleft=-4000,
                   jright=5000, merit=2.0, n0_digits=900,
                   endpoints=dict(p1=dict(fermat_bases_pass=True, is_prime_mr=True),
                                  p2=dict(fermat_bases_pass=True, is_prime_mr=True)),
                   interior=dict(count=8999, sieve_factored=8996,
                                 fermat_composite=3, pseudoprimes=0, prp_alarms=[]),
                   mr_rounds=50),
              open(os.path.join(J, "certs_in", "notary_cert_gap9000.json"), "w"))
    r = subprocess.run([PY, os.path.join(HERE, "pipeline.py"), "--once"],
                       cwd=J, capture_output=True, text=True)
    stj = json.load(open(os.path.join(J, "pipeline_state.json")))
    ok(next(v for v in stj.values() if v["gap"] == 9000)["status"] == "CERTIFIED",
       "K1 remote cert auto-adopted (out-of-band find now certified)")
    ok("adopted notary_cert_gap9000.json" in r.stdout,
       "K2 adoption is audited like any other transition")

    print("[L] --retry-failed returns stranded work to the queue")
    stj = json.load(open(os.path.join(J, "pipeline_state.json")))
    fid8 = next(k for k, v in stj.items() if v["gap"] == 8000)
    stj[fid8]["status"] = "FAILED"          # as if its notary was killed
    json.dump(stj, open(os.path.join(J, "pipeline_state.json"), "w"))
    r = subprocess.run([PY, os.path.join(HERE, "pipeline.py"), "--retry-failed"],
                       cwd=J, capture_output=True, text=True)
    ok(r.returncode == 0 and "1 FAILED finds returned" in r.stdout,
       "L1 FAILED -> DISCOVERED")
    stj = json.load(open(os.path.join(J, "pipeline_state.json")))
    ok(stj[fid8]["status"] == "DISCOVERED", "L2 state reflects the retry")
    ok("start_new_session=True" in open(os.path.join(HERE, "pipeline.py")).read(),
       "L3 notaries are detached (Ctrl-C on the pipeline cannot kill them)")

    print(f"\nPIPE GATE: ALL CHECKS PASS -- {N[0]} checks "
          f"[{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
