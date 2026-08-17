#!/usr/bin/env python3
"""net_doctor -- why can't this box reach GitHub? Stdlib only, no deps.

Tests each layer separately so the fix follows from the verdict instead of
from guesswork:
  1 proxy env      2 DNS (A + AAAA)      3 raw TCP 443 per address family
  4 TLS handshake  5 HTTPS small GET     6 HTTPS LARGE transfer (MTU probe)
  7 private-repo auth (with --token)     8 SSH transports (22 and 443)
  9 MTU / git version

  python3 net_doctor.py                       # anonymous checks
  python3 net_doctor.py --token ghp_xxx --repo djuk8/beacon_fleet
"""
import argparse, os, socket, ssl, subprocess, sys, time, urllib.error
import urllib.request

R = {}


def head(t): print(f"\n[{t}]")


def say(k, ok_, msg):
    R[k] = ok_
    print(("  OK   " if ok_ else "  FAIL ") + msg)


def tcp(host, port, family=0, timeout=8):
    t0 = time.time()
    infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
    if not infos: raise OSError("no address")
    af, st, pr, _, sa = infos[0]
    s = socket.socket(af, st, pr); s.settimeout(timeout)
    try:
        s.connect(sa)
        return time.time() - t0, sa[0]
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=None)
    ap.add_argument("--repo", default="djuk8/beacon_fleet")
    a = ap.parse_args()

    head("1 proxy environment")
    px = {k: v for k, v in os.environ.items() if "proxy" in k.lower()}
    say("proxy", True, f"proxy vars: {px if px else 'none'}"
        + ("  <-- a proxy is set; git must honour it too" if px else ""))

    head("2 DNS")
    v4 = v6 = []
    try:
        v4 = sorted({i[4][0] for i in socket.getaddrinfo(
            "github.com", 443, socket.AF_INET, socket.SOCK_STREAM)})
        say("dns4", bool(v4), f"github.com A: {', '.join(v4)}")
    except Exception as e:
        say("dns4", False, f"A lookup failed: {e}")
    try:
        v6 = sorted({i[4][0] for i in socket.getaddrinfo(
            "github.com", 443, socket.AF_INET6, socket.SOCK_STREAM)})
        say("dns6", True, f"github.com AAAA: {', '.join(v6) or 'none'}")
    except Exception:
        say("dns6", True, "github.com AAAA: none (fine, IPv4-only)")

    head("3 raw TCP :443")
    for fam, name in ((socket.AF_INET, "IPv4"), (socket.AF_INET6, "IPv6")):
        if fam == socket.AF_INET6 and not v6: continue
        try:
            dt, ip = tcp("github.com", 443, fam)
            say(f"tcp{name}", True, f"{name} connect to {ip} in {dt*1000:.0f} ms")
        except Exception as e:
            say(f"tcp{name}", False, f"{name} connect: {type(e).__name__}: {e}")

    head("4 TLS handshake")
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection(("github.com", 443), 10) as s:
            with ctx.wrap_socket(s, server_hostname="github.com") as ss:
                say("tls", True, f"{ss.version()}, cipher {ss.cipher()[0]}")
    except Exception as e:
        say("tls", False, f"{type(e).__name__}: {e}")

    head("5 HTTPS small GET (api.github.com)")
    try:
        with urllib.request.urlopen("https://api.github.com/zen", timeout=15) as r:
            say("https_small", True, f"HTTP {r.status}, body {len(r.read())} B")
    except Exception as e:
        say("https_small", False, f"{type(e).__name__}: {e}")

    head("6 HTTPS LARGE transfer (MTU / middlebox probe, ~4 MB)")
    url = ("https://raw.githubusercontent.com/primegap-list-project/"
           "prime-gap-list/master/allgaps.sql")
    try:
        t0 = time.time(); n = 0
        with urllib.request.urlopen(url, timeout=60) as r:
            while n < 4_000_000:
                b = r.read(65536)
                if not b: break
                n += len(b)
        dt = time.time() - t0
        say("https_large", n > 1_000_000,
            f"{n/1e6:.1f} MB in {dt:.1f}s ({n/dt/1e6:.1f} MB/s)")
    except Exception as e:
        say("https_large", False, f"{type(e).__name__}: {e}  <-- classic MTU "
                                  f"or middlebox signature")

    if a.token:
        head("7 private-repo auth")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{a.repo}",
            headers={"Authorization": f"Bearer {a.token}",
                     "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                import json
                j = json.load(r)
                say("auth", True, f"repo {j.get('full_name')} "
                                  f"private={j.get('private')}, "
                                  f"push={j.get('permissions', {}).get('push')}")
        except urllib.error.HTTPError as e:
            say("auth", False, f"HTTP {e.code} -- token wrong, expired, or "
                               f"not scoped to this repo")
        except Exception as e:
            say("auth", False, f"{type(e).__name__}: {e}")

    head("8 SSH transports (the usual escape hatch)")
    for host, port, key in (("github.com", 22, "ssh22"),
                            ("ssh.github.com", 443, "ssh443")):
        try:
            dt, ip = tcp(host, port)
            say(key, True, f"{host}:{port} reachable ({dt*1000:.0f} ms)")
        except Exception as e:
            say(key, False, f"{host}:{port}: {type(e).__name__}")

    head("9 local facts")
    try:
        for n in sorted(os.listdir("/sys/class/net")):
            if n == "lo": continue
            mtu = open(f"/sys/class/net/{n}/mtu").read().strip()
            print(f"  iface {n}: MTU {mtu}"
                  + ("   <-- non-standard; suspect for TLS resets"
                     if mtu not in ("1500", "9000") else ""))
    except OSError:
        pass
    g = subprocess.run(["git", "--version"], capture_output=True, text=True)
    print(f"  {g.stdout.strip() or 'git missing'}")

    print("\n=== VERDICT ===")
    if not R.get("tcpIPv4"):
        print("  Network cannot reach github.com:443 at all -- egress blocked.")
        print("  -> use the Jupyter-pull fallback (fleet_pull.py from shredder)")
    elif R.get("https_small") and not R.get("https_large"):
        print("  Small requests fine, large transfers die = MTU/middlebox.")
        print("  -> git config --global http.version HTTP/1.1")
        print("  -> git config --global http.postBuffer 524288000")
        print("  -> ip link set dev eth0 mtu 1400   (needs privileges)")
        print("  -> if still failing: SSH transport over 443 (see below)")
    elif not R.get("tls") or not R.get("https_small"):
        print("  TLS/HTTPS to github is being interrupted.")
        print("  -> git config --global http.version HTTP/1.1")
        print("  -> SSH transport over 443 (see below)")
    elif R.get("auth") is False:
        print("  Network is fine; the TOKEN is the problem (scope/expiry).")
    else:
        print("  All layers OK from python. If git still fails, it is git's")
        print("  own TLS stack (gnutls): use HTTP/1.1 or the SSH transport.")
    if R.get("ssh443"):
        print("\n  SSH-over-443 escape hatch (most robust in containers):")
        print("    ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519")
        print("    cat ~/.ssh/id_ed25519.pub   # add as a DEPLOY KEY (write) on the repo")
        print("    printf 'Host github.com\\n HostName ssh.github.com\\n "
              "Port 443\\n User git\\n' >> ~/.ssh/config")
        print("    git clone git@github.com:<user>/<repo>.git fleet")


if __name__ == "__main__":
    main()
