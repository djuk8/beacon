/* ref856.c -- the v8.56 referee: survivors and predictor sums computed DIRECTLY per (k, p), for any list of k's.
 * Independent of every production sieve path: no progressions, no row steps, no lattices, no first-hit, no js2 constants, no records.
 * It shares only the venue tables (primes and pe_p = P_eff mod p), which v8.56 does not touch.
 *   ref_bits : bit i <-> even offset j = 2(i - Sh), |j| <= 2Sh (Sh = hi/2); alive iff |j| > lo and no odd prime p of the given tables
 *              divides n0 + j, n0 = k * P_eff, i.e. (k*pe_p + j) % p != 0. Wheel primes (pe_p = 0) kill j == 0 (mod p) automatically.
 *   ref_pred : pred(k) = sum_p tab_p[(-k*pe_p) mod p]  (the full-window predictor's definition, bs_api.c), summed directly per k.
 * Build: gcc -O3 -march=native -fopenmp -shared -fPIC -o ref856.so ref856.c */
#include <stdint.h>
#include <string.h>
#include <omp.h>

static inline uint64_t kmodp_mul(uint64_t k, uint64_t pe, uint64_t p) {              /* (k * pe) mod p, exact for p < 2^63 */
    uint64_t a = k % p, b = pe % p;
    if (p < (1ULL << 32)) return (a * b) % p;
    return (uint64_t)(((__uint128_t)a * b) % p);
}
static void kill_table(uint64_t *w, int64_t k, const int64_t *ps, const int64_t *pes, int64_t n, int64_t Sh) {
    const int64_t J = 2 * Sh;                                                         /* window: even j in [-J, J] */
    for (int64_t q = 0; q < n; q++) {
        int64_t p = ps[q]; if (p == 2) continue;
        int64_t r = (int64_t)kmodp_mul((uint64_t)k, (uint64_t)pes[q], (uint64_t)p);    /* n0 mod p */
        int64_t j0 = (p - r) % p;                                                    /* p | n0 + j  <=>  j == j0 (mod p) */
        int64_t j = -J + ((j0 + J) % p);                                             /* smallest j >= -J in the class */
        if (j & 1) j += p;                                                           /* p odd: next member has the other parity */
        for (; j <= J; j += 2 * p) { int64_t i = j / 2 + Sh; w[i >> 6] &= ~(1ULL << (i & 63)); }
    }
}
void ref_bits(const int64_t *ks, int64_t nk, const int64_t *prs, const int64_t *pem, int64_t np, const int64_t *qd, const int64_t *ped, int64_t nq,
              int64_t lo, int64_t hi, uint64_t *bits, int nthreads) {
    const int64_t Sh = hi / 2, I = 2 * Sh + 1, BW = (I + 63) / 64;
    if (nthreads > 0) omp_set_num_threads(nthreads);
    #pragma omp parallel for schedule(dynamic, 8)
    for (int64_t x = 0; x < nk; x++) {
        uint64_t *w = bits + x * BW; memset(w, 0, (size_t)BW * 8);
        for (int64_t i = 0; i < I; i++) { int64_t aj = 2 * (i - Sh); if (aj < 0) aj = -aj; if (aj > lo) w[i >> 6] |= 1ULL << (i & 63); }   /* j = 0 dead (lo >= 0) */
        kill_table(w, ks[x], prs, pem, np, Sh);
        if (nq > 0) kill_table(w, ks[x], qd, ped, nq, Sh);
    }
}
void ref_pred(const int64_t *ks, int64_t nk, const int64_t *p, const int64_t *pe, const int64_t *off, const uint16_t *tab, int64_t np, double *out, int nthreads) {
    if (nthreads > 0) omp_set_num_threads(nthreads);
    #pragma omp parallel for schedule(static)
    for (int64_t x = 0; x < nk; x++) {
        int64_t acc = 0;
        for (int64_t q = 0; q < np; q++) { int64_t r = (p[q] - (int64_t)kmodp_mul((uint64_t)ks[x], (uint64_t)pe[q], (uint64_t)p[q])) % p[q]; acc += tab[off[q] + r]; }
        out[x] = (double)acc;
    }
}
const char *ref856_version(void) { return "ref856 v1 (direct per-(k,p) referee)"; }
