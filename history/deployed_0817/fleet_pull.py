#!/usr/bin/env python3
"""fleet_pull -- pull worker logs off a box that only exposes Jupyter.

Topology this solves: shredder is behind a VPN (outbound only, no inbound);
box1 is a vast.ai container with no ssh address but a public Jupyter server.
Jupyter's REST contents API is an HTTP read path, so shredder PULLS:

    shredder  --outbound HTTPS-->  box1:jupyter/api/contents  -->  logs

Read-only by construction: only GET /api/contents is ever called. Nothing on
the remote box can be written, moved, or executed by this tool.

Safety:
  * atomic writes (tmp + os.replace) -- a killed pull never truncates history
  * truncation guard: a fetched log with FEWER data rows than the local copy
    is refused (--force overrides), so a partial read cannot clobber finds
  * per-file row delta reported; exit 1 if any file failed
  * stdlib only (no pip on shredder), --insecure for vast's self-signed TLS

Credentials: put them in a 0600 JSON conf, never on the command line
(argv is world-readable in ps).

    cat > pull_box1.json <<'JSON'
    {"url": "https://1.2.3.4:8080", "token": "abc123...",
     "remote_dir": "beacon/p3", "out": "gpu_logs/box1",
     "dir_glob": "w*", "file": "livefire_log.csv", "insecure": true}
    JSON
    chmod 600 pull_box1.json
    python3 fleet_pull.py --conf pull_box1.json

Find url+token by running this INSIDE the box's Jupyter terminal:
    jupyter server list          # or: jupyter notebook list

pipeline.conf integration:
    "remote_pulls": ["python3 fleet_pull.py --conf pull_box1.json"]
"""
import argparse, fnmatch, http.cookiejar, json, os, ssl, sys, urllib.error
import urllib.parse, urllib.request

_OPENER = None


def opener(conf):
    """One opener for the process: carries TLS policy and the cookie jar
    (Jupyter password auth is cookie-based, token auth is header-based)."""
    global _OPENER
    if _OPENER is not None:
        return _OPENER
    handlers = []
    if conf.get("insecure"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    cj = http.cookiejar.CookieJar()
    handlers.append(urllib.request.HTTPCookieProcessor(cj))
    op = urllib.request.build_opener(*handlers)
    op.cookiejar = cj
    _OPENER = op
    return op


def login(conf):
    """Exchange a Jupyter PASSWORD for a session cookie (_xsrf handshake)."""
    base = conf["url"].rstrip("/")
    op = opener(conf)
    op.open(base + "/login", timeout=conf.get("timeout", 60)).read()
    xsrf = next((c.value for c in op.cookiejar if c.name == "_xsrf"), None)
    if not xsrf:
        raise SystemExit("login: server sent no _xsrf cookie -- is this "
                         "really a Jupyter server?")
    data = urllib.parse.urlencode({"_xsrf": xsrf,
                                   "password": conf["password"]}).encode()
    req = urllib.request.Request(base + "/login", data=data)
    try:
        op.open(req, timeout=conf.get("timeout", 60)).read()
    except urllib.error.HTTPError:
        pass          # the post-login landing page may 404/redirect oddly;
                      # what matters is whether a session cookie was issued
    if not any(c.name.startswith("username-") for c in op.cookiejar):
        raise SystemExit("login: password rejected (no session cookie issued)")
    print("  logged in with password (session cookie held)")


def prime(conf):
    """Some fronting proxies (vast.ai Instance Portal) authenticate via a
    ?token= query param that sets a session cookie, and ignore Jupyter's
    Authorization header. Prime the cookie jar once, tolerate failure."""
    base = conf["url"].rstrip("/")
    try:
        req = urllib.request.Request(
            f"{base}/?token={urllib.parse.quote(conf['token'])}")
        opener(conf).open(req, timeout=conf.get("timeout", 60)).read(2048)
        ck = [c.name for c in opener(conf).cookiejar]
        if ck: print(f"  primed session cookies: {', '.join(ck)}")
    except Exception:
        pass


def api(conf, path, params=None):
    base = conf["url"].rstrip("/")
    params = dict(params or {})
    if conf.get("token"):
        params["token"] = conf["token"]      # proxies want it in the query
    q = urllib.parse.urlencode(params)
    url = f"{base}/api/contents/{urllib.parse.quote(path)}" + (f"?{q}" if q else "")
    hdr = {"Accept": "application/json"}
    if conf.get("token"):
        hdr["Authorization"] = f"token {conf['token']}"
    if conf.get("basic"):
        import base64
        hdr["Authorization"] = "Basic " + base64.b64encode(
            conf["basic"].encode()).decode()
    req = urllib.request.Request(url, headers=hdr)
    with opener(conf).open(req, timeout=conf.get("timeout", 60)) as r:
        return json.load(r)


def datarows(text):
    return max(0, len([l for l in text.splitlines() if l.strip()]) - 1)


def pull_one(conf, rpath, lpath, force):
    j = api(conf, rpath, {"content": "1", "format": "text", "type": "file"})
    text = j.get("content")
    if text is None:
        raise ValueError("no content field (wrong endpoint or a directory?)")
    new = datarows(text)
    old = datarows(open(lpath).read()) if os.path.exists(lpath) else 0
    if new < old and not force:
        return ("REFUSED", old, new)
    os.makedirs(os.path.dirname(lpath) or ".", exist_ok=True)
    tmp = lpath + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, lpath)
    return ("OK", old, new)


def explain(e, conf):
    """Turn Jupyter's auth/routing errors into an instruction, not a traceback."""
    hdrs = dict(getattr(e, "headers", {}) or {})
    interesting = {k: v for k, v in hdrs.items()
                   if k.lower() in ("www-authenticate", "server", "location",
                                    "content-type", "set-cookie")}
    if interesting:
        print("  response headers: " + json.dumps(interesting))
    try:
        body = e.read(300).decode(errors="replace").strip()
        if body: print(f"  body: {body[:300]}")
    except Exception:
        pass
    if e.code == 401 and "www-authenticate" in {k.lower() for k in hdrs}:
        print("HTTP 401 with WWW-Authenticate -- the server wants HTTP Basic "
              "auth (a fronting proxy, not Jupyter itself).\n"
              "  Try: --basic <user>:<password>  (vast portal: often the "
              "instance user / portal password)")
        return 1
    if e.code == 401:
        print("HTTP 401 Unauthorized -- this Jupyter DOES require auth "
              "(so it is not an open shell).\n"
              "  Find the credential ON THE BOX, in this order:\n"
              "    jupyter server list\n"
              "    cat /proc/$(pgrep -f jupyter | head -1)/cmdline | tr '\\0' ' '\n"
              "    env | grep -iE 'token|jupyter|password'\n"
              "  Then: put it in the conf as \"token\", or if it is a "
              "PASSWORD, use --password / \"password\" in the conf.")
    elif e.code == 403:
        print("HTTP 403 Forbidden -- credential present but rejected "
              "(wrong/expired token, or password needed instead).")
    elif e.code == 404:
        print(f"HTTP 404 -- remote_dir {conf.get('remote_dir')!r} does not "
              f"exist under this server's root, or the base URL has a path "
              f"prefix. Run with --probe to walk the tree.")
    else:
        print(f"HTTP {e.code} {e.reason}")
    return 1


def probe(conf, maxdepth=3):
    """Find the directory that holds the worker dirs. Jupyter's root is not
    necessarily $HOME, so remote_dir must be relative to whatever it serves."""
    seen, queue, hits = set(), [(conf.get("remote_dir", ""), 0)], []
    while queue:
        path, depth = queue.pop(0)
        if path in seen or depth > maxdepth: continue
        seen.add(path)
        try:
            listing = api(conf, path)
        except urllib.error.HTTPError as e:
            if depth == 0:
                return explain(e, conf)
            print(f"  {path or '<root>'}: HTTP {e.code}"); continue
        except Exception as e:
            print(f"  {path or '<root>'}: {type(e).__name__}: {e}"); continue
        entries = listing.get("content", [])
        subs = [e for e in entries if e.get("type") == "directory"]
        workers = [e for e in subs
                   if fnmatch.fnmatch(e["name"], conf.get("dir_glob", "w*"))]
        files = [e["name"] for e in entries if e.get("type") == "file"]
        mark = "  <== CANDIDATE remote_dir" if workers else ""
        print(f"  {path or '<root>'}/  ({len(subs)} dirs, {len(files)} files)"
              f"{mark}")
        if workers:
            hits.append((path, sorted(e["name"] for e in workers)))
        for e in subs:
            if not e["name"].startswith("."):
                queue.append((e.get("path") or f"{path}/{e['name']}".strip("/"),
                              depth + 1))
    print()
    for path, ws in hits:
        print(f"  remote_dir = {path!r}   workers: {', '.join(ws[:8])}"
              + (" ..." if len(ws) > 8 else ""))
    return 0 if hits else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf")
    ap.add_argument("--url"); ap.add_argument("--token")
    ap.add_argument("--token-file")
    ap.add_argument("--password", help="Jupyter password (cookie login)")
    ap.add_argument("--basic", help="HTTP Basic credentials user:pass")
    ap.add_argument("--remote-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dir-glob", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--probe", action="store_true",
                    help="walk the remote tree and report where worker dirs live")
    a = ap.parse_args()

    conf = json.load(open(a.conf)) if a.conf else {}
    for k, v in (("url", a.url), ("token", a.token), ("out", a.out),
                 ("remote_dir", a.remote_dir), ("dir_glob", a.dir_glob),
                 ("file", a.file)):
        if v is not None: conf[k] = v
    if a.insecure: conf["insecure"] = True
    if a.token_file: conf["token"] = open(a.token_file).read().strip()
    if a.password: conf["password"] = a.password
    if a.basic: conf["basic"] = a.basic
    if not conf.get("url"):
        raise SystemExit("missing url (use --conf or --url)")
    if conf.get("token"):
        prime(conf)
    if conf.get("password"):
        login(conf)
    elif not conf.get("token"):
        print("  WARN: no token/password -- assuming a tokenless Jupyter. If "
              "the server is on a public URL, that URL is an open shell.",
              file=sys.stderr)
    conf.setdefault("remote_dir", ""); conf.setdefault("out", ".")
    conf.setdefault("dir_glob", "w*"); conf.setdefault("file", "livefire_log.csv")

    if a.probe:
        return probe(conf)
    print(f"  source {conf['url'].split('//')[-1][:40]}/"
          f"{conf['remote_dir']}  ->  dest {os.path.abspath(conf['out'])}")
    try:
        listing = api(conf, conf["remote_dir"])
    except urllib.error.HTTPError as e:
        return explain(e, conf)
    dirs = sorted(e["name"] for e in listing.get("content", [])
                  if e.get("type") == "directory"
                  and fnmatch.fnmatch(e["name"], conf["dir_glob"]))
    if not dirs:
        print(f"no dirs matching {conf['dir_glob']!r} under "
              f"{conf['remote_dir']!r}"); return 1
    fails = tot_new = tot_delta = 0
    for d in dirs:
        rpath = "/".join(x for x in (conf["remote_dir"], d, conf["file"]) if x)
        lpath = os.path.join(conf["out"], d, conf["file"])
        try:
            status, old, new = pull_one(conf, rpath, lpath, a.force)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                if not a.quiet: print(f"  {d}: no {conf['file']} (skipped)")
                continue
            print(f"  {d}: HTTP {e.code} {e.reason}"); fails += 1; continue
        except Exception as e:
            print(f"  {d}: {type(e).__name__}: {e}"); fails += 1; continue
        if status == "REFUSED":
            print(f"  {d}: REFUSED -- remote {new} rows < local {old} "
                  f"(use --force to override)"); fails += 1; continue
        tot_new += new; tot_delta += new - old
        if not a.quiet:
            print(f"  {d}: {new:,} rows (+{new-old:,})")
    print(f"pulled {len(dirs)-fails}/{len(dirs)} logs, {tot_new:,} rows total "
          f"(+{tot_delta:,} since last pull)" + (f", {fails} FAILED" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
