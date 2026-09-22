/* fastmake_c.c -- C kernel for scanhunt's ring-survivor sieve (BEACON O1, C, 2026-08-21).
 * CONTRACT = fastmake.block_js (numpy) exactly: for each k, even-j survivors of
 * [nlo, nhi] ascending, then of [plo, phi] ascending, where for ring (lo, hi]:
 *   lo == 0 : nlo=-hi nhi=-1     plo=1     phi=hi
 *   lo  > 0 : nlo=-hi nhi=-lo-1  plo=lo+1  phi=hi
 * A position j is killed by an odd prime p <= Q iff (n0 + j) % p == 0 with
 * n0 % p = (k % p) * (PEm[p] % p) % p.  p = 2 skipped (n0 odd, even j).
 * First landing >= jlo: st = jlo + ((j0 - jlo) mod p); if st odd: st += p
 * (p odd flips parity); kills at st, st+2p, ... <= jhi.  Same arithmetic as
 * ScanSieve.survivors and fastmake._side (both paths agree mathematically).
 *
 * API (ctypes):
 *   int fm_block_js(const int64_t *ks, int nk, const int64_t *prs, const int64_t *PEm,
 *                   int np_, int64_t lo, int64_t hi,
 *                   int32_t *out_js, int32_t *out_cnt, int64_t out_cap)
 *   out_js: concatenated survivors for all ks in contract order; out_cnt[i] = count for k i.
 *   returns total count, or -1 if out_cap too small, -2 on bad args.
 * Build: gcc -O3 -shared -fPIC -o fastmake_c.so fastmake_c.c   (add -march=native if the box allows)
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

static inline int64_t pmod(int64_t a, int64_t p) { int64_t r = a % p; return r < 0 ? r + p : r; }

/* survivors of one side [jlo, jhi] for one k.  n0m[i] = n0 mod prs[i]; jlom[i] = jlo mod prs[i] (precomputed per ring).
   No divisions: j0 = (p - n0m) if n0m else 0; d = j0 - jlom (+p if negative); st = jlo + d; odd st -> st + p. */
static int side(const int64_t *prs, const int64_t *n0m, const int64_t *jlom, int np_, int64_t jlo, int64_t jhi,
                unsigned char *alive, int32_t *out)
{
    int64_t js0 = jlo + (jlo & 1);
    int64_t m = (jhi - js0) / 2 + 1;
    if (m <= 0) return 0;
    memset(alive, 1, (size_t)m);
    for (int i = 1; i < np_; i++) {
        int64_t p = prs[i];
        int64_t j0 = n0m[i] ? p - n0m[i] : 0;
        int64_t d = j0 - jlom[i]; if (d < 0) d += p;
        int64_t st = jlo + d;
        if (st & 1) st += p;
        if (st > jhi) continue;
        int64_t idx = (st - js0) >> 1;
        for (; idx < m; idx += p) alive[idx] = 0;
    }
    int n = 0;
    for (int64_t i = 0; i < m; i++) if (alive[i]) out[n++] = (int32_t)(js0 + 2 * i);
    return n;
}

int fm_block_js(const int64_t *ks, int nk, const int64_t *prs, const int64_t *PEm, int np_,
                int64_t lo, int64_t hi, int32_t *out_js, int32_t *out_cnt, int64_t out_cap)
{
    if (nk < 0 || np_ < 1 || hi <= lo || lo < 0) return -2;
    int64_t nlo = -hi, nhi = lo ? -lo - 1 : -1, plo = lo ? lo + 1 : 1, phi = hi;
    int64_t mmax = (hi - lo) / 2 + 2;
    unsigned char *alive = (unsigned char *)malloc((size_t)mmax + 8);
    int64_t *n0m = (int64_t *)malloc(sizeof(int64_t) * (size_t)np_);
    int64_t *pem = (int64_t *)malloc(sizeof(int64_t) * (size_t)np_);     /* PEm mod p, doubled for the step */
    int64_t *nlm = (int64_t *)malloc(sizeof(int64_t) * (size_t)np_);     /* nlo mod p */
    int64_t *plm = (int64_t *)malloc(sizeof(int64_t) * (size_t)np_);     /* plo mod p */
    if (!alive || !n0m || !pem || !nlm || !plm) { free(alive); free(n0m); free(pem); free(nlm); free(plm); return -2; }
    for (int i = 1; i < np_; i++) { int64_t p = prs[i]; pem[i] = pmod(PEm[i], p); nlm[i] = pmod(nlo, p); plm[i] = pmod(plo, p); }
    int64_t tot = 0; int64_t kprev = 0; int have_prev = 0;
    for (int t = 0; t < nk; t++) {
        int64_t k = ks[t];
        int64_t dk = have_prev ? k - kprev : 0;
        if (have_prev && dk > 0 && dk <= 64) {
            /* linear form: n0m += dk * PEm (mod p), dk small -> add dk times the step, no division */
            for (int i = 1; i < np_; i++) {
                int64_t p = prs[i], r = n0m[i], s = pem[i];
                for (int64_t q = 0; q < dk; q++) { r += s; if (r >= p) r -= p; }
                n0m[i] = r;
            }
        } else {
            for (int i = 1; i < np_; i++) { int64_t p = prs[i]; n0m[i] = ((k % p) * pem[i]) % p; }
        }
        kprev = k; have_prev = 1;
        if (tot + mmax * 2 > out_cap) { free(alive); free(n0m); free(pem); free(nlm); free(plm); return -1; }
        int a = side(prs, n0m, nlm, np_, nlo, nhi, alive, out_js + tot);
        int b = side(prs, n0m, plm, np_, plo, phi, alive, out_js + tot + a);
        out_cnt[t] = a + b; tot += a + b;
    }
    free(alive); free(n0m); free(pem); free(nlm); free(plm);
    return (int)tot;
}

/* ---------------------------------------------------------------- packing ----
 * fm_block_pack: for each k, center-out (|j| ascending, ties: negative first == numpy stable
 * argsort on the contract order) js and the candidates n0 + j as nb-byte little-endian
 * integers, n0 = k * P_eff.  P_eff given as little-endian bytes (peff_nb bytes).
 *   int64 fm_block_pack(const int64_t *ks, int nk, const int32_t *js_in, const int32_t *cnt,
 *                       const unsigned char *peff, int peff_nb, int nb,
 *                       int32_t *js_out, unsigned char *bin_out, int64_t bin_cap)
 *   js_in/cnt: output of fm_block_js.  js_out: same layout, sorted.  bin_out: cnt-sum * nb bytes.
 *   returns total candidates or -1 (capacity) / -2 (args; nb must be a multiple of 8 and >= peff_nb+8).
 */
static int cmp_center(const void *a, const void *b) {
    int32_t x = *(const int32_t *)a, y = *(const int32_t *)b;
    int64_t ax = x < 0 ? -(int64_t)x : x, ay = y < 0 ? -(int64_t)y : y;
    if (ax != ay) return ax < ay ? -1 : 1;
    return x < y ? -1 : (x > y ? 1 : 0);               /* tie |x| == |y|: negative first */
}

int64_t fm_block_pack(const int64_t *ks, int nk, const int32_t *js_in, const int32_t *cnt,
                      const unsigned char *peff, int peff_nb, int nb,
                      int32_t *js_out, unsigned char *bin_out, int64_t bin_cap)
{
    if (nb % 8 || nb < peff_nb + 8 || nb > 8192) return -2;
    int L = nb / 8;
    uint64_t *pe = (uint64_t *)calloc((size_t)L, 8), *n0 = (uint64_t *)calloc((size_t)L, 8);
    if (!pe || !n0) { free(pe); free(n0); return -2; }
    memcpy(pe, peff, (size_t)peff_nb);                  /* little-endian bytes == little-endian limbs on LE hosts */
    int64_t tot = 0, off = 0;
    for (int t = 0; t < nk; t++) {
        int n = cnt[t];
        if ((tot + n) * (int64_t)nb > bin_cap) { free(pe); free(n0); return -1; }
        memcpy(js_out + off, js_in + off, sizeof(int32_t) * (size_t)n);
        qsort(js_out + off, (size_t)n, sizeof(int32_t), cmp_center);
        /* n0 = k * P_eff (k < 2^63, one limb) */
        uint64_t k = (uint64_t)ks[t]; unsigned __int128 carry = 0;
        for (int i = 0; i < L; i++) { unsigned __int128 v = (unsigned __int128)pe[i] * k + carry; n0[i] = (uint64_t)v; carry = v >> 64; }
        for (int c = 0; c < n; c++) {
            int32_t j = js_out[off + c]; uint64_t *w = (uint64_t *)(bin_out + (tot + c) * nb);
            memcpy(w, n0, (size_t)nb);
            if (j >= 0) { uint64_t add = (uint64_t)j; for (int i = 0; i < L && add; i++) { uint64_t s = w[i] + add; add = (s < w[i]); w[i] = s; } }
            else        { uint64_t sub = (uint64_t)(-(int64_t)j); for (int i = 0; i < L && sub; i++) { uint64_t s = w[i] - sub; sub = (w[i] < sub); w[i] = s; } }
        }
        tot += n; off += n;
    }
    free(pe); free(n0);
    return tot;
}

/* fm_deepen v0.4 (2026-09-08: FK lattice walk + bucketed landings) / v0.2 (O3, 2026-09-02): hybrid enumeration + per-k alive BITMAPS.
 *  - dense regime (expected landings >= 2): incremental window scan (t -= c per even j)
 *  - sparse regime: first-hit chaining, O(log p) per landing instead of O(window) per prime
 *  - kills applied as bit-clears into 197-byte per-k bitmaps (L2-resident; no random js scans)
 *  - js rebuilt from bitmaps in fm_block_js order (neg side ascending, then pos side ascending)
 * Gated: gate_fh 600-trial brute referee (enumeration), M1D cross-path identity (wired path). */
/* firsthit.c -- smallest x >= 0 with l <= (a*x) mod m <= r  (0 <= a < m, 0 <= l <= r < m); -1 if none.
   Classic Euclid-style recursion, O(log m). (C, 2026-09-02) */
typedef __int128 i128;
int64_t first_hit(int64_t a, int64_t m, int64_t l, int64_t r) {
    if (l == 0) return 0;
    if (a == 0) return -1;
    int64_t x0 = (l + a - 1) / a;                    /* first multiple of a reaching l without wrapping */
    if (a * x0 <= r) return x0;
    /* need k>=1 wraps: a*x = l + k*m + d (0<=d<=r-l)  =>  (k*m) mod a in [(-r) mod a, (-l) mod a] */
    int64_t ma = m % a;
    int64_t lo = ((-r) % a + a) % a, hi = ((-l) % a + a) % a;
    int64_t k = -1;
    if (r - l + 1 >= a) k = 1;                        /* arc covers all residues */
    else if (lo <= hi) k = first_hit(ma, a, lo, hi);
    else {                                            /* wrapped arc: two pieces, take the smaller k */
        int64_t k1 = first_hit(ma, a, lo, a - 1), k2 = first_hit(ma, a, 0, hi);
        if (k1 < 0) k = k2; else if (k2 < 0) k = k1; else k = k1 < k2 ? k1 : k2;
    }
    if (k < 0) return -1;
    if (k == 0) k = 1;                                /* k=0 would be a direct hit, already excluded */
    i128 num = (i128)k * m + l;
    return (int64_t)((num + a - 1) / a);
}

static int64_t fm_next_hit(int64_t a, int64_t p, int64_t off, int64_t T, int64_t i0, int64_t I) {
    int64_t c = (int64_t)(((__int128)a * i0 + off) % p);
    int64_t lo = ((-c) % p + p) % p, hi = ((T - 1 - c) % p + p) % p, y;
    if (T >= p) y = 0;
    else if (lo <= hi) y = first_hit(a, p, lo, hi);
    else { int64_t y1 = first_hit(a, p, lo, p - 1), y2 = first_hit(a, p, 0, hi);
           y = (y1 < 0) ? y2 : (y2 < 0) ? y1 : (y1 < y2 ? y1 : y2); }
    if (y < 0) return -1;
    int64_t i = i0 + y; return i < I ? i : -1;
}
static uint64_t fm_inv(uint64_t a, uint64_t m) {
    int64_t t0 = 0, t1 = 1; uint64_t r0 = m, r1 = a % m;
    while (r1) { uint64_t q = r0 / r1; int64_t t2 = t0 - (int64_t)q * t1; t0 = t1; t1 = t2; uint64_t r2 = r0 - q * r1; r0 = r1; r1 = r2; }
    return (uint64_t)(t0 < 0 ? t0 + (int64_t)m : t0);
}
/* Franke-Kleinjung reduced basis for L0 = {(t,i): t == i*s (mod p)}, width T, p > T (referee: fk_walk.c, 50k trials, 0 mismatches).
   Result: -T < a0 <= 0 <= b0 < T, b0 - a0 >= T, a1,b1 >= 1. Enumeration from a lattice point (x,y), 0 <= x < T:
   x >= -a0 -> +a ; x < T-b0 -> +b ; else -> +a+b  (next landing in increasing i, O(1) each). */
static inline void fk_reduce(int64_t p, int64_t s, int64_t T, int64_t *A0, int64_t *A1, int64_t *B0, int64_t *B1) {
    int64_t a0 = -p, a1 = 0, b0 = s, b1 = 1;
    for (;;) {
        if (-a0 >= T && b0 >= T) {
            if (-a0 >= b0) { int64_t q = (-a0) / b0; a0 += q * b0; a1 += q * b1; }
            else           { int64_t q = b0 / (-a0); b0 += q * a0; b1 += q * a1; }
            continue;
        }
        if (-a0 >= T) { int64_t q = (-a0 - T) / b0 + 1; a0 += q * b0; a1 += q * b1; break; }
        if (b0 >= T)  { int64_t q = (b0 - T) / (-a0) + 1; b0 += q * a0; b1 += q * a1; break; }
        break;
    }
    *A0 = a0; *A1 = a1; *B0 = b0; *B1 = b1;
}

int64_t fm_deepen(const int64_t *ks, int nk, int32_t *js, int32_t *cnt,
                  const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t lo, int64_t hi)
{
    if (nk <= 0 || nq <= 0) return 0;
    const int64_t Sh = hi / 2, I = 2 * Sh + 1;                     /* even j only: bit i <-> j = 2*(i - Sh) */
    const size_t BW = (size_t)((I + 63) / 64);
    int64_t k0 = ks[0], T = (ks[nk - 1] - k0) / 2 + 1;
    int32_t *tmap = (int32_t *)malloc(sizeof(int32_t) * (size_t)T);
    uint64_t *bits = (uint64_t *)calloc((size_t)nk * BW, sizeof(uint64_t));
    int64_t *offs = (int64_t *)malloc(sizeof(int64_t) * (size_t)nk);
    if (!tmap || !bits || !offs) { free(tmap); free(bits); free(offs); return -1; }
    memset(tmap, 0xFF, sizeof(int32_t) * (size_t)T);
    int64_t off = 0;
    for (int i = 0; i < nk; i++) {
        tmap[(ks[i] - k0) / 2] = i; offs[i] = off;
        uint64_t *b = bits + (size_t)i * BW;
        for (int c = 0; c < cnt[i]; c++) { int64_t j = js[off + c]; int64_t bi = j / 2 + Sh; b[bi >> 6] |= 1ULL << (bi & 63); }
        off += cnt[i];
    }
    const char *dbg = getenv("FM_DEBUG");
    if (dbg) fprintf(stderr, "[deepen v0.4] nk=%d T=%ld nq=%ld lo=%ld hi=%ld\n", nk, (long)T, (long)nq, (long)lo, (long)hi);
    /* v0.3 (2026-09-08): BUCKETED landing application. Landings are emitted as (idx,i) pairs into per-chunk buffers
       (CH ks per chunk -> ~200 KB of bitmap, L2-resident) and applied chunk by chunk at each flush. Same set of bit
       clears as v0.2 (order-independent), so the output is byte-identical; but the random 20-MB walk becomes
       sequential buffer writes + L2-local clears, ~4x faster and -- decisively -- immune to cache contention from
       neighbouring makes (the block-5 slot-curve collapse). */
    enum { CH_SHIFT = 10, CH = 1 << CH_SHIFT };
    const int nch = (nk + CH - 1) / CH;
    uint64_t **bk = (uint64_t **)calloc((size_t)nch, sizeof(uint64_t *));
    size_t *bl = (size_t *)calloc((size_t)nch, sizeof(size_t)), *bc = (size_t *)calloc((size_t)nch, sizeof(size_t));
    if (!bk || !bl || !bc) { free(bk); free(bl); free(bc); free(tmap); free(bits); free(offs); return -1; }
    const size_t FLUSH_AT = (size_t)4 << 20;   /* landings buffered before a flush (~32 MB of pairs) */
    size_t pending = 0;
    int64_t kills = 0;
    #define FLUSH() do { for (int ch = 0; ch < nch; ch++) { uint64_t *v = bk[ch]; size_t n = bl[ch]; \
            for (size_t e = 0; e < n; e++) { int32_t idx = (int32_t)(v[e] >> 32), ii = (int32_t)(v[e] & 0xFFFFFFFFu); \
                uint64_t *b = bits + (size_t)idx * BW; \
                if (b[ii >> 6] & (1ULL << (ii & 63))) { b[ii >> 6] &= ~(1ULL << (ii & 63)); cnt[idx]--; kills++; } } \
            bl[ch] = 0; } pending = 0; } while (0)
    #define EMIT(tt, ii) do { int32_t idx = tmap[(tt)]; if (idx >= 0) { int ch = idx >> CH_SHIFT; \
            if (bl[ch] == bc[ch]) { size_t nc = bc[ch] ? bc[ch] * 2 : 4096; uint64_t *nv = (uint64_t *)realloc(bk[ch], nc * sizeof(uint64_t)); \
                if (!nv) { fprintf(stderr, "[deepen v0.3] OOM\n"); abort(); } bk[ch] = nv; bc[ch] = nc; } \
            bk[ch][bl[ch]++] = ((uint64_t)(uint32_t)idx << 32) | (uint32_t)(ii); pending++; } } while (0)
    for (int64_t qi = 0; qi < nq; qi++) {
        if (dbg && (qi & 0xFFFFF) == 0) fprintf(stderr, "[deepen v0.3] qi=%ld/%ld kills=%ld pending=%zu\n", (long)qi, (long)nq, (long)kills, pending);
        uint64_t p = (uint64_t)qd[qi], pe = (uint64_t)PEd[qi] % p;
        uint64_t B = (2 * pe) % p; if (!B) continue;
        uint64_t inv2 = (p + 1) / 2;
        uint64_t k0m = (uint64_t)(k0 % (int64_t)p);
        uint64_t A = (p - (uint64_t)(((__uint128_t)k0m * pe) % p)) % p;            /* -k0*pe */
        uint64_t A2 = (uint64_t)(((__uint128_t)A * inv2) % p), B2 = (uint64_t)(((__uint128_t)B * inv2) % p);
        uint64_t c = fm_inv(B2, p);
        uint64_t tc = (uint64_t)(((__uint128_t)c * ((A2 + (uint64_t)Sh) % p)) % p);
        uint64_t step = p - c;
        if ((int64_t)p <= T) {                                   /* tiny primes: several landings per row -> row scan */
            uint64_t t = tc;
            for (int64_t i = 0; i < I; i++) { int64_t aj = 2 * (i - Sh); if (aj < 0) aj = -aj;
                if (aj > lo) for (uint64_t tt = t; (int64_t)tt < T; tt += p) EMIT((int64_t)tt, i);
                t += step; if (t >= p) t -= p; }
        } else {                                                  /* v0.4: FK lattice walk, O(1) per landing, no row scan */
            int64_t a = (int64_t)step;
            int64_t y = fm_next_hit(a, (int64_t)p, (int64_t)tc, T, 0, I);
            if (y >= 0) {
                int64_t x = (int64_t)(((__int128)a * y + (int64_t)tc) % p);
                int64_t a0, a1, b0, b1; fk_reduce((int64_t)p, a, T, &a0, &a1, &b0, &b1);
                while (y < I) {
                    int64_t aj = 2 * (y - Sh); if (aj < 0) aj = -aj;
                    if (aj > lo) EMIT(x, y);
                    if (x >= -a0)        { x += a0;      y += a1; }
                    else if (x < T - b0) { x += b0;      y += b1; }
                    else                 { x += a0 + b0; y += a1 + b1; }
                }
            }
        }
        if (pending >= FLUSH_AT) FLUSH();
    }
    FLUSH();
    #undef EMIT
    #undef FLUSH
    for (int ch = 0; ch < nch; ch++) free(bk[ch]);
    free(bk); free(bl); free(bc);
    /* rebuild js in fm_block_js order (neg asc, then pos asc), written TIGHT: segment i starts at the running
       offset, so the caller's cumsum(cnt) slicing is exact with no compaction pass (v0.2.1) */
    int64_t tight = 0;
    for (int i = 0; i < nk; i++) {
        uint64_t *b = bits + (size_t)i * BW; int32_t *o = js + tight; int n = 0;
        for (int64_t bi = 0; bi < Sh; bi++) if (b[bi >> 6] & (1ULL << (bi & 63))) o[n++] = (int32_t)(2 * (bi - Sh));
        for (int64_t bi = Sh; bi < I; bi++) if (b[bi >> 6] & (1ULL << (bi & 63))) o[n++] = (int32_t)(2 * (bi - Sh));
        cnt[i] = n; tight += n;
    }
    free(tmap); free(bits); free(offs);
    return kills;
}

/* fm_block_js2 (O3 sieve, 2026-09-02): prime-OUTER bitmap sieve for rung-1 blocks.
 * Replaces the per-k prime-table streaming (~20 GB/make at Q=1e6, the DRAM-wall hog) with one pass over
 * the primes and per-k 197-byte alive bitmaps: the linear form n0(t) = (k0+2t)*P_eff turns every prime
 * into a lattice walk over the whole block (identical mathematics to fm_deepen v0.2).
 *   p | 2*P_eff: p==2 never divides an odd candidate (skip); p | P_eff kills j == 0 (mod p) for EVERY k (wheel mask).
 * Output contract == fm_block_js: per-k js, even j in [-hi,hi] with |j|>lo, order neg-asc then pos-asc.
 *   int64 fm_block_js2(const int64* ks, int nk, const int64* prs, const int64* PEm, int64 np,
 *                      int64 lo, int64 hi, int32* out, int32* cnt, int64 cap)  -> total candidates, -1 on alloc/cap */
int64_t fm_block_js2(const int64_t *ks, int nk, const int64_t *prs, const int64_t *PEm, int64_t np,
                     int64_t lo, int64_t hi, int32_t *out, int32_t *cnt, int64_t cap)
{
    if (nk <= 0) return 0;
    const int64_t Sh = hi / 2, I = 2 * Sh + 1;
    const size_t BW = (size_t)((I + 63) / 64);
    int64_t k0 = ks[0], T = (ks[nk - 1] - k0) / 2 + 1;
    int32_t *tmap = (int32_t *)malloc(sizeof(int32_t) * (size_t)T);
    uint64_t *bits = (uint64_t *)malloc(sizeof(uint64_t) * (size_t)nk * BW);
    uint64_t *wheel = (uint64_t *)malloc(sizeof(uint64_t) * BW);
    if (!tmap || !bits || !wheel) { free(tmap); free(bits); free(wheel); return -1; }
    memset(tmap, 0xFF, sizeof(int32_t) * (size_t)T);
    for (int i = 0; i < nk; i++) tmap[(ks[i] - k0) / 2] = i;
    /* wheel: start all-alive in window (|j|>lo), then kill j == 0 (mod p) for every p | P_eff (p>2) */
    memset(wheel, 0, sizeof(uint64_t) * BW);
    for (int64_t bi = 0; bi < I; bi++) { int64_t aj = 2 * (bi - Sh); if (aj < 0) aj = -aj; if (aj > lo) wheel[bi >> 6] |= 1ULL << (bi & 63); }
    for (int64_t qi = 0; qi < np; qi++) {
        uint64_t p = (uint64_t)prs[qi]; if (p == 2) continue;
        uint64_t pe = (uint64_t)PEm[qi] % p;
        if ((2 * pe) % p == 0) {                                     /* p | P_eff: j == 0 mod p dead for all k */
            for (int64_t j = -(Sh * 2); j <= Sh * 2; j += 2) if (j % (int64_t)p == 0) { int64_t bi = j / 2 + Sh; wheel[bi >> 6] &= ~(1ULL << (bi & 63)); }
        }
    }
    for (int i = 0; i < nk; i++) memcpy(bits + (size_t)i * BW, wheel, sizeof(uint64_t) * BW);
    /* linear-form primes: everything with 2*pe != 0 mod p (swap primes 3,5,7,11 and zd < p <= Q) */
    for (int64_t qi = 0; qi < np; qi++) {
        uint64_t p = (uint64_t)prs[qi]; if (p == 2) continue;
        uint64_t pe = (uint64_t)PEm[qi] % p, B = (2 * pe) % p; if (!B) continue;
        uint64_t inv2 = (p + 1) / 2, k0m = (uint64_t)(k0 % (int64_t)p);
        uint64_t A = (p - (uint64_t)(((__uint128_t)k0m * pe) % p)) % p;
        uint64_t A2 = (uint64_t)(((__uint128_t)A * inv2) % p), B2 = (uint64_t)(((__uint128_t)B * inv2) % p);
        uint64_t c = fm_inv(B2, p);
        uint64_t tc = (uint64_t)(((__uint128_t)c * ((A2 + (uint64_t)Sh) % p)) % p), step = p - c;
        #define APPLY2(tt, ii) do { int32_t idx = tmap[(tt)]; if (idx >= 0) { uint64_t *b = bits + (size_t)idx * BW; b[(ii) >> 6] &= ~(1ULL << ((ii) & 63)); } } while (0)
        if ((__int128)I * T >= 2 * (__int128)p) {
            uint64_t t = tc;
            for (int64_t i = 0; i < I; i++) { for (uint64_t tt = t; (int64_t)tt < T; tt += p) APPLY2((int64_t)tt, i);
                t += step; if (t >= p) t -= p; }
        } else {
            int64_t a = (int64_t)step, i = 0;
            while ((i = fm_next_hit(a, (int64_t)p, (int64_t)tc, T, i, I)) >= 0) {
                int64_t t = (int64_t)(((__int128)a * i + (int64_t)tc) % p); APPLY2(t, i); i++; }
        }
        #undef APPLY2
    }
    /* emit in fm_block_js order: neg side ascending, then pos side ascending */
    int64_t tot = 0;
    for (int i = 0; i < nk; i++) {
        uint64_t *b = bits + (size_t)i * BW; int n = 0; int32_t *o = out + tot;
        for (int64_t bi = 0; bi < Sh; bi++) if (b[bi >> 6] & (1ULL << (bi & 63))) { if (tot + n >= cap) { free(tmap); free(bits); free(wheel); return -1; } o[n++] = (int32_t)(2 * (bi - Sh)); }
        for (int64_t bi = Sh; bi < I; bi++) if (b[bi >> 6] & (1ULL << (bi & 63))) { if (tot + n >= cap) { free(tmap); free(bits); free(wheel); return -1; } o[n++] = (int32_t)(2 * (bi - Sh)); }
        cnt[i] = n; tot += n;
    }
    free(tmap); free(bits); free(wheel);
    return tot;
}
