#!/usr/bin/env python3
"""make_v855.py -- turn the repo's kit v8.54 into v8.55 IN PLACE (run from the repo root on shredder: python3 tools/make_v855.py).
Every edit checks its anchor before touching anything and is skipped if already applied; tracked copies AND the kit tarball's copies
are edited; the kit tarball is rebuilt from the repo's own v8.54 tarball (never from a copy made elsewhere). Prints what it did."""
import os, sys, subprocess, tarfile, tempfile, shutil, glob
ROOT = os.getcwd(); assert os.path.isdir("deploy/kit_v8") and os.path.isfile("deploy/fresh_box.sh"), "run from the repo root"
old_kit = sorted(glob.glob("deploy/kit_v8/o1_kit_v8.5*.tgz"))[-1]; print("kit in:", old_kit)
assert "v8.54" in old_kit, f"expected the v8.54 kit, found {old_kit}"
log = []
def edit(path, fn, must):
    s = open(path).read(); t = fn(s, path)
    if t is None: log.append(f"  {path}: already v8.55"); return
    if t == s:
        assert not must, f"{path}: anchor absent in a file that deploys - stop"; log.append(f"  {path}: anchor absent - left as is"); return
    open(path, "w").write(t); log.append(f"  {path}: edited")
def rep1(s, a, b, path):
    c = s.count(a); assert c == 1, f"{path}: anchor found {c} times: {a[:70]!r}"; return s.replace(a, b)
# ---------------- the edits ----------------
def e_driver(s, p):
    if "FERMAT_GEC" in s and "DRIVER_SPIN" in s: return None
    s = rep1(s, "#include <stdio.h>\n", "/* v3.5/3.6 (2026-10-06): FERMAT_GEC 0 = no Gerbicz-Li check (+13%, verdicts identical; an hourly canary and the notary\n"
             "   replace it; build -DFERMAT_GEC=1 for the G2 fault-injection drill). DRIVER_SPIN 0 = blocking sync: the host thread sleeps\n"
             "   while the GPU works (99% -> 11% of a core per driver, same tests/s). */\n#ifndef DRIVER_SPIN\n#define DRIVER_SPIN 0\n#endif\n"
             "#ifndef FERMAT_GEC\n#define FERMAT_GEC 0\n#endif\n#include <stdio.h>\n", p)
    s = rep1(s, "      if(chunk_in_blk==J) {                    /* block boundary */", "      if(FERMAT_GEC && chunk_in_blk==J) {      /* block boundary */", p)
    s = rep1(s, "    if(blk_in_span>0) {                        /* final partial span */", "    if(FERMAT_GEC && blk_in_span>0) {          /* final partial span */", p)
    return rep1(s, "  cudaSetDevice(device);\n", "  cudaSetDevice(device);\n#if !DRIVER_SPIN\n  { cudaError_t fe = cudaSetDeviceFlags(cudaDeviceScheduleBlockingSync); if (fe != cudaSuccess) fprintf(stderr, \"warning: blocking sync not set: %s\\n\", cudaGetErrorString(fe)); }\n#endif\n", p)
PRED_V2 = r'''#include <string.h>
static void *pred_run(void *arg) {   /* v2 (2026-10-06): periodic table per prime + periodic add; identical sums, ~5.5x less work */
    pjob_t *J = arg; pred_t *M = J->M; int64_t T = J->T;
    int32_t *acc = calloc((size_t)T, sizeof(int32_t)); int64_t pmax = 0;
    for (int64_t q = J->q0; q < J->q1; q++) if (M->p[q] > pmax) pmax = M->p[q];
    uint16_t *d = malloc((size_t)(pmax + 512) * sizeof(uint16_t));
    for (int64_t q = J->q0; q < J->q1; q++) {
        int64_t p = M->p[q], e = M->pe[q]; const uint16_t *c = M->tab + M->off[q];
        int64_t r = (p - ((J->k0 % p) * e) % p) % p, step = (p - (2 * e) % p) % p;
        {   int64_t s8 = (8 * step) % p, rr[8]; rr[0] = r; for (int i = 1; i < 8; i++) { rr[i] = rr[i - 1] + step; if (rr[i] >= p) rr[i] -= p; }
            int64_t u = 0;
            for (; u + 8 <= p; u += 8) for (int i = 0; i < 8; i++) { d[u + i] = c[rr[i]]; rr[i] += s8; if (rr[i] >= p) rr[i] -= p; }
            for (int i = 0; u < p; u++, i++) d[u] = c[rr[i]]; }
        int64_t L = p;
        if (p < 256) { int64_t m = (256 + p - 1) / p; for (int64_t i = 1; i < m; i++) memcpy(d + i * p, d, (size_t)p * sizeof(uint16_t)); L = m * p; }
        for (int64_t t0 = 0; t0 < T; t0 += L) { int64_t len = T - t0 < L ? T - t0 : L; int32_t *restrict a = acc + t0; const uint16_t *restrict dd = d; for (int64_t u = 0; u < len; u++) a[u] += dd[u]; }
    }
    free(d); double *out = malloc((size_t)T * sizeof(double)); for (int64_t t = 0; t < T; t++) out[t] = acc[t]; free(acc); J->out = out; return NULL;
}
'''
def e_bsapi(s, p):
    if "pred_run v2" in s or "v2 (2026-10-06): periodic table" in s: return None
    i = s.find("static void *pred_run(void *arg) {"); j = s.find("void bs_predict(void *m,")
    if i < 0 or j < 0: return s
    old = s[i:j]; assert "acc[t] += c[r]; r += step;" in old, f"{p}: unexpected pred_run body - stop"; return s[:i] + PRED_V2 + s[j:]
def e_gocrown(s, p):
    if "gcc -O3 -march=native -shared -fPIC -o bs_api.so" in s: return None
    a = "gcc -O3 -shared -fPIC -o bs_api.so bs_api.c -lpthread"; return rep1(s, a, a.replace("-O3 ", "-O3 -march=native "), p) if a in s else s
def e_onstart(s, p):
    if "BSDNICE=$(kn BSDNICE 0)" in s: return None
    a = "BSDNICE=$(kn BSDNICE 5)"; return rep1(s, a, "BSDNICE=$(kn BSDNICE 0)   # v8.55: 0 - in rental containers a nice value cannot be lowered again", p) if a in s else s
GUARD = 'pgrep -f salvage_v1.py >/dev/null && { echo "$(date -u +%FT%TZ) harvest: previous walk still running - skip"; exit 0; }\n'
def e_harvest(s, p):
    if "hunt_s1*" not in s and GUARD in s: return None
    s = s.replace("hunt_s1*", "hunt_s*")
    if GUARD not in s:
        lines = s.split("\n"); idx = max(i for i, l in enumerate(lines[:6]) if l.startswith("#")) + 1; lines.insert(idx, GUARD.rstrip("\n")); s = "\n".join(lines)
    return s
def e_daily(s, p):
    if "hunt_s1*" not in s and "walked/**/*sc_r07_" in s: return None
    return s.replace("walked/**/sc_r07_", "walked/**/*sc_r07_").replace("hunt_s1*", "hunt_s*")
def e_salvage(s, p):
    if "set(owner) | set(dup)" in s: return None
    if 'jobs, owner, acct = [], [], {' not in s: return s
    s = rep1(s, 'jobs, owner, acct = [], [], {', 'jobs, owner, dup, acct = [], [], [], {', p)
    s = rep1(s, 'if not pend: acct["already"] += 1; continue', 'if not pend: acct["already"] += 1; dup.append(mf); continue          # v8.55: archive duplicates too', p)
    return rep1(s, "for mf in set(owner): os.replace(", "for mf in set(owner) | set(dup): os.replace(", p)
def e_fresh(s, p):
    if "canary_2048.bin" in s: return None
    for a, b in [('mkdir -p "$P3/cuda" && cp "$K/g1_fermat_v3.cu" "$P3/cuda/" && ( cd "$P3/cuda"', '[ -x "$P3/g1_fermat_v3" ] || { mkdir -p "$P3/cuda" && cp "$K/g1_fermat_v3.cu" "$P3/cuda/" && ( cd "$P3/cuda"'),
                 ('-lgmp 2>&1 | grep -iv warning | tail -3 ); [ -x "$P3/g1_fermat_v3" ] || die', '-lgmp 2>&1 | grep -iv warning | tail -3 ); }; [ -x "$P3/g1_fermat_v3" ] || die'),
                 ('"$P3/g1_fermat_v3" --help 2>&1 | grep -q usage || die "g1_fermat_v3 does not run"', 'OUT=$("$P3/g1_fermat_v3" --help 2>&1 || true); echo "$OUT" | grep -q usage || die "g1_fermat_v3 does not run: $OUT"')]:
        if a in s: s = s.replace(a, b)
    a = 'say "kit $(basename $KIT) -> $K ($(ls $K | wc -l) files); theater $R"'
    if "early seed" not in s and a in s:
        s = s.replace(a, a + '\necho "$SEED" > "$R/SIEVESEED.txt"; [ -n "$SEED2" ] && echo "$SEED2" > "$R/SIEVESEED2.txt"   # early seed: written before any step that can fail', 1)
    a = '# 3. seed knob, then go_crown does the rest'
    canary = ('# 2b. canary (v8.55): 200 known primes + 200 composites at 2,029 bits; the production driver must reproduce the expected verdicts\n'
              'cp "$K/canary_2048.bin" "$K/canary_expected.bin" "$K/canary.sh" "$P3/" && chmod +x "$P3/canary.sh" || die "canary files missing from the kit"\n'
              '( cd "$P3" && ./g1_fermat_v3 canary_2048.bin /tmp/canary_v0.bin > /dev/null 2>&1 && cmp -s /tmp/canary_v0.bin canary_expected.bin ) || die "canary FAILED on card 0 - driver build or card is bad"; say "canary: driver reproduces the expected verdicts"\n')
    s = rep1(s, a, canary + a, p)
    a = '( crontab -l 2>/dev/null; echo "17 * * * * $K/harvest_hourly.sh >> $R/harvest.log 2>&1" ) | sort -u | crontab -'
    s = rep1(s, a, '( crontab -l 2>/dev/null; echo "17 * * * * $K/harvest_hourly.sh >> $R/harvest.log 2>&1"; echo "43 * * * * $P3/canary.sh" ) | sort -u | crontab -', p)
    return s.replace("healthy = ~11k w/s per RTX 5090", "healthy = ~12.5k w/s per RTX 5090 at 575 W").replace("(run it yourself from $R: bash $K/go_crown.sh)", "(run it yourself from $R: bash $K/go_crown.sh, then add the cron lines: harvest at :17, $P3/canary.sh at :43)")
EDITS = {"g1_fermat_v3.cu": (e_driver, True), "bs_api.c": (e_bsapi, True), "go_crown.sh": (e_gocrown, True), "onstart_raid_v2.sh": (e_onstart, True),
         "harvest_hourly.sh": (e_harvest, True), "daily.sh": (e_daily, True), "salvage_v1.py": (e_salvage, True), "fresh_box.sh": (e_fresh, True)}
# ---------------- tracked copies ----------------
tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split() if os.path.isdir(".git") else \
          [os.path.relpath(os.path.join(d, f)) for d, _, fs in os.walk(".") if ".git" not in d for f in fs]
print("tracked copies:")
for path in tracked:
    b = os.path.basename(path)
    if b in EDITS: edit(path, EDITS[b][0], must=(b == "fresh_box.sh"))
print("\n".join(log)); log.clear()
# ---------------- the kit tarball ----------------
tmp = tempfile.mkdtemp(); tarfile.open(old_kit).extractall(tmp); kd = os.path.join(tmp, "o1_kit"); assert os.path.isdir(kd)
print("kit copies:")
for b, (fn, must) in EDITS.items():
    p = os.path.join(kd, b)
    if os.path.exists(p): edit(p, fn, must=must)
for f in ("canary_2048.bin", "canary_expected.bin", "canary.sh"): shutil.copy2(os.path.join("tools/canary", f), kd)
log.append("  canary files added to the kit")
print("\n".join(log))
new_kit = "deploy/kit_v8/o1_kit_v8.55.tgz"
with tarfile.open(new_kit, "w:gz") as t: t.add(kd, arcname="o1_kit")
if os.path.isdir(".git"): subprocess.run(["git", "rm", "-q", old_kit])
else: os.remove(old_kit)
shutil.rmtree(tmp); print(f"kit out: {new_kit} ({os.path.getsize(new_kit):,} bytes); {old_kit} removed")
print("next: bash -n on the edited scripts, git diff --stat, then commit + stamp + push")
