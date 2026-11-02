#!/usr/bin/env python3
"""make_v856.py -- turn the repo's kit v8.55 into v8.56 IN PLACE (run from the repo root: python3 tools/make_v856.py).
v8.56 = single-class hunting (CLASS_RESULT_v0): a sieve daemon can walk ONE residue class mod 2310, k = k0 + 2310 t (--step 2310
--kclass C), so every row of a pool is a valid window and only the best classes are hunted (317 / 1993: record odds x1.21/window).
--step 2 (the default everywhere) is byte-identical to v8.55 by construction: every S-dependent line keeps the v8.55 expression
when S == 2, and gate_856 proves it. Edits (anchor-checked, each skipped if already applied):
  bs_api.c   bs_records_flat_s / bs_js2_consts_s / bs_predict_s (old names = S=2 wrappers), bs_api_version
  gbs.cu     k = k0 + S t, small-prime row factor (S/2)*pe, gbs_set_step(); CPU twin cuda/gbs_cpu.c ships beside it (gates)
  gbsd.py    --step/--kclass/--kbase, kblock 8311 at S=2310 (8,311 windows per ring as today), state + manifest tagged with the class
  fastmake.py  single-class sets take the per-k kernel (js2 / fm_deepen index rows over the odd-k span: 1,155 rows per window)
  onstart_raid_v2.sh  knobs SIEVESTEP/SIEVECLASS/SIEVEKBASE/SIEVEBID (+ ...2 for the second sieve card; bids from 1e9 / 2e9); absent = v8.55 launch
Kit: rebuilt from the repo's own v8.55 tarball with the edited copies + gbs_cpu.c, ref856.c, gate_856.sh, gate_856_cpu.py, ab856.py."""
import os, sys, subprocess, tarfile, tempfile, shutil, glob
ROOT = os.getcwd(); assert os.path.isdir("deploy/kit_v8") and os.path.isfile("deploy/fresh_box.sh"), "run from the repo root"
old_kit = sorted(glob.glob("deploy/kit_v8/o1_kit_v8.5*.tgz"))[-1]; print("kit in:", old_kit)
if "v8.56" in old_kit: print("kit is already v8.56 - nothing to do"); sys.exit(0)
assert "v8.55" in old_kit, f"expected the v8.55 kit, found {old_kit}"
log = []
def edit(path, fn, must):
    s = open(path).read(); t = fn(s, path)
    if t is None: log.append(f"  {path}: already v8.56"); return
    if t == s:
        assert not must, f"{path}: anchor absent in a file that deploys - stop"; log.append(f"  {path}: anchor absent - left as is"); return
    open(path, "w").write(t); log.append(f"  {path}: edited")
def rep1(s, a, b, path):
    c = s.count(a); assert c == 1, f"{path}: anchor found {c} times: {a[:90]!r}"; return s.replace(a, b)
def repn(s, a, b, n, path):
    c = s.count(a); assert c == n, f"{path}: anchor found {c} times (want {n}): {a[:90]!r}"; return s.replace(a, b)

# ---------------- bs_api.c ----------------
def e_bsapi(s, p):
    if "bs_records_flat_s" in s: return None
    s = rep1(s, "int64_t bs_records_flat(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, rec_t *out) {\n",
             "int64_t bs_records_flat_s(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, int64_t S, rec_t *out) {   /* v8.56: rows k = k0 + S*t */\n", p)
    s = rep1(s, "        uint64_t sp = p - pe;\n",
             "        uint64_t f = (S == 2) ? pe : mulmod((uint64_t)(S / 2) % p, pe, p); if (!f) return -1;   /* v8.56: per-row shift (S/2)*pe; 0 = same kill every row (p | S/2): never for deep primes */\n"
             "        uint64_t sp = p - f;\n", p)
    s = rep1(s, "        out[n++] = rec_pack(p, t, i, a0, a1, b0);\n    }\n    return n;\n}\n",
             "        out[n++] = rec_pack(p, t, i, a0, a1, b0);\n    }\n    return n;\n}\n"
             "int64_t bs_records_flat(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, rec_t *out) { return bs_records_flat_s(qd, PEd, nq, k0, T, hi, 2, out); }\n", p)
    s = rep1(s, "void bs_js2_consts(int64_t k0, const int64_t *prs, const int64_t *PEm, int64_t np, int64_t hi, int64_t *tc_out, int64_t *step_out) {\n    int64_t Sh = hi / 2;\n",
             "int64_t bs_js2_consts_s(int64_t k0, const int64_t *prs, const int64_t *PEm, int64_t np, int64_t hi, int64_t S, int64_t *tc_out, int64_t *step_out) {   /* v8.56: rows k = k0 + S*t; returns #constant-kill primes (must be 0) */\n    int64_t Sh = hi / 2, nconst = 0;\n", p)
    s = rep1(s, "        uint64_t c = fm_inv(B2, p);\n        tc_out[qi] = (int64_t)(((__uint128_t)c * ((A2 + (uint64_t)Sh) % p)) % p); step_out[qi] = (int64_t)(p - c);\n    }\n}\n",
             "        if (S != 2) B2 = mulmod((uint64_t)(S / 2) % p, pe, p);                                  /* v8.56: per-row shift (S/2)*pe (== B*inv2 at S = 2) */\n"
             "        if (!B2) { tc_out[qi] = -1; step_out[qi] = 0; nconst++; continue; }                     /* p | S/2: the same kill in every row - not a walk */\n"
             "        uint64_t c = fm_inv(B2, p);\n        tc_out[qi] = (int64_t)(((__uint128_t)c * ((A2 + (uint64_t)Sh) % p)) % p); step_out[qi] = (int64_t)(p - c);\n    }\n    return nconst;\n}\n"
             "void bs_js2_consts(int64_t k0, const int64_t *prs, const int64_t *PEm, int64_t np, int64_t hi, int64_t *tc_out, int64_t *step_out) { bs_js2_consts_s(k0, prs, PEm, np, hi, 2, tc_out, step_out); }\n", p)
    s = rep1(s, "typedef struct { pred_t *M; int64_t k0, T, q0, q1; double *out; } pjob_t;",
             "typedef struct { pred_t *M; int64_t k0, T, q0, q1; double *out; int64_t S; } pjob_t;   /* v8.56: S = progression step */", p)
    s = rep1(s, "int64_t r = (p - ((J->k0 % p) * e) % p) % p, step = (p - (2 * e) % p) % p;",
             "int64_t r = (p - ((J->k0 % p) * e) % p) % p, step = (J->S == 2) ? (p - (2 * e) % p) % p : (p - ((J->S % p) * e) % p) % p;   /* v8.56: k = k0 + S*t */", p)
    s = rep1(s, "void bs_predict(void *m, int64_t k0, int64_t T, int nthreads, double *out) {\n",
             "void bs_predict_s(void *m, int64_t k0, int64_t T, int64_t S, int nthreads, double *out) {   /* v8.56: pred for k = k0 + S*t, t in [0,T) */\n", p)
    s = rep1(s, "jb[r].M = M; jb[r].k0 = k0; jb[r].T = T; jb[r].q0", "jb[r].M = M; jb[r].k0 = k0; jb[r].T = T; jb[r].S = S; jb[r].q0", p)
    s = rep1(s, "    for (int r = 0; r < nthreads; r++) { pthread_join(th[r], NULL); for (int64_t t = 0; t < T; t++) out[t] += jb[r].out[t]; free(jb[r].out); }\n}\n",
             "    for (int r = 0; r < nthreads; r++) { pthread_join(th[r], NULL); for (int64_t t = 0; t < T; t++) out[t] += jb[r].out[t]; free(jb[r].out); }\n}\n"
             "void bs_predict(void *m, int64_t k0, int64_t T, int nthreads, double *out) { bs_predict_s(m, k0, T, 2, nthreads, out); }\n", p)
    return s + "/* v8.56: library tag (receipts) */\nconst char *bs_api_version(void) { return \"bs_api v8.56 (step-aware: S = 2 | 2310)\"; }\n"

# ---------------- gbs.cu ----------------
SETSTEP = ("/* v8.56: progression step, set once after gbs_create and before the first block; the host constants must be built for the same S */\n"
           "int gbs_set_step(void *g, int64_t S) { gbs_t *G = (gbs_t *)g; if (S < 2 || (S & 1)) return -1; if (G->cur) return -2; G->S = S; return 0; }\n")
def e_gbscu(s, p):
    if "gbs_set_step" in s: return None
    s = rep1(s, "    uint64_t *d_wheel;                                              /* wheel template for wheel primes in the medium table */\n} gbs_t;",
             "    uint64_t *d_wheel;                                              /* wheel template for wheel primes in the medium table */\n"
             "    int64_t S;                                                      /* v8.56: progression step, k = k0 + S*t (2 = every odd k; 2310 = one class) */\n} gbs_t;", p)
    s = rep1(s, "const int64_t *moff, const uint64_t *wheel) {\n", "const int64_t *moff, const uint64_t *wheel, int64_t S) {\n", p)
    s = rep1(s, "int64_t t = tbase + row; int64_t k = k0 + 2 * t;", "int64_t t = tbase + row; int64_t k = k0 + S * t;", p)
    s = rep1(s, "if ((2 * e) % p == 0) r = Sh % p; else { r = (spc[q] - (t % p) * e) % p; if (r < 0) r += p; }",
             "if ((2 * e) % p == 0) r = Sh % p; else { int64_t f = (S == 2) ? e : ((S / 2) % p) * e % p; r = (spc[q] - (t % p) * f) % p; if (r < 0) r += p; }   /* v8.56: row shift (S/2)*pe; 0 for 3,5,7,11 at S = 2310 (same kill every row) */", p)
    s = rep1(s, "G->nsm = nsm; G->nmed = nmed;", "G->nsm = nsm; G->nmed = nmed; G->S = 2;", p)
    s = rep1(s, "G->d_moff, G->d_wheel);", "G->d_moff, G->d_wheel, G->S);", p)
    return rep1(s, "int64_t gbs_cur(void *g) { return ((gbs_t *)g)->cur; }\n", "int64_t gbs_cur(void *g) { return ((gbs_t *)g)->cur; }\n" + SETSTEP, p)

# ---------------- gbsd.py ----------------
def e_gbsd(s, p):
    if "--kclass" in s: return None
    s = rep1(s, 'Rings are exactly what `scanhunt make --round 1 --select N` / bsd.py produce (gate: byte-identical)."""',
             'Rings are exactly what `scanhunt make --round 1 --select N` / bsd.py produce (gate: byte-identical).\n'
             'v8.56: --step 2310 --kclass C walks ONE residue class mod 2310 (k = k0 + 2310 t, k0 = first k >= --kbase in the class, default 1e15;\n'
             'CLASS_RESULT_v0); every row is a valid window, kblock 8311 keeps 8,311 windows per ring. --step 2 (default) = v8.55 byte for byte."""', p)
    s = rep1(s, "magic, outs, bid_step, seed_=0):", "magic, outs, bid_step, seed_=0, step_=2, kclass_=-1):", p)
    s = rep1(s, "        L.bs_predict.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int, _c.c_void_p]\n",
             "        L.bs_predict.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int, _c.c_void_p]\n"
             "        if step_ != 2: L.bs_predict_s.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_int, _c.c_void_p]   # v8.56\n", p)
    s = rep1(s, "_W.update(dict(L=L, fm=_fm, cfg=cfg, seed=seed_,", "_W.update(dict(L=L, fm=_fm, cfg=cfg, seed=seed_, S=step_, kclass=kclass_,", p)
    s = rep1(s, 'ks_all = W["k0"] + 2 * (blk * T + np.arange(T, dtype=np.int64));', 'ks_all = W["k0"] + W["S"] * (blk * T + np.arange(T, dtype=np.int64));', p)
    s = rep1(s, 'L.bs_predict(W["PRED"], int(W["k0"] + 2 * blk * T), T, W["pt"], pr.ctypes.data);',
             '(L.bs_predict(W["PRED"], int(W["k0"] + 2 * blk * T), T, W["pt"], pr.ctypes.data) if W["S"] == 2 else L.bs_predict_s(W["PRED"], int(W["k0"] + W["S"] * blk * T), T, W["S"], W["pt"], pr.ctypes.data));', p)
    s = rep1(s, 'pred_z=round(zsel, 3)))', 'pred_z=round(zsel, 3), **({} if W["S"] == 2 else dict(step=W["S"], kclass=W["kclass"]))))', p)
    s = rep1(s, 'ap.add_argument("--kblock", type=int, default=20000);', 'ap.add_argument("--kblock", type=int, default=0);', p)
    s = rep1(s, '    ap.add_argument("--pred-pb", type=int, default=100000);',
             '    ap.add_argument("--step", type=int, default=2); ap.add_argument("--kclass", type=int, default=-1); ap.add_argument("--kbase", type=int, default=0)   # v8.56: --step 2310 --kclass C [--kbase K]: one residue class mod 2310\n'
             '    ap.add_argument("--pred-pb", type=int, default=100000);', p)
    s = rep1(s, "    a = ap.parse_args()\n    ns = argparse.Namespace(",
             "    a = ap.parse_args()\n"
             "    if not a.kblock: a.kblock = 20000 if a.step == 2 else 8311                     # v8.56: 8311 x 12 = 99,732 single-class rows -> 8,311 windows per ring, as at step 2\n"
             "    if a.step != 2 and (a.step != 2310 or not 0 < a.kclass < 2310 or math.gcd(a.kclass, 2310) != 1):\n"
             "        sys.exit(\"gbsd: --step 2310 needs --kclass C with 0 < C < 2310 and gcd(C, 2310) == 1 (best pair: 317 / 1993)\")\n"
             "    ns = argparse.Namespace(", p)
    s = rep1(s, "    T = a.kblock * a.select; k0 = sc.kstart(cfg); nb = a.bits // 8\n",
             "    T = a.kblock * a.select; k0 = sc.kstart(cfg); nb = a.bits // 8\n"
             "    if a.step != 2: kb = a.kbase or 10 ** 15; k0 = kb + (a.kclass - kb) % 2310      # v8.56: first k >= kbase in the class (single-class k-space starts at 1e15)\n", p)
    s = rep1(s, "    L = ctypes.CDLL(a.api); G = ctypes.CDLL(a.gpu_api)\n",
             "    L = ctypes.CDLL(a.api); G = ctypes.CDLL(a.gpu_api)\n"
             "    if a.step != 2:                                                                    # v8.56: a v8.55 library would sieve the wrong progression silently -> refuse\n"
             "        miss = [f for f, lib in ((\"bs_js2_consts_s\", L), (\"bs_records_flat_s\", L), (\"bs_predict_s\", L), (\"gbs_set_step\", G)) if not hasattr(lib, f)]\n"
             "        if miss: sys.exit(f\"gbsd: --step {a.step} needs the v8.56 libraries (missing {miss} in {a.api} / {a.gpu_api})\")\n"
             "        L.bs_js2_consts_s.restype = ctypes.c_int64; L.bs_js2_consts_s.argtypes = [ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p]\n"
             "        L.bs_records_flat_s.restype = ctypes.c_int64; L.bs_records_flat_s.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]\n"
             "        G.gbs_set_step.restype = ctypes.c_int; G.gbs_set_step.argtypes = [ctypes.c_void_p, ctypes.c_int64]\n", p)
    s = rep1(s, '    except Exception: print(f"gbsd: fresh progression for seed {a.seed} (state {statef})", flush=True)\n',
             '    except Exception: print(f"gbsd: fresh progression for seed {a.seed} (state {statef})", flush=True)\n'
             '    if blk and (stt.get("step", 2), stt.get("kclass", -1), stt.get("k0", k0)) != (a.step, a.kclass, k0):   # v8.56: never resume another progression\'s state\n'
             '        sys.exit(f"gbsd: state {statef} is step {stt.get(\'step\', 2)} class {stt.get(\'kclass\', -1)} k0 {stt.get(\'k0\', \'?\')} - not this daemon (step {a.step} class {a.kclass} k0 {k0})")\n', p)
    s = rep1(s, "json.dump(dict(seed=a.seed, next_block=nb, next_bid=nbid, ts=time.time()), f)",
             "json.dump(dict(seed=a.seed, next_block=nb, next_bid=nbid, ts=time.time(), **({} if a.step == 2 else dict(step=a.step, kclass=a.kclass, k0=k0))), f)", p)
    s = rep1(s, "    k0_run = k0 + 2 * blk * T ", "    k0_run = k0 + a.step * blk * T ", p)
    s = rep1(s, "(k0_run = k0 + {2*blk*T:,})", "(k0_run = k0 + {a.step*blk*T:,})", p)
    s = rep1(s, "    mtc = np.empty(nmed, dtype=np.int64); mstep = np.empty(nmed, dtype=np.int64); L.bs_js2_consts(k0_run, mp.ctypes.data, me.ctypes.data, nmed, hi, mtc.ctypes.data, mstep.ctypes.data)\n",
             "    mtc = np.empty(nmed, dtype=np.int64); mstep = np.empty(nmed, dtype=np.int64)\n"
             "    if a.step == 2: L.bs_js2_consts(k0_run, mp.ctypes.data, me.ctypes.data, nmed, hi, mtc.ctypes.data, mstep.ctypes.data)\n"
             "    elif L.bs_js2_consts_s(k0_run, mp.ctypes.data, me.ctypes.data, nmed, hi, a.step, mtc.ctypes.data, mstep.ctypes.data) != 0: sys.exit(\"gbsd: a medium prime divides step/2 - raise --pmask\")\n", p)
    s = rep1(s, "    rec = np.empty((len(qd), 3), dtype=np.uint64); nrec = L.bs_records_flat(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, rec.ctypes.data)\n",
             "    rec = np.empty((len(qd), 3), dtype=np.uint64)\n"
             "    nrec = L.bs_records_flat(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, rec.ctypes.data) if a.step == 2 else L.bs_records_flat_s(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, a.step, rec.ctypes.data)\n"
             "    if nrec < 0: sys.exit(\"gbsd: a deep prime divides step/2 (impossible above 11) - stop\")\n", p)
    s = rep1(s, '    if not g: sys.exit("gbs_create failed (GPU memory? device?)")\n',
             '    if not g: sys.exit("gbs_create failed (GPU memory? device?)")\n'
             '    if a.step != 2 and G.gbs_set_step(g, a.step) != 0: sys.exit("gbsd: gbs_set_step failed")\n', p)
    s = rep1(s, "upload {time.time()-t1:.1f}s\", flush=True)",
             "upload {time.time()-t1:.1f}s\" + ('' if a.step == 2 else f\" | v8.56 single-class: k = k0 + {a.step} t, class {a.kclass}\"), flush=True)", p)
    return rep1(s, "sc.MAGIC_C, outs, a.bid_step, a.seed))", "sc.MAGIC_C, outs, a.bid_step, a.seed, a.step, a.kclass))", p)

# ---------------- fastmake.py ----------------
SINGLE = '''def _single_class(ks):
    """v8.56: True for a set of ks in ONE residue class mod 2310 (single-class daemon rings, k = k0 + 2310 t). fm_block_js2 / fm_deepen
    index rows over the odd-k span (1,155 rows per window for such a set: ~500x the work) -> the per-k kernel (same survivors: the contract)."""
    return len(ks) >= 2 and bool(np.all(np.asarray(ks, dtype=np.int64) % 2310 == int(ks[0]) % 2310))

def block_js('''
def e_fastmake(s, p):
    if "_single_class" in s: return None
    s = rep1(s, "def block_js(", SINGLE, p)
    s = repn(s, '_use2 = (nk >= 500) and (__import__("os").environ.get("FM_JS2", "1") != "0")', '_use2 = (nk >= 500) and (__import__("os").environ.get("FM_JS2", "1") != "0") and not _single_class(ks)', 2, p)
    return repn(s, "    if qd is not None:\n        qd = np.ascontiguousarray(np.asarray(qd, dtype=np.int64));",
                "    if qd is not None:\n        if _single_class(ks): raise RuntimeError(\"v8.56: deepening a single-class set (DEEPR > 1) is not supported - keep DEEPR=1\")\n"
                "        qd = np.ascontiguousarray(np.asarray(qd, dtype=np.int64));", 2, p)

# ---------------- onstart_raid_v2.sh ----------------
KNOBS = ('X1=""; [ "$(kn SIEVESTEP 2)" = 2310 ] && X1="--step 2310 --kclass $(kn SIEVECLASS 317) --kbase $(kn SIEVEKBASE 1000000000000000) --bid-start $(kn SIEVEBID 1000000001)"   # v8.56: one residue class mod 2310 per sieve daemon; bids >= 1e9 mark its rings in the feeder ledgers\n'
         'X2=""; [ "$(kn SIEVESTEP2 2)" = 2310 ] && X2="--step 2310 --kclass $(kn SIEVECLASS2 1993) --kbase $(kn SIEVEKBASE2 1000000000000000) --bid-start $(kn SIEVEBID2 2000000001)"\n')
def e_onstart(s, p):
    if "SIEVESTEP" in s: return None
    s = rep1(s, 'if [ "$BSD" = 3 ]; then\n  SEED=$(cat /root/beacon/raid610/SIEVESEED.txt', KNOBS + 'if [ "$BSD" = 3 ]; then\n  SEED=$(cat /root/beacon/raid610/SIEVESEED.txt', p)
    s = rep1(s, 'echo "$(date -u) SIEVE CARD c$SIEVECARD seed $SEED serving $SERVE";', 'echo "$(date -u) SIEVE CARD c$SIEVECARD seed $SEED serving $SERVE${X1:+ | $X1}";', p)
    s = rep1(s, 'echo "$(date -u) SIEVE CARD c$SIEVECARD2 seed $SEED2 serving $SERVE2";', 'echo "$(date -u) SIEVE CARD c$SIEVECARD2 seed $SEED2 serving $SERVE2${X2:+ | $X2}";', p)
    s = rep1(s, "--gpu-api /root/beacon/raid610/gbs.so >> /root/beacon/raid610/gbsd_sieve.log", "--gpu-api /root/beacon/raid610/gbs.so $X1 >> /root/beacon/raid610/gbsd_sieve.log", p)
    return rep1(s, "--gpu-api /root/beacon/raid610/gbs.so >> /root/beacon/raid610/gbsd_sieve2.log", "--gpu-api /root/beacon/raid610/gbs.so $X2 >> /root/beacon/raid610/gbsd_sieve2.log", p)

EDITS = {"bs_api.c": (e_bsapi, True), "gbs.cu": (e_gbscu, True), "gbsd.py": (e_gbsd, True), "fastmake.py": (e_fastmake, True), "onstart_raid_v2.sh": (e_onstart, True)}
NEW = {"gbs_cpu.c": "cuda/gbs_cpu.c", "ref856.c": "tools/sieve/ref856.c", "gate_856.sh": "gates/gate_856.sh", "gate_856_cpu.py": "gates/gate_856_cpu.py",
       "ab856.py": "tools/ab856.py", "deploy_856.sh": "theater/raid610/deploy_856.sh"}
for b, src in NEW.items(): assert os.path.isfile(src), f"new v8.56 file missing: {src}"
# ---------------- tracked copies ----------------
tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split() if os.path.isdir(".git") else \
          [os.path.relpath(os.path.join(d, f)) for d, _, fs in os.walk(".") if ".git" not in d for f in fs]
print("tracked copies:")
for path in tracked:
    b = os.path.basename(path)
    if b in EDITS and not path.startswith("history/"): edit(path, EDITS[b][0], must=True)
print("\n".join(log)); log.clear()
# ---------------- the kit tarball ----------------
tmp = tempfile.mkdtemp(); tarfile.open(old_kit).extractall(tmp); kd = os.path.join(tmp, "o1_kit"); assert os.path.isdir(kd)
print("kit copies:")
for b, (fn, must) in EDITS.items():
    p = os.path.join(kd, b); assert os.path.exists(p), f"kit lacks {b}"; edit(p, fn, must=must)
for b, src in NEW.items(): shutil.copy2(src, os.path.join(kd, b)); log.append(f"  {b}: added ({src})")
shutil.rmtree(os.path.join(kd, "__pycache__"), ignore_errors=True)
print("\n".join(log))
new_kit = "deploy/kit_v8/o1_kit_v8.56.tgz"
with tarfile.open(new_kit, "w:gz") as t: t.add(kd, arcname="o1_kit")
if os.path.isdir(".git"): subprocess.run(["git", "rm", "-q", old_kit])
else: os.remove(old_kit)
shutil.rmtree(tmp); print(f"kit out: {new_kit} ({os.path.getsize(new_kit):,} bytes); {old_kit} removed")
print("next: bash -n on the edited scripts, gates (python3 gates/gate_856_cpu.py), git diff --stat, then commit + stamp + push")
