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
