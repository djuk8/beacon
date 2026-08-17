#!/usr/bin/env python3
"""gate_pull -- G-PULL. Mock Jupyter contents API, real puller code.

Legs: A auth enforced  B directory walk + glob  C content fidelity
D incremental delta  E truncation guard (the find-protection fence)
F --force override  G missing-file tolerance  H bad-token failure exit.
"""
import http.server, json, os, shutil, socketserver, subprocess, sys
import threading, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "gtree")
OUT = os.path.join(HERE, "gout")
TOKEN = "s3cr3t"
PY = sys.executable
N = [0]


def ok(cond, msg):
    print(("  pass: " if cond else "  FAIL: ") + msg)
    if not cond: sys.exit(1)
    N[0] += 1


PW = ["", set()]        # [password, issued session cookies]
QUERY_ONLY = [False]    # mock a proxy that ONLY accepts ?token= (vast portal)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        if self.path.rstrip("/") != "/login":
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        body = urllib.parse.parse_qs(self.rfile.read(n).decode())
        if body.get("password", [""])[0] == PW[0] and PW[0]:
            PW[1].add("sess1")
            self.send_response(302)
            self.send_header("Set-Cookie", "username-8888=sess1; Path=/")
            self.send_header("Location", "/"); self.end_headers()
        else:
            self.send_response(403); self.end_headers()

    def do_GET(self):
        if self.path in ("/", ""):
            self.send_response(200); self.end_headers()
            self.wfile.write(b"jupyter"); return
        if self.path.rstrip("/") == "/login":
            self.send_response(200)
            self.send_header("Set-Cookie", "_xsrf=xtok; Path=/")
            self.end_headers(); self.wfile.write(b"<form>"); return
        if QUERY_ONLY[0]:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("token", [""])[0] != TOKEN:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"message":"portal: token required"}'); return
        elif PW[0]:
            ck = self.headers.get("Cookie", "")
            if "username-8888=sess1" not in ck:
                self.send_response(401); self.end_headers()
                self.wfile.write(b'{"message":"unauthorized"}'); return
        elif TOKEN and self.headers.get("Authorization") != f"token {TOKEN}":
            self.send_response(403); self.end_headers()
            self.wfile.write(b'{"message":"forbidden"}'); return
        u = urllib.parse.urlparse(self.path)
        if not u.path.startswith("/api/contents/") and u.path != "/api/contents":
            self.send_response(404); self.end_headers(); return
        rel = urllib.parse.unquote(u.path[len("/api/contents/"):]).strip("/")
        full = os.path.join(ROOT, rel) if rel else ROOT
        if os.path.isdir(full):
            body = dict(name=os.path.basename(full), type="directory",
                        content=[dict(name=e, path=os.path.join(rel, e),
                                      type="directory" if os.path.isdir(
                                          os.path.join(full, e)) else "file")
                                 for e in sorted(os.listdir(full))])
        elif os.path.isfile(full):
            body = dict(name=os.path.basename(full), type="file",
                        format="text", content=open(full).read())
        else:
            self.send_response(404); self.end_headers()
            self.wfile.write(b'{"message":"not found"}'); return
        b = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)


def log(n, start=0):
    h = "ts,D,zdesign,z,k,gap,merit,jleft,jright,tests,survivors,t_trial_s\n"
    return h + "".join(f"{1700000000+i},9800,349,1000000000,s5101t{i},"
                       f"{100000+i},1.0,-50000,50000,9,9,1.0\n"
                       for i in range(start, start + n))


def run(extra=()):
    return subprocess.run([PY, os.path.join(HERE, "fleet_pull.py"),
                           "--url", f"http://127.0.0.1:{PORT}",
                           "--token", TOKEN, "--remote-dir", "beacon/p3",
                           "--out", OUT, *extra],
                          capture_output=True, text=True)


def rows(w):
    p = os.path.join(OUT, w, "livefire_log.csv")
    return len(open(p).read().strip().splitlines()) - 1 if os.path.exists(p) else -1


shutil.rmtree(ROOT, ignore_errors=True); shutil.rmtree(OUT, ignore_errors=True)
base = os.path.join(ROOT, "beacon", "p3")
for w, n in (("w5101", 40), ("w5102", 25), ("w5004", 10)):
    os.makedirs(os.path.join(base, w))
    open(os.path.join(base, w, "livefire_log.csv"), "w").write(log(n))
os.makedirs(os.path.join(base, "w5103"))          # dir with no log yet
os.makedirs(os.path.join(base, "table_98w_1e9"))  # non-worker dir, must be ignored

socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(0.3)

t0 = time.time()
print("[A/B/C] auth, walk, fidelity")
r = run()
ok(r.returncode == 0, f"A1 pull exits 0")
ok(rows("w5101") == 40 and rows("w5102") == 25 and rows("w5004") == 10,
   f"B1 three worker logs pulled ({rows('w5101')}/{rows('w5102')}/{rows('w5004')} rows)")
ok(not os.path.exists(os.path.join(OUT, "table_98w_1e9")),
   "B2 non-worker dir ignored by glob")
ok(open(os.path.join(OUT, "w5101", "livefire_log.csv")).read() ==
   open(os.path.join(base, "w5101", "livefire_log.csv")).read(),
   "C1 content byte-identical to remote")

print("[D] incremental delta")
open(os.path.join(base, "w5101", "livefire_log.csv"), "w").write(log(55))
r = run()
ok(rows("w5101") == 55 and "+15" in r.stdout, f"D1 grew 40 -> 55, delta reported")

print("[E] truncation guard (protects banked finds)")
open(os.path.join(base, "w5101", "livefire_log.csv"), "w").write(log(9))
r = run()
ok(r.returncode == 1 and "REFUSED" in r.stdout and rows("w5101") == 55,
   "E1 shrunken remote refused, local 55 rows intact")

print("[F] --force override")
r = run(["--force"])
ok(rows("w5101") == 9, "F1 --force accepts the shrunken file")

print("[G] tolerance for a worker with no log yet")
ok("w5103" in r.stdout and "skipped" in r.stdout, "G1 missing log skipped, not failed")

print("[H] bad token")
r = subprocess.run([PY, os.path.join(HERE, "fleet_pull.py"), "--url",
                    f"http://127.0.0.1:{PORT}", "--token", "wrong",
                    "--remote-dir", "beacon/p3", "--out", OUT],
                   capture_output=True, text=True)
ok(r.returncode != 0 and "403" in (r.stdout + r.stderr),
   "H1 wrong token -> HTTP 403, nonzero exit")

print("[I] probe mode + tokenless server")
r = run(["--probe", "--remote-dir", ""])
ok(r.returncode == 0 and "CANDIDATE" in r.stdout and "beacon/p3" in r.stdout,
   "I1 probe finds the worker dir from the root")
globals()["TOKEN"] = ""         # server now accepts anything (tokenless)
r = subprocess.run([PY, os.path.join(HERE, "fleet_pull.py"), "--url",
                    f"http://127.0.0.1:{PORT}", "--remote-dir", "beacon/p3",
                    "--out", OUT, "--force"], capture_output=True, text=True)
ok(r.returncode == 0 and "WARN: no token" in r.stderr,
   "I2 tokenless pull works and warns")

print("[M] conf precedence: defaults must NOT override the conf file")
import json as _json
confp = os.path.join(HERE, "gconf.json")
altout = os.path.join(HERE, "gout_conf")
shutil.rmtree(altout, ignore_errors=True)
_json.dump(dict(url=f"http://127.0.0.1:{PORT}", token=TOKEN,
                remote_dir="beacon/p3", out=altout, dir_glob="w*",
                file="livefire_log.csv"), open(confp, "w"))
r = subprocess.run([PY, os.path.join(HERE, "fleet_pull.py"), "--conf", confp,
                    "--force"], capture_output=True, text=True)
ok(r.returncode == 0 and os.path.exists(
       os.path.join(altout, "w5101", "livefire_log.csv")),
   "M1 files land at the conf's out, not at the argparse default '.'")
ok(not os.path.exists(os.path.join(HERE, "w5101")),
   "M2 nothing written into the current directory")
ok("dest " in r.stdout and "source " in r.stdout,
   "M3 resolved source and destination printed before pulling")

print("[L] proxy that accepts ONLY ?token= (vast Instance Portal shape)")
QUERY_ONLY[0] = True
r = subprocess.run([PY, os.path.join(HERE, "fleet_pull.py"), "--url",
                    f"http://127.0.0.1:{PORT}", "--token", TOKEN,
                    "--remote-dir", "beacon/p3", "--out", OUT, "--force"],
                   capture_output=True, text=True)
ok(r.returncode == 0 and "rows" in r.stdout,
   "L1 query-param auth works where the header alone would 401")
r = subprocess.run([PY, os.path.join(HERE, "fleet_pull.py"), "--url",
                    f"http://127.0.0.1:{PORT}", "--token", "wrong",
                    "--remote-dir", "beacon/p3", "--out", OUT],
                   capture_output=True, text=True)
ok(r.returncode == 1 and "body:" in r.stdout,
   "L2 401 dumps server headers/body for diagnosis")
QUERY_ONLY[0] = False

print("[K] password login + auth diagnostics")
globals()["TOKEN"] = "irrelevant"
PW[0] = "hunter2"
r = subprocess.run([PY, os.path.join(HERE, "fleet_pull.py"), "--url",
                    f"http://127.0.0.1:{PORT}", "--remote-dir", "beacon/p3",
                    "--out", OUT], capture_output=True, text=True)
ok(r.returncode == 1 and "401" in r.stdout and "jupyter server list" in r.stdout,
   "K1 401 explained with the find-the-credential recipe, no traceback")
r = subprocess.run([PY, os.path.join(HERE, "fleet_pull.py"), "--url",
                    f"http://127.0.0.1:{PORT}", "--password", "hunter2",
                    "--remote-dir", "beacon/p3", "--out", OUT, "--force"],
                   capture_output=True, text=True)
ok(r.returncode == 0 and "logged in with password" in r.stdout,
   "K2 password login succeeds and pulls")

srv.shutdown()
print(f"\nPULL GATE: ALL CHECKS PASS -- {N[0]} checks [{time.time()-t0:.0f}s]")
