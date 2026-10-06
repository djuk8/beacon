#!/usr/bin/env python3
"""patch_pred_v2.py SRC DST -- write DST = SRC (bs_api.c) with pred_run replaced by the periodic-table version (identical sums, ~5x less work)."""
import sys
src, dst = sys.argv[1], sys.argv[2]; s = open(src).read()
old = s[s.index("static void *pred_run(void *arg) {"):s.index("void bs_predict(void *m,")]
assert "acc[t] += c[r]; r += step;" in old, "unexpected pred_run body - stop"
new = r'''#include <string.h>
static void *pred_run(void *arg) {   /* v2 (2026-10-06): periodic table per prime + periodic add; identical sums, ~5x less work */
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
open(dst, "w").write(s.replace(old, new)); print(f"{dst}: pred_run v2 written")
