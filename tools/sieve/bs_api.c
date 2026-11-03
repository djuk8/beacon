/* bs_api.c v2 -- ctypes surface for bsieve.c v2 (packed records, staged pushes, emit/apply phases). */
#include "bsieve.c"
#include <pthread.h>
void *bs_create(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi) {
    int64_t pmax = qd[nq - 1]; return bsieve_init(qd, PEd, nq, k0, T, hi, (int)(pmax / T) + 3);
}
void bs_block(void *S, uint64_t *bits) { bsieve_block((bsieve_t *)S, bits); }
int64_t bs_I(void *S) { return ((bsieve_t *)S)->I; }
int64_t bs_cur(void *S) { return ((bsieve_t *)S)->cur; }
int64_t bs_applied(void *S) { return ((bsieve_t *)S)->applied; }

/* bits_from_js: set alive bits for window w (row w of bits) from js list (even j's); rows not touched stay 0 (dead) */
void bs_bits_from_js(const int32_t *js, const int32_t *cnt, const int32_t *rows, int64_t nk, int64_t Sh, int64_t BW, uint64_t *bits) {
    int64_t off = 0;
    for (int64_t k = 0; k < nk; k++) {
        uint64_t *w = bits + (size_t)rows[k] * BW;
        for (int32_t c = 0; c < cnt[k]; c++) { int64_t i = (int64_t)js[off + c] / 2 + Sh; w[i >> 6] |= 1ULL << (i & 63); }
        off += cnt[k];
    }
}
/* js_from_bits: for each requested row, write its alive j's (ascending) into out; returns total; cnt per row */
int64_t bs_js_from_bits(const uint64_t *bits, int64_t BW, int64_t I, int64_t Sh, const int32_t *rows, int64_t nk, int32_t *out, int32_t *cnt, int64_t cap) {
    int64_t off = 0;
    for (int64_t k = 0; k < nk; k++) {
        const uint64_t *w = bits + (size_t)rows[k] * BW; int32_t n = 0;
        for (int64_t wi = 0; wi < BW; wi++) { uint64_t x = w[wi];
            while (x) { int b = __builtin_ctzll(x); x &= x - 1; int64_t i = wi * 64 + b; if (i >= I) break; if (off + n >= cap) return -1; out[off + n++] = (int32_t)(2 * (i - Sh)); } }
        cnt[k] = n; off += n;
    }
    return off;
}


/* ---------------- threaded partition: P sieves over round-robin prime sets, same progression ---------------- */
typedef struct { void **parts; int P; int64_t T, BW; uint64_t *bits; int nch; } bsmt_t;
typedef struct { bsmt_t *M; int r; } job_t;
static void *run_emit(void *arg) { job_t *j = arg; bsieve_emit((bsieve_t *)j->M->parts[j->r]); return NULL; }
static void *run_apply(void *arg) {                                   /* chunk owner: chunks c == r (mod P), all partitions' buffers */
    job_t *j = arg; bsmt_t *M = j->M;
    for (int c = j->r; c < M->nch; c += M->P) for (int q = 0; q < M->P; q++) bsieve_apply_chunk((bsieve_t *)M->parts[q], c, M->bits);
    return NULL; }
void *bs_create_mt(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, int P) {
    bsmt_t *M = calloc(1, sizeof *M); M->P = P; M->T = T; M->parts = calloc(P, sizeof(void *));
    int64_t pmax = qd[nq - 1];
    for (int r = 0; r < P; r++) {
        int64_t n_r = (nq - r + P - 1) / P; int64_t *q_r = malloc(n_r * 8), *e_r = malloc(n_r * 8);
        for (int64_t i = 0, k = r; k < nq; k += P, i++) { q_r[i] = qd[k]; e_r[i] = PEd[k]; }
        M->parts[r] = bsieve_init(q_r, e_r, n_r, k0, T, hi, (int)(pmax / T) + 3);
        free(q_r); free(e_r);
        M->BW = ((bsieve_t *)M->parts[r])->BW; M->nch = ((bsieve_t *)M->parts[r])->nch;
    }
    return M;
}
void bs_block_mt(void *m, uint64_t *bits) {
    bsmt_t *M = m; M->bits = bits; pthread_t th[64]; job_t jb[64];
    for (int r = 0; r < M->P; r++) { jb[r].M = M; jb[r].r = r; pthread_create(&th[r], NULL, run_emit, &jb[r]); }
    for (int r = 0; r < M->P; r++) pthread_join(th[r], NULL);
    for (int r = 0; r < M->P; r++) pthread_create(&th[r], NULL, run_apply, &jb[r]);
    for (int r = 0; r < M->P; r++) pthread_join(th[r], NULL);
}
int64_t bs_I_mt(void *m) { return ((bsieve_t *)((bsmt_t *)m)->parts[0])->I; }
void bs_set_tmap_mt(void *m, const int32_t *tmap) { bsmt_t *M = m; for (int r = 0; r < M->P; r++) ((bsieve_t *)M->parts[r])->tmap = tmap; }   /* compact bitmaps: rows = coprime windows */

/* ---------------- small-prime mask stage (p <= PMAX_MASK): periodic kills applied as word masks ---------------- */
/* kills of prime p in window t are at bit i == c_p - t*pe_p (mod p)  [i = j/2 + Sh; n0(t) = (k0+2t)*P_eff, pe_p = P_eff mod p].
   Table: for each p, p masks of BW words: mask[r] has bits {i < I : i == r (mod p)}. Per window: bits[t] &= ~mask[(c_p - t*pe_p) mod p]. */
typedef struct { int np; int64_t *p, *pe, *c; uint64_t **mask; int64_t BW, I, Sh, k0; } smask_t;
void *bs_smask_create(const int64_t *primes, const int64_t *pe, int np, int64_t k0, int64_t hi) {
    smask_t *M = calloc(1, sizeof *M); M->np = np; M->Sh = hi / 2; M->I = 2 * M->Sh + 1; M->BW = (M->I + 63) / 64; M->k0 = k0;
    M->p = malloc(np * 8); M->pe = malloc(np * 8); M->c = malloc(np * 8); M->mask = calloc(np, sizeof(uint64_t *));
    for (int q = 0; q < np; q++) {
        int64_t p = primes[q], e = pe[q] % p; M->p[q] = p; M->pe[q] = e;
        int64_t inv2 = (p + 1) / 2, k0m = k0 % p;                                    /* c_p = Sh - k0*pe*inv2 (mod p) */
        M->c[q] = ((M->Sh % p) - ((k0m * e) % p) * inv2 % p + 2 * p) % p;
        M->mask[q] = calloc((size_t)p * M->BW, 8);
        for (int64_t i = 0; i < M->I; i++) { int64_t r = i % p; M->mask[q][r * M->BW + (i >> 6)] |= 1ULL << (i & 63); }
    }
    return M;
}
/* apply to rows: for window index tt (absolute t = t_base + row offset given by rows[k]) -- rows are window indices within the block, tbase = block's first t */
void bs_smask_apply(void *m, int64_t tbase, const int32_t *rows, int64_t nk, uint64_t *bits) {
    smask_t *M = m;
    for (int64_t k = 0; k < nk; k++) {
        int64_t t = tbase + rows[k]; uint64_t *w = bits + (size_t)k * M->BW;              /* compact layout: bitmap row k, window offset rows[k] */
        for (int q = 0; q < M->np; q++) {
            int64_t p = M->p[q], e = M->pe[q]; int64_t r; if (p == 2) continue;                    /* n0 odd, j even: 2 never kills (js2 skips it too) */
            if ((2 * e) % p == 0) r = M->Sh % p;                                          /* p | P_eff (wheel prime): j == 0 mod p dead in EVERY window -> i == Sh (mod p) */
            else { r = (M->c[q] - (t % p) * e) % p; if (r < 0) r += p; }                 /* linear-form prime (3,5,7,11 and p > zd) */
            const uint64_t *mk = M->mask[q] + (size_t)r * M->BW;
            for (int64_t wi = 0; wi < M->BW; wi++) w[wi] &= ~mk[wi];
        }
    }
}

static uint64_t fm_inv(uint64_t a, uint64_t m) {
    int64_t t0 = 0, t1 = 1; uint64_t r0 = m, r1 = a % m;
    while (r1) { uint64_t q = r0 / r1; int64_t t2 = t0 - (int64_t)q * t1; t0 = t1; t1 = t2; uint64_t r2 = r0 - q * r1; r0 = r1; r1 = r2; }
    return (uint64_t)(t0 < 0 ? t0 + (int64_t)m : t0);
}

/* bs_js2_bits: the js2 linear-form sieve (primes in the given table) applied IN PLACE to a T-row block bitmap.
   rows[k] = block row of window k (ks[k]); bits rows must be pre-initialized by the caller (1 = alive). Wheel primes
   (p | P_eff) in the table kill j == 0 (mod p) in every window; p == 2 is skipped. Same math as fm_block_js2. */
void bs_js2_bits(const int64_t *ks, int nk, const int32_t *rows, const int64_t *prs, const int64_t *PEm, int64_t np,
                 int64_t lo, int64_t hi, int64_t T, uint64_t *bits) {
    const int64_t Sh = hi / 2, I = 2 * Sh + 1; const size_t BW = (size_t)((I + 63) / 64);
    int64_t k0 = ks[0];
    int32_t *tmap = (int32_t *)malloc(sizeof(int32_t) * (size_t)T); memset(tmap, 0xFF, sizeof(int32_t) * (size_t)T);
    for (int i = 0; i < nk; i++) tmap[(ks[i] - k0) / 2] = rows[i];
    {   /* wheel primes (p | P_eff) in the table: j == 0 (mod p) dead in every window -> ONE template, AND'd into each row */
        uint64_t *wheel = malloc(BW * 8); memset(wheel, 0xFF, BW * 8); int any = 0;
        for (int64_t qi = 0; qi < np; qi++) {
            uint64_t p = (uint64_t)prs[qi]; if (p == 2) continue; uint64_t pe = (uint64_t)PEm[qi] % p;
            if ((2 * pe) % p == 0) { any = 1; for (int64_t j = -(Sh * 2); j <= Sh * 2; j += 2) if (j % (int64_t)p == 0) { int64_t bi = j / 2 + Sh; wheel[bi >> 6] &= ~(1ULL << (bi & 63)); } }
        }
        if (any) for (int i = 0; i < nk; i++) { uint64_t *b = bits + (size_t)rows[i] * BW; for (size_t w = 0; w < BW; w++) b[w] &= wheel[w]; }
        free(wheel);
    }
    for (int64_t qi = 0; qi < np; qi++) {                                      /* linear-form primes */
        uint64_t p = (uint64_t)prs[qi]; if (p == 2) continue;
        uint64_t pe = (uint64_t)PEm[qi] % p, B = (2 * pe) % p; if (!B) continue;
        uint64_t inv2 = (p + 1) / 2, k0m = (uint64_t)(k0 % (int64_t)p);
        uint64_t A = (p - (uint64_t)(((__uint128_t)k0m * pe) % p)) % p;
        uint64_t A2 = (uint64_t)(((__uint128_t)A * inv2) % p), B2 = (uint64_t)(((__uint128_t)B * inv2) % p);
        uint64_t cc = fm_inv(B2, p);
        uint64_t tc = (uint64_t)(((__uint128_t)cc * ((A2 + (uint64_t)Sh) % p)) % p), step = p - cc;
        #define APPLYB(tt, ii) do { int32_t idx = tmap[(tt)]; if (idx >= 0) { uint64_t *b = bits + (size_t)idx * BW; b[(ii) >> 6] &= ~(1ULL << ((ii) & 63)); } } while (0)
        if ((__int128)I * T >= 2 * (__int128)p) {
            uint64_t t = tc;
            for (int64_t i = 0; i < I; i++) { for (uint64_t tt = t; (int64_t)tt < T; tt += p) APPLYB((int64_t)tt, i); t += step; if (t >= p) t -= p; }
        } else {
            int64_t aa = (int64_t)step, i = 0;
            while ((i = fm_next_hit(aa, (int64_t)p, (int64_t)tc, T, i, I)) >= 0) { int64_t t = (int64_t)(((__int128)aa * i + (int64_t)tc) % p); APPLYB(t, i); i++; }
        }
        #undef APPLYB
    }
    free(tmap);
}
/* initialize block rows for the given windows: all alive except j == 0 (bit Sh) and |j| <= lo */
void bs_rows_init(const int32_t *rows, int64_t nk, int64_t lo, int64_t hi, uint64_t *bits) {
    const int64_t Sh = hi / 2, I = 2 * Sh + 1; const size_t BW = (size_t)((I + 63) / 64);
    uint64_t *wheel = calloc(BW, 8);
    for (int64_t bi = 0; bi < I; bi++) { int64_t aj = 2 * (bi - Sh); if (aj < 0) aj = -aj; if (aj > lo) wheel[bi >> 6] |= 1ULL << (bi & 63); }
    for (int64_t k = 0; k < nk; k++) memcpy(bits + (size_t)rows[k] * BW, wheel, BW * 8);
    free(wheel);
}

/* ---------------- exports for the GPU sieve (gbs.cu): all per-prime arithmetic stays here, on the certified code ---------------- */
/* flat records (bsieve.c v2 init without buckets): returns count written (primes with a landing); out must hold nq records */
int64_t bs_records_flat_s(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, int64_t S, rec_t *out) {   /* v8.56: rows k = k0 + S*t */
    int64_t Sh = hi / 2, I = 2 * Sh + 1, n = 0;
    for (int64_t q = 0; q < nq; q++) {
        uint64_t p = (uint64_t)qd[q], pe = (uint64_t)PEd[q] % p; uint64_t B = (2 * pe) % p; if (!B) continue;
        uint64_t inv2 = (p + 1) / 2, k0m = (uint64_t)(k0 % (int64_t)p);
        uint64_t i0 = (uint64_t)(((uint64_t)Sh % p + p - mulmod(mulmod(k0m, pe, p), inv2, p)) % p);
        uint64_t f = (S == 2) ? pe : mulmod((uint64_t)(S / 2) % p, pe, p); if (!f) return -1;   /* v8.56: per-row shift (S/2)*pe; 0 = same kill every row (p | S/2): never for deep primes */
        uint64_t sp = p - f;
        int64_t t = fm_next_hit((int64_t)sp, (int64_t)p, (int64_t)i0, I, 0, (int64_t)p); if (t < 0) continue;
        int32_t i = (int32_t)((i0 + (__uint128_t)(uint64_t)t * sp) % p);
        int32_t a0, b0; int64_t a1, b1; fk_reduce((int64_t)p, (int64_t)sp, I, &a0, &a1, &b0, &b1);
        out[n++] = rec_pack(p, t, i, a0, a1, b0);
    }
    return n;
}
int64_t bs_records_flat(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, rec_t *out) { return bs_records_flat_s(qd, PEd, nq, k0, T, hi, 2, out); }
/* v8.57: WIDE packed records for windows wider than the bsieve.c v2 fields allow (I > 2047; rings 1+2 = 4,375 columns):
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
/* js2 constants for medium primes: tc, step per prime (same formulas as fm_block_js2) */
int64_t bs_js2_consts_s(int64_t k0, const int64_t *prs, const int64_t *PEm, int64_t np, int64_t hi, int64_t S, int64_t *tc_out, int64_t *step_out) {   /* v8.56: rows k = k0 + S*t; returns #constant-kill primes (must be 0) */
    int64_t Sh = hi / 2, nconst = 0;
    for (int64_t qi = 0; qi < np; qi++) {
        uint64_t p = (uint64_t)prs[qi], pe = (uint64_t)PEm[qi] % p, B = (2 * pe) % p;
        if (p == 2 || !B) { tc_out[qi] = -1; step_out[qi] = 0; continue; }
        uint64_t inv2 = (p + 1) / 2, k0m = (uint64_t)(k0 % (int64_t)p);
        uint64_t A = (p - (uint64_t)(((__uint128_t)k0m * pe) % p)) % p;
        uint64_t A2 = (uint64_t)(((__uint128_t)A * inv2) % p), B2 = (uint64_t)(((__uint128_t)B * inv2) % p);
        if (S != 2) B2 = mulmod((uint64_t)(S / 2) % p, pe, p);                                  /* v8.56: per-row shift (S/2)*pe (== B*inv2 at S = 2) */
        if (!B2) { tc_out[qi] = -1; step_out[qi] = 0; nconst++; continue; }                     /* p | S/2: the same kill in every row - not a walk */
        uint64_t c = fm_inv(B2, p);
        tc_out[qi] = (int64_t)(((__uint128_t)c * ((A2 + (uint64_t)Sh) % p)) % p); step_out[qi] = (int64_t)(p - c);
    }
    return nconst;
}
void bs_js2_consts(int64_t k0, const int64_t *prs, const int64_t *PEm, int64_t np, int64_t hi, int64_t *tc_out, int64_t *step_out) { bs_js2_consts_s(k0, prs, PEm, np, hi, 2, tc_out, step_out); }
/* wheel template for a prime table: alive bits (|j| > lo, j != 0) minus j == 0 (mod p) for every wheel prime (p | P_eff) in the table */
void bs_wheel(const int64_t *prs, const int64_t *PEm, int64_t np, int64_t lo, int64_t hi, uint64_t *out) {
    int64_t Sh = hi / 2, I = 2 * Sh + 1; size_t BW = (size_t)((I + 63) / 64); memset(out, 0, BW * 8);
    for (int64_t bi = 0; bi < I; bi++) { int64_t aj = 2 * (bi - Sh); if (aj < 0) aj = -aj; if (aj > lo) out[bi >> 6] |= 1ULL << (bi & 63); }
    for (int64_t qi = 0; qi < np; qi++) { uint64_t p = (uint64_t)prs[qi]; if (p == 2) continue; uint64_t pe = (uint64_t)PEm[qi] % p;
        if ((2 * pe) % p == 0) for (int64_t j = -(Sh * 2); j <= Sh * 2; j += 2) if (j % (int64_t)p == 0) { int64_t bi = j / 2 + Sh; out[bi >> 6] &= ~(1ULL << (bi & 63)); } }
}
/* mask constants + concatenated table from a smask (c per prime; offsets in words) */
void bs_smask_export(void *m, int64_t *c_out, int64_t *off_out, uint64_t *table_out) {
    smask_t *M = m; int64_t off = 0;
    for (int q = 0; q < M->np; q++) { c_out[q] = M->c[q]; off_out[q] = off; memcpy(table_out + off, M->mask[q], (size_t)M->p[q] * M->BW * 8); off += M->p[q] * M->BW; }
}
int64_t bs_smask_words(void *m) { smask_t *M = m; int64_t w = 0; for (int q = 0; q < M->np; q++) w += M->p[q] * M->BW; return w; }
/* popcount per row (alive candidates per window) */
void bs_row_counts(const uint64_t *bits, int64_t T, int64_t BW, int64_t I, int32_t *cnt) {
    uint64_t lastmask = (I % 64) ? ((1ULL << (I % 64)) - 1) : ~0ULL;
    for (int64_t r = 0; r < T; r++) { const uint64_t *w = bits + r * BW; int c = 0; for (int64_t x = 0; x < BW; x++) c += __builtin_popcountll(x == BW - 1 ? (w[x] & lastmask) : w[x]); cnt[r] = c; }
}

/* ================= full-window sparsity PREDICTOR (2026-09-11 night) =================
   Survivors of window k = wheel pattern minus kills by linear-form primes; prime p kills the wheel-survivors j with
   j == -k*pe_p (mod p). So   pred(k) = sum_p cnt_p[(-k*pe_p) mod p]   where cnt_p[r] = #wheel-survivors == r (mod p)
   over the FULL window (|j| <= hi), computed once per venue. Measured: corr(pred, true survivors) = -0.40 with p <= 1e5;
   ranking a 12x pool by pred (+ r1 count) moves E_total by -1.3% -> x1.45 crown-lambda per window (vs x1.20 by r1 count). */
typedef struct { int64_t np; int64_t *p, *pe, *off; uint16_t *tab; int64_t hi; } pred_t;
/* wheel-survivor j list (even, j != 0, coprime to every prime 13..zd) -- caller passes the wheel primes */
void *bs_pred_create(const int64_t *prs, const int64_t *PEm, int64_t nprs, const int64_t *wheelp, int64_t nwheel, int64_t hi, int64_t pmax, int64_t *nlin_out, int64_t *words_out) {
    /* wheel survivors */
    int64_t nW = 0; int64_t *W = malloc(sizeof(int64_t) * (size_t)(hi + 1));
    for (int64_t j = -hi; j <= hi; j += 2) { if (!j) continue; int ok = 1; for (int64_t q = 0; q < nwheel && ok; q++) if (j % wheelp[q] == 0) ok = 0; if (ok) W[nW++] = j; }
    /* linear primes: 3,5,7,11 and wheel-free primes above the wheel up to pmax (pe != 0 mod p) */
    pred_t *M = calloc(1, sizeof *M); M->hi = hi; M->p = malloc(8 * (size_t)nprs); M->pe = malloc(8 * (size_t)nprs); M->off = malloc(8 * (size_t)nprs);
    int64_t off = 0, n = 0;
    for (int64_t q = 0; q < nprs; q++) { int64_t p = prs[q]; if (p == 2 || p > pmax) continue; int64_t e = PEm[q] % p; if (e == 0) continue;
        M->p[n] = p; M->pe[n] = e; M->off[n] = off; off += p; n++; }
    M->np = n; M->tab = calloc((size_t)off, sizeof(uint16_t));
    for (int64_t q = 0; q < n; q++) { int64_t p = M->p[q]; uint16_t *c = M->tab + M->off[q];
        for (int64_t i = 0; i < nW; i++) { int64_t r = W[i] % p; if (r < 0) r += p; if (c[r] < 65535) c[r]++; } }
    free(W); *nlin_out = n; *words_out = off; return M;
}
/* pred for a contiguous progression k = k0 + 2t, t in [0,T): incremental residues, one add per (prime, t). threads: split primes. */
#include <pthread.h>
typedef struct { pred_t *M; int64_t k0, T, q0, q1; double *out; int64_t S; } pjob_t;   /* v8.56: S = progression step */
#include <string.h>
static void *pred_run(void *arg) {   /* v2 (2026-10-06): periodic table per prime + periodic add; identical sums, ~5.5x less work */
    pjob_t *J = arg; pred_t *M = J->M; int64_t T = J->T;
    int32_t *acc = calloc((size_t)T, sizeof(int32_t)); int64_t pmax = 0;
    for (int64_t q = J->q0; q < J->q1; q++) if (M->p[q] > pmax) pmax = M->p[q];
    uint16_t *d = malloc((size_t)(pmax + 512) * sizeof(uint16_t));
    for (int64_t q = J->q0; q < J->q1; q++) {
        int64_t p = M->p[q], e = M->pe[q]; const uint16_t *c = M->tab + M->off[q];
        int64_t r = (p - ((J->k0 % p) * e) % p) % p, step = (J->S == 2) ? (p - (2 * e) % p) % p : (p - ((J->S % p) * e) % p) % p;   /* v8.56: k = k0 + S*t */
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
void bs_predict_s(void *m, int64_t k0, int64_t T, int64_t S, int nthreads, double *out) {   /* v8.56: pred for k = k0 + S*t, t in [0,T) */
    pred_t *M = m; if (nthreads < 1) nthreads = 1; if (nthreads > 32) nthreads = 32; pthread_t th[32]; pjob_t jb[32];
    for (int r = 0; r < nthreads; r++) { jb[r].M = M; jb[r].k0 = k0; jb[r].T = T; jb[r].S = S; jb[r].q0 = M->np * r / nthreads; jb[r].q1 = M->np * (r + 1) / nthreads; pthread_create(&th[r], NULL, pred_run, &jb[r]); }
    for (int64_t t = 0; t < T; t++) out[t] = 0;
    for (int r = 0; r < nthreads; r++) { pthread_join(th[r], NULL); for (int64_t t = 0; t < T; t++) out[t] += jb[r].out[t]; free(jb[r].out); }
}
void bs_predict(void *m, int64_t k0, int64_t T, int nthreads, double *out) { bs_predict_s(m, k0, T, 2, nthreads, out); }
/* constructor from caller-owned (memory-mapped, shared) arrays: p, pe, off (int64, np entries), tab (uint16, words entries) */
void *bs_pred_attach(const int64_t *p, const int64_t *pe, const int64_t *off, const uint16_t *tab, int64_t np, int64_t hi) {
    pred_t *M = calloc(1, sizeof *M); M->np = np; M->hi = hi; M->p = (int64_t *)p; M->pe = (int64_t *)pe; M->off = (int64_t *)off; M->tab = (uint16_t *)tab; return M;
}
void bs_pred_export(void *m, int64_t *p, int64_t *pe, int64_t *off, uint16_t *tab, int64_t words) {
    pred_t *M = m; memcpy(p, M->p, 8 * (size_t)M->np); memcpy(pe, M->pe, 8 * (size_t)M->np); memcpy(off, M->off, 8 * (size_t)M->np); memcpy(tab, M->tab, 2 * (size_t)words);
}
/* v8.56: library tag (receipts) */
const char *bs_api_version(void) { return "bs_api v8.56 (step-aware: S = 2 | 2310)"; }
