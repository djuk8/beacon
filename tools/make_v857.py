#!/usr/bin/env python3
"""make_v857.py -- turn the repo's kit v8.56 into v8.57 IN PLACE (run from the repo root: python3 tools/make_v857.py).
v8.57 = ring 2 deep-sieved on the GPU daemon. With --gpu-rings 2 the daemon's GPU sieve covers rings 1+2 (|j| <= edges[1] = 4374)
at the daemon's depth (1e10) instead of ring 1 alone. Selection and the rung-1 ring file are UNCHANGED (selection reads the ring-1
part of the wider bitmap); the kept windows' ring-2 survivors ride in the manifest ("r2", int16 offsets, base64), the fold carries
them for the windows that pass ring 1, and the rung-2 make packs them instead of re-sieving ring 2 to 1e5 on the CPU. Sieving only
removes composites, so every ladder decision is unchanged; ring-2 tests per entering window roughly halve (60 -> ~30).
--gpu-rings 1 (the default) = v8.56 byte for byte. Edits (anchor-checked, each skipped if already applied):
  bs_api.c        bs_records_flat_w (wide record layout: i 13 / a0 14 / b0 13 bits, I <= 8191), bs_row_counts_rng
  gbs.cu, gbs_cpu.c   record layout switch gbs_set_format(g, 1) (v2 layout stays the default); gbs_block refuses I > 2047 in v2
  gbsd.py         --gpu-rings 1|2; ring-1 counts from the wider bitmap; manifest "r2"
  scanhunt_v0.py  cmd_fold carries "r2" for the windows that advance; cmd_make round 2 packs the carried ring-2 survivors
  onstart_raid_v2.sh  knobs SIEVERINGS (first sieve daemon) / SIEVERINGS2 (second) = 2 -> --gpu-rings 2; absent = v8.56
Kit: rebuilt from the repo's v8.56 tarball with the edited copies + gate_857_cpu.py, gate_857.sh, deploy_857.sh, ab857.py."""
import os, sys, subprocess, tarfile, tempfile, shutil, glob
assert os.path.isdir("deploy/kit_v8") and os.path.isfile("deploy/fresh_box.sh"), "run from the repo root"
old_kit = sorted(glob.glob("deploy/kit_v8/o1_kit_v8.5*.tgz"))[-1]; print("kit in:", old_kit)
if "v8.57" in old_kit: print("kit is already v8.57 - nothing to do"); sys.exit(0)
assert "v8.56" in old_kit, f"expected the v8.56 kit, found {old_kit}"
log = []
def edit(path, fn):
    s = open(path).read(); t = fn(s, path)
    if t is None: log.append(f"  {path}: already v8.57"); return
    assert t != s, f"{path}: nothing changed - stop"; open(path, "w").write(t); log.append(f"  {path}: edited")
def rep1(s, a, b, path):
    c = s.count(a); assert c == 1, f"{path}: anchor found {c} times: {a[:90]!r}"; return s.replace(a, b)

# ---------------- bs_api.c ----------------
WIDE = r'''/* v8.57: WIDE packed records for windows wider than the bsieve.c v2 fields allow (I > 2047; rings 1+2 = 4,375 columns):
   w0 = p (36 bits) | i (13 bits, <<36) | a0+8192 (14 bits, <<49);  w1 = t (44 bits) | b0 (13 bits, <<44);  w2 = a1.   I <= 8191.
   Read only by gbs.cu / gbs_cpu.c after gbs_set_format(g, 1); bsieve.c (the CPU daemon) keeps the v2 layout. Same per-prime math
   as bs_records_flat_s (first landing, FK basis), only the packing differs. Returns -2 if I > 8191, -1 if a prime divides S/2. */
static inline rec_t rec_pack_w(uint64_t p, int64_t t, int32_t i, int32_t a0, int64_t a1, int32_t b0) {
    rec_t r; r.w0 = p | ((uint64_t)(uint32_t)i << 36) | ((uint64_t)(uint32_t)(a0 + 8192) << 49);
    r.w1 = (uint64_t)t | ((uint64_t)(uint32_t)b0 << 44); r.w2 = (uint64_t)a1; return r; }
int64_t bs_records_flat_w(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, int64_t S, rec_t *out) {
    int64_t Sh = hi / 2, I = 2 * Sh + 1, n = 0; if (I > 8191) return -2;
    for (int64_t q = 0; q < nq; q++) {
        uint64_t p = (uint64_t)qd[q], pe = (uint64_t)PEd[q] % p; uint64_t B = (2 * pe) % p; if (!B) continue;
        uint64_t inv2 = (p + 1) / 2, k0m = (uint64_t)(k0 % (int64_t)p);
        uint64_t i0 = (uint64_t)(((uint64_t)Sh % p + p - mulmod(mulmod(k0m, pe, p), inv2, p)) % p);
        uint64_t f = (S == 2) ? pe : mulmod((uint64_t)(S / 2) % p, pe, p); if (!f) return -1;
        uint64_t sp = p - f;
        int64_t t = fm_next_hit((int64_t)sp, (int64_t)p, (int64_t)i0, I, 0, (int64_t)p); if (t < 0) continue;
        int32_t i = (int32_t)((i0 + (__uint128_t)(uint64_t)t * sp) % p);
        int32_t a0, b0; int64_t a1, b1; fk_reduce((int64_t)p, (int64_t)sp, I, &a0, &a1, &b0, &b1);
        out[n++] = rec_pack_w(p, t, i, a0, a1, b0);
    }
    return n;
}
/* v8.57: popcount per row over bit columns [c0, c1] only (the ring-1 counts inside a rings-1+2 bitmap) */
void bs_row_counts_rng(const uint64_t *bits, int64_t T, int64_t BW, int64_t c0, int64_t c1, int32_t *cnt) {
    int64_t w0 = c0 >> 6, w1 = c1 >> 6; uint64_t m0 = ~0ULL << (c0 & 63), m1 = ((c1 & 63) == 63) ? ~0ULL : ((1ULL << ((c1 & 63) + 1)) - 1);
    for (int64_t r = 0; r < T; r++) { const uint64_t *w = bits + r * BW; int c = 0;
        for (int64_t x = w0; x <= w1; x++) { uint64_t v = w[x]; if (x == w0) v &= m0; if (x == w1) v &= m1; c += __builtin_popcountll(v); }
        cnt[r] = c; }
}
const char *bs_api_v857(void) { return "bs_api v8.57 (wide records, ring-1 range counts)"; }
'''
def e_bsapi(s, p):
    if "bs_records_flat_w" in s: return None
    a = "int64_t bs_records_flat(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, rec_t *out) { return bs_records_flat_s(qd, PEd, nq, k0, T, hi, 2, out); }\n"
    return rep1(s, a, a + WIDE, p)

# ---------------- gbs.cu ----------------
SETFMT = ("/* v8.57: record layout of the uploaded records - 0 = bsieve.c v2 (bs_records_flat*, I <= 2047), 1 = wide (bs_records_flat_w,\n"
          "   I <= 8191); set once after gbs_create, before the first block */\n"
          "int gbs_set_format(void *g, int wide) { gbs_t *G = (gbs_t *)g; if (wide != 0 && wide != 1) return -1; if (G->cur) return -2;\n"
          "    if ((!wide && G->I > 2047) || (wide && G->I > 8191)) return -3;\n"
          "    G->wide = wide; return 0; }\n")
UNPACK_OLD = "int64_t x = R_I(r); int32_t a0 = R_A0(r), b0 = R_B0(r); int64_t a1 = R_A1(r); int64_t p = (int64_t)R_P(r);"
UNPACK_NEW = ("int64_t x = wide ? (int64_t)((r.w0 >> 36) & 8191) : R_I(r); int32_t a0 = wide ? (int32_t)((r.w0 >> 49) & 16383) - 8192 : R_A0(r), "
              "b0 = wide ? (int32_t)((r.w1 >> 44) & 8191) : R_B0(r); int64_t a1 = R_A1(r); int64_t p = (int64_t)R_P(r);   /* v8.57: wide layout when set */")
REPACK_OLD = "r.w0 = (r.w0 & ~(2047ULL << 36)) | ((uint64_t)(uint32_t)x << 36);"
REPACK_NEW = "r.w0 = (r.w0 & ~((wide ? 8191ULL : 2047ULL) << 36)) | ((uint64_t)(uint32_t)x << 36);"
def e_gbscu(s, p):
    if "gbs_set_format" in s: return None
    s = rep1(s, "    int64_t S;                                                      /* v8.56: progression step, k = k0 + S*t (2 = every odd k; 2310 = one class) */\n} gbs_t;",
             "    int64_t S;                                                      /* v8.56: progression step, k = k0 + S*t (2 = every odd k; 2310 = one class) */\n"
             "    int wide;                                                       /* v8.57: record layout, 0 = bsieve.c v2 (I <= 2047), 1 = wide (I <= 8191) */\n} gbs_t;", p)
    s = rep1(s, "__global__ void k_deep(int64_t T, int64_t I, int64_t BW, int64_t tbase, uint64_t *bits, int64_t nrec, rec_t *rec) {",
             "__global__ void k_deep(int64_t T, int64_t I, int64_t BW, int64_t tbase, uint64_t *bits, int64_t nrec, rec_t *rec, int wide) {", p)
    s = rep1(s, UNPACK_OLD, UNPACK_NEW, p); s = rep1(s, REPACK_OLD, REPACK_NEW, p)
    s = rep1(s, "G->nmed = nmed; G->S = 2;", "G->nmed = nmed; G->S = 2; G->wide = 0;", p)
    s = rep1(s, "(G->T, G->I, G->BW, tbase, G->d_bits, G->nrec, G->d_rec);", "(G->T, G->I, G->BW, tbase, G->d_bits, G->nrec, G->d_rec, G->wide);", p)
    s = rep1(s, "    gbs_t *G = (gbs_t *)g; int64_t tbase = G->cur * G->T;\n",
             "    gbs_t *G = (gbs_t *)g; int64_t tbase = G->cur * G->T;\n"
             "    if (!G->wide && G->I > 2047) { fprintf(stderr, \"gbs: I %ld needs the wide record layout (gbs_set_format)\\n\", (long)G->I); return -1; }   /* v8.57 */\n", p)
    a = "int gbs_set_step(void *g, int64_t S) { gbs_t *G = (gbs_t *)g; if (S < 2 || (S & 1)) return -1; if (G->cur) return -2; G->S = S; return 0; }\n"
    return rep1(s, a, a + SETFMT, p)
def e_gbscpu(s, p):
    if "gbs_set_format" in s: return None
    s = rep1(s, "    int64_t S;\n} gbs_t;", "    int64_t S;\n    int wide;                                                       /* v8.57: record layout (gbs.cu) */\n} gbs_t;", p)
    s = rep1(s, "    const int64_t T = G->T, I = G->I, BW = G->BW, lim = tbase + T;\n", "    const int64_t T = G->T, I = G->I, BW = G->BW, lim = tbase + T; const int wide = G->wide;\n", p)
    s = rep1(s, UNPACK_OLD, UNPACK_NEW, p); s = rep1(s, REPACK_OLD, REPACK_NEW, p)
    s = rep1(s, "G->nmed = nmed; G->S = 2;", "G->nmed = nmed; G->S = 2; G->wide = 0;", p)
    s = rep1(s, "    gbs_t *G = (gbs_t *)g; int64_t tbase = G->cur * G->T;\n",
             "    gbs_t *G = (gbs_t *)g; int64_t tbase = G->cur * G->T;\n    if (!G->wide && G->I > 2047) return -1;                         /* v8.57: as gbs.cu */\n", p)
    a = "int gbs_set_step(void *g, int64_t S) { gbs_t *G = (gbs_t *)g; if (S < 2 || (S & 1)) return -1; if (G->cur) return -2; G->S = S; return 0; }\n"
    return rep1(s, a, a + SETFMT, p)

# ---------------- gbsd.py ----------------
def e_gbsd(s, p):
    if "--gpu-rings" in s: return None
    s = rep1(s, "CLASS_RESULT_v0); every row is a valid window, kblock 8311 keeps 8,311 windows per ring. --step 2 (default) = v8.55 byte for byte.\"\"\"",
             "CLASS_RESULT_v0); every row is a valid window, kblock 8311 keeps 8,311 windows per ring. --step 2 (default) = v8.55 byte for byte.\n"
             "v8.57: --gpu-rings 2 sieves rings 1+2 on the GPU at --deepq; the ring file and the selection are unchanged (ring-1 part of the\n"
             "bitmap), the kept windows' ring-2 survivors ride in the manifest (\"r2\") to the ladder's rung-2 make. --gpu-rings 1 = v8.56.\"\"\"", p)
    s = rep1(s, "import argparse, ctypes, json, math, os, struct, sys, time\n", "import argparse, base64, ctypes, json, math, os, struct, sys, time\n", p)
    s = rep1(s, "magic, outs, bid_step, seed_=0, step_=2, kclass_=-1):", "magic, outs, bid_step, seed_=0, step_=2, kclass_=-1, gr_=1, r1c_=(0, 0), dq_=0, r1hi_=0):", p)
    s = rep1(s, "    L.bs_js_from_bits.restype = _c.c_int64; L.bs_js_from_bits.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_void_p, _c.c_int64, _c.c_void_p, _c.c_void_p, _c.c_int64]\n",
             "    L.bs_js_from_bits.restype = _c.c_int64; L.bs_js_from_bits.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_void_p, _c.c_int64, _c.c_void_p, _c.c_void_p, _c.c_int64]\n"
             "    if gr_ > 1: L.bs_row_counts_rng.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_void_p]   # v8.57\n", p)
    s = rep1(s, "_W.update(dict(L=L, fm=_fm, cfg=cfg, seed=seed_, S=step_, kclass=kclass_,", "_W.update(dict(L=L, fm=_fm, cfg=cfg, seed=seed_, S=step_, kclass=kclass_, GR=gr_, R1C=r1c_, DQ=dq_, R1HI=r1hi_,", p)
    s = rep1(s, "    cnt = np.empty(T, dtype=np.int32); L.bs_row_counts(bits.ctypes.data, T, BW, I, cnt.ctypes.data)\n",
             "    cnt = np.empty(T, dtype=np.int32); L.bs_row_counts(bits.ctypes.data, T, BW, I, cnt.ctypes.data)\n"
             "    if W[\"GR\"] > 1: cnt_all = cnt; cnt = np.empty(T, dtype=np.int32); L.bs_row_counts_rng(bits.ctypes.data, T, BW, W[\"R1C\"][0], W[\"R1C\"][1], cnt.ctypes.data)   # v8.57: selection keeps reading ring 1 only\n", p)
    s = rep1(s, "    out = np.empty(int(cnt[kept].sum()) + 16, dtype=np.int32);", "    out = np.empty(int((cnt if W[\"GR\"] == 1 else cnt_all)[kept].sum()) + 16, dtype=np.int32);", p)
    s = rep1(s, "js_sel = [out[offs[i]:offs[i] + cnt2[i]] for i in range(len(kept))]\n",
             "js_sel = [out[offs[i]:offs[i] + cnt2[i]] for i in range(len(kept))]\n"
             "    if W[\"GR\"] > 1: r1 = W[\"R1HI\"]; js2_sel = [j[np.abs(j) > r1] for j in js_sel]; js_sel = [j[np.abs(j) <= r1] for j in js_sel]   # v8.57: ring 1 -> ring file, ring 2 -> manifest\n", p)
    s = rep1(s, "kclass=W[\"kclass\"]))))\n    json.dump(man, open(tmp + \".manifest.json\", \"w\"))\n",
             "kclass=W[\"kclass\"]))))\n"
             "    if W[\"GR\"] > 1: man[\"r2\"] = dict(lo=r1, hi=W[\"cfg\"][\"edges\"][1], q=W[\"DQ\"], cnt=[int(len(j)) for j in js2_sel], b64=base64.b64encode((np.concatenate(js2_sel) if js2_sel else np.zeros(0)).astype(\"<i2\").tobytes()).decode(\"ascii\"))\n"
             "    json.dump(man, open(tmp + \".manifest.json\", \"w\"))\n", p)
    s = rep1(s, "| tail {time.time()-t0:.2f}s pred_z {zsel:+.2f} -> {os.path.basename(odir)}\"",
             "| tail {time.time()-t0:.2f}s pred_z {zsel:+.2f} -> {os.path.basename(odir)}\" + ('' if W[\"GR\"] == 1 else f\" | r2 {sum(len(j) for j in js2_sel)/max(len(js2_sel),1):.1f}/k\")", p)
    s = rep1(s, "    ap.add_argument(\"--step\", type=int, default=2);", "    ap.add_argument(\"--gpu-rings\", type=int, default=1)   # v8.57: 2 = the GPU sieves rings 1+2 (ring 2 rides to the ladder pre-sieved)\n    ap.add_argument(\"--step\", type=int, default=2);", p)
    s = rep1(s, "    if not a.kblock: a.kblock = 20000 if a.step == 2 else 8311 ",
             "    if a.gpu_rings not in (1, 2): sys.exit(\"gbsd: --gpu-rings 1 or 2\")\n    if not a.kblock: a.kblock = 20000 if a.step == 2 else 8311 ", p)
    s = rep1(s, "    edges = [int(x) for x in a.rings.split(\",\")]; hi = edges[0]; Sh = hi // 2; I = 2 * Sh + 1; BW = (I + 63) // 64\n",
             "    edges = [int(x) for x in a.rings.split(\",\")]; hi = edges[a.gpu_rings - 1]; Sh = hi // 2; I = 2 * Sh + 1; BW = (I + 63) // 64   # v8.57: rings 1..gpu_rings\n"
             "    r1c = (Sh - edges[0] // 2, Sh + edges[0] // 2)                    # bit columns of ring 1 inside the sieved window\n", p)
    s = rep1(s, "    L = ctypes.CDLL(a.api); G = ctypes.CDLL(a.gpu_api)\n",
             "    L = ctypes.CDLL(a.api); G = ctypes.CDLL(a.gpu_api)\n"
             "    if a.gpu_rings > 1:                                                   # v8.57: a v8.56 library cannot hold the wider window -> refuse\n"
             "        miss = [f for f, lib in ((\"bs_records_flat_w\", L), (\"bs_row_counts_rng\", L), (\"gbs_set_format\", G)) if not hasattr(lib, f)]\n"
             "        if miss: sys.exit(f\"gbsd: --gpu-rings {a.gpu_rings} needs the v8.57 libraries (missing {miss} in {a.api} / {a.gpu_api})\")\n"
             "        L.bs_records_flat_w.restype = ctypes.c_int64; L.bs_records_flat_w.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]\n"
             "        G.gbs_set_format.restype = ctypes.c_int; G.gbs_set_format.argtypes = [ctypes.c_void_p, ctypes.c_int]\n", p)
    s = rep1(s, "    nrec = L.bs_records_flat(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, rec.ctypes.data) if a.step == 2 else L.bs_records_flat_s(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, a.step, rec.ctypes.data)\n",
             "    if a.gpu_rings > 1: nrec = L.bs_records_flat_w(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, a.step, rec.ctypes.data)   # v8.57: wide layout\n"
             "    else: nrec = L.bs_records_flat(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, rec.ctypes.data) if a.step == 2 else L.bs_records_flat_s(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, a.step, rec.ctypes.data)\n", p)
    s = rep1(s, "    if a.step != 2 and G.gbs_set_step(g, a.step) != 0: sys.exit(\"gbsd: gbs_set_step failed\")\n",
             "    if a.step != 2 and G.gbs_set_step(g, a.step) != 0: sys.exit(\"gbsd: gbs_set_step failed\")\n"
             "    if a.gpu_rings > 1 and G.gbs_set_format(g, 1) != 0: sys.exit(\"gbsd: gbs_set_format failed\")\n", p)
    s = rep1(s, "+ ('' if a.step == 2 else f\" | v8.56 single-class: k = k0 + {a.step} t, class {a.kclass}\"), flush=True)",
             "+ ('' if a.step == 2 else f\" | v8.56 single-class: k = k0 + {a.step} t, class {a.kclass}\") + ('' if a.gpu_rings == 1 else f\" | v8.57 GPU rings 1+2 (|j| <= {hi})\"), flush=True)", p)
    return rep1(s, "sc.MAGIC_C, outs, a.bid_step, a.seed, a.step, a.kclass))", "sc.MAGIC_C, outs, a.bid_step, a.seed, a.step, a.kclass, a.gpu_rings, r1c, a.deepq, edges[0]))", p)

# ---------------- scanhunt_v0.py ----------------
FOLD_OLD = '''    pos = 0
    surv_ks = []
    prp_tot = 0
    for k, js, sz in zip(man["ks"], man["js"], man["sizes"]):
        vl = v[pos:pos + sz]; pos += sz
        hits = [js[i] for i in range(sz) if vl[i] in (1, 2)]
        prp_tot += len(hits)
        if not hits:
            surv_ks.append(k)
    json.dump(dict(ks=surv_ks, bid=man["bid"], round=r),
              open(f"sc_carry_r{r:02d}.json", "w"))
'''
FOLD_NEW = '''    pos = 0
    surv_ks = []
    surv_ix = []
    prp_tot = 0
    for ix, (k, js, sz) in enumerate(zip(man["ks"], man["js"], man["sizes"])):
        vl = v[pos:pos + sz]; pos += sz
        hits = [js[i] for i in range(sz) if vl[i] in (1, 2)]
        prp_tot += len(hits)
        if not hits:
            surv_ks.append(k); surv_ix.append(ix)
    carry = dict(ks=surv_ks, bid=man["bid"], round=r)
    if r == 1 and "r2" in man:     # v8.57: the GPU daemon's ring-2 survivors (sieved to its depth) ride along for the windows that advance
        import base64
        R2 = man["r2"]; cnt2 = [int(c) for c in R2["cnt"]]; allj = np.frombuffer(base64.b64decode(R2["b64"]), dtype="<i2")
        assert len(cnt2) == len(man["ks"]) and sum(cnt2) == len(allj), "r2 payload does not match the manifest -- FATAL"
        off = np.concatenate([[0], np.cumsum(cnt2)]).astype(np.int64); sel = [allj[off[i]:off[i + 1]] for i in surv_ix]
        carry["r2"] = dict(lo=R2["lo"], hi=R2["hi"], q=R2["q"], cnt=[int(len(x)) for x in sel],
                           b64=base64.b64encode(np.concatenate(sel).astype("<i2").tobytes() if sel else b"").decode("ascii"))
    json.dump(carry, open(f"sc_carry_r{r:02d}.json", "w"))
'''
MAKE_OLD = "        if r == 1 and nsel_ > 1:                                          # SPARSE-WINDOW SELECTION (SELECT_PREREG: x1.33 pass, rung-independent)\n"
MAKE_NEW = '''        r2c = carry.get("r2") if r >= 2 else None                         # v8.57: this ring was already sieved by the GPU daemon (to its depth)
        if r2c is not None and (int(r2c["lo"]), int(r2c["hi"])) == (lo, hi) and len(r2c["cnt"]) == len(ks):
            import base64
            allj = np.frombuffer(base64.b64decode(r2c["b64"]), dtype="<i2").astype(np.int64); off = np.concatenate([[0], np.cumsum(r2c["cnt"])]).astype(np.int64)
            assert off[-1] == len(allj), "r2 carry payload corrupt -- FATAL"
            pjs, psizes, packed = fastmake.pack_given(ks, [allj[off[i]:off[i + 1]] for i in range(len(ks))], int(P_eff), nb)
            sizes = list(psizes); blobs = [(k, j.tolist(), None) for k, j in zip(ks, pjs)]
            print(f"make r{r}: ring from the GPU daemon's sieve (q {float(r2c['q']):.0e}): {len(ks):,} ks, mean {sum(sizes)/max(len(sizes),1):.1f}/k", flush=True)
        elif r == 1 and nsel_ > 1:                                        # SPARSE-WINDOW SELECTION (SELECT_PREREG: x1.33 pass, rung-independent)
'''
def e_scanhunt(s, p):
    if "v8.57" in s: return None
    s = rep1(s, FOLD_OLD, FOLD_NEW, p); return rep1(s, MAKE_OLD, MAKE_NEW, p)

# ---------------- onstart_raid_v2.sh ----------------
def e_onstart(s, p):
    if "SIEVERINGS" in s: return None
    a = 'X2=""; [ "$(kn SIEVESTEP2 2)" = 2310 ] && X2="--step 2310 --kclass $(kn SIEVECLASS2 1993) --kbase $(kn SIEVEKBASE2 1000000000000000) --bid-start $(kn SIEVEBID2 2000000001)"\n'
    return rep1(s, a, a + '[ "$(kn SIEVERINGS 1)" = 2 ] && X1="$X1 --gpu-rings 2"; [ "$(kn SIEVERINGS2 1)" = 2 ] && X2="$X2 --gpu-rings 2"   # v8.57: the GPU sieves rings 1+2; ring 2 reaches the ladder pre-sieved\n', p)

EDITS = {"tools/sieve/bs_api.c": e_bsapi, "cuda/gbs.cu": e_gbscu, "cuda/gbs_cpu.c": e_gbscpu, "theater/raid610/gbsd.py": e_gbsd,
         "theater/raid610/scanhunt_v0.py": e_scanhunt, "theater/raid610/onstart_raid_v2.sh": e_onstart}
NEW = {"gate_857_cpu.py": "gates/gate_857_cpu.py", "gate_857.sh": "gates/gate_857.sh", "deploy_857.sh": "theater/raid610/deploy_857.sh", "ab857.py": "tools/ab857.py"}
for b, src in NEW.items(): assert os.path.isfile(src), f"new v8.57 file missing: {src}"
print("tracked copies:")
for path, fn in EDITS.items(): edit(path, fn)
print("\n".join(log)); log.clear()
tmp = tempfile.mkdtemp(); tarfile.open(old_kit).extractall(tmp, filter="data") if sys.version_info >= (3, 12) else tarfile.open(old_kit).extractall(tmp)
kd = os.path.join(tmp, "o1_kit"); assert os.path.isdir(kd)
print("kit copies:")
for path, fn in EDITS.items():
    kp = os.path.join(kd, os.path.basename(path)); assert os.path.exists(kp), f"kit lacks {os.path.basename(path)}"; edit(kp, fn)
for b, src in NEW.items(): shutil.copy2(src, os.path.join(kd, b)); log.append(f"  {b}: added ({src})")
shutil.rmtree(os.path.join(kd, "__pycache__"), ignore_errors=True)
print("\n".join(log))
new_kit = "deploy/kit_v8/o1_kit_v8.57.tgz"
with tarfile.open(new_kit, "w:gz") as t: t.add(kd, arcname="o1_kit")
if os.path.isdir(".git"): subprocess.run(["git", "rm", "-q", old_kit])
else: os.remove(old_kit)
shutil.rmtree(tmp); print(f"kit out: {new_kit} ({os.path.getsize(new_kit):,} bytes); {old_kit} removed")
print("next: bash -n, gates (python3 gates/gate_857_cpu.py), git diff --stat, commit + stamp + push")
